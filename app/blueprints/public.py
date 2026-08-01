from datetime import date

from flask import Blueprint, abort, current_app, render_template, request, send_from_directory

from ..auth import current_user
from ..constants import REGIONS, SOCIETY_SECTIONS
from ..db import get_db

bp = Blueprint("public", __name__)

UPCOMING_LIMIT = 6


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

    upcoming = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved'
          AND shows.show IS NOT NULL
          AND shows.opening_date >= ?
          AND shows.status IS NOT 'Cancelled'
        ORDER BY shows.opening_date
        LIMIT ?
        """,
        (date.today().isoformat(), UPCOMING_LIMIT),
    ).fetchall()

    return render_template(
        "index.html",
        societies=societies,
        upcoming=upcoming,
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

    shows = db.execute(
        """
        SELECT * FROM shows
        WHERE society_id = ? AND moderation_status = 'approved'
        ORDER BY season DESC, show
        """,
        (society_id,),
    ).fetchall()

    return render_template("society_detail.html", society=society, shows=shows)


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


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename)
