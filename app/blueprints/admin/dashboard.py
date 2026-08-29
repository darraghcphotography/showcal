from datetime import date, timedelta

from flask import abort, flash, redirect, render_template, request, url_for

from ...auth import login_required
from ...db import get_db
from ...dedupe import find_candidates
from ...venues import dismissed_venue_pairs, merge_candidates
from ...season import current_season, historical_results_year
from . import bp
from ._shared import (
    MISSING_DATES_WHERE,
    MISSING_POSTER_WHERE,
    NEEDS_REVIEW_WHERE,
    missing_poster_params,
    needs_review_params,
)
from .duplicates import TITLE_KEYED_TABLES, move_title_keyed_rows
from .historical_reviews import find_mismatched_skeleton_shows
from .historical_society_links import undecided_name_count


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
    current = current_season(db)

    pending_count = db.execute(
        "SELECT COUNT(*) FROM shows WHERE moderation_status = 'pending'"
    ).fetchone()[0]

    needs_review_count = db.execute(
        f"SELECT COUNT(*) FROM shows WHERE {NEEDS_REVIEW_WHERE}", needs_review_params(db)
    ).fetchone()[0]

    # Shared with the "Fix dates" page this counter links to - see
    # MISSING_DATES_WHERE.
    missing_dates_count = db.execute(
        f"SELECT COUNT(*) FROM shows WHERE {MISSING_DATES_WHERE}"
    ).fetchone()[0]

    # Upcoming only, so this can actually reach zero - see MISSING_POSTER_WHERE.
    missing_poster_count = db.execute(
        f"SELECT COUNT(*) FROM shows WHERE {MISSING_POSTER_WHERE}", missing_poster_params()
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

    # no_region = 1 is a settled answer ("there isn't one"), not an unanswered
    # question - same reason source='historical' is excluded from the counters
    # above. Without it AIMS itself would sit here forever.
    historical_regions_pending_count = db.execute(
        "SELECT COUNT(*) FROM historical_society_regions "
        "WHERE confirmed_region IS NULL AND no_region = 0"
    ).fetchone()[0]

    # Only counts societies a moderator could actually resolve from data on
    # hand (at least one of their own shows has venue text recorded) - see
    # admin.venues, which applies the same has_evidence split. A society with
    # zero venue history isn't a "possible error" waiting to be fixed, it's a
    # permanent gap until it gets more show data, so it's excluded here too
    # rather than inflating this count (and skewing "quick win" below) with
    # entries nothing can clear.
    missing_venue_count = db.execute(
        """
        SELECT COUNT(*) FROM societies s
        WHERE s.section != 'Inactive' AND s.default_venue IS NULL
          AND EXISTS (
            SELECT 1 FROM shows sh
            WHERE sh.society_id = s.id AND sh.venue IS NOT NULL AND sh.venue != ''
          )
        """
    ).fetchone()[0]

    # Venue merge suggestions still awaiting a decision. Counts venues, not
    # pairs, matching what /admin/venue-directory lists. Dismissals are
    # subtracted (see dismissed_venue_pairs) so this can reach zero - the
    # matcher is deliberately loose and proposes real non-matches.
    venue_duplicate_count = len(
        merge_candidates(
            db.execute("SELECT id, name FROM venues").fetchall(),
            dismissed=dismissed_venue_pairs(db),
        )
    )

    duplicate_historical_count = len(_duplicate_historical_rows(db))
    orphaned_info, orphaned_links = _orphaned_titles(db)
    orphaned_titles_count = len({r["show"] for r in orphaned_info} | {r["show"] for r in orphaned_links})

    historical_reviews_pending_count = db.execute(
        "SELECT COUNT(*) FROM historical_reviews WHERE moderation_status = 'pending'"
    ).fetchone()[0]
    mismatched_skeleton_shows_count = len(find_mismatched_skeleton_shows(db))

    photo_submissions_pending_count = db.execute(
        "SELECT COUNT(*) FROM photo_submissions WHERE status = 'pending'"
    ).fetchone()[0]

    logo_candidates_pending_count = db.execute(
        "SELECT COUNT(*) FROM logo_candidates WHERE status = 'pending'"
    ).fetchone()[0]

    # Distinct printed names still awaiting a link decision. Deliberately NOT a
    # replacement for unmatched_award_societies_count below: that's a *row*
    # count which is correctly permanent (most of these societies are defunct
    # and will never match), whereas this one genuinely reaches zero, because
    # "no current society" is a real answer that clears a name. Two counters
    # saying two different true things.
    unlinked_society_names_count = undecided_name_count(db)

    # The most recent season where every show has safely concluded (closed
    # at least 60 days ago, giving adjudication time to happen) - if there's
    # still no historical_results row for its award year, those results
    # probably just haven't been entered yet via /admin/awards.
    cutoff = (date.today() - timedelta(days=60)).isoformat()
    concluded = db.execute(
        """
        SELECT season FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved'
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
            "label": "Photo submissions awaiting moderation",
            "count": photo_submissions_pending_count,
            "url": url_for("admin.photo_submissions_queue"),
        },
        {
            "label": "Logo candidates awaiting approval",
            "count": logo_candidates_pending_count,
            "url": url_for("admin.logo_candidates_queue"),
        },
        {
            "label": "Historical societies with a region awaiting confirmation",
            "count": historical_regions_pending_count,
            "url": url_for("admin.historical_societies"),
        },
        {
            "label": "Award-archive society names awaiting a link decision",
            "count": unlinked_society_names_count,
            "url": url_for("admin.historical_society_links_queue"),
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
        missing_poster_count=missing_poster_count,
        venue_duplicate_count=venue_duplicate_count,
        duplicate_count=duplicate_count,
        unmatched_award_societies_count=unmatched_award_societies_count,
        historical_regions_pending_count=historical_regions_pending_count,
        missing_venue_count=missing_venue_count,
        duplicate_historical_count=duplicate_historical_count,
        orphaned_titles_count=orphaned_titles_count,
        mismatched_skeleton_shows_count=mismatched_skeleton_shows_count,
        awards_pending_season=awards_pending_season,
        historical_reviews_pending_count=historical_reviews_pending_count,
        photo_submissions_pending_count=photo_submissions_pending_count,
        logo_candidates_pending_count=logo_candidates_pending_count,
        unlinked_society_names_count=unlinked_society_names_count,
        quick_win=quick_win,
    )


def _real_titles(db):
    """Every title that actually exists on a production, sorted - the set an
    orphaned row has to be pointed back at. Same union _orphaned_titles checks
    against, so the two can never disagree about what "real" means."""
    return sorted(
        r[0] for r in db.execute(
            "SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' "
            "UNION SELECT show FROM historical_results WHERE show IS NOT NULL"
        ).fetchall()
    )


@bp.route("/data-quality")
@login_required
def data_quality():
    db = get_db()
    orphaned_info, orphaned_links = _orphaned_titles(db)
    return render_template(
        "admin/data_quality.html",
        duplicate_rows=_duplicate_historical_rows(db),
        orphaned_info=orphaned_info,
        orphaned_links=orphaned_links,
        all_titles=_real_titles(db),
    )


@bp.route("/data-quality/orphaned/rename", methods=("POST",))
@login_required
def rename_orphaned_title():
    """Re-point an orphaned show_info/show_links row at a title that really
    exists, which is what the section's own hint text has always promised and
    nothing could actually do: the "Edit" link only edits a row's *contents*
    (it's keyed by the title in the URL, with no rename field), and "Clear"
    only deletes. Fixing a casing drift meant a database shell.

    The target is constrained to a real existing title rather than free text -
    a free-text rename could just as easily create a second orphan, and this
    site's no-fuzzy-matching rule means the match has to be exact to work.
    The datalist on the form only suggests, so it's re-checked here."""
    db = get_db()
    table = request.form.get("table", "")
    old = request.form.get("old", "").strip()
    new = request.form.get("new", "").strip()

    if table not in TITLE_KEYED_TABLES:
        abort(400)
    if not old or not new:
        flash("Pick the title this should point at.", "error")
        return redirect(url_for("admin.data_quality"))
    if new not in _real_titles(db):
        flash(f'"{new}" isn\'t a title on any production - pick one from the list.', "error")
        return redirect(url_for("admin.data_quality"))
    if not db.execute(f"SELECT 1 FROM {table} WHERE show = ?", (old,)).fetchone():
        abort(404)

    # Same drop-vs-carry rule the merge tool uses: `show` is the PRIMARY KEY on
    # both tables, so renaming onto a title that already has a row would be a
    # collision, and in that case the orphan is the redundant one.
    collided = bool(db.execute(f"SELECT 1 FROM {table} WHERE show = ?", (new,)).fetchone())
    move_title_keyed_rows(db, new, old)
    db.commit()
    if collided:
        flash(f'"{new}" already had its own {table.replace("_", " ")} row, so the orphaned '
              f'"{old}" one was removed rather than overwriting it.', "success")
    else:
        flash(f'Re-pointed "{old}" to "{new}" - it renders on that title\'s page now.', "success")
    return redirect(url_for("admin.data_quality"))


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
