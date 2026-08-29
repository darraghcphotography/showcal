"""One-off correction for extract_historical_reviews.py's old .title()
artifact (fixed 2026-08-24, see _title_case there): "25TH ANNUAL..." became
"25Th Annual...", not "25th Annual..." - str.title() capitalizes the first
letter after ANY non-alphabetic character, including a digit. Ordinals are
common in show titles, so this hit real productions
("The 25th Annual Putnam County Spelling Bee").

Corrects historical_reviews.show_raw everywhere it carries the artifact, and
any skeleton show (source='historical', created by approving one of those
reviews - see admin/historical_reviews.py) whose own title inherited it and
was never corrected by hand since. Safe to re-run: only ever touches rows
still carrying the exact broken spelling.

Usage:
    py fix_ordinal_titlecasing.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python fix_ordinal_titlecasing.py --db /data/aims.db
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import productions_build  # noqa: E402

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

_TITLE_AFTER_DIGIT_RE = re.compile(r"(\d)([A-Z])")


def _fix(title):
    return _TITLE_AFTER_DIGIT_RE.sub(lambda m: m.group(1) + m.group(2).lower(), title)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    reviews = db.execute("SELECT id, show_raw, show_id FROM historical_reviews").fetchall()
    review_fixes = [(r["id"], r["show_raw"], _fix(r["show_raw"]), r["show_id"])
                     for r in reviews if r["show_raw"] and _fix(r["show_raw"]) != r["show_raw"]]

    for review_id, old, new, _ in review_fixes:
        db.execute("UPDATE historical_reviews SET show_raw = ? WHERE id = ?", (new, review_id))
        print(f"  historical_reviews {review_id}: {old!r} -> {new!r}")

    shows = db.execute("SELECT id, show FROM shows WHERE source = 'historical'").fetchall()
    show_fixes = [(s["id"], s["show"], _fix(s["show"])) for s in shows if s["show"] and _fix(s["show"]) != s["show"]]

    for show_id, old, new in show_fixes:
        # Same collision guard as apply_show_title_match (admin/historical_reviews.py) -
        # a corrected title could in principle already exist for this society/season.
        row = db.execute("SELECT society_id, season FROM shows WHERE id = ?", (show_id,)).fetchone()
        existing = db.execute(
            "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ? AND id != ?",
            (row["society_id"], row["season"], new, show_id),
        ).fetchone()
        if existing is not None:
            print(f"  SKIPPED shows {show_id}: {new!r} already exists as show {existing['id']} "
                  "for this society/season - needs a look by hand")
            continue
        db.execute("UPDATE shows SET show = ? WHERE id = ?", (new, show_id))
        print(f"  shows {show_id}: {old!r} -> {new!r}")

    if show_fixes:
        productions_build.mark_stale(db)

    print(f"\n{len(review_fixes)} historical_reviews rows, {len(show_fixes)} shows rows corrected")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
