from datetime import date, timedelta
from urllib.parse import quote_plus

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for

from .. import notify
from ..auth import current_user
from ..calendar_links import google_calendar_url
from ..constants import REGIONS, SHOWS_COVERAGE_START_YEAR, SOCIETY_SECTIONS, SUGGESTION_CATEGORIES
from ..db import get_db
from ..rate_limit import limiter
from ..search import fts_match_ids
from ..season import current_season
from ..shows import is_upcoming as _is_upcoming

bp = Blueprint("public", __name__)

UPCOMING_LIMIT = 6
CHANGELOG_TEASER_LIMIT = 3


@bp.route("/")
def index():
    db = get_db()

    upcoming_region = request.args.get("upcoming_region", "")
    upcoming_query = """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved'
          AND shows.show IS NOT NULL
          AND shows.opening_date >= ?
          AND shows.status IS NOT 'Cancelled'
          AND NOT societies.hidden
    """
    upcoming_params = [date.today().isoformat()]
    if upcoming_region in REGIONS:
        upcoming_query += " AND shows.region = ?"
        upcoming_params.append(upcoming_region)
    upcoming_query += " ORDER BY shows.opening_date LIMIT ?"
    upcoming_params.append(UPCOMING_LIMIT)
    upcoming = db.execute(upcoming_query, upcoming_params).fetchall()

    # Whichever of the upcoming shows above happen to have a poster - same
    # list, same region filter, same order, not a separate query. Keeps the
    # gallery honest: it can never show a show that isn't actually in the
    # "Upcoming shows" table right below it.
    poster_gallery = [show for show in upcoming if show["poster_filename"]]

    changelog_teaser = db.execute(
        "SELECT entry, date(created_at) AS entry_date FROM changelog_entries ORDER BY created_at DESC LIMIT ?",
        (CHANGELOG_TEASER_LIMIT,),
    ).fetchall()

    return render_template(
        "index.html",
        upcoming=upcoming,
        poster_gallery=poster_gallery,
        regions=REGIONS,
        upcoming_region=upcoming_region,
        changelog_teaser=changelog_teaser,
    )


@bp.route("/societies")
def societies_list():
    region = request.args.get("region", "")
    section = request.args.get("section", "")
    q = request.args.get("q", "").strip()
    # Only a logged-in moderator/admin can even ask to see inactive societies -
    # anonymous visitors always get the filtered default.
    show_inactive = request.args.get("show_inactive") == "1" and current_user() is not None

    db = get_db()

    query = "SELECT * FROM societies WHERE 1=1"
    params = []
    if not show_inactive:
        query += " AND section != 'Inactive' AND NOT hidden"
    if region in REGIONS:
        query += " AND region = ?"
        params.append(region)
    if section in SOCIETY_SECTIONS:
        query += " AND section = ?"
        params.append(section)
    if q:
        # FTS5 (typo/partial-word tolerant), falling back to a plain LIKE if
        # the index isn't available for any reason - search must never hard-fail.
        ids = fts_match_ids(db, "societies_fts", q)
        if ids is not None:
            query += f" AND id IN ({','.join('?' * len(ids))})" if ids else " AND 0"
            params.extend(ids)
        else:
            query += " AND name LIKE ? ESCAPE '\\'"
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
    query += " ORDER BY name"

    societies = db.execute(query, params).fetchall()

    return render_template(
        "societies_list.html",
        societies=societies,
        regions=REGIONS,
        sections=SOCIETY_SECTIONS,
        selected_region=region,
        selected_section=section,
        q=q,
        show_inactive=show_inactive,
    )


