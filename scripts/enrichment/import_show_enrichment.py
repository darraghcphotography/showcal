"""Loads an enrichment worklist for show titles into `show_info` - synopsis,
rights, premiere and creative-credit fields (see `enrichment/ENRICHMENT_BRIEF.md`
and `enrichment/CREDITS_AND_CONTACTS_BRIEF.md`).

Handles both worklist shapes, since they share a `title` key and differ only in
which of FIELDS they carry: `shows_worklist.json` (synopsis/rights/premiere) and
`show_credits_worklist.json` (composer/lyricist/book_author/licensing_house).

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

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

FIELDS = (
    "synopsis", "rights_url", "rights_status", "premiere_year", "premiere_place",
    # Creative credits, added 2026-08-25 - the columns shipped after this
    # script was first written, so a worklist carrying them was silently
    # dropping four fields on the floor until they were listed here.
    "composer", "lyricist", "book_author", "licensing_house",
)
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
            # Built from `changing` rather than a hardcoded column list, so
            # adding a field to FIELDS is the only change a new column needs -
            # the hardcoded version silently ignored four columns once already.
            columns = ", ".join(changing)
            placeholders = ", ".join(f":{f}" for f in changing)
            db.execute(
                f"INSERT INTO show_info (show, {columns}, updated_at) "
                f"VALUES (:show, {placeholders}, datetime('now'))",
                dict(changing, show=title),
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
