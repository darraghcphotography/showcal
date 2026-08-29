"""One-off backfill: give every award-only production of the `shows` era a
skeleton `shows` row, so it appears in its society's own Show history.

THE GAP. A production that exists only as award records in
`historical_results` has no `shows` row. The society page's "Show history"
table reads `shows`, so that production is invisible there - it sits in the
lower "other productions" list instead. Maynooth's PRO hit exactly this with
Into the Woods 22/23, and the self-service form then refused the submission
that would have closed the gap (fixed separately in `app/similarity.py`).

THE RULE. A nomination is proof the production really happened, so a
nominated production belongs in its society's history at any year. That is
Darragh's call on 2026-08-28, and it replaces the year cut-off the plan
originally proposed (>= 2006). The cut-off was arguing about presentation;
this argues about what is true, which is the better rule.

It also makes the society page's two sections mean something clean:

  * "Show history" - productions we hold a real record of, whether member
    submitted, imported, or nominated for an award.
  * "Also on record (awards archive)" - productions we only know happened.

The second section's own wording already promises exactly that split ("most
never won or were nominated for anything, which is normal"). It cannot honour
that while nominated productions are still sitting inside it.

A production whose award rows all have a NULL category is NOT backfilled.
Those are bulk "this production happened" entries rather than nominations,
and the archive section is the right home for them.

Season comes from the award year, which is the season's *ending* year -
2023 -> '22/23', matching Maynooth. `region` comes from the society,
`section` from the award record's `tier`.

These rows carry `source='historical'`, the same skeleton pattern
`app/blueprints/admin/historical_reviews.py` already uses when a moderator
approves a review with no show to attach to. That tag is what keeps them out
of the stats and leaderboard queries, so nothing double-counts.

Two properties were verified before writing this, and both still hold:

  * No double display. `historical_timeline` (app/blueprints/public.py)
    already excludes any production that has an approved `shows` row, so
    these productions MOVE from "other productions" up into Show history
    rather than appearing in both.
  * No admin counter noise. `app/blueprints/admin/_shared.py` already
    excludes `source='historical'` from the "missing a review link" counts.

The rows render with "Not recorded" dates, because award data holds no dates.
That is expected, and the existing past-season wording already handles it.

Safe to re-run: every insert is guarded against the `ux_shows_natural_key`
unique index (society, season, title, NOCASE), so a second run inserts
nothing.

Usage:
    py backfill_award_only_productions.py [--db aims.db] [--dry-run]

    docker exec aims-web python backfill_award_only_productions.py \
        --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
import sys
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def season_for(year):
    """Award year is the season's ending year: 2023 -> '22/23'."""
    return f"{(year - 1) % 100:02d}/{year % 100:02d}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    # One row per production that was nominated for something but has no
    # approved `shows` row. Grouped by production_id so a production with six
    # award records produces one skeleton, not six. `tier` and `show` are
    # taken with MIN() only to pick a single representative value - they are
    # identical across a production's own award rows.
    #
    # The JOIN to societies is doing real work beyond fetching `region`: it
    # drops productions whose society_id points at nothing. Those are the
    # printed historical names still awaiting a decision at
    # /admin/historical-society-links, and clearing that queue makes several
    # hundred more productions eligible on a re-run.
    candidates = db.execute(
        """
        SELECT h.production_id,
               h.society_id,
               MIN(h.year)  AS year,
               MIN(h.show)  AS show,
               MIN(h.tier)  AS tier,
               s.region     AS region
        FROM historical_results h
        JOIN societies s ON s.id = h.society_id
        WHERE h.show IS NOT NULL
          AND h.production_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM historical_results x
                       WHERE x.production_id = h.production_id
                         AND x.category_name IS NOT NULL)
          AND NOT EXISTS (SELECT 1 FROM shows
                           WHERE shows.production_id = h.production_id
                             AND shows.moderation_status = 'approved')
        GROUP BY h.production_id
        ORDER BY h.society_id, year, show
        """,
    ).fetchall()

    print(f"Nominated productions with no show page: {len(candidates)}")

    inserted = 0
    skipped = []
    for row in candidates:
        season = season_for(row["year"])
        # The unique index is (society_id, season, COALESCE(show,'') NOCASE).
        # A row can already occupy that key without being linked to this
        # production - an unapproved submission, or a title variant the
        # productions rebuild grouped differently. Insert would fail on it.
        clash = db.execute(
            "SELECT id, moderation_status, source FROM shows "
            " WHERE society_id = ? AND season = ? AND show = ? COLLATE NOCASE",
            (row["society_id"], season, row["show"]),
        ).fetchone()
        if clash is not None:
            skipped.append((row, clash))
            continue

        db.execute(
            """
            INSERT INTO shows (society_id, season, region, section, show,
                               production_id, source, moderation_status)
            VALUES (?, ?, ?, ?, ?, ?, 'historical', 'approved')
            """,
            (row["society_id"], season, row["region"], row["tier"], row["show"],
             row["production_id"]),
        )
        inserted += 1

    print(f"  inserted {inserted} skeleton rows")
    if skipped:
        print(f"  skipped {len(skipped)} - the natural key is already taken:")
        for row, clash in skipped:
            print(f"    soc={row['society_id']:>4} {season_for(row['year'])} {row['show']!r}"
                  f"  -- shows.id {clash['id']} ({clash['source']}/{clash['moderation_status']})")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("Committed.")
    db.close()


if __name__ == "__main__":
    main()