SEARCH_RESULT_LIMIT = 12


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    db = get_db()
    societies = []
    titles = []
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

        # FTS5 (typo/partial-word tolerant), falling back to a plain LIKE -
        # same pattern as societies_list()'s own search box.
        society_ids = fts_match_ids(db, "societies_fts", q)
        if society_ids is not None:
            if society_ids:
                societies = db.execute(
                    f"SELECT * FROM societies WHERE id IN ({','.join('?' * len(society_ids))}) "
                    "AND section != 'Inactive' AND NOT hidden ORDER BY name LIMIT ?",
                    (*society_ids, SEARCH_RESULT_LIMIT),
                ).fetchall()
        else:
            societies = db.execute(
                "SELECT * FROM societies WHERE name LIKE ? ESCAPE '\\' "
                "AND section != 'Inactive' AND NOT hidden ORDER BY name LIMIT ?",
                (f"%{escaped}%", SEARCH_RESULT_LIMIT),
            ).fetchall()

        # Every matching title from either the current shows table or the
        # older awards archive, same shape as titles_list()'s own query -
        # deliberately one "Shows" result kind rather than a separate "Award"
        # one, since /titles/<title> already surfaces both a show's
        # production history and its awards together.
        titles = db.execute(
            """
            SELECT show, COUNT(*) AS n FROM (
                SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical'
                UNION ALL
                SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
            )
            WHERE show LIKE ? ESCAPE '\\'
            GROUP BY show ORDER BY show LIMIT ?
            """,
            (SHOWS_COVERAGE_START_YEAR, f"%{escaped}%", SEARCH_RESULT_LIMIT),
        ).fetchall()

    return render_template("search.html", q=q, societies=societies, titles=titles, limit=SEARCH_RESULT_LIMIT)


@bp.route("/adjudicators")
def adjudicators_list():
    db = get_db()
    # Only ever an adjudicator with at least one real season/tier assignment -
    # one added in /admin/adjudicators but never assigned yet has nothing to
    # show publicly (matches the 404 a direct /adjudicators/<id> link to one
    # gets below).
    adjudicators = db.execute(
        """
        SELECT adjudicators.id, adjudicators.name, adjudicators.notes, COUNT(*) AS season_count
        FROM adjudicators
        JOIN adjudicator_assignments ON adjudicator_assignments.adjudicator_id = adjudicators.id
        GROUP BY adjudicators.id
        ORDER BY adjudicators.name
        """
    ).fetchall()
    review_counts = dict(db.execute(
        """
        SELECT adjudicator_assignments.adjudicator_id, COUNT(*) AS n
        FROM adjudicator_assignments
        JOIN shows ON shows.season = adjudicator_assignments.season
                  AND shows.section = adjudicator_assignments.section
        JOIN societies ON societies.id = shows.society_id
        WHERE shows.review_status = 'Published' AND shows.review_url IS NOT NULL
          AND shows.moderation_status = 'approved' AND NOT societies.hidden
        GROUP BY adjudicator_assignments.adjudicator_id
        """
    ).fetchall())
    return render_template("adjudicators_list.html", adjudicators=adjudicators, review_counts=review_counts)


@bp.route("/adjudicators/<int:adjudicator_id>")
def adjudicator_detail(adjudicator_id):
    db = get_db()
    adjudicator = db.execute("SELECT * FROM adjudicators WHERE id = ?", (adjudicator_id,)).fetchone()
    if adjudicator is None:
        abort(404)

    seasons_judged = db.execute(
        "SELECT season, section FROM adjudicator_assignments WHERE adjudicator_id = ? ORDER BY season DESC",
        (adjudicator_id,),
    ).fetchall()
    if not seasons_judged:
        abort(404)

    # Only actual published reviews here (unlike /admin/adjudicators'
    # cross-check view, which deliberately shows every show in their
    # assigned seasons regardless of review status) - this page is "here's
    # what X has written", not an admin verification tool. Same hidden-
    # society exclusion as the homepage/Season Archive/calendar feed.
    reviews = db.execute(
        """
        SELECT shows.id, shows.show, shows.season, shows.section, shows.opening_date, shows.review_url,
               societies.name AS society_name
        FROM shows
        JOIN adjudicator_assignments ON adjudicator_assignments.season = shows.season
                                     AND adjudicator_assignments.section = shows.section
        JOIN societies ON societies.id = shows.society_id
        WHERE adjudicator_assignments.adjudicator_id = ?
          AND shows.review_status = 'Published' AND shows.review_url IS NOT NULL
          AND shows.moderation_status = 'approved' AND NOT societies.hidden
        ORDER BY shows.opening_date DESC
        """,
        (adjudicator_id,),
    ).fetchall()

    return render_template(
        "adjudicator_detail.html", adjudicator=adjudicator, seasons_judged=seasons_judged, reviews=reviews,
    )


