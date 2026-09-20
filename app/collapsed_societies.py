"""Award rows filed under a society that did not stage the show.

Two societies were merged into one name before the data reached us, so one
society's record carries another's nominations. `docs/collapsed-societies.md`
has the evidence; this module is the part the app needs: finding the affected
groups, and reading what has already been decided about them.

**The unit is a season and a section**, `(society_id, year, tier)`. A society
competes in one section per season, so when a society's rows appear in both
Gilbert and Sullivan in one year, it is not one stray row that is wrong - it is
the whole of one side, belonging to somebody else.

Nothing here writes. Applying a decision lives in the admin blueprint, behind a
moderator and a confirmation, because reassigning decades-old award records is
the one change this archive must never make on a guess.
"""
from .db import get_db

# Only these two are sections. A historical row can carry tier NULL (before
# AIMS split the sections in 2001) or an empty string, and those are not a side
# of anything - they must never be offered for reassignment on this evidence.
SECTIONS = ("Gilbert", "Sullivan")


def conflicted_societies(db=None):
    """Societies with rows in both sections in the same season.

    This is the detector, and it is a floor rather than a total: it can only
    see a year in which *both* of the collapsed societies were nominated. Where
    only one of them was, there is no conflict to spot and the rows are just as
    misfiled - 2008 is a real example, confirmed against the official list.
    """
    db = db or get_db()
    return db.execute(
        """
        SELECT s.id, s.name,
               COUNT(DISTINCT hr.year) AS conflict_years,
               COUNT(*)                AS award_rows
          FROM historical_results hr
          JOIN societies s ON s.id = hr.society_id
         WHERE hr.tier IN (?, ?)
           AND EXISTS (
                 SELECT 1 FROM historical_results other
                  WHERE other.society_id = hr.society_id
                    AND other.year = hr.year
                    AND other.tier IN (?, ?)
                    AND other.tier <> hr.tier
           )
      GROUP BY s.id, s.name
      ORDER BY award_rows DESC, s.name
        """,
        SECTIONS + SECTIONS,
    ).fetchall()


def societies_in_scope(db=None):
    """Every society the queue should list: still collapsed, or dealt with.

    Not just the conflicted ones. Separating a collapsed society is what makes
    the conflict go away, so a society that has been fixed drops straight out of
    `conflicted_societies` - and with it would go its decisions, its evidence
    and its Undo buttons. The correction would hide itself, which is the same
    failure as a moved season vanishing, one level up.

    So a society stays listed while it has a decision or a suggestion against
    it, however tidy its award rows now look.
    """
    db = db or get_db()
    return db.execute(
        """
        SELECT s.id, s.name,
               COUNT(DISTINCT CASE WHEN hr.id IS NOT NULL THEN hr.year END) AS conflict_years,
               COUNT(hr.id)                                                 AS award_rows
          FROM societies s
          LEFT JOIN historical_results hr
                 ON hr.society_id = s.id
                AND hr.tier IN (?, ?)
                AND EXISTS (
                      SELECT 1 FROM historical_results other
                       WHERE other.society_id = hr.society_id
                         AND other.year = hr.year
                         AND other.tier IN (?, ?)
                         AND other.tier <> hr.tier
                )
         WHERE hr.id IS NOT NULL
            OR EXISTS (SELECT 1 FROM collapsed_society_decisions d WHERE d.society_id = s.id)
            OR EXISTS (SELECT 1 FROM collapsed_society_suggestions g WHERE g.society_id = s.id)
      GROUP BY s.id, s.name
      ORDER BY award_rows DESC, s.name
        """,
        SECTIONS + SECTIONS,
    ).fetchall()


