"""Resets two shows marked "Published" that have no review link.

`review_status = 'Published'` is meant to say "there is an AIMS review to
read", and the admin form sets it by itself the moment a review URL is
attached. Two 26/27 shows carried the status with no link at all:

  * shows.id 3094  All Shook Up - Mallow Musical Society, opening 2027-04-16
  * shows.id 3096  Dear Evan Hansen - Newry Youth Performing Arts, closed 2026-10-03

The public page printed the bare word, so an April 2027 production read
"Review: Published" (site audit, 2026-10-05). Neither has a review yet: one
hasn't opened and the other closed two days before the audit.

Both go back to 'None', the status every new show starts with. That keeps
Dear Evan Hansen in the admin reviews queue, which is where its link will be
added once AIMS publishes it. The admin form now refuses Published without a
link, so this can't recur through it.

Scoped to the listed ids AND to the condition still being true, so a re-run
after someone has added a link changes nothing.

Usage:
    py scripts/backfills/reset_published_without_link.py [--db aims.db] [--dry-run]

    docker exec aims-web python \\
        /app/scripts/backfills/reset_published_without_link.py --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
from pathlib import Path

SHOW_IDS = (3094, 3096)

STILL_BROKEN = (
    "review_status = 'Published' AND (review_url IS NULL OR review_url = '')"
)


def reset(db, show_ids=SHOW_IDS):
    """Reset the listed shows that are still Published-without-link.
    Returns the rows it changed, as they were before the change."""
    marks = ",".join("?" * len(show_ids))
    rows = db.execute(
        f"""
        SELECT shows.id, shows.show, shows.season, shows.opening_date,
               shows.closing_date, societies.name AS society
          FROM shows JOIN societies ON societies.id = shows.society_id
         WHERE shows.id IN ({marks}) AND {STILL_BROKEN}
         ORDER BY shows.id
        """,
        show_ids,
    ).fetchall()
    if rows:
        db.execute(
            f"UPDATE shows SET review_status = 'None', updated_at = datetime('now') "
            f"WHERE id IN ({marks}) AND {STILL_BROKEN}",
            show_ids,
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # Resolved lazily: piped through `docker exec -i ... python -`, __file__ is
    # "<stdin>" and parents[2] would raise before --db is even read.
    default_db = "aims.db"
    if __file__ not in ("<stdin>", "-"):
        default_db = str(Path(__file__).resolve().parents[2] / "aims.db")
    parser.add_argument("--db", default=default_db)
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    rows = reset(db)
    if not rows:
        print("Nothing to do - none of the listed shows is still Published without a link.")
    for r in rows:
        print(f"  shows.id {r['id']}  {r['show']} - {r['society']} ({r['season']}, "
              f"{r['opening_date']} to {r['closing_date']}): Published -> None")

    left = db.execute(f"SELECT COUNT(*) FROM shows WHERE {STILL_BROKEN}").fetchone()[0]
    print(f"\n{len(rows)} show(s) reset. Published-without-link left anywhere: {left} (should be 0).")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("Written.")
    db.close()


if __name__ == "__main__":
    main()
