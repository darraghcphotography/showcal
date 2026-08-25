"""Sets `societies.founded_year` for the societies whose founding year has been
verified against a real source.

This is deliberately hand-listed rather than driven off a worklist. The
delegated founding-years pass (2026-08-25, second attempt) followed the
behavioural rules well - 109 of 143 rows left blank, zero violations of the
`must_be_on_or_before` bounds - but its evidence was fabricated wholesale:

  * 19 of the 34 cited `source_url` domains do not resolve at all.
  * 8 more resolve but 404 on the cited path.
  * 0 of 34 `evidence_quote` values could be found on the page cited. The
    Cecilians quote ("Founded in 1919 by Father William Dwane") was attributed
    to a page about a different organisation's choir, founded 1981 by someone
    else.

The years themselves are probably largely right - they look like accurate
recall dressed in invented citations - but "probably right and unverifiable"
isn't the standard anything else in this database is held to, so none of that
file was imported.

Every year below was instead confirmed directly:

  * Malahide and Naas - fetched from the society's own homepage (the URL we
    already hold on file, from the enrichment pass that WAS spot-checked).
  * Leixlip and Nenagh - same, and they independently corroborate the
    delegated pass, which returned the same two years.
  * Tullamore and Castlerea - from the anniversary programme photographs
    submitted via /submit/photo and read on 2026-08-24. Castlerea's programme
    is headed "celebrating 50 years" with productions from 1968; Tullamore's
    lists its first production in 1955.

All six sit within the `must_be_on_or_before` bound derived from our own
earliest award record for that society.

Only ever fills a blank, so a moderator edit always wins; safe to re-run.

Usage:
    py import_founding_years.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python import_founding_years.py --db /data/aims.db
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

# (society name, founded_year, evidence)
FOUNDING_YEARS = [
    ("Malahide Musical & Dramatic Society", 1976,
     'malahidemusical.com: "Malahide Musical & Dramatic Society was established in 1976 when a '
     'number of people from Malahide Sports & Recreation Club..."'),
    ("Naas Musical Society", 1995,
     'naasmusicalsociety.net: "Naas Musical Society was Founded in 1995 by Mona Conroy and Mary Fox"'),
    ("Leixlip Musical & Variety Group", 1980,
     'lmvg.ie - founding year on the About page; independently matches the delegated pass'),
    ("Nenagh Choral Society Ltd", 1949,
     'nenaghchoralsociety.com site header: "Nenagh Choral Society Ltd Established 1949"; '
     'independently matches the delegated pass'),
    ("Tullamore Musical Society", 1954,
     "Society's own anniversary programme (photo submission, 2026-08-24) - first production listed 1955"),
    ("Castlerea Musical Society", 1968,
     'Society\'s own 50th-anniversary programme (photo submission, 2026-08-24) - '
     '"celebrating 50 years", productions from 1968'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    updated, skipped, problems = 0, 0, []

    for name, year, evidence in FOUNDING_YEARS:
        society = db.execute(
            "SELECT id, name, founded_year FROM societies WHERE name = ?", (name,)
        ).fetchone()
        if society is None:
            problems.append(f"no such society: {name!r}")
            continue
        if society["founded_year"]:
            print(f"  already set: {name} ({society['founded_year']})")
            skipped += 1
            continue

        # Re-assert the bound at write time, not just at research time - our own
        # records are the check, and they can move.
        bound = db.execute(
            "SELECT MIN(year) FROM historical_results WHERE society_id = ?", (society["id"],)
        ).fetchone()[0]
        if bound and year > bound:
            problems.append(f"{name}: {year} is later than our earliest record ({bound}) - not written")
            continue

        db.execute("UPDATE societies SET founded_year = ? WHERE id = ?", (year, society["id"]))
        print(f"  {name}: {year}")
        print(f"      {evidence}")
        updated += 1

    print(f"\n{updated} set, {skipped} already had one")
    if problems:
        print("\nProblems:")
        for p in problems:
            print(f"  {p}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