@bp.route("/societies/<int:society_id>")
def society_detail(society_id):
    db = get_db()
    society = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
        abort(404)

    viewer = current_user()
    # Hidden means the society asked not to be publicly associated with
    # AIMS - 404 for anyone not logged in as a moderator, so the page still
    # works for a moderator reviewing/unhiding it. Doesn't touch historical
    # stats/awards/Season Archive - see schema.sql's societies.hidden.
    if society["hidden"] and viewer is None:
        abort(404)

    # Only fetched for an admin viewer - lets them hand out this society's
    # login code straight from its own page instead of hunting for it (or
    # re-creating it) on /admin/invite-codes. Same "still valid" check as
    # auth.py's active_society_code().
    society_code = None
    society_login_url = None
    if viewer and viewer["role"] == "admin":
        society_code = db.execute(
            """
            SELECT * FROM invite_codes WHERE society_id = ? AND is_active = 1
            AND (expires_at IS NULL OR expires_at >= ?)
            ORDER BY created_at DESC LIMIT 1
            """,
            (society_id, date.today().isoformat()),
        ).fetchone()
        # Built here (not in the template) so it reuses notify.py's SITE_URL
        # handling - url_for(..., _external=True) can't be trusted behind
        # the Cloudflare Tunnel/PrefixMiddleware setup (see notify.py).
        society_login_url = notify.link(url_for("society.login"))

    shows = db.execute(
        """
        SELECT * FROM shows
        WHERE society_id = ? AND moderation_status = 'approved'
        ORDER BY season DESC, show
        """,
        (society_id,),
    ).fetchall()

    # Season strings sort correctly as text (see schema.sql's design note).
    # A future-season row with no title yet is just a "slotted, TBA" placeholder -
    # not worth a blank line in the history table. One that's already been
    # announced gets pulled out into its own "coming up" block instead of
    # blending into the history below it.
    current = current_season(db)
    future_shows = [s for s in shows if s["season"] > current and s["show"] is not None]
    shows = [s for s in shows if s["season"] <= current]

    # Pre-2024 award/nomination history from the AIMS awards archive - one row
    # per category (so a single production can appear several times, once per
    # category it was up for). show can be NULL here (person-level awards like
    # the Mary Kelly/Unsung Hero Award aren't tied to a specific production).
    # A row with no category/result at all isn't an award record - it's a
    # bare "this production happened" entry (see admin.bulk_historical_
    # productions) - split those into their own show-history list rather
    # than rendering as a nomination row full of "—" placeholders.
    historical_rows = db.execute(
        """
        SELECT year, tier, category_name, result, show, nominee_name, role, reason
        FROM historical_results
        WHERE society_id = ?
        ORDER BY year DESC, category_name
        """,
        (society_id,),
    ).fetchall()
    historical = [r for r in historical_rows if r["category_name"] is not None or r["result"] is not None]
    historical_shows = [r for r in historical_rows if r["category_name"] is None and r["result"] is None]

    # A compact "trophy case" summary - total wins, Best Overall Show wins
    # specifically, and the earliest year on record (from the awards archive,
    # falling back to the earliest season in shows if there's no archive
    # history at all).
    award_totals = db.execute(
        """
        SELECT COUNT(*), SUM(CASE WHEN category_name = 'Best Overall Show' THEN 1 ELSE 0 END), MIN(year)
        FROM historical_results WHERE society_id = ? AND result = 'Winner'
        """,
        (society_id,),
    ).fetchone()
    total_wins, best_show_wins, earliest_award_year = award_totals

    # Runner-up finishes for Best Overall Show specifically - a separate
    # query rather than folding into award_totals above, since that one's
    # outer WHERE is scoped to result = 'Winner' (needed for total_wins/
    # earliest_award_year) and would silently zero these out otherwise.
    best_show_second, best_show_third = db.execute(
        """
        SELECT
            SUM(CASE WHEN result = 'Second Place' THEN 1 ELSE 0 END),
            SUM(CASE WHEN result = 'Third Place' THEN 1 ELSE 0 END)
        FROM historical_results
        WHERE society_id = ? AND category_name = 'Best Overall Show'
        """,
        (society_id,),
    ).fetchone()

    earliest_season = db.execute(
        "SELECT MIN(season) FROM shows WHERE society_id = ? AND show IS NOT NULL", (society_id,)
    ).fetchone()[0]
    active_since = earliest_award_year or (2000 + int(earliest_season[:2]) if earliest_season else None)

    return render_template(
        "society_detail.html", society=society, shows=shows, future_shows=future_shows, historical=historical,
        historical_shows=historical_shows,
        total_wins=total_wins, best_show_wins=best_show_wins, active_since=active_since,
        best_show_second=best_show_second, best_show_third=best_show_third, society_code=society_code,
        society_login_url=society_login_url,
    )


