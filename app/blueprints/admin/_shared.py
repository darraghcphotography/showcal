"""Cross-cutting constants and helpers used by more than one admin submodule.

Kept separate from __init__.py (which only defines the blueprint and wires up
route-registration imports) so every submodule can import from here without
risking a circular import through __init__.py itself.
"""

import re
from datetime import date

from ...season import current_season

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://")


# "This production has run, nobody has written it up anywhere, and it isn't
# marked as deliberately un-adjudicated" - i.e. a review link a moderator can
# actually go and add.
#
# Three places asked this separately and disagreed: the dashboard counter and
# the shows-list filter behind it both said 115 against real data, while the
# Reviews queue tool said 29. The queue was the right one - the other two were
# season-based, so they counted 86 shows that hadn't happened yet. Defined once
# here, on the queue's terms, so all three agree and can't drift again.
#
# The review check goes through production_id rather than show_id. That's the
# same set today (a production only ever has one shows row, which the rebuild's
# own verification enforces) - it's written this way because "has this
# production been reviewed" is the question actually being asked, and it stays
# right if that ever stops being one row.
#
# Takes named params :today and :current_season. A show with no dates at all
# counts as run only once its season is over - an announced-but-undated show in
# the current season hasn't happened, but an undated one from 10/11 certainly
# has, and dropping it would hide real work rather than noise.
#
# Reads production_id, so any route using it must call
# productions_build.ensure_current(db) first (dashboard, shows_list,
# reviews_queue all do) - otherwise it reads a stale link and silently
# under-reports.
NEEDS_REVIEW_WHERE = """
    shows.moderation_status = 'approved'
    AND shows.show IS NOT NULL
    AND shows.source != 'historical'
    AND shows.status IS NOT 'Cancelled'
    AND shows.review_status != 'Not adjudicated'
    AND (shows.review_url IS NULL OR shows.review_url = '')
    AND (COALESCE(shows.closing_date, shows.opening_date) <= :today
         OR (COALESCE(shows.closing_date, shows.opening_date) IS NULL
             AND shows.season < :current_season))
    AND NOT EXISTS (
        SELECT 1 FROM historical_reviews
        WHERE historical_reviews.production_id = shows.production_id
          AND historical_reviews.moderation_status = 'approved'
    )
"""


def needs_review_params(db):
    return {"today": date.today().isoformat(), "current_season": current_season(db)}
