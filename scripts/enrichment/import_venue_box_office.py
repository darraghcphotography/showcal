"""Loads `enrichment/venue_box_office_worklist.json` (see
`enrichment/CREDITS_AND_CONTACTS_BRIEF.md`) into `venues.box_office_phone` /
`box_office_url`.

Matched by name through `venue_aliases`, not by the worklist's `id` - venues is
a derived table (app/venues_build.py) that can renumber rows on rebuild, so the
only stable identity is a spelling that has actually appeared in shows.venue.
Same as import_venue_enrichment.py. Only fills a currently-blank field, so a
moderator edit always wins; safe to re-run.

Spot-checked before first import (2026-08-25), unlike the coordinate worklist
from the same batch which was rejected as fabricated:
  * St. Michael's Theatre, New Ross - "051 421 255" matches the theatre's own
    contact page exactly.
  * Border-town area codes are right where a county-based guess would be wrong
    (New Ross and Carrick-on-Suir on 051, Ballinasloe on 090, Ratoath and
    Dunboyne on 01, Castleblayney on 042). That's real exchange-area knowledge,
    not pattern-matching from the county name.
  * All 8 shared phone numbers are pairs of duplicate venue rows for the same
    real building (Civic Theatre Tallaght, Siamsa Tire, the Island Arts Centre
    ...), i.e. correctly consistent rather than copy-pasted noise.
  * 36 of 108 rows left blank rather than padded - the brief's "a blank beats a
    guess" rule actually being followed.

Usage:
    py import_venue_box_office.py [--db aims.db] [--json enrichment/venue_box_office_worklist.json] [--dry-run]

    docker compose exec aims-web python import_venue_box_office.py --db /data/aims.db --json /data/venue_box_office_worklist.json
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.venues import normalize_venue  # noqa: E402

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

FIELDS = ("box_office_phone", "box_office_url")


def resolve(db, name):
    row = db.execute(
        "SELECT venue_id FROM venue_aliases WHERE name_key = ?", (normalize_venue(name),)
    ).fetchone()
    return row["venue_id"] if row else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--json", default=str(ROOT / "enrichment" / "venue_box_office_worklist.json"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    rows = json.loads(Path(args.json).read_text(encoding="utf-8"))

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    updated, skipped, unmatched, offered_nothing = [], [], [], 0

    for row in rows:
        if not any(row.get(f) for f in FIELDS):
            offered_nothing += 1
            continue

        venue_id = resolve(db, row["name"])
        if venue_id is None:
            unmatched.append(row["name"])
            continue
        current = db.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()

        changing = {f: row[f] for f in FIELDS if row.get(f) and not current[f]}
        if not changing:
            skipped.append(current["name"])
            continue

        assignments = ", ".join(f"{f} = :{f}" for f in changing)
        db.execute(
            f"UPDATE venues SET {assignments}, updated_at = datetime('now') WHERE id = :id",
            dict(changing, id=venue_id),
        )
        updated.append((current["name"], sorted(changing)))

    print(f"Updated {len(updated)} venues:")
    for name, fields in updated:
        print(f"  {name}: {', '.join(fields)}")
    print(f"\nSkipped (already had data in every field the worklist offered): {len(skipped)}")
    print(f"Worklist rows with nothing to offer (left blank by the researcher): {offered_nothing}")
    if unmatched:
        print(f"\nUnmatched (no spelling in venue_aliases matches this name): {len(unmatched)}")
        for name in unmatched:
            print(f"  {name}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print(f"\nCommitted {len(updated)} updates")
    db.close()


if __name__ == "__main__":
    main()