@bp.route("/shows/<int:show_id>")
def show_detail(show_id):
    db = get_db()
    show = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.id = ? AND shows.moderation_status = 'approved'
        """,
        (show_id,),
    ).fetchone()
    if show is None:
        abort(404)

    # Same "upcoming" definition as the homepage's Upcoming shows list -
    # only nudge for details on shows that haven't happened yet.
    is_upcoming = _is_upcoming(show)

    # The show-dates calendar link is redundant once a show has already
    # happened - gated on the same is_upcoming used for the ticket/poster
    # nudge above. (The adjudication-forms reminder used to live here too,
    # but it's only actually useful to the show's own committee, not a
    # random visitor - it now lives on the society's own edit-show page,
    # see society.edit_show().)
    gcal_show_url = None
    # Just opening_date minus 6 weeks (AIMS's real application deadline) -
    # unlike the actual scheduled adjudication_date, this is fine to show
    # publicly since it's only ever arithmetic on a date the page already
    # displays, never AIMS's own internal scheduling info.
    adjudication_cutoff = None
    if is_upcoming:
        opening = date.fromisoformat(show["opening_date"])
        closing = date.fromisoformat(show["closing_date"]) if show["closing_date"] else opening
        gcal_show_url = google_calendar_url(
            text=f"{show['show']} - {show['society_name']}",
            start=opening,
            end_exclusive=closing + timedelta(days=1),
            details=f"AIMS production - {url_for('public.show_detail', show_id=show['id'], _external=True)}",
            location=show["venue"] or "",
        )
        if show["review_status"] != "Not adjudicated":
            adjudication_cutoff = (opening - timedelta(weeks=6)).isoformat()

    # AIMS assigns one adjudicator per tier per season, not per show - so a
    # published review's likely author is whoever covered this show's own
    # season+section, looked up via app.admin's adjudicator_assignments
    # rather than a per-show author field (see /admin/adjudicators). A
    # season/tier can rarely have two rows (a recorded mid-season change) -
    # there's no per-show date-range data to say which of the two actually
    # wrote this specific review, so deliberately don't guess: only credit
    # when exactly one adjudicator is on record for that season/tier.
    reviewed_by = None
    if show["review_status"] == "Published" and show["review_url"] and show["section"]:
        candidates = db.execute(
            """
            SELECT adjudicators.id, adjudicators.name
            FROM adjudicator_assignments
            JOIN adjudicators ON adjudicators.id = adjudicator_assignments.adjudicator_id
            WHERE adjudicator_assignments.season = ? AND adjudicator_assignments.section = ?
            """,
            (show["season"], show["section"]),
        ).fetchall()
        reviewed_by = candidates[0] if len(candidates) == 1 else None

    # Full extracted review text from the AIMS ShowTimes archive (Step 4) -
    # separate from the review_status/review_url pair above, which is a
    # plain external link for 23/24-onward shows that were never in the PDF
    # archive. A show can only ever have one of these approved at once in
    # practice (the archive stops before this site's own coverage begins),
    # but nothing enforces that, so this is its own independent lookup.
    historical_review = db.execute(
        """
        SELECT historical_reviews.review_text, historical_reviews.source_issue,
               adjudicators.id AS adjudicator_id, adjudicators.name AS adjudicator_name
        FROM historical_reviews
        LEFT JOIN adjudicators ON adjudicators.id = historical_reviews.adjudicator_id
        WHERE historical_reviews.show_id = ? AND historical_reviews.moderation_status = 'approved'
        """,
        (show_id,),
    ).fetchone()

    return render_template(
        "show_detail.html", show=show, is_upcoming=is_upcoming,
        gcal_show_url=gcal_show_url, adjudication_cutoff=adjudication_cutoff, reviewed_by=reviewed_by,
        historical_review=historical_review,
    )


TITLES_SORT_OPTIONS = {
    "title": "show COLLATE NOCASE",
    "most": "n DESC, show COLLATE NOCASE",
    "least": "n ASC, show COLLATE NOCASE",
}
# "stale" isn't a SQL ORDER BY - last-performed year comes from a separate
# lookup (see last_performed below), so it's sorted in Python after the fact.
TITLES_SORT_CHOICES = set(TITLES_SORT_OPTIONS) | {"stale"}


@bp.route("/titles")
def titles_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "title")
    if sort not in TITLES_SORT_CHOICES:
        sort = "title"

    query = """
        SELECT show, COUNT(*) AS n FROM (
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical'
            UNION ALL
            SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
        )
    """
    params = [SHOWS_COVERAGE_START_YEAR]
    if q:
        query += " WHERE show LIKE ? ESCAPE '\\'"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    query += f" GROUP BY show ORDER BY {TITLES_SORT_OPTIONS[sort if sort != 'stale' else 'title']}"

    rows = db.execute(query, params).fetchall()

    manual_links = dict(db.execute("SELECT show, url FROM show_links").fetchall())
    has_info = {r[0] for r in db.execute("SELECT show FROM show_info").fetchall()}
    # Last performed - the true most recent year on record for a title from
    # either source, unfiltered by SHOWS_COVERAGE_START_YEAR (that filter
    # only exists above to avoid double-counting a production in both
    # tables; a recency question has no such double-counting problem).
    last_performed = dict(db.execute(
        """
        SELECT show, MAX(year) FROM (
            SELECT show, CAST(substr(opening_date, 1, 4) AS INTEGER) AS year
            FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' AND opening_date IS NOT NULL
            UNION ALL
            SELECT show, year FROM historical_results WHERE show IS NOT NULL
        )
        GROUP BY show
        """
    ).fetchall())

    shows = [
        {
            "title": r["show"],
            "count": r["n"],
            "last_year": last_performed.get(r["show"]),
            "url": manual_links.get(r["show"]),
            "is_manual": r["show"] in manual_links,
            "has_info": r["show"] in has_info,
            "search_url": f"https://en.wikipedia.org/w/index.php?search={quote_plus(r['show'] + ' musical')}",
        }
        for r in rows
    ]

    if sort == "stale":
        shows.sort(key=lambda s: (s["last_year"] is None, s["last_year"] or 0))

    return render_template("titles_list.html", shows=shows, q=q, sort=sort)


@bp.route("/titles/<path:title>")
def title_detail(title):
    db = get_db()
    shows = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.show = ? AND shows.moderation_status = 'approved'
        ORDER BY shows.season DESC, societies.name
        """,
        (title,),
    ).fetchall()

    # Distinct (year, society) before 23/24 - historical_results has one row
    # per award category, not per production, so this collapses back to one
    # row per actual staging. Stops before SHOWS_COVERAGE_START_YEAR so a
    # 23/24+ production already listed above under "full detail" doesn't
    # also show up a second time down here.
    historical = db.execute(
        """
        SELECT DISTINCT year, society_name FROM historical_results
        WHERE show = ? AND year < ? ORDER BY year DESC
        """,
        (title, SHOWS_COVERAGE_START_YEAR),
    ).fetchall()

    if not shows and not historical:
        abort(404)

    info = db.execute("SELECT * FROM show_info WHERE show = ?", (title,)).fetchone()

    # AIMS debut - earliest record of this title, whichever source it comes
    # from. historical is already the pre-23/24 archive, so if it has any
    # rows its earliest (last, since it's sorted DESC) year always predates
    # anything in shows. Otherwise fall back to the earliest season string
    # among shows - lexical comparison matches chronological order for this
    # site's YY/YY+1 seasons, same assumption all_seasons sorting relies on.
    if historical:
        debut_label = str(historical[-1]["year"])
    elif shows:
        debut_label = f"{min(s['season'] for s in shows)} season"
    else:
        debut_label = None

    return render_template(
        "title_detail.html", title=title, shows=shows, historical=historical, info=info, debut_label=debut_label
    )


