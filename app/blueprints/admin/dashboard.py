from datetime import date, timedelta

from flask import flash, redirect, render_template, url_for

from ... import productions_build
from ...auth import login_required
from ...db import get_db
from ...dedupe import find_candidates
from ...season import current_season, historical_results_year
from . import bp
from ._shared import NEEDS_REVIEW_WHERE, needs_review_params
from .historical_reviews import find_mismatched_skeleton_shows


def _duplicate_historical_rows(db):
    """Bare historical_results rows (no category/result - see
    admin.bulk_historical_productions) that duplicate either a real
    award-archive row or a shows table entry for the same production. See
    find_duplicate_historical_rows.py, which this mirrors - kept as a live
    dashboard check too, not just a one-off script, so a recurrence (a
    future tool bug, a moderator double-pasting a list) surfaces on its own
    rather than needing someone to remember to run the script again.

    Both halves match on production_id now rather than re-deriving "same
    production" per query. The shows half used to compare the show's opening
    *calendar year* against the award year, which is only ever true for a
    spring production and is never true for a skeleton show (no dates at
    all) - so it found 0 duplicates against real data while 9 sat there,
    every one a bulk-added row for a production that already had a shows
    row."""
    return db.execute(
        """
        SELECT h1.id, h1.year, h1.show, h1.society_name
        FROM historical_results h1
        WHERE h1.category_name IS NULL AND h1.result IS NULL
          AND h1.production_id IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM historical_results h2
            WHERE h2.production_id = h1.production_id AND h2.id != h1.id
          )
        UNION
        SELECT h.id, h.year, h.show, h.society_name
        FROM historical_results h
        WHERE h.category_name IS NULL AND h.result IS NULL
          AND h.production_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM shows s WHERE s.production_id = h.production_id)
        ORDER BY society_name, year
        """
    ).fetchall()


def _orphaned_titles(db):
    """show_info/show_links rows whose title has no exact match in
    shows/historical_results - silently invisible everywhere they'd
    normally render (see the "Fiddler On The Roof" casing bug found and
    fixed 2026-08-06). Exact-string match, same as everywhere else on this
    site title-matching is done - a real casing/punctuation drift is
    exactly what this is meant to catch."""
    real_titles = {
        r[0] for r in db.execute(
            "SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' "
            "UNION SELECT show FROM historical_results WHERE show IS NOT NULL"
        ).fetchall()
    }
    orphaned_info = [
        r for r in db.execute("SELECT show, updated_at FROM show_info").fetchall() if r["show"] not in real_titles
    ]
    orphaned_links = [
        r for r in db.execute("SELECT show, url FROM show_links").fetchall() if r["show"] not in real_titles
    ]
    return orphaned_info, orphaned_links


