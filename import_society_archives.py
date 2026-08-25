"""Imports societies' own published production archives
(`enrichment/society_archives_worklist.json`) as bare historical_results rows -
"this happened", no award/category attached, same shape as the Naas and
Tullamore/Castlerea programme backfills.

ONLY the societies whose returned data passed the overlap check are listed in
TRUSTED below. That check is the whole point of how the worklist was built:
each row carried the productions we already hold, and a transcription of those
known years either matches ours or it doesn't.

  * Baldoyle 96%, Limerick 93%, Oyster Lane 9 exact matches including "All 4
    One" (2008), an obscure original show - conclusive evidence of real
    transcription, since those can't be guessed.
  * Carnew scored 0% across 16 overlapping years (every one a different,
    plausible musical) and 9 Arch 25% - both rejected, not imported.
  * 13 of the 19 societies were correctly returned blank as unreachable.

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

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from import_awards import SHOW_RENAMES  # noqa: E402

TRUSTED = {
    "Baldoyle Musical Society",
    "Limerick Musical Society",
    "Oyster Lane Theatre Group",
}

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
            near = db.execute(
                "SELECT year FROM historical_results "
                " WHERE society_id = ? AND show = ? AND ABS(year - ?) <= 1",
                (society["id"], title, year),
            ).fetchone()
            if near:
                print(f"  skip {year} {title!r} - already on record at {near['year']}")
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
