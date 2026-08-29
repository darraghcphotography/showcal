"""Imports societies' own published production archives
(`enrichment/society_archives_worklist.json`) as bare historical_results rows -
"this happened", no award/category attached, same shape as the Naas and
Tullamore/Castlerea programme backfills.

*** READ THIS BEFORE TRUSTING ANY SOCIETY HERE (added 2026-08-28) ***

The overlap check below is NOT sufficient on its own, and Oyster Lane proved
it. The check validates a transcription against years we ALREADY HOLD award
data for - which is precisely the set of years the import is not adding
anything for. Every row that actually contributes new information is, by
definition, in a year we had nothing to compare against, so it is never
checked. A society reported wrong entries in its own history (2026-08-27);
both bad rows were in that blind spot, and all 18 Oyster Lane rows were
rolled back (`rollback_oyster_lane_archive.py`).

A score below the 93-100% the other societies reached is also a signal in its
own right: Oyster Lane scored 69% (9/13) and was left in TRUSTED anyway.

ONLY the societies whose returned data passed the overlap check are listed in
TRUSTED below. That check is the whole point of how the worklist was built:
each row carried the productions we already hold, and a transcription of those
known years either matches ours or it doesn't.

  * Baldoyle 96%, Limerick 93% - strong.
  * Oyster Lane 69% (9/13), including "All 4 One" (2008), an obscure original
    show that can't be guessed - which is why it was trusted at the time. That
    reasoning was wrong: real transcription of the checkable years does not
    make the uncheckable years right. REJECTED 2026-08-28, rows deleted.
  * Carnew scored 0% across 16 overlapping years (every one a different,
    plausible musical) and 9 Arch 25% - both rejected, not imported.
  * 13 of the 19 societies were correctly returned blank as unreachable.

Round 2 (2026-08-25, after a redo of the 14 originally-blank rows with a
firmer "no bare unreachable" instruction):

  * Killarney 100% (7/7) and Castlebar 100% (5/5) - clean, added to TRUSTED.
  * Harolds Cross Tallaght 0% (0/5) and Muse Productions 0% (0/3) - same red
    flag as Carnew, rejected.
  * Fortwilliam 55% (17/31) and Glencullen 47% (8/17) - too mixed to trust,
    rejected.
  * Kilmacud, Boyle and Waterford returned real transcriptions but share zero
    overlapping years with anything already on record, so the cross-check
    has nothing to test them against - genuinely unverifiable by this method,
    not the same as passing. Not imported; would need a different check.

Two corrections applied to incoming titles/years:

  * SHOW_RENAMES from import_awards.py, so a title lands in the same canonical
    spelling the rest of the archive uses ("Michael Collins" -> "Michael
    Collins - A Musical Drama", "The Boyfriend" -> "The Boy Friend").
  * A +/-1 year duplicate guard. A society's own site dates a production by
    calendar year; AIMS's award year is the season's *ending* year, so the two
    disagree by one for autumn productions. Oyster Lane's recent entries are
    shifted exactly that way. Skipping a title we already hold within a year of
    the claimed date avoids re-inserting the same production under a second
    date - the same drift already seen in the Naas backfill.

Usage:
    py import_society_archives.py [--db aims.db] [--json enrichment/society_archives_worklist.json] [--dry-run]

    docker compose exec aims-web python import_society_archives.py --db /data/aims.db --json /data/society_archives_worklist.json
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from import_awards import SHOW_RENAMES  # noqa: E402
from app.similarity import normalize_title  # noqa: E402

TRUSTED = {
    "Baldoyle Musical Society",
    "Limerick Musical Society",
    "Killarney Musical Society",
    "Castlebar Musical & Dramatic Society",
}

# Oyster Lane Theatre Group was in TRUSTED and was REMOVED on 2026-08-28 after
# the society reported wrong entries in its own history. Its 18 imported rows
# were rolled back (`rollback_oyster_lane_archive.py`). Do not re-add it without
# a check that can actually test the rows being added - see the warning above
# about what the overlap check cannot see.

REASON = "From the society's own published production archive (2026-08-25)"


def canonical(title):
    title = (title or "").strip()
    return SHOW_RENAMES.get(title, title)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--json", default=str(ROOT / "enrichment" / "society_archives_worklist.json"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    rows = json.loads(Path(args.json).read_text(encoding="utf-8"))
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    inserted, skipped_dupe, skipped_untrusted = 0, 0, 0

    for entry in rows:
        name = entry["society"]
        if name not in TRUSTED:
            skipped_untrusted += 1
            continue
        society = db.execute("SELECT id, name FROM societies WHERE name = ?", (name,)).fetchone()
        if society is None:
            print(f"  NO SUCH SOCIETY: {name!r}")
            continue

        print(f"\n{name}")
        for production in sorted(entry.get("productions") or [], key=lambda p: p.get("year") or 0):
            year, title = production.get("year"), canonical(production.get("title"))
            if not year or not title:
                continue

            # Same title already on record within a year either way - either the
            # exact row, or the same production dated by the other convention.
            #
            # Compared on normalize_title, not the raw string. An exact `show = ?`
            # let case/punctuation variants straight past this guard and created
            # redundant bare rows next to the award record they duplicated
            # ("The Pirates of Penzance" vs "The Pirates Of Penzance", Limerick
            # 2011; found and cleaned up 2026-08-28). Normalisation only, never
            # fuzzy - the same distinction already settled for match_show_for_edit.
            near = None
            for row in db.execute(
                "SELECT year, show FROM historical_results "
                " WHERE society_id = ? AND show IS NOT NULL AND ABS(year - ?) <= 1",
                (society["id"], year),
            ):
                if normalize_title(row["show"]) == normalize_title(title):
                    near = row
                    break
            if near:
                print(f"  skip {year} {title!r} - already on record at {near['year']} as {near['show']!r}")
                skipped_dupe += 1
                continue

            db.execute(
                "INSERT INTO historical_results (year, show, society_name, society_id, reason, source) "
                "VALUES (?, ?, ?, ?, ?, 'manual')",
                (year, title, society["name"], society["id"], REASON),
            )
            print(f"  add  {year} {title!r}")
            inserted += 1

    print(f"\n{inserted} added, {skipped_dupe} already on record, "
          f"{skipped_untrusted} societies not in TRUSTED (not imported)")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
