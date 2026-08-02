"""Import AIMS's full historical awards archive (1977-) into historical_results.

Imports every row in the CSV, including years that overlap shows.csv's own
coverage (23/24 onward, i.e. award Year 2024+) - award-level detail (who was
nominated/won which category) isn't tracked anywhere in the shows table, so
there's nothing to double-count there. The one place that DOES need care is
stats: any query that counts historical_results rows as equivalent to a
shows-table row (e.g. "most performed shows") must add `year < 2024` itself
to avoid counting a 23/24+ production twice - see info.py's stats(). Re-running
this wipes and reloads historical_results from the CSV (safe: nothing in the
app writes to this table, unlike shows/societies).

Usage:
    py import_awards.py [--db aims.db] [--csv "AIMS_Awards - Results.csv"]
"""
import argparse
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

# Known duplicate/mangled show titles found by auditing the one-off list
# after import - same idea as fix_show_titles.py's RENAMES, but applied here
# at import time since historical_results is fully regenerated on every run.
SHOW_RENAMES = {
    "Title Of Show": "Title of Show",
    "Michael Collins -  A Musical Drama": "Michael Collins",  # matches the canonical merge in fix_show_titles.py
    "Made In Dagenham": "Made in Dagenham",
    "Oliver": "Oliver!",
    "Die Fliedermaus": "Die Fledermaus",  # German for "the bat" - "Fliedermaus" isn't a word
    "Finians Rainbow": "Finian's Rainbow",
    "Kipp Half a Sixpence": "Half a Sixpence",
    "Shrek The Musical": "Shrek",
    "Shrek the Musical": "Shrek",
    "Pirates of Penzance": "The Pirates of Penzance",  # 81 rows use "The", only a handful drop it
    "Me & My Girl": "Me and My Girl",  # official title spells out "and" - found while auditing top titles
}

# Rows where the source data genuinely concatenated two separate real
# productions into one Showname field (not a mistaken/replaced title, like
# SHOW_RENAMES above - both shows actually happened). Each entry here gets
# turned into two rows instead of one, same year/society/category, one per
# real show. Confirmed with the maintainer.
SHOW_SPLITS = {
    "Annie & Pirates Of Penzance": ["Annie", "The Pirates of Penzance"],
}

# Known duplicate/mangled society names found by fuzzy-matching unmatched
# historical societies against the current societies roster - same idea as
# SHOW_RENAMES, but for ResolvedSocietyName.
SOCIETY_RENAMES = {
    "Lisnagarvey Operatic  and Dramatic Society": "Lisnagarvey Operatic and Dramatic Society",  # double space
    "Glencullen Dundrum Musical & Dramatic Society": "Glencullen Dundrum MDS",  # matches societies.name exactly
    "Cecilian Theatre Arts Society, Dublin": "Cecilian Theatre Arts",
    "DCU Drama": "DCU Drama Society",
    "Bardic Theatre, Dungannon": "Bardic Theatre",
    "Fun Company, Sligo": "Sligo Fun Company",  # matches societies.name exactly (AIMS.ie Western region listing)
    "Fusion Theatre Group": "Fusion Theatre, Lisburn",  # same defunct/inactive group, consolidating the name only
}

# Rows where the source data left CategoryName blank - found by auditing the
# 2026 Mary Kelly/Unsung Hero Award nominees (blank category + blank show is
# otherwise a near-unique signature of that category, 162 of 167 such rows -
# confirmed against these specific ones with the maintainer). Keyed by
# (year, society_name, nominee_name) since that uniquely identifies a row
# without a category to key off in the source data.
CATEGORY_FIXES = {
    (2026, "Oyster Lane Theatre Group", "Paddy & Marie Hayes"): "Mary Kelly/Unsung Hero Award",
    (2026, "Harolds Cross Tallaght Musical Society", "Máirín Heffernan"): "Mary Kelly/Unsung Hero Award",
    (2026, "Newcastle Glees Musical Society", "Edna Howard"): "Mary Kelly/Unsung Hero Award",
    (2026, "Inish Theatre Group", "Adrian McMyler"): "Mary Kelly/Unsung Hero Award",
    (2026, "Baldoyle Musical Society", "James & Nina O’Keeffe"): "Mary Kelly/Unsung Hero Award",
}


def normalize(value):
    value = (value or "").strip()
    return value or None


def normalize_show(value):
    value = normalize(value)
    if value is None:
        return None
    return SHOW_RENAMES.get(value, value)


def normalize_society(value):
    value = normalize(value)
    if value is None:
        return None
    return SOCIETY_RENAMES.get(value, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--csv", default=str(ROOT / "AIMS_Awards - Results.csv"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))

    name_to_id = dict(conn.execute("SELECT name, id FROM societies").fetchall())

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # Only ever touches 'import' rows - anything added by hand via /admin/awards
    # (source='manual') survives every re-run of this script untouched.
    conn.execute("DELETE FROM historical_results WHERE source = 'import'")

    inserted = 0
    skipped_bad_year = 0
    for row in rows:
        year_str = row.get("Year", "").strip()
        if not year_str.isdigit():
            skipped_bad_year += 1
            continue
        year = int(year_str)

        society_name = normalize_society(row.get("ResolvedSocietyName"))
        raw_show = normalize(row.get("Showname"))
        show_titles = SHOW_SPLITS.get(raw_show) or [normalize_show(row.get("Showname"))]
        nominee_name = normalize(row.get("NomineeName"))

        category_name = normalize(row.get("CategoryName"))
        if category_name is None:
            category_name = CATEGORY_FIXES.get((year, society_name, nominee_name))

        for show_title in show_titles:
            conn.execute(
                """
                INSERT INTO historical_results (
                    year, tier, category_name, result, show, society_name, society_id,
                    nominee_name, role, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    year,
                    normalize(row.get("SchemeName")),
                    category_name,
                    normalize(row.get("ResultText")),
                    show_title,
                    society_name,
                    name_to_id.get(society_name) if society_name else None,
                    nominee_name,
                    normalize(row.get("Role")),
                    normalize(row.get("Reason")),
                ),
            )
            inserted += 1

    conn.commit()

    distinct_productions = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT year, show, society_name FROM historical_results WHERE show IS NOT NULL)"
    ).fetchone()[0]
    matched_societies = conn.execute(
        "SELECT COUNT(DISTINCT society_name) FROM historical_results WHERE society_id IS NOT NULL"
    ).fetchone()[0]
    total_societies = conn.execute(
        "SELECT COUNT(DISTINCT society_name) FROM historical_results WHERE society_name IS NOT NULL"
    ).fetchone()[0]

    conn.close()

    print(f"Imported {inserted} award-result rows")
    if skipped_bad_year:
        print(f"Skipped {skipped_bad_year} row(s) with no valid Year")
    print(f"Distinct historical productions: {distinct_productions}")
    print(f"Societies matched to current roster: {matched_societies} of {total_societies}")


if __name__ == "__main__":
    main()