@bp.route("/")
@login_required
def dashboard():
    db = get_db()
    # Several counters below read production_id, so the derived table has to
    # be current with the source tables first (no-op unless something moved).
    productions_build.ensure_current(db)
    current = current_season(db)

    pending_count = db.execute(
        "SELECT COUNT(*) FROM shows WHERE moderation_status = 'pending'"
    ).fetchone()[0]

    needs_review_count = db.execute(
        f"SELECT COUNT(*) FROM shows WHERE {NEEDS_REVIEW_WHERE}", needs_review_params(db)
    ).fetchone()[0]

    # Same reasoning as needs_review_count above - a skeleton show is
    # deliberately minimal (show/society/season/tier only) and will never
    # have real dates on record, so it's excluded rather than sitting in this
    # count forever unfixable.
    missing_dates_count = db.execute(
        """
        SELECT COUNT(*) FROM shows
        WHERE moderation_status = 'approved' AND show IS NOT NULL AND source != 'historical'
          AND (opening_date IS NULL OR closing_date IS NULL)
        """
    ).fetchone()[0]

    titles = {
        r[0] for r in db.execute(
            """
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION
            SELECT show FROM historical_results WHERE show IS NOT NULL
            """
        ).fetchall()
    }
    dismissed = {
        (r[0], r[1]) for r in db.execute("SELECT title_a, title_b FROM dismissed_duplicate_pairs").fetchall()
    }
    duplicate_count = len(find_candidates(titles, dismissed))

    unmatched_award_societies_count = db.execute(
        "SELECT COUNT(*) FROM historical_results WHERE society_name IS NOT NULL AND society_id IS NULL"
    ).fetchone()[0]

    historical_regions_pending_count = db.execute(
        "SELECT COUNT(*) FROM historical_society_regions WHERE confirmed_region IS NULL"
    ).fetchone()[0]

    missing_venue_count = db.execute(
        "SELECT COUNT(*) FROM societies WHERE section != 'Inactive' AND default_venue IS NULL"
    ).fetchone()[0]

    duplicate_historical_count = len(_duplicate_historical_rows(db))
    orphaned_info, orphaned_links = _orphaned_titles(db)
    orphaned_titles_count = len({r["show"] for r in orphaned_info} | {r["show"] for r in orphaned_links})

    historical_reviews_pending_count = db.execute(
        "SELECT COUNT(*) FROM historical_reviews WHERE moderation_status = 'pending'"
    ).fetchone()[0]
    mismatched_skeleton_shows_count = len(find_mismatched_skeleton_shows(db))

    # The most recent season where every show has safely concluded (closed
    # at least 60 days ago, giving adjudication time to happen) - if there's
    # still no historical_results row for its award year, those results
    # probably just haven't been entered yet via /admin/awards.
    cutoff = (date.today() - timedelta(days=60)).isoformat()
    concluded = db.execute(
        """
        SELECT season FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND status IS NOT 'Cancelled'
        GROUP BY season
        HAVING MAX(COALESCE(closing_date, opening_date)) <= ?
        ORDER BY season DESC LIMIT 1
        """,
        (cutoff,),
    ).fetchone()
    awards_pending_season = None
    if concluded:
        # The shared helper, not its own inline copy of the same sum - this is
        # a shows-table season, which is what that helper is safe for.
        award_year = historical_results_year(concluded["season"])
        has_awards = db.execute("SELECT 1 FROM historical_results WHERE year = ?", (award_year,)).fetchone()
        if not has_awards:
            awards_pending_season = concluded["season"]

    # The smallest non-zero, realistically-clearable count on the page - featured
    # up top as a "start here" pick. Excludes unmatched_award_societies_count,
    # which is explicitly a permanent, not-meant-to-reach-zero count (see its
    # own hint below) and would otherwise almost always "win" by being the
    # biggest number, not the quickest one.
    quick_win_candidates = [
        {"label": "Pending submissions", "count": pending_count, "url": url_for("admin.queue")},
        {
            "label": "Historical reviews awaiting moderation",
            "count": historical_reviews_pending_count,
            "url": url_for("admin.historical_reviews_queue"),
        },
        {
            "label": "Historical societies with a region awaiting confirmation",
            "count": historical_regions_pending_count,
            "url": url_for("admin.historical_societies"),
        },
        {
            "label": "Shows missing a date",
            "count": missing_dates_count,
            "url": url_for("admin.fix_dates", missing=1),
        },
        {
            "label": "Active societies missing a default venue",
            "count": missing_venue_count,
            "url": url_for("admin.venues"),
        },
        {
            "label": "Shows missing a review link",
            "count": needs_review_count,
            "url": url_for("admin.shows_list", needs_review=1),
        },
        {"label": "Possible duplicate titles", "count": duplicate_count, "url": url_for("admin.duplicate_titles")},
        {
            "label": "Duplicate historical productions",
            "count": duplicate_historical_count,
            "url": url_for("admin.data_quality"),
        },
        {"label": "Orphaned title data", "count": orphaned_titles_count, "url": url_for("admin.data_quality")},
        {
            "label": "Skeleton shows whose title doesn't line up with the awards archive",
            "count": mismatched_skeleton_shows_count,
            "url": url_for("admin.historical_shows_title_check"),
        },
    ]
    quick_win = min(
        (c for c in quick_win_candidates if c["count"]), key=lambda c: c["count"], default=None
    )

    return render_template(
        "admin/dashboard.html",
        pending_count=pending_count,
        needs_review_count=needs_review_count,
        missing_dates_count=missing_dates_count,
        duplicate_count=duplicate_count,
        unmatched_award_societies_count=unmatched_award_societies_count,
        historical_regions_pending_count=historical_regions_pending_count,
        missing_venue_count=missing_venue_count,
        duplicate_historical_count=duplicate_historical_count,
        orphaned_titles_count=orphaned_titles_count,
        mismatched_skeleton_shows_count=mismatched_skeleton_shows_count,
        awards_pending_season=awards_pending_season,
        historical_reviews_pending_count=historical_reviews_pending_count,
        quick_win=quick_win,
    )


@bp.route("/data-quality")
@login_required
def data_quality():
    db = get_db()
    # _duplicate_historical_rows reads production_id (see its docstring), so
    # the derived table has to be current first.
    productions_build.ensure_current(db)
    orphaned_info, orphaned_links = _orphaned_titles(db)
    return render_template(
        "admin/data_quality.html",
        duplicate_rows=_duplicate_historical_rows(db),
        orphaned_info=orphaned_info,
        orphaned_links=orphaned_links,
    )


@bp.route("/data-quality/historical/<int:row_id>/delete", methods=("POST",))
@login_required
def delete_duplicate_historical_row(row_id):
    db = get_db()
    db.execute("DELETE FROM historical_results WHERE id = ?", (row_id,))
    db.commit()
    flash("Duplicate row deleted.", "success")
    return redirect(url_for("admin.data_quality"))


@bp.route("/traffic")
@login_required
def traffic():
    db = get_db()
    total_views = db.execute("SELECT COALESCE(SUM(views), 0) FROM page_views").fetchone()[0]
    pages = db.execute(
        "SELECT path, views, last_viewed FROM page_views ORDER BY views DESC LIMIT 30"
    ).fetchall()
    return render_template("admin/traffic.html", total_views=total_views, pages=pages)
