"""Fills in `societies.lifecycle_status` for every society nobody has judged yet.

The lifecycle field shipped with the coverage checklist and then sat unused -
all 194 societies were NULL, so `/admin/society-checklist` treated a panto
company that has never appeared in a single result exactly like Kilkenny, who
open in five weeks. That makes the chasing list longer than the real job and is
the fastest way to stop anyone using it.

**These are guesses, not research.** Every value here is derived from one thing:
the most recent year we have any record of that society producing anything -
a show, an award result, or a ShowTimes review. A moderator's own decision
always wins: this only ever fills a NULL, so re-running it never overwrites a
human answer, and any row it gets wrong can be corrected in one click on the
checklist.

The thresholds, and why they sit where they do:

  * **Active** - has an upcoming production, or last produced in 2023 or later.
    Three seasons is inside the window where a society simply hasn't announced
    yet, and a wrong "Active" costs one wasted email, where a wrong "Closed"
    quietly drops a living society off the list. When the two errors are that
    lopsided, the threshold belongs on the generous side.
  * **Dormant** - last produced 2018-2022. Covid sits inside this window, so a
    society silent since 2019 may well have been killed by it or may be about
    to come back; either way it is worth a look and not worth an assumption.
  * **Closed** - last produced 2017 or earlier, i.e. at least eight years of
    silence in a record that covers them. Amateur societies that stop for that
    long do not restart. This is the only bucket that removes a society from the
    chase counter on the strength of a guess, which is why the line is drawn
    conservatively - it is 10 societies, few enough to eyeball.
  * **Out of scope** - nothing on record at all AND already marked section
    'Inactive'. These are the panto companies, youth theatres, school societies
    and choirs on the list: not AIMS musical societies whose productions we
    track, and never were.
  * **Unverified** - nothing on record at all, but they ARE in a current AIMS
    tier (Gilbert/Sullivan). In scope by definition, yet invisible in our data,
    which is a real question rather than an answer. Left chaseable on purpose.

Usage:
    py scripts/backfills/guess_society_lifecycle.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python scripts/backfills/guess_society_lifecycle.py \n        --db /data/aims.db

(the full path matters in the container - the image keeps this under
scripts/backfills/, and ROOT below is computed from that depth)
"""
import argparse
import sqlite3
from collections import Counter
from pathlib import Path

# Repo root is two levels up since the one-off scripts moved into
# scripts/<group>/ (2026-08-29).
ROOT = Path(__file__).resolve().parents[2]

ACTIVE_SINCE = 2023    # produced this recently -> still going
DORMANT_SINCE = 2018   # produced between here and ACTIVE_SINCE -> quiet, not gone


def season_year(season):
    """The calendar year a '25/26'-style season ends in, or None."""
    if not season or "/" not in season:
        return None
    try:
        return 2000 + int(season.split("/")[1])
    except ValueError:
        return None


def classify(has_upcoming, last_year, section):
    """(status, why) for one society, or (None, why) when we shouldn't guess.

    Kept pure and separate from the database so the thresholds above can be
    tested directly - see tests/test_society_lifecycle_guess.py.
    """
    if has_upcoming:
        return "Active", "has an upcoming production"
    if last_year:
        if last_year >= ACTIVE_SINCE:
            return "Active", f"last produced {last_year}"
        if last_year >= DORMANT_SINCE:
            return "Dormant", f"last produced {last_year}, nothing since"
        return "Closed", f"last produced {last_year}, silent ever since"
    if section == "Inactive":
        return "Out of scope", "nothing on record, and not in an AIMS tier"
    return "Unverified", f"nothing on record, but listed in the {section} tier"


def latest_activity(db):
    """{society_id: last year we have any record of them producing anything}."""
    last = {}

    def note(society_id, year):
        if society_id and year:
            last[society_id] = max(last.get(society_id, 0), int(year))

    for r in db.execute(
        "SELECT society_id, season FROM shows WHERE moderation_status = 'approved'"
    ):
        note(r["society_id"], season_year(r["season"]))
    for r in db.execute(
        "SELECT society_id, year FROM historical_results WHERE society_id IS NOT NULL"
    ):
        note(r["society_id"], r["year"])
    for r in db.execute(
        "SELECT society_id, season FROM historical_reviews WHERE society_id IS NOT NULL"
    ):
        note(r["society_id"], season_year(r["season"]))
    return last


def societies_with_upcoming(db):
    return {
        r["society_id"]
        for r in db.execute(
            """SELECT DISTINCT society_id FROM shows
                WHERE moderation_status = 'approved'
                  AND COALESCE(opening_date, adjudication_date) >= date('now')"""
        )
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    last = latest_activity(db)
    upcoming = societies_with_upcoming(db)
    tally, skipped = Counter(), 0

    for s in db.execute("SELECT id, name, section, lifecycle_status FROM societies ORDER BY name"):
        if s["lifecycle_status"]:
            skipped += 1
            continue

        status, why = classify(s["id"] in upcoming, last.get(s["id"]), s["section"])
        if status is None:
            continue

        db.execute("UPDATE societies SET lifecycle_status = ? WHERE id = ?", (status, s["id"]))
        tally[status] += 1
        # Only print the judgement calls - 140-odd "Active, has an upcoming
        # production" lines bury the ten rows actually worth reading.
        if status != "Active":
            print(f"  {status:13} {s['name']}  ({why})")

    print()
    for status, n in tally.most_common():
        print(f"  {n:4} {status}")
    print(f"  {skipped:4} left alone (already decided by a moderator)")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nWritten. Any row is one click to correct on /admin/society-checklist.")
    db.close()


if __name__ == "__main__":
    main()
