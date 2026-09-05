"""Repoints the one orphaned historical_review left behind by the SONG merge.

`merge_song_dundalk.py` (2026-09-03) deleted the duplicate society's shows
because the surviving society already held the same productions. It checked
every table that references a *society*, and refused to delete while any still
pointed at the duplicate - but it never checked what referenced the **shows it
was deleting itself**. `historical_reviews.show_id` did.

Row 595 - a real adjudicator review of SONG Dundalk's 13/14 Little Women,
printed in ShowTimes Issue 93 - was left pointing at deleted show 1596.

Confirmed by bisecting the nightly backups rather than by reading the script:

    aims-20260902-233744  fk_violations=0  show 1596 present
    aims-20260903-154853  fk_violations=1  show 1596 gone

The fix is to repoint, not to delete. Show 1147 is society 108's 13/14 Little
Women - the same production, under the society the merge kept - so the review
belongs to it. Nulling `show_id` would resolve the constraint just as well and
would quietly add a 56th orphaned review to a pile already on the roadmap.

NOT FIXED HERE, deliberately. This row's `society_raw` reads "Shannon Musical
Society" and its `society_id` is 98 (Shannon), while the review text plainly
says "SONG in Dundalk gave us a compelling tale". That mis-attribution predates
the merge and is a judgement call about a printed source nobody here can see,
so it is recorded rather than guessed at.

Usage:
    py scripts/backfills/fix_orphaned_song_review.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python \\
        scripts/backfills/fix_orphaned_song_review.py --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
from pathlib import Path

_here = Path(__file__).resolve()
ROOT = _here.parents[2] if len(_here.parents) > 2 else Path.cwd()

REVIEW_ID = 595
DEAD_SHOW_ID = 1596
KEEPER_SHOW_ID = 1147


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    review = db.execute(
        "SELECT id, show_id, season, show_raw FROM historical_reviews WHERE id = ?",
        (REVIEW_ID,),
    ).fetchone()
    if review is None:
        print(f"No historical_review {REVIEW_ID} - nothing to do.")
        return
    if review["show_id"] != DEAD_SHOW_ID:
        print(f"Review {REVIEW_ID} points at show {review['show_id']}, not {DEAD_SHOW_ID} - "
              "already fixed or changed since. Refusing to touch it.")
        return

    # The replacement has to actually be the same production, not just any row.
    keeper = db.execute(
        "SELECT id, season, show, society_id FROM shows WHERE id = ?", (KEEPER_SHOW_ID,)
    ).fetchone()
    if keeper is None:
        raise SystemExit(f"Show {KEEPER_SHOW_ID} is missing - refusing to repoint at nothing.")
    if keeper["season"] != review["season"]:
        raise SystemExit(
            f"Season mismatch: review is {review['season']}, show {KEEPER_SHOW_ID} is "
            f"{keeper['season']}. Refusing."
        )

    print(f"review {REVIEW_ID}  {review['season']} {review['show_raw']}")
    print(f"  show_id {review['show_id']} (deleted)  ->  {keeper['id']} "
          f"({keeper['season']} {keeper['show']}, society {keeper['society_id']})")
    db.execute("UPDATE historical_reviews SET show_id = ? WHERE id = ?",
               (KEEPER_SHOW_ID, REVIEW_ID))

    violations = db.execute("PRAGMA foreign_key_check").fetchall()
    print(f"\nforeign key violations after the change: {len(violations)}")
    for v in violations:
        print("  ", tuple(v))

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nWritten.")
    db.close()


if __name__ == "__main__":
    main()
