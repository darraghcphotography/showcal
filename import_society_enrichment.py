"""Loads Antigravity's enrichment pass for societies with zero social/about
info (`enrichment/societies_worklist.json`, see `enrichment/ENRICHMENT_BRIEF.md`
and ROADMAP.md) into the `societies` table.

Matches on `societies.id`, which is stable (seeded from societies.csv, not
autoincrement - see schema.sql), not on name. Only ever fills a currently-blank
field: `about`/`website_url`/`facebook_url`/`instagram_url` are society-editable
via the society's own login, so a real value entered that way always wins over
this one-off batch, the same trust model as import_csv.py's treatment of
moderator-edited fields. Safe to re-run - already-filled fields are reported as
skipped, never overwritten.

Usage:
    py import_society_enrichment.py [--db aims.db] [--json enrichment/societies_worklist.json] [--dry-run]
"""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

FIELDS = ("website_url", "facebook_url", "instagram_url", "about")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--json", default=str(ROOT / "enrichment" / "societies_worklist.json"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    rows = json.loads(Path(args.json).read_text(encoding="utf-8"))

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    updated, skipped, unmatched = [], [], []

    for row in rows:
        current = db.execute(
            "SELECT * FROM societies WHERE id = ?", (row["id"],)
        ).fetchone()
        if current is None:
            unmatched.append((row["id"], row["name"]))
            continue
        if current["name"] != row["name"]:
            unmatched.append((row["id"], f"{row['name']!r} (db has {current['name']!r})"))
            continue

        changing = {
            f: row[f] for f in FIELDS
            if row.get(f) and not current[f]
        }
        if not changing:
            skipped.append(row["name"])
            continue

        assignments = ", ".join(f"{f} = :{f}" for f in changing)
        db.execute(
            f"UPDATE societies SET {assignments} WHERE id = :id",
            dict(changing, id=row["id"]),
        )
        updated.append((row["name"], sorted(changing)))

    print(f"Updated {len(updated)} societies:")
    for name, fields in updated:
        print(f"  {name}: {', '.join(fields)}")
    print(f"\nSkipped (already had data in every field the worklist offered): {len(skipped)}")
    if unmatched:
        print(f"\nUnmatched (no such society id, or name changed since the worklist was made): {len(unmatched)}")
        for id_, name in unmatched:
            print(f"  id {id_}: {name}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print(f"\nCommitted {len(updated)} updates")
    db.close()


if __name__ == "__main__":
    main()
