"""Deletes one production that was announced and then never happened.

`shows.id 1997` is "A Chorus Line (Cancelled)" - Maynooth University Musical
Society, opening 2020-05-21, a COVID casualty. Whoever recorded it put the
cancellation into the show's *title*, because there was nowhere else to put it:
`shows.status` was the only cancelled flag this app ever had and it was dropped
in August 2026 as unreliable (see `_migrate_drop_shows_status`).

The consequence is that a run which never took place is counted as a real
staging. It inflates the productions total, it appears on /titles as its own
distinct show next to the genuine "A Chorus Line", it sits in the /stats
"one-off productions" list, and it adds one to Maynooth's production count on
both /societies and their own page.

Darragh's call, 2026-09-02: it never happened, so it does not belong in a record
of what was staged. Delete it.

Only the `shows` row is deleted here. The matching `productions` row is derived
(see app/productions_build.py) and disappears on the next rebuild, which the app
performs on startup and lazily whenever the source tables have moved - so this
script deliberately does not touch it by hand, and reports what the rebuild will
be left to do.

This is scoped to one row by id AND by title, so it cannot quietly widen if it
is ever re-run against a different database.

Usage:
    py scripts/backfills/delete_cancelled_chorus_line.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python \\
        scripts/backfills/delete_cancelled_chorus_line.py --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
from pathlib import Path

SHOW_ID = 1997
SHOW_TITLE = "A Chorus Line (Cancelled)"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # Resolved lazily rather than at import: this file gets piped straight into
    # `docker exec -i ... python -` on the NAS, where __file__ is "<stdin>" and
    # parents[2] raises before argparse ever runs - even though --db is being
    # passed explicitly and the default is never used.
    default_db = "aims.db"
    if __file__ not in ("<stdin>", "-"):
        default_db = str(Path(__file__).resolve().parents[2] / "aims.db")
    parser.add_argument("--db", default=default_db)
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    row = db.execute(
        """
        SELECT shows.id, shows.show, shows.season, shows.opening_date,
               shows.production_id, societies.name AS society
          FROM shows JOIN societies ON societies.id = shows.society_id
         WHERE shows.id = ? AND shows.show = ?
        """,
        (SHOW_ID, SHOW_TITLE),
    ).fetchone()

    if row is None:
        print(f"No shows row {SHOW_ID} titled {SHOW_TITLE!r} - nothing to do.")
        db.close()
        return

    print("Deleting:")
    print(f"  shows.id {row['id']}  {row['show']}")
    print(f"  {row['society']} - season {row['season']}, opening {row['opening_date']}")
    print(f"  linked productions.id {row['production_id']}")

    # Anything hanging off this show should be reported before it goes, rather
    # than discovered missing later.
    for table, column in (("historical_reviews", "production_id"),
                          ("historical_results", "production_id")):
        n = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (row["production_id"],)
        ).fetchone()[0]
        print(f"  {table} rows linked to that production: {n}")

    before = db.execute("SELECT COUNT(*) FROM productions").fetchone()[0]
    db.execute("DELETE FROM shows WHERE id = ? AND show = ?", (SHOW_ID, SHOW_TITLE))
    print(f"\n{db.total_changes} shows row(s) deleted.")
    print(f"productions still holds {before} row(s); the derived rebuild drops "
          f"id {row['production_id']} on the app's next startup or lazy rebuild.")

    still_there = db.execute(
        "SELECT COUNT(*) FROM shows WHERE show LIKE '%Cancelled%'"
    ).fetchone()[0]
    print(f"shows still carrying 'Cancelled' in a title: {still_there} (should be 0).")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nWritten.")
    db.close()


if __name__ == "__main__":
    main()
