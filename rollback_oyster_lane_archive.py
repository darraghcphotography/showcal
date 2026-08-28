"""One-off rollback: Oyster Lane's archive import, plus the redundant bare rows
the old exact-string duplicate guard let through.

Two separate problems, both found on 2026-08-27/28, both fixed here.

1. OYSTER LANE'S ARCHIVE ROWS ARE NOT TRUSTWORTHY. A society reported wrong
   entries in its own history. `import_society_archives.py` validated each
   delegated transcription by cross-checking it against years we already held
   award data for - but that check is structurally incapable of catching the
   errors that matter: it only validates years we already had data for, i.e.
   precisely the years the import wasn't adding anything. The rows that
   actually added new information were never checkable, and Oyster Lane's
   "The Wiz" (1998) and "The Boy Friend" (1999) sit in exactly that blind spot.
   Oyster Lane also scored 69% (9/13) when every other trusted society scored
   93-100%; that should have pulled it out of TRUSTED at the time and didn't.

   So: delete all 18 rows tagged with the archive REASON for society 87, and
   drop Oyster Lane from TRUSTED. Baldoyle (96%), Limerick (93%), Killarney
   (100%) and Castlebar (100%) stay - genuinely strong evidence.

2. THE DUPLICATE GUARD COMPARED RAW STRINGS. `import_society_archives.py`,
   `tullamore_castlerea_history_backfill.py` and `naas_history_backfill.py` all
   checked `show = ?` exactly, so a case or punctuation variant of a title we
   already held slipped straight past and inserted a redundant bare row beside
   the award record it duplicated. All three now compare with
   `app/similarity.py`'s `normalize_title` (normalisation, never fuzzy - the
   same distinction already settled for `match_show_for_edit`).

   This cleans up the rows that already got in. They are found by rule, not by
   hardcoded id: a bare row (no category) carrying one of the backfill REASON
   tags, whose society and normalized title match some *other* row within a
   year. As of 2026-08-28 that is exactly 3 rows outside the Oyster Lane
   rollback (a 4th, Oyster Lane 2012 "Beauty And The Beast", goes with it):

     * Limerick Musical Society 2011 "The Pirates of Penzance"
       (vs the award record's "The Pirates Of Penzance")
     * Tullamore Musical Society 1990 "Oh! Susanna" (vs "Oh Susanna!")
     * Tullamore Musical Society 2007 "Hello! Dolly" (vs "Hello, Dolly!")

   Deliberately NOT caught by that rule, and correctly so: rows where `reason`
   holds a real AIMS award citation rather than an import tag - e.g. id 10483
   (Tullamore 1996 "Oliver!") and 10494 (Naas 1996 "My Fair Lady"), both
   `result='Nominee'`, reason "For the most effective use of human, material
   and theatrical resources". Those are genuine award records that happen to
   have a NULL category, not import artifacts. Hence the REASON_TAGS allowlist
   below rather than a bare `reason IS NOT NULL`.

Usage:
    py rollback_oyster_lane_archive.py [--db aims.db] [--dry-run]

    docker exec aims-web python rollback_oyster_lane_archive.py --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from app.similarity import normalize_title  # noqa: E402

OYSTER_LANE_ID = 87
ARCHIVE_REASON_LIKE = "%own published production archive%"

# Only rows written by one of the bulk backfills are candidates for the
# duplicate cleanup. A `reason` that is a real award citation must never match.
REASON_TAGS = (
    "%own published production archive%",
    "%anniversary programme (photo submission%",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    # --- 1. Oyster Lane rollback ------------------------------------------
    doomed = db.execute(
        "SELECT id, year, show FROM historical_results "
        " WHERE society_id = ? AND reason LIKE ? ORDER BY year",
        (OYSTER_LANE_ID, ARCHIVE_REASON_LIKE),
    ).fetchall()

    print(f"Oyster Lane archive rows to delete: {len(doomed)}")
    for row in doomed:
        print(f"  del {row['id']:>6} {row['year']} {row['show']!r}")
    rolled_back_ids = {row["id"] for row in doomed}

    # --- 2. Redundant bare rows from the broken guard ---------------------
    candidates = []
    for tag in REASON_TAGS:
        candidates.extend(db.execute(
            "SELECT id, society_id, year, show, reason FROM historical_results "
            " WHERE category_name IS NULL AND show IS NOT NULL AND reason LIKE ?",
            (tag,),
        ).fetchall())

    redundant = []
    for row in candidates:
        if row["id"] in rolled_back_ids:
            continue  # already going, don't report it twice
        norm = normalize_title(row["show"])
        others = db.execute(
            "SELECT id, year, show FROM historical_results "
            " WHERE society_id = ? AND id != ? AND show IS NOT NULL "
            "   AND ABS(year - ?) <= 1",
            (row["society_id"], row["id"], row["year"]),
        ).fetchall()
        matches = [o for o in others if normalize_title(o["show"]) == norm]
        if matches:
            redundant.append((row, matches))

    print(f"\nRedundant bare rows to delete: {len(redundant)}")
    for row, matches in redundant:
        dupes = ", ".join(f"{m['id']}/{m['year']} {m['show']!r}" for m in matches)
        print(f"  del {row['id']:>6} soc={row['society_id']} {row['year']} "
              f"{row['show']!r}  -- duplicates {dupes}")

    # --- apply -------------------------------------------------------------
    all_ids = sorted(rolled_back_ids | {row["id"] for row, _ in redundant})
    db.executemany("DELETE FROM historical_results WHERE id = ?",
                   [(i,) for i in all_ids])

    print(f"\n{len(all_ids)} rows deleted "
          f"({len(rolled_back_ids)} Oyster Lane archive, {len(redundant)} redundant duplicates)")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("Committed.")
    db.close()


if __name__ == "__main__":
    main()
