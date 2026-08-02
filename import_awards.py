"""Import AIMS's historical awards archive (1977-) into historical_results.

Only imports rows for years strictly before shows.csv's own coverage, so
this can never double-count a production already in the shows table - see
the comment on historical_results in schema.sql for how that cutoff works
and why. Re-running this wipes and reloads historical_results from the CSV
(safe: nothing in the app writes to this table, unlike shows/societies).

Usage:
    py import_awards.py [--db aims.db] [--csv "AIMS_Awards - Results.csv"] [--cutoff-year 2024]
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
}

# Rows where the source data genuinely concatenated two separate real
# productions into one Showname field (not a mistaken/replaced title, like
# SHOW_RENAMES above - both shows actually happened). Each entry here gets
# turned into two rows instead of one, same year/society/category, one per
# real show. Confirmed with the maintainer.
SHOW_SPLITS = {
    "Annie & Pirates Of Penzance": ["Annie", "Pirates of Penzance"],
}


def normalize(value):
    value = (value or "").strip()
    return value or None


def normalize_show(value):
    value = normalize(value)
    if value is None:
        return None
    return SHOW_RENAMES.get(value, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--csv", default=str(ROOT / "AIMS_Awards - Results.csv"))
    parser.add_argument(
        "--cutoff-year", type=int, default=2024,
        help="Only import rows with Year strictly less than this (default 2024, "
             "matching shows.csv's earliest season 23/24).",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))

    name_to_id = dict(conn.execute("SELECT name, id FROM societies").fetchall())

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    conn.execute("DELETE FROM historical_results")

    inserted = 0
    skipped_bad_year = 0
    for row in rows:
        year_str = row.get("Year", "").strip()
        if not year_str.isdigit():
            skipped_bad_year += 1
            continue
        year = int(year_str)
        if year >= args.cutoff_year:
            continue

        society_name = normalize(row.get("ResolvedSocietyName"))
        raw_show = normalize(row.get("Showname"))
        show_titles = SHOW_SPLITS.get(raw_show) or [normalize_show(row.get("Showname"))]

        for show_title in show_titles:
            conn.execute(
                """
                INSERT INTO historical_results (
                    year, tier, category_name, result, show, society_name, society_id,
                    nominee_name, role
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    year,
                    normalize(row.get("SchemeName")),
                    normalize(row.get("CategoryName")),
                    normalize(row.get("ResultText")),
                    show_title,
                    society_name,
                    name_to_id.get(society_name) if society_name else None,
                    normalize(row.get("NomineeName")),
                    normalize(row.get("Role")),
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

    print(f"Imported {inserted} award-result rows (years before {args.cutoff_year})")
    if skipped_bad_year:
        print(f"Skipped {skipped_bad_year} row(s) with no valid Year")
    print(f"Distinct historical productions: {distinct_productions}")
    print(f"Societies matched to current roster: {matched_societies} of {total_societies}")


if __name__ == "__main__":
    main()
