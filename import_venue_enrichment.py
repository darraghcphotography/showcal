"""Loads Antigravity's enrichment pass for venues missing capacity/coordinates/
website (`enrichment/venues_worklist.json`, see `enrichment/ENRICHMENT_BRIEF.md`
and ROADMAP.md) into the `venues` table.

Matches by name through `venue_aliases`, not by the worklist's `id` - venues is
a derived table (app/venues_build.py) that can insert/renumber rows on rebuild,
so the only stable identity is a spelling that has actually appeared in
shows.venue, same as enrich_venues.py's own resolve(). Only writes
CURATED_COLUMNS (county, capacity, auditorium_type, latitude, longitude,
website_url) - town/region are re-derived by the rebuild and would just be
overwritten again. Only ever fills a currently-blank field, so a real
moderator edit always wins; safe to re-run.

`venue_type` in the worklist is deliberately NOT imported here - there is no
such column yet (see ROADMAP.md's "Venue categorization" item, still an open
design decision on the category schema/filter/badges). Rows carrying it are
reported at the end so that decision has real data to work from later.

Usage:
    py import_venue_enrichment.py [--db aims.db] [--json enrichment/venues_worklist.json] [--dry-run]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.venues import normalize_venue  # noqa: E402

ROOT = Path(__file__).parent

CURATED_FIELDS = ("county", "capacity", "auditorium_type", "latitude", "longitude", "website_url")


def resolve(db, name):
    row = db.execute(
        "SELECT venue_id FROM venue_aliases WHERE name_key = ?", (normalize_venue(name),)
    ).fetchone()
    return row["venue_id"] if row else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--json", default=str(ROOT / "enrichment" / "venues_worklist.json"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    rows = json.loads(Path(args.json).read_text(encoding="utf-8"))

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    updated, skipped, unmatched = [], [], []
    venue_types = []

    for row in rows:
        venue_id = resolve(db, row["name"])
        if venue_id is None:
            unmatched.append(row["name"])
            continue
        current = db.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()

        if row.get("venue_type"):
            venue_types.append((current["name"], row["venue_type"]))

        changing = {
            f: row[f] for f in CURATED_FIELDS
            if row.get(f) is not None and not current[f]
        }
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
    if unmatched:
        print(f"\nUnmatched (no spelling in venue_aliases matches this name): {len(unmatched)}")
        for name in unmatched:
            print(f"  {name}")
    print(f"\nvenue_type collected but not written (no column yet - see ROADMAP.md): {len(venue_types)}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print(f"\nCommitted {len(updated)} updates")
    db.close()


if __name__ == "__main__":
    main()
