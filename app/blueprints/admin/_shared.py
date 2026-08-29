"""Cross-cutting constants and helpers used by more than one admin submodule.

Kept separate from __init__.py (which only defines the blueprint and wires up
route-registration imports) so every submodule can import from here without
risking a circular import through __init__.py itself.
"""

import re
from datetime import date

from flask import request, url_for

from ...constants import DATE_RE  # noqa: F401 - re-exported for admin submodules
from ...season import current_season

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
# Reads production_id. Nothing to remember any more: a before_request in
# app/__init__.py keeps the derived tables current for every request, so this
# can't read a stale link. That used to be sixteen per-route calls, and a route
# that forgot one didn't error, it silently under-reported.
NEEDS_REVIEW_WHERE = """
    shows.moderation_status = 'approved'
    AND shows.show IS NOT NULL
    AND shows.source != 'historical'
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


# "This show is missing at least one date a moderator could actually go and
# fill in."
#
# Same shape of bug as NEEDS_REVIEW_WHERE above, found the same way: the
# dashboard counter said 30 against real data while the "Fix dates" page it
# links to listed 812, because only the counter excluded source='historical'.
# A skeleton historical row is deliberately minimal (show/society/season/tier
# only) and will never have real dates on record, so it belongs in neither -
# a moderator clicking "30" was meeting 782 rows they could never action.
# Defined once here so the two can't drift apart again.
MISSING_DATES_WHERE = """
    shows.moderation_status = 'approved'
    AND shows.show IS NOT NULL
    AND shows.source != 'historical'
    AND (shows.opening_date IS NULL OR shows.closing_date IS NULL)
"""


# Upcoming shows with no poster uploaded. Deliberately *only* upcoming: a
# poster is promotional material for a run that hasn't happened yet, so a
# 1979 production will never acquire one. Counting all of them would be the
# same trap MISSING_DATES_WHERE describes above, at far bigger scale - only
# 55 of the ~5,000 shows on record have a poster at all, so an unscoped
# counter would read ~5,000 and never move. Scoped this way it means "shows
# still on sale that have nothing to show", and it can reach zero.
#
# Became worth tracking on 2026-08-29, when the homepage moved from 54px
# thumbnails to poster-led cards: a missing poster went from barely visible
# to a large blank card sitting beside real artwork.
MISSING_POSTER_WHERE = """
    shows.moderation_status = 'approved'
    AND shows.show IS NOT NULL
    AND shows.poster_filename IS NULL
    AND shows.opening_date IS NOT NULL
    AND shows.opening_date >= :today
"""


def missing_poster_params():
    return {"today": date.today().isoformat()}


# Admin-only, single-segment allowlist. A "come back where I was" redirect
# that trusted the submitted value outright is an open-redirect hole
# (?next=https://elsewhere), so the form posts an endpoint *name* and this
# resolves it - a value that isn't on the list is ignored rather than
# followed. Lives here rather than in shows.py since 2026-08-29, when
# societies.py needed it too (generating a login code from the missing-poster
# chasing list has to return there, not to the society's public page).
RETURNABLE_ENDPOINTS = {
    "admin.data_quality",
    "admin.duplicate_titles",
    "admin.missing_posters",
    "admin.shows_list",
}


def back_to(default):
    endpoint = request.form.get("next", "")
    return url_for(endpoint) if endpoint in RETURNABLE_ENDPOINTS else default


def needs_review_params(db):
    return {"today": date.today().isoformat(), "current_season": current_season(db)}