def groups_for(society_id, db=None):
    """Every season-and-section group of one society's award rows.

    All of them, not only the conflicted seasons, because once a society is
    known to be collapsed its single-section years are suspect too - that is
    exactly where 2008 hid. The queue shows which seasons are in conflict and
    which are not; it does not decide for anyone on that basis.

    A group that has already been moved away is included too, with no rows left
    under this society. Without that it would vanish from the page the moment
    the decision was made, taking its Undo button with it - and an
    irreversible-by-accident move is the failure this whole queue exists to
    prevent.
    """
    db = db or get_db()
    return db.execute(
        """
        SELECT hr.year,
               hr.tier,
               COUNT(*) AS row_count,
               GROUP_CONCAT(DISTINCT hr.show) AS shows,
               EXISTS (
                 SELECT 1 FROM historical_results other
                  WHERE other.society_id = hr.society_id
                    AND other.year = hr.year
                    AND other.tier IN (?, ?)
                    AND other.tier <> hr.tier
               ) AS in_conflict
          FROM historical_results hr
         WHERE hr.society_id = ?
           AND hr.tier IN (?, ?)
      GROUP BY hr.year, hr.tier

         UNION

        SELECT d.year, d.tier, 0, NULL, 0
          FROM collapsed_society_decisions d
         WHERE d.society_id = ?
           AND NOT EXISTS (
                 SELECT 1 FROM historical_results hr
                  WHERE hr.society_id = d.society_id
                    AND hr.year = d.year
                    AND hr.tier = d.tier
           )
      ORDER BY 1 DESC, 2
        """,
        SECTIONS + (society_id,) + SECTIONS + (society_id,),
    ).fetchall()


def suggestions_for(society_id, db=None):
    """What the archive proposes, keyed by (year, tier), best first."""
    db = db or get_db()
    rows = db.execute(
        """
        SELECT * FROM collapsed_society_suggestions
         WHERE society_id = ?
      ORDER BY year DESC, tier, confidence DESC, suggested_name
        """,
        (society_id,),
    ).fetchall()
    by_group = {}
    for row in rows:
        by_group.setdefault((row["year"], row["tier"]), []).append(row)
    return by_group


def recurring_names(society_id, db=None):
    """Which other society the archive keeps naming, across how many seasons.

    This is the part that separates a finding from a coincidence, and it is
    worth having on the page rather than only in a script. One page naming
    another society beside one nominee is weak - a person can share a name, and
    a flattened table row sits next to its neighbours. The *same* society
    turning up against seven different seasons of the same collapsed record is
    not something that happens by accident.
    """
    db = db or get_db()
    return db.execute(
        """
        SELECT suggested_name,
               MAX(suggested_id)                  AS suggested_id,
               COUNT(DISTINCT year || '/' || tier) AS seasons,
               SUM(confidence)                    AS votes
          FROM collapsed_society_suggestions
         WHERE society_id = ?
      GROUP BY suggested_name
      ORDER BY seasons DESC, votes DESC, suggested_name
        """,
        (society_id,),
    ).fetchall()


def decisions_for(society_id, db=None):
    """What has already been settled, keyed by (year, tier)."""
    db = db or get_db()
    return {
        (row["year"], row["tier"]): row
        for row in db.execute(
            "SELECT * FROM collapsed_society_decisions WHERE society_id = ?",
            (society_id,),
        ).fetchall()
    }


def undecided_count(db=None):
    """Groups that carry an archive suggestion and no decision yet.

    Deliberately counted from the *suggestions*, not from the conflicts. A
    conflicted season with no evidence behind it is not work anybody can do -
    counting it would put a number on the dashboard that no amount of
    moderating could clear, which is the one thing an admin counter must not
    do. Every row counted here has a source attached and a decision available,
    so this can reach zero.
    """
    db = db or get_db()
    return db.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT DISTINCT s.society_id, s.year, s.tier
              FROM collapsed_society_suggestions s
             WHERE NOT EXISTS (
                   SELECT 1 FROM collapsed_society_decisions d
                    WHERE d.society_id = s.society_id
                      AND d.year = s.year
                      AND d.tier = s.tier
             )
        )
        """
    ).fetchone()[0]
