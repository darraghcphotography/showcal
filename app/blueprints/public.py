from datetime import date
from urllib.parse import quote_plus

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for

from ..auth import current_user
from ..constants import REGIONS, SHOWS_COVERAGE_START_YEAR, SOCIETY_SECTIONS
from ..db import get_db

bp = Blueprint("public", __name__)

UPCOMING_LIMIT = 6
POSTER_GALLERY_LIMIT = 8


@bp.route("/")
def index():
    region = request.args.get("region", "")
    section = request.args.get("section", "")
    q = request.args.get("q", "").strip()
    # Only a logged-in moderator/admin can even ask to see inactive societies -
    # anonymous visitors always get the filtered default.
    show_inactive = request.args.get("show_inactive") == "1" and current_user() is not None

    query = "SELECT * FROM societies WHERE 1=1"
    params = []
    if not show_inactive:
        query += " AND section != 'Inactive'"
    if region in REGIONS:
        query += " AND region = ?"
        params.append(region)
    if section in SOCIETY_SECTIONS:
        query += " AND section = ?"
        params.append(section)
    if q:
        query += " AND name LIKE ? ESCAPE '\\'"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    query += " ORDER BY name"

    db = get_db()
    societies = db.execute(query, params).fetchall()

    # Deliberately separate from the Browse filters above (region/section/q) -
    # "what's coming up near me" and "which societies are in a region" are
    # different questions, so this gets its own small filter rather than
    # reusing/overloading the same one.
    upcoming_region = request.args.get("upcoming_region", "")
    upcoming_query = """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved'
          AND shows.show IS NOT NULL
          AND shows.opening_date >= ?
          AND shows.status IS NOT 'Cancelled'
    """
    upcoming_params = [date.today().isoformat()]
    if upcoming_region in REGIONS:
        upcoming_query += " AND shows.region = ?"
        upcoming_params.append(upcoming_region)
    upcoming_query += " ORDER BY shows.opening_date LIMIT ?"
    upcoming_params.append(UPCOMING_LIMIT)
    upcoming = db.execute(upcoming_query, upcoming_params).fetchall()

    poster_gallery = db.execute(
        """
        SELECT shows.id, shows.show, shows.poster_filename, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved' AND shows.poster_filename IS NOT NULL
        ORDER BY shows.created_at DESC
        LIMIT ?
        """,
        (POSTER_GALLERY_LIMIT,),
    ).fetchall()

    return render_template(
        "index.html",
        societies=societies,
        upcoming=upcoming,
        poster_gallery=poster_gallery,
        regions=REGIONS,
        sections=SOCIETY_SECTIONS,
        selected_region=region,
        selected_section=section,
        q=q,
        show_inactive=show_inactive,
        upcoming_region=upcoming_region,
    )


@bp.route("/societies/<int:society_id>")
def society_detail(society_id):
    db = get_db()
    society = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
        abort(404)

    shows = db.execute(
        """
        SELECT * FROM shows
        WHERE society_id = ? AND moderation_status = 'approved'
        ORDER BY season DESC, show
        """,
        (society_id,),
    ).fetchall()

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

    return render_template("society_detail.html", society=society, shows=shows, historical=historical)


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

    return render_template("show_detail.html", show=show)


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


@bp.route("/suggest", methods=("GET", "POST"))
def suggest():
    if request.method == "POST":
        # Honeypot - same pattern as the show submission form.
        if request.form.get("website", ""):
            return redirect(url_for("public.suggest_thanks"))

        message = request.form.get("message", "").strip()
        submitted_name = request.form.get("submitted_name", "").strip() or None

        if not message:
            flash("Enter your suggestion before submitting.", "error")
            return render_template("suggest.html", form=request.form)

        get_db().execute(
            "INSERT INTO feature_suggestions (message, submitted_name) VALUES (?, ?)",
            (message, submitted_name),
        )
        get_db().commit()
        return redirect(url_for("public.suggest_thanks"))

    return render_template("suggest.html", form={})


@bp.route("/suggest/thanks")
def suggest_thanks():
    return render_template("suggest_thanks.html")


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename)
