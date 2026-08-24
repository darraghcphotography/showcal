"""Loads Antigravity's enrichment pass for titles with no synopsis/rights data
(`enrichment/shows_worklist.json`, see `enrichment/ENRICHMENT_BRIEF.md` and
ROADMAP.md) into `show_info`.

Matches on the exact title string against shows/historical_results, same as
enrich_show_info.py - show_info.show is a plain TEXT primary key, no fuzzy
matching (this repo deliberately avoids it, see app/similarity.py). Only fills
a currently-blank field, so a real moderator edit made via
/admin/titles/<title>/info always wins over this one-off batch; safe to re-run.

Usage:
    py import_show_enrichment.py [--db aims.db] [--json enrichment/shows_worklist.json] [--dry-run]
"""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

FIELDS = ("synopsis", "rights_url", "rights_status", "premiere_year", "premiere_place")
VALID_RIGHTS_STATUS = ("Available", "Contact publisher", "Restricted")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--json", default=str(ROOT / "enrichment" / "shows_worklist.json"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    rows = json.loads(Path(args.json).read_text(encoding="utf-8"))

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    updated, skipped, unmatched, rejected = [], [], [], []

    for row in rows:
        title = row["title"]

        status = row.get("rights_status")
        if status and status not in VALID_RIGHTS_STATUS:
            rejected.append((title, f"rights_status {status!r} isn't one of {VALID_RIGHTS_STATUS}"))
            continue

        exists = db.execute(
            "SELECT 1 FROM shows WHERE show = ? UNION SELECT 1 FROM historical_results WHERE show = ? LIMIT 1",
            (title, title),
        ).fetchone()
        if not exists:
            unmatched.append(title)
            continue

        current = db.execute("SELECT * FROM show_info WHERE show = ?", (title,)).fetchone()

        if current is None:
            changing = {f: row[f] for f in FIELDS if row.get(f) is not None}
            if not changing:
                skipped.append(title)
                continue
            db.execute(
                "INSERT INTO show_info (show, synopsis, rights_url, rights_status, "
                "premiere_year, premiere_place, updated_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                (title, changing.get("synopsis"), changing.get("rights_url"),
                 changing.get("rights_status"), changing.get("premiere_year"), changing.get("premiere_place")),
            )
        else:
            changing = {f: row[f] for f in FIELDS if row.get(f) is not None and not current[f]}
            if not changing:
                skipped.append(title)
                continue
            assignments = ", ".join(f"{f} = :{f}" for f in changing)
            db.execute(
                f"UPDATE show_info SET {assignments}, updated_at = datetime('now') WHERE show = :show",
                dict(changing, show=title),
            )

        updated.append((title, sorted(changing)))

    print(f"Updated {len(updated)} titles:")
    for title, fields in updated:
        print(f"  {title}: {', '.join(fields)}")
    print(f"\nSkipped (already had data in every field the worklist offered): {len(skipped)}")
    if unmatched:
        print(f"\nUnmatched (no such title in shows/historical_results, check spelling): {len(unmatched)}")
        for title in unmatched:
            print(f"  {title}")
    if rejected:
        print(f"\nRejected (bad rights_status value): {len(rejected)}")
        for title, why in rejected:
            print(f"  {title}: {why}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print(f"\nCommitted {len(updated)} updates")
    db.close()


if __name__ == "__main__":
    main()
