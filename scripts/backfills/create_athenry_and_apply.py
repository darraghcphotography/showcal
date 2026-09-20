"""Create Athenry Musical Society and move its award records back to it.

Jack Rawlings reported on 2026-09-17 that Athenry Musical Society is missing
from the site and its awards show under Athlone. He was right.
`docs/collapsed-societies.md` holds the full evidence; this script is the part
that acts on it, once, against a real database.

**Why a script rather than the queue page.** The queue at
`/admin/collapsed-societies` is the normal way to do this and it stays the
normal way. Two of these seven seasons cannot be done there yet: 2003 has no
machine-matched suggestion (the show is printed as *Sugar* where we hold *Some
Like It Hot* - the same musical under its other title, which no string match
will join), and 2008 is not a conflicted season at all, because only one of the
two societies was nominated that year. Both are sourced by reading the official
page. So this does the whole set in one pass, in the same shape the page would.

It writes the same `collapsed_society_decisions` rows the page writes, with the
source on every one, so **every move here is undoable from that page** by
whoever comes after. Nothing here is a special case that the UI cannot see.

    py scripts/backfills/create_athenry_and_apply.py --db /data/aims.db --dry-run
    py scripts/backfills/create_athenry_and_apply.py --db /data/aims.db

Take a backup first. `backup_db.py` is right there.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOCIETY_NAME = "Athenry Musical Society"
FROM_SOCIETY = "Athlone Musical Society"

# Everything known about the society, and where it is known from. Athenry is
# not a current AIMS member - it is absent from the Western region list on
# aims.ie - so it goes in as Inactive rather than as a live society.
SOCIETY = {
    "name": SOCIETY_NAME,
    "region": "Western",
    "section": "Inactive",
    "founded_year": 1999,
    "notes": (
        "Founded 21 April 1999 as Athenry Millennium Musical Society; first production "
        "Fiddler on the Roof, Presentation College Gymnasium, 3-5 March 2000 (athenry.org). "
        "Competed in the AIMS Sullivan section in 2001 and in Gilbert by 2010 "
        "(AIMS adjudication rosters, via the Internet Archive). Not a current AIMS "
        "member: absent from the Western region list on aims.ie, checked 2026-09-20. "
        "Its AIMS award records had been filed under Athlone Musical Society in the "
        "source data, and were restored to Athenry in September 2026 from the official "
        "AIMS nominations lists of the time."
    ),
}

# One entry per season and section, with the page that settles it. Every one of
# these was read off the official AIMS list, not inferred from the tier test.
SEASONS = [
    (2001, "Sullivan",
     "Official AIMS 2000/2001 nominations: Best Director (Sullivan, Tommy Ebbs Trophy) "
     "- Paula Short, Anything Goes, Athenry Musical Society.",
     "http://www.aims.ie/seminarnominations.htm", "20010720034012"),
    (2003, "Sullivan",
     "Official AIMS 2003 Sullivan results: Best Stage Manager - Athenry Musical Society, "
     "Brian Brady, Sugar; Best Comedian - Athenry Musical Society, Peter Kennedy, Jerry, "
     "Sugar. We hold both against Some Like It Hot, the same musical under its other title.",
     "http://aims.ie/awards/nominations_results_sullivan.asp", "20030610230645"),
    (2004, "Sullivan",
     "Official AIMS 2004 nominations: Best Stage Manager - Brian Brady, My Fair Lady, "
     "Athenry Musical Society. Corroborated by athenry.org, which records My Fair Lady "
     "as the society's fifth-anniversary production.",
     "http://aims.ie/awards/2004/noms2004.pdf", "20040623091916"),
    (2005, "Sullivan",
     "Official AIMS 2005 Sullivan nominations: Best Male Singer - Pat Naughton as Emile "
     "de Becque, South Pacific, and Best House Management, South Pacific - both Athenry.",
     "http://aims.ie/awards/nominations_sullivan.asp", "20051217093038"),
    (2006, "Sullivan",
     "Official AIMS 2006 Sullivan nominations: Cathriona O'Connell as Lady Jaqueline, "
     "Me & My Girl, Athenry Musical Society.",
     "http://www.aims.ie/awards/nominations_sullivan.asp", "20060618164831"),
    (2007, "Sullivan",
     "Official AIMS 2007 Sullivan nominations: Best Comedienne - Marilyn Bane as Adelaide, "
     "Guys and Dolls, Athenry Musical Society.",
     "http://www.aims.ie/awards/nominations_sullivan.asp", "20070615072541"),
    (2008, "Sullivan",
     "Official AIMS 2008 Sullivan nominations: exactly two Athenry entries - Best Chorus "
     "and Best Visual, both Pirates of Penzance - matching the two rows we hold. The word "
     "Athlone does not appear on that page. This season is not flagged by the two-tier "
     "test, because only one of the two societies was nominated.",
     "http://www.aims.ie/awards/nominations_sullivan.asp", "20090225182638"),
]

DECIDED_BY = "claude (sourced from the AIMS archive)"


def ensure_society(db, dry_run, log=print):
    row = db.execute("SELECT id, name FROM societies WHERE name = ?", (SOCIETY_NAME,)).fetchone()
    if row:
        log("{} already exists (id {}).".format(row["name"], row["id"]))
        return row["id"]
    log("CREATE society {!r}: {} / {} / founded {}".format(
        SOCIETY_NAME, SOCIETY["region"], SOCIETY["section"], SOCIETY["founded_year"]))
    if dry_run:
        return None
    return db.execute(
        """
        INSERT INTO societies (name, region, section, founded_year, notes)
        VALUES (:name, :region, :section, :founded_year, :notes)
        RETURNING id
        """, SOCIETY).fetchone()["id"]


def season_label(year):
    """AIMS award year 2005 is the 04/05 season."""
    return "{:02d}/{:02d}".format((year - 1) % 100, year % 100)


def move_show_row(db, from_id, to_id, year, show, region, dry_run, log=print):
    """Move the production row that goes with a moved award season.

    The collapse is not only in `historical_results`. `shows` carries a
    `source='historical'` row per awarded production, derived from the same
    data, so it inherits the same error - Athlone shows two productions in
    exactly the disputed seasons, one of them Athenry's. Moving the award
    records alone would leave Athenry's shows still listed on Athlone's page,
    which is the half-fix a visitor would actually notice.

    Scoped to `source='historical'`: a member-submitted row is somebody's own
    entry about their own society and is never touched by this.
    """
    season = season_label(year)
    rows = db.execute(
        "SELECT id, show FROM shows WHERE society_id = ? AND season = ? AND show = ? "
        "AND source = 'historical'",
        (from_id, season, show)).fetchall()
    if not rows:
        log("      (no historical shows row for {} {})".format(season, show))
        return 0
    if not dry_run:
        db.execute(
            "UPDATE shows SET society_id = ?, region = ? WHERE id IN ({})".format(
                ",".join("?" * len(rows))),
            [to_id, region] + [r["id"] for r in rows])
    log("      + production row: {} {}".format(season, show))
    return len(rows)


def apply_season(db, from_id, to_id, year, tier, note, url, capture, dry_run, log=print):
    rows = db.execute(
        """
        SELECT id, category_name, result, show, nominee_name
          FROM historical_results
         WHERE society_id = ? AND year = ? AND tier = ?
      ORDER BY category_name
        """, (from_id, year, tier)).fetchall()
    if not rows:
        log("  {} {}: nothing to move (already moved, or never there)".format(year, tier))
        return 0

    log("  {} {}: {} record(s)".format(year, tier, len(rows)))
    for row in rows:
        log("      {} - {}{}".format(
            row["category_name"], row["show"] or "?",
            " - " + row["nominee_name"] if row["nominee_name"] else ""))

    shows = {row["show"] for row in rows if row["show"]}
    for show in sorted(shows):
        move_show_row(db, from_id, to_id, year, show, SOCIETY["region"], dry_run, log)
    if dry_run:
        return len(rows)

    db.execute(
        "UPDATE historical_results SET society_id = ?, society_name = ? "
        "WHERE society_id = ? AND year = ? AND tier = ?",
        (to_id, SOCIETY_NAME, from_id, year, tier))
    # The same row the queue page writes, so Undo works there afterwards. The
    # citation travels with the decision rather than living only in a commit
    # message nobody will be reading in five years.
    db.execute(
        """
        INSERT INTO collapsed_society_decisions
               (society_id, year, tier, moved_to_id, no_change, previous_name,
                note, decided_by, updated_at)
        VALUES (?, ?, ?, ?, 0, ?, ?, ?, datetime('now'))
        ON CONFLICT(society_id, year, tier) DO UPDATE SET
               moved_to_id = excluded.moved_to_id, no_change = 0,
               previous_name = excluded.previous_name, note = excluded.note,
               decided_by = excluded.decided_by, updated_at = excluded.updated_at
        """,
        (from_id, year, tier, to_id, FROM_SOCIETY,
         "{} [source: {} captured {}]".format(note, url, capture), DECIDED_BY))
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    athlone = db.execute("SELECT id FROM societies WHERE name = ?", (FROM_SOCIETY,)).fetchone()
    if athlone is None:
        print("No society named {!r} in this database.".format(FROM_SOCIETY))
        return 2

    athenry_id = ensure_society(db, args.dry_run)
    print()
    moved = 0
    for year, tier, note, url, capture in SEASONS:
        moved += apply_season(db, athlone["id"], athenry_id, year, tier,
                              note, url, capture, args.dry_run)

    if args.dry_run:
        print("\nDry run - nothing written. {} record(s) would move.".format(moved))
        return 0

    # An in-place UPDATE moves neither COUNT(*) nor MAX(id), which is all the
    # productions fingerprint looks at - so the derived table would never notice
    # this on its own. Same reason the queue page marks stale after a move.
    db.execute("DELETE FROM productions_build_state")
    db.commit()
    print("\n{} record(s) moved to {}. Every season is undoable from "
          "/admin/collapsed-societies.".format(moved, SOCIETY_NAME))
    return 0


if __name__ == "__main__":
    sys.exit(main())
