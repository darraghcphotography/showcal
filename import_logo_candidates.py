"""Imports candidate society logos found by a delegated web search
(`enrichment/logo_worklist*.json`) into `logo_candidates` for a moderator to
approve/reject one at a time via /admin/logo-candidates - never a direct
write to societies.logo_filename.

Only rows with `"found": true` are imported. Each one is fetched and
validated right here at import time (see uploads.py's fetch_logo_candidate) -
never trust a source_url without opening it, same rule as everything else
delegated this way. A row whose URL doesn't actually decode as a real image
still gets a row (status stays 'pending', filename stays NULL, fetch_error
records why) rather than being silently dropped - a moderator should be able
to see that a candidate was found but couldn't be verified, not just have it
vanish.

A society already holding a pending/approved/rejected candidate is skipped -
re-running this after a partial import, or after sending the same worklist
twice, doesn't duplicate rows.

Usage:
    py import_logo_candidates.py [--db aims.db] [--json enrichment/logo_worklist.json] [--dry-run]

    docker compose exec aims-web python import_logo_candidates.py --db /data/aims.db --json /data/logo_worklist.json
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from app.uploads import fetch_logo_candidate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--json", default=str(ROOT / "enrichment" / "logo_worklist.json"))
    parser.add_argument("--upload-dir", default=str(ROOT / "uploads"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would happen, fetch nothing, write nothing")
    args = parser.parse_args()

    rows = json.loads(Path(args.json).read_text(encoding="utf-8"))
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    imported, skipped_not_found, skipped_existing, fetch_failed = 0, 0, 0, 0

    for row in rows:
        if not row.get("found"):
            skipped_not_found += 1
            continue

        society_id = row["society_id"]
        existing = db.execute(
            "SELECT id FROM logo_candidates WHERE society_id = ?", (society_id,)
        ).fetchone()
        if existing:
            print(f"  skip {row['society_name']!r} - already has a candidate row (id {existing['id']})")
            skipped_existing += 1
            continue

        url = row["logo_url"]
        print(f"\n{row['society_name']} <- {url}")
        if args.dry_run:
            print("  --dry-run: would fetch and stage this")
            imported += 1
            continue

        filename, fetch_error = None, None
        try:
            filename = fetch_logo_candidate(url, args.upload_dir)
            print(f"  fetched -> {filename}")
        except ValueError as e:
            fetch_error = str(e)
            print(f"  FETCH FAILED: {fetch_error}")
            fetch_failed += 1

        db.execute(
            "INSERT INTO logo_candidates (society_id, source_url, source_page_url, notes, filename, fetch_error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (society_id, url, row.get("source_page_url"), row.get("notes"), filename, fetch_error),
        )
        imported += 1

    print(f"\n{imported} staged ({fetch_failed} of those failed to fetch and need a manual look), "
          f"{skipped_existing} already had a candidate, {skipped_not_found} were found:false")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