@bp.route("/more")
def more():
    """Mobile-only "More" tab destination - everything that isn't one of the
    bottom bar's 5 main tabs. Renders fine at any width, just isn't linked
    from anywhere except the bottom bar (see base.html)."""
    return render_template("more.html")


@bp.route("/about")
def about():
    db = get_db()
    total_societies = db.execute("SELECT COUNT(*) FROM societies").fetchone()[0]
    # Same filter as /societies' default (anonymous) view - the number a
    # visitor actually finds if they click through, not the full archive
    # total (which includes Inactive/hidden societies kept for historical
    # record). See the 2026-08-05 site review: these two numbers used to
    # diverge with no explanation, reading as a mismatch rather than by design.
    active_societies = db.execute(
        "SELECT COUNT(*) FROM societies WHERE section != 'Inactive' AND NOT hidden"
    ).fetchone()[0]
    historical_from = db.execute("SELECT MIN(year) FROM historical_results").fetchone()[0]
    return render_template(
        "about.html", total_societies=total_societies, active_societies=active_societies,
        historical_from=historical_from,
    )


@bp.route("/suggest", methods=("GET", "POST"))
@limiter.limit("5 per minute")
def suggest():
    if request.method == "POST":
        # Honeypot - same pattern as the show submission form.
        if request.form.get("website", ""):
            return redirect(url_for("public.suggest_thanks"))

        message = request.form.get("message", "").strip()
        category = request.form.get("category", "")
        submitted_name = request.form.get("submitted_name", "").strip() or None
        contact = request.form.get("contact", "").strip() or None

        if not message:
            flash("Enter your suggestion before submitting.", "error")
            return render_template("suggest.html", form=request.form, categories=SUGGESTION_CATEGORIES)
        if category not in SUGGESTION_CATEGORIES:
            flash("Choose a type for your suggestion.", "error")
            return render_template("suggest.html", form=request.form, categories=SUGGESTION_CATEGORIES)

        get_db().execute(
            "INSERT INTO feature_suggestions (message, category, submitted_name, contact) VALUES (?, ?, ?, ?)",
            (message, category, submitted_name, contact),
        )
        get_db().commit()
        notify.send(
            f"New suggestion ({category})",
            f"From: {submitted_name or 'Anonymous'}\n\n{message}\n\n"
            f"Review it: {notify.link(url_for('admin.suggestions'))}",
        )
        return redirect(url_for("public.suggest_thanks"))

    return render_template("suggest.html", form={}, categories=SUGGESTION_CATEGORIES)


