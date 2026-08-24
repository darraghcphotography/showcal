"""Fill in societies.default_venue for a handful of the 71 societies the
Gemini-sourced backfill (backfill_default_venues.py, 2026-08-24 session) had
nothing to say about - it was exhausted for these names.

Source this time: only this repo's own data. shows.venue is the *only* place
venue text lives (historical_results and historical_reviews carry no venue
column at all), so for each of the 71 societies with no default_venue this
queried `SELECT venue, COUNT(*) FROM shows WHERE society_id = ? GROUP BY
venue` and looked for one venue that clearly dominates.

Verdict: most of the 71 don't have enough to go on. 51 have zero shows with
any venue text recorded at all. Of the 20 that have at least one, most have
only 1-2 shows total and no real majority (a specific building's name split
1-1 against a bare town/county string isn't a majority, it's a coin flip -
left alone rather than guessed). Exactly 3 clear a "confident" bar:

  * Stage One New-Musical Group (S.O.N.G.) - 4 of 4 shows with a venue
    recorded (05/06-27/28 span, 19 shows total) name the same building,
    spelled two ways: "An Táin Arts Centre" x3, "An Táin Arts" x1. Matches
    the spelling Dundalk Musical Society's own default_venue already uses
    for the same building (venues.id=92).
  * Twin Productions - 2 of 2 shows with a venue recorded both say "Town
    Hall Theatre, Galway" verbatim (venues.id=1, same spelling Encore
    Theatre Company and Patrician Musical Society already use).
  * South Eastern Theatre Group - 2 of 2 shows with a venue recorded name
    the same building, spelled two ways: "Theatre Royal Waterford" and
    "Theatre Royal, Waterford" (venues.id=40, same spelling Waterford
    Musical Society's own default_venue already uses).

All three came from source='import' or source='historical' rows (spreadsheet/
archive data), not a member's own self-submission, and none contradicted
itself across seasons.

Usage:
    py backfill_default_venues_round2.py [--db aims.db] [--dry-run]
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent


# (society name, venue to set, evidence)
ROWS = [
    ('Stage One New-Musical Group (S.O.N.G.)', 'An Táin Arts Centre, Dundalk',
     '4 of 4 shows with a venue recorded since 05/06 name this building '
     '("An Táin Arts Centre" x3, "An Táin Arts" x1)'),
    ('Twin Productions', 'Town Hall Theatre, Galway',
     '2 of 2 shows with a venue recorded both say "Town Hall Theatre, Galway"'),
    ('South Eastern Theatre Group', 'Theatre Royal, Waterford',
     '2 of 2 shows with a venue recorded name this building '
     '("Theatre Royal Waterford" and "Theatre Royal, Waterford")'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    set_count = 0
    already = []
    missing = []
    for society, venue, why in ROWS:
        row = db.execute(
            "SELECT id, default_venue FROM societies WHERE name = ?", (society,)
        ).fetchone()
        if row is None:
            missing.append(society)
            continue
        if row["default_venue"]:
            # Somebody has set one since this list was built. Theirs wins.
            already.append((society, row["default_venue"]))
            continue
        db.execute("UPDATE societies SET default_venue = ? WHERE id = ?", (venue, row["id"]))
        print(f"  {society}: {venue}")
        print(f"      {why}")
        set_count += 1

    if already:
        print()
        print(f"Left alone - already had a default venue ({len(already)}):")
        for society, venue in already:
            print(f"  {society}: {venue}")
    if missing:
        print()
        print(f"No society by that name ({len(missing)}):")
        for society in missing:
            print(f"  {society}")

    filled = db.execute(
        "SELECT COUNT(*) FROM societies WHERE default_venue IS NOT NULL AND default_venue != ''"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM societies").fetchone()[0]
    print()
    print(f"Set {set_count}. {filled} of {total} societies now have a default venue.")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
