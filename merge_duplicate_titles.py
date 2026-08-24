"""One-off merge for spelling-variant title pairs identified by hand
(2026-08-24 evening run-through found these visible once the productions
cutover stopped hiding them; the site's own fuzzy duplicate detector
doesn't flag either pair on its own, so this needed a manual look rather
than the bulk /admin/duplicate-titles tool - see ROADMAP.md).

Each pair was checked against real production data before being added here:
a society appearing under both spellings is direct evidence of the same
show, not two different ones. The canonical spelling is whichever carries
the majority of existing records, to minimize how many rows change and
match the more common real-world spelling:
  - "Fame" -> "Fame: The Musical" (7 records vs 2; Leixlip Musical & Variety
    Group staged it under both spellings)
  - "Sugar The Musical - Some Like It Hot" -> "Sugar" (5 records vs 1;
    Mitchelstown Musical Society staged it under both spellings - "Sugar"
    is the real 1972 Broadway title, "Some Like It Hot" a later
    licensing/revival name for the same show)

Deliberately NOT included: "Peter Pan" / "Peter Pan, A Musical Adventure"
(no overlapping society, and the latter is a real distinct licensed title
by Piers Chater-Robinson - not enough evidence either way that this is a
spelling duplicate rather than two different shows).

Usage:
    py merge_duplicate_titles.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python merge_duplicate_titles.py --db /data/aims.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.blueprints.admin.duplicates import _merge_titles  # noqa: E402

ROOT = Path(__file__).parent

# (canonical, other spelling to fold into it)
MERGES = [
    ("Fame: The Musical", "Fame"),
    ("Sugar", "Sugar The Musical - Some Like It Hot"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    for canonical, other in MERGES:
        before = (
            db.execute("SELECT COUNT(*) FROM shows WHERE show = ?", (other,)).fetchone()[0]
            + db.execute("SELECT COUNT(*) FROM historical_results WHERE show = ?", (other,)).fetchone()[0]
        )
        if before == 0:
            print(f"  already merged (or never existed): {other!r}")
            continue
        _merge_titles(db, canonical, other)
        print(f"  {other!r} -> {canonical!r} ({before} row(s))")

        # _merge_titles only moves shows/historical_results - show_info and
        # show_links are still keyed by the exact title string (see their
        # own schema.sql comments), so a row still sitting under "other"
        # would silently orphan the moment its last shows/historical_results
        # row is gone - the same class of bug admin/data_quality.py's
        # "Orphaned title data" check exists to catch. If the canonical
        # title doesn't have its own row, the "other" row is the real data
        # and gets carried over; if it does, "other"'s is redundant (both
        # titles independently got a synopsis from the same enrichment pass
        # earlier this session, for Fame at least) and is just dropped.
        for table in ("show_info", "show_links"):
            other_row = db.execute(f"SELECT 1 FROM {table} WHERE show = ?", (other,)).fetchone()
            if not other_row:
                continue
            canonical_row = db.execute(f"SELECT 1 FROM {table} WHERE show = ?", (canonical,)).fetchone()
            if canonical_row:
                db.execute(f"DELETE FROM {table} WHERE show = ?", (other,))
                print(f"    dropped redundant {table} row for {other!r} (canonical already has one)")
            else:
                db.execute(f"UPDATE {table} SET show = ? WHERE show = ?", (canonical, other))
                print(f"    carried {table} over from {other!r}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
