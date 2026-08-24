"""One-off backfill of 6 productions missing from Naas Musical Society's
record, read directly off their own 30th-anniversary programme (a photo
submitted via /submit/photo, admin/photo_submissions.py id 1, 2026-08-24 -
the first real test of that intake, and of the long-parked "OCR test on a
programme photo" idea: no OCR tool was needed, the photo was read directly).

The programme is a 6x5 grid of poster tiles, one per production, 1996-2026 -
24 of the 30 were already on record and needed nothing; these 6 were the
gaps. Same insert shape as admin.bulk_historical_productions (a bare
historical_results row - no award/category attached, just "this happened"),
with the same title, and the poster's own printed year taken as-is (not
+1'd) - Darragh's call 2026-08-24, since 14 of the 30 productions on the
poster already match the database's year with no offset at all, against
only 2 that would want one.

Usage:
    py naas_history_backfill.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python naas_history_backfill.py --db /data/aims.db
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

SOCIETY_NAME = "Naas Musical Society"
REASON = "From the society's own 30th-anniversary programme (photo submission, 2026-08-24)"

# (year, show) - as printed on the poster
PRODUCTIONS = [
    (2002, "Anything Goes"),
    (2004, "The Music Man"),
    (2006, "Brigadoon"),
    (2008, "Carousel"),
    (2010, "Fiddler on the Roof"),
    (2020, "Sister Act"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    society = db.execute("SELECT id, name FROM societies WHERE name = ?", (SOCIETY_NAME,)).fetchone()
    if society is None:
        raise SystemExit(f"No society named {SOCIETY_NAME!r} found.")

    inserted, skipped = 0, 0
    for year, show in PRODUCTIONS:
        existing = db.execute(
            "SELECT 1 FROM historical_results WHERE year = ? AND show = ? AND society_id = ?",
            (year, show, society["id"]),
        ).fetchone()
        if existing:
            print(f"  already on record: {year} {show!r}")
            skipped += 1
            continue
        db.execute(
            "INSERT INTO historical_results (year, show, society_name, society_id, reason, source) "
            "VALUES (?, ?, ?, ?, ?, 'manual')",
            (year, show, society["name"], society["id"], REASON),
        )
        print(f"  added: {year} {show!r}")
        inserted += 1

    print(f"\n{inserted} added, {skipped} already on record")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
