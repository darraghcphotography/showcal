from datetime import date
from urllib.parse import quote_plus

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for

from .. import notify
from ..auth import current_user
from ..constants import REGIONS, SHOWS_COVERAGE_START_YEAR, SOCIETY_SECTIONS, SUGGESTION_CATEGORIES
from ..db import get_db
from ..rate_limit import limiter
from ..search import fts_match_ids
from ..season import current_season

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
    historical = db.execute(
        """
        SELECT year, tier, category_name, result, show, nominee_name, role, reason
        FROM historical_results
        WHERE society_id = ?
        ORDER BY year DESC, category_name
        """,
        (society_id,),
    ).fetchall()

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
    is_upcoming = (
        show["status"] != "Cancelled"
        and show["opening_date"] is not None
        and show["opening_date"] >= date.today().isoformat()
    )

    return render_template("show_detail.html", show=show, is_upcoming=is_upcoming)


TITLES_SORT_OPTIONS = {
    "title": "show COLLATE NOCASE",
    "most": "n DESC, show COLLATE NOCASE",
    "least": "n ASC, show COLLATE NOCASE",
}


@bp.route("/titles")
def titles_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "title")
    if sort not in TITLES_SORT_OPTIONS:
        sort = "title"

    query = """
        SELECT show, COUNT(*) AS n FROM (
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION ALL
            SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
        )
    """
    params = [SHOWS_COVERAGE_START_YEAR]
    if q:
        query += " WHERE show LIKE ? ESCAPE '\\'"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    query += f" GROUP BY show ORDER BY {TITLES_SORT_OPTIONS[sort]}"

    rows = db.execute(query, params).fetchall()

    manual_links = dict(db.execute("SELECT show, url FROM show_links").fetchall())
    has_info = {r[0] for r in db.execute("SELECT show FROM show_info").fetchall()}

    shows = [
        {
            "title": r["show"],
            "count": r["n"],
            "url": manual_links.get(r["show"]),
            "is_manual": r["show"] in manual_links,
            "has_info": r["show"] in has_info,
            "search_url": f"https://en.wikipedia.org/w/index.php?search={quote_plus(r['show'] + ' musical')}",
        }
        for r in rows
    ]

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

    return render_template("title_detail.html", title=title, shows=shows, historical=historical, info=info)


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
        SELECT message, category, triage_status FROM feature_suggestions
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
