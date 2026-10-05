"""Points two shows at their real venue instead of a note about the run.

Two 26/27 shows had a note typed into the venue field, and the venues table -
which is derived from shows.venue (see app/venues_build.py) - turned each note
into a venue with its own public page:

  * shows.id 385  Newsies - Bellvue Academy of Performing Arts: "Cork run"
  * shows.id 398  Sweet Charity - Trim Musical Society: "40th Anniversary (March run)"

Each is set to its society's default venue. That is a judgement call, so the
mapping goes to Darragh after the dry run and the real run waits for his yes. Nothing else is touched: the next venues rebuild (on app startup, or
lazily when shows move) re-points the shows and drops the two note "venues",
which nobody has curated, so they have no capacity or map pin to lose.

Scoped to the id AND to the venue text still being the note, so a re-run after
someone has corrected it by hand changes nothing.

Usage:
    py scripts/backfills/fix_run_note_venues.py [--db aims.db] [--dry-run]

    docker exec aims-web python \\
        /app/scripts/backfills/fix_run_note_venues.py --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
from pathlib import Path

# show id -> (the note sitting in shows.venue, the real venue)
FIXES = {
    385: ("Cork run", "The Everyman, Cork"),
    398: ("40th Anniversary (March run)", "Swift Cultural Centre, Trim"),
}


def apply(db, fixes=FIXES):
    """Rewrite each listed show's venue if it still holds the note.
    Returns (show id, title, society, old, new) for every row it changed."""
    changed = []
    for show_id, (note, venue) in fixes.items():
        row = db.execute(
            """
            SELECT shows.id, shows.show, societies.name AS society
              FROM shows JOIN societies ON societies.id = shows.society_id
             WHERE shows.id = ? AND shows.venue = ?
            """,
            (show_id, note),
        ).fetchone()
        if row is None:
            continue
        db.execute(
            "UPDATE shows SET venue = ?, updated_at = datetime('now') WHERE id = ? AND venue = ?",
            (venue, show_id, note),
        )
        changed.append((row["id"], row["show"], row["society"], note, venue))
    return changed


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

    changed = apply(db)
    if not changed:
        print("Nothing to do - every listed show already has a real venue.")
    for show_id, title, society, old, new in changed:
        print(f"  shows.id {show_id}  {title} - {society}: {old!r} -> {new!r}")
    for show_id, (_, venue) in FIXES.items():
        known = db.execute("SELECT id FROM venues WHERE name = ?", (venue,)).fetchone()
        where = f"existing venue id {known[0]}" if known else "NO matching venue yet - the rebuild will create one"
        print(f"  {venue!r}: {where}")

    print(f"\n{len(changed)} show(s) updated. The venues rebuild re-points them and drops the note venues.")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("Written.")
    db.close()


if __name__ == "__main__":
    main()
