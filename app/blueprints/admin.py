import functools
import re
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ..auth import current_user, login_required
from ..constants import REGIONS, REVIEW_STATUSES, SHOW_SECTIONS
from ..db import get_db
from ..uploads import save_poster

bp = Blueprint("admin", __name__, url_prefix="/admin")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def admin_required(view):
    @functools.wraps(view)
    @login_required
    def wrapped(**kwargs):
        if current_user()["role"] != "admin":
            abort(403)
        return view(**kwargs)

    return wrapped


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("admin.queue"))
    return render_template("admin/login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("public.index"))


@bp.route("/")
@login_required
def dashboard():
    return redirect(url_for("admin.queue"))


@bp.route("/queue")
@login_required
def queue():
    db = get_db()
    pending = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'pending'
        ORDER BY shows.created_at
        """
    ).fetchall()
    return render_template("admin/queue.html", shows=pending)


@bp.route("/queue/<int:show_id>/approve", methods=("POST",))
@login_required
def approve(show_id):
    db = get_db()
    user = current_user()
    db.execute(
        """
        UPDATE shows
        SET moderation_status = 'approved', moderated_by = ?, moderated_at = ?, updated_at = ?
        WHERE id = ? AND moderation_status = 'pending'
        """,
        (user["username"], datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), show_id),
    )
    db.commit()
    flash("Show approved and now live.", "success")
    return redirect(url_for("admin.queue"))


@bp.route("/queue/<int:show_id>/reject", methods=("POST",))
@login_required
def reject(show_id):
    db = get_db()
    user = current_user()
    db.execute(
        """
        UPDATE shows
        SET moderation_status = 'rejected', moderated_by = ?, moderated_at = ?, updated_at = ?
        WHERE id = ? AND moderation_status = 'pending'
        """,
        (user["username"], datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), show_id),
    )
    db.commit()
    flash("Submission rejected.", "success")
    return redirect(url_for("admin.queue"))


@bp.route("/shows")
@login_required
def shows_list():
    q = request.args.get("q", "").strip()
    needs_review = request.args.get("needs_review", "")

    query = """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved'
    """
    params = []
    if q:
        query += " AND (shows.show LIKE ? ESCAPE '\\' OR societies.name LIKE ? ESCAPE '\\')"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        params += [like, like]
    if needs_review:
        query += " AND shows.review_status != 'Published' AND shows.show IS NOT NULL"
    query += " ORDER BY shows.season DESC, societies.name"

    shows = get_db().execute(query, params).fetchall()
    return render_template("admin/shows_list.html", shows=shows, q=q, needs_review=needs_review)


@bp.route("/shows/<int:show_id>/edit", methods=("GET", "POST"))
@login_required
def edit_show(show_id):
    db = get_db()
    show = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.id = ?
        """,
        (show_id,),
    ).fetchone()
    if show is None:
        abort(404)

    if request.method == "POST":
        errors = []
        season = request.form.get("season", "").strip()
        region = request.form.get("region", "")
        section = request.form.get("section") or None
        show_title = request.form.get("show", "").strip() or None
        opening_date = request.form.get("opening_date", "").strip() or None
        closing_date = request.form.get("closing_date", "").strip() or None
        adjudication_date = request.form.get("adjudication_date", "").strip() or None
        venue = request.form.get("venue", "").strip() or None
        director = request.form.get("director", "").strip() or None
        musical_director = request.form.get("musical_director", "").strip() or None
        choreographer = request.form.get("choreographer", "").strip() or None
        review_url = request.form.get("review_url", "").strip() or None
        review_status = request.form.get("review_status", "None")
        ticket_url = request.form.get("ticket_url", "").strip() or None
        cancelled = bool(request.form.get("cancelled"))

        if region not in REGIONS:
            errors.append("Choose a valid region.")
        if section is not None and section not in SHOW_SECTIONS:
            errors.append("Choose a valid tier.")
        for label, value in (
            ("Opening date", opening_date),
            ("Closing date", closing_date),
            ("Adjudication date", adjudication_date),
        ):
            if value and not DATE_RE.match(value):
                errors.append(f"{label} must be a valid date.")

        # Attaching a review URL is what makes a review "Published" - this is
        # the one thing that overrides whatever was picked in the dropdown,
        # per the moderation workflow (attach link -> flips to Published).
        if review_url:
            review_status = "Published"
        elif review_status not in REVIEW_STATUSES:
            errors.append("Choose a valid review status.")

        poster_filename = show["poster_filename"]
        poster_file = request.files.get("poster")
        if poster_file and poster_file.filename:
            try:
                poster_filename = save_poster(poster_file, current_app.config["UPLOAD_DIR"])
            except ValueError as e:
                errors.append(str(e))
        elif request.form.get("remove_poster"):
            poster_filename = None

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/edit_show.html", show=show, regions=REGIONS,
                                    sections=SHOW_SECTIONS, review_statuses=REVIEW_STATUSES)

        db.execute(
            """
            UPDATE shows SET
                season = ?, region = ?, section = ?, show = ?,
                opening_date = ?, closing_date = ?, adjudication_date = ?,
                venue = ?, director = ?, musical_director = ?, choreographer = ?,
                review_url = ?, review_status = ?, ticket_url = ?, poster_filename = ?, status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                season, region, section, show_title,
                opening_date, closing_date, adjudication_date,
                venue, director, musical_director, choreographer,
                review_url, review_status, ticket_url, poster_filename, "Cancelled" if cancelled else None,
                datetime.utcnow().isoformat(), show_id,
            ),
        )
        db.commit()
        flash("Show updated.", "success")
        return redirect(url_for("admin.shows_list"))

    return render_template("admin/edit_show.html", show=show, regions=REGIONS,
                            sections=SHOW_SECTIONS, review_statuses=REVIEW_STATUSES)


@bp.route("/invite-codes")
@admin_required
def invite_codes():
    codes = get_db().execute("SELECT * FROM invite_codes ORDER BY created_at DESC").fetchall()
    return render_template("admin/invite_codes.html", codes=codes, today=date.today().isoformat())


@bp.route("/invite-codes/create", methods=("POST",))
@admin_required
def create_invite_code():
    code = request.form.get("code", "").strip()
    label = request.form.get("label", "").strip() or None
    expires_at = request.form.get("expires_at", "").strip() or None

    if not code:
        flash("Enter a code.", "error")
        return redirect(url_for("admin.invite_codes"))

    db = get_db()
    existing = db.execute("SELECT id FROM invite_codes WHERE code = ?", (code,)).fetchone()
    if existing:
        flash("That code already exists.", "error")
        return redirect(url_for("admin.invite_codes"))

    db.execute(
        "INSERT INTO invite_codes (code, label, expires_at, created_by) VALUES (?, ?, ?, ?)",
        (code, label, expires_at, current_user()["username"]),
    )
    db.commit()
    flash("Invite code created.", "success")
    return redirect(url_for("admin.invite_codes"))


@bp.route("/invite-codes/<int:code_id>/toggle", methods=("POST",))
@admin_required
def toggle_invite_code(code_id):
    db = get_db()
    row = db.execute("SELECT * FROM invite_codes WHERE id = ?", (code_id,)).fetchone()
    if row is None:
        abort(404)
    db.execute("UPDATE invite_codes SET is_active = ? WHERE id = ?", (0 if row["is_active"] else 1, code_id))
    db.commit()
    return redirect(url_for("admin.invite_codes"))