@bp.route("/suggest/thanks")
def suggest_thanks():
    return render_template("suggest_thanks.html")


@bp.route("/suggestions")
def suggestions_board():
    db = get_db()
    # Lane order (not alphabetical): Planned -> In Progress -> Done reads as
    # a pipeline, "Not planned" as the reference tail - still shown so a
    # duplicate idea can be spotted before resubmitting. Ordered within each
    # lane by triaged_at (falls back to created_at for rows triaged before
    # that column existed) so the most recently-moved item floats to the top.
    rows = db.execute(
        """
        SELECT message, category, triage_status, admin_note FROM feature_suggestions
        WHERE triage_status IN ('Planned', 'In Progress', 'Done', 'Not planned')
        ORDER BY
            CASE triage_status WHEN 'Planned' THEN 0 WHEN 'In Progress' THEN 1 WHEN 'Done' THEN 2 WHEN 'Not planned' THEN 3 END,
            COALESCE(triaged_at, created_at) DESC
        """
    ).fetchall()
    lanes = {status: [] for status in ("Planned", "In Progress", "Done", "Not planned")}
    for row in rows:
        lanes[row["triage_status"]].append(row)
    # "Recently shipped" is the curated/manual changelog only now that a
    # finished suggestion is visible in its own Done lane above - showing
    # the same item in both places would just be clutter. This still covers
    # shipped work that didn't start as a suggestion (e.g. the nav rework).
    changelog = db.execute(
        "SELECT entry, created_at AS entry_date FROM changelog_entries ORDER BY created_at DESC"
    ).fetchall()
    return render_template("suggestions_board.html", lanes=lanes, changelog=changelog)


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename)
