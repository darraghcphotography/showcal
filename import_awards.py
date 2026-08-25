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
    "Michael Collins -  A Musical Drama": "Michael Collins - A Musical Drama",  # double-space typo
    "Michael Collins, A Musical Drama": "Michael Collins - A Musical Drama",  # older records use a comma, not a hyphen
    "Michael Collins": "Michael Collins - A Musical Drama",  # never shorten this one - see fix_show_titles.py
    "Made In Dagenham": "Made in Dagenham",
    "Oliver": "Oliver!",
    "Die Fliedermaus": "Die Fledermaus",  # German for "the bat" - "Fliedermaus" isn't a word
    "Finians Rainbow": "Finian's Rainbow",
    "Kipp Half a Sixpence": "Half a Sixpence",
    "Shrek The Musical": "Shrek",
    "Shrek the Musical": "Shrek",
    "Pirates of Penzance": "The Pirates of Penzance",  # 81 rows use "The", only a handful drop it
    "Me & My Girl": "Me and My Girl",  # official title spells out "and" - found while auditing top titles

    # Found via a full run of the duplicate-title finder after a member noticed
    # "Beauty & The Beast" and "9 To 5 The Musical" still showing separately on
    # Shows A-Z - turned out several fix_show_titles.py renames (which only
    # touch the shows table) were never mirrored here for historical_results,
    # so the old spelling survived in the archive even after the current-era
    # table was fixed. Canonical spelling chosen as: whichever the shows table
    # already uses if it's used there, else the official/grammatically correct
    # form, else the more common historical spelling.
    "Into The Woods": "Into the Woods",
    "Beauty & The Beast": "Beauty and the Beast",
    "Cry Baby": "Cry-Baby",
    "RENT": "Rent",
    "Sound of Music": "The Sound of Music",
    "The Sound Of Music": "The Sound of Music",
    "9 To 5 The Musical": "9 to 5",
    "Big FIsh": "Big Fish",
    "Fiddler On The Roof": "Fiddler on the Roof",
    "Half A Sixpence": "Half a Sixpence",
    "Kipps Half a Sixpence": "Half a Sixpence",
    "Little Shop Of Horrors": "Little Shop of Horrors",
    "Man Of La Mancha": "Man of La Mancha",
    "Orpheus In The Underworld": "Orpheus in the Underworld",
    "Singin' In The Rain": "Singin' in the Rain",
    "Singin in the Rain": "Singin' in the Rain",
    "Singing in the Rain": "Singin' in the Rain",
    "The Phantom Of The Opera": "The Phantom of the Opera",
    "Phantom of the Opera": "The Phantom of the Opera",
    "The Witches Of Eastwick": "The Witches of Eastwick",
    "Witches of Eastwick": "The Witches of Eastwick",
    "Carrie -  The Musical": "Carrie - The Musical",
    "The Clockmakers Daughter": "The Clockmaker's Daughter",
    "Hello Dolly!": "Hello, Dolly!",
    "The Boyfriend": "The Boy Friend",  # official title of the 1920s musical is two words
    "Seussical - The Musical": "Seussical",  # matches the existing "Seussical! The Musical" -> "Seussical" merge
    "Seussical The Musical": "Seussical",
    "Oklahoma": "Oklahoma!",
    "Showboat": "Show Boat",  # official title is two words
    "The Gipsy Baron": "The Gypsy Baron",  # archaic spelling of the same operetta
    "Pippin!": "Pippin",  # official title has no exclamation mark
    "Belle of New York": "The Belle of New York",
    "The Belle Of New York": "The Belle of New York",
    "Bonnie and Clyde": "Bonnie & Clyde",  # official title uses an ampersand
    "Desert Song": "The Desert Song",
    "Guys & Dolls": "Guys and Dolls",  # official title spells out "and"
    "The King and I": "The King & I",
    "White Horse Inn": "The White Horse Inn",
    "Die Fleidermaus": "Die Fledermaus",  # a second, different typo of the same German title
    "The Hot Mikado": "Hot Mikado",  # same show, "The" is inconsistently applied - NOT the same as The Mikado
    "Les Misérables": "Les Miserables",  # accented vs unaccented, same show (the accented text is valid
                                              # UTF-8 - a terminal display quirk made it look mangled during review)
    "The Prince of Egypt: The Musical": "The Prince of Egypt",  # matches the shorter title already used in shows
    "Beautiful - The Carole King Musical": "Beautiful: The Carole King Musical",  # official title
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--csv", default=str(ROOT / "AIMS_Awards - Results.csv"))
    # argv is threaded through (rather than always reading sys.argv) so the
    # re-import durability test can drive this against a temp database - that
    # test is the one that catches society links being silently wiped.
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))

    name_to_id = dict(conn.execute("SELECT name, id FROM societies").fetchall())

    # Overlay the moderator-confirmed links for printed names that don't match a
    # societies row exactly (see historical_society_links in schema.sql). Without
    # this, the DELETE below would throw away every hand-made link on every run,
    # silently - all of the unmatched rows are source='import'. Applied to the
    # name->id map rather than as a post-insert UPDATE sweep so it can't drift
    # from the insert path, and so it covers the SHOW_SPLITS two-row branch free.
    live_ids = set(name_to_id.values())
    links = conn.execute(
        "SELECT society_name, society_id FROM historical_society_links WHERE society_id IS NOT NULL"
    ).fetchall()
    for society_name, society_id in links:
        if society_id in live_ids:
            name_to_id[society_name] = society_id
        else:
            # The society was deleted or merged away since the link was made.
            # Skipping beats writing a dangling foreign key.
            print(f"  ! confirmed link for {society_name!r} points at society id {society_id}, "
                  "which no longer exists - skipping it")
    if links:
        print(f"Applied {len(links)} moderator-confirmed society link(s) from historical_society_links")

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
