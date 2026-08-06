import functools
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ..auth import current_user, login_required
from ..constants import (
    AWARD_RESULTS, REGIONS, REVIEW_STATUSES, RIGHTS_STATUSES, SHOW_SECTIONS, SOCIETY_SECTIONS,
    SUGGESTION_CATEGORIES, SUGGESTION_STATUSES,
)
from ..db import get_db
from ..dedupe import find_candidates
from ..invite_words import ADJECTIVES, NOUNS
from ..rate_limit import limiter
from ..season import current_season, season_range
from ..similarity import find_close_title
from ..uploads import save_poster

bp = Blueprint("admin", __name__, url_prefix="/admin")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://")

PROFILE_URL_FIELDS = (
    ("Website", "website_url"), ("Facebook", "facebook_url"),
    ("Instagram", "instagram_url"), ("TikTok", "tiktok_url"),
    ("Other link", "other_url"),
)


def _generate_invite_code(db):
    while True:
        code = f"{secrets.choice(ADJECTIVES)}-{secrets.choice(NOUNS)}"
        if not db.execute("SELECT 1 FROM invite_codes WHERE code = ? COLLATE NOCASE", (code,)).fetchone():
            return code


def admin_required(view):
    @functools.wraps(view)
    @login_required
    def wrapped(**kwargs):
        if current_user()["role"] != "admin":
            abort(403)
        return view(**kwargs)

    return wrapped


@bp.route("/login", methods=("GET", "POST"))
@limiter.limit("10 per minute")
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


def _duplicate_historical_rows(db):
    """Bare historical_results rows (no category/result - see
    admin.bulk_historical_productions) that duplicate either a real
    award-archive row or a shows table entry for the same production. See
    find_duplicate_historical_rows.py, which this mirrors - kept as a live
    dashboard check too, not just a one-off script, so a recurrence (a
    future tool bug, a moderator double-pasting a list) surfaces on its own
    rather than needing someone to remember to run the script again."""
    return db.execute(
        """
        SELECT h1.id, h1.year, h1.show, h1.society_name
        FROM historical_results h1
        WHERE h1.category_name IS NULL AND h1.result IS NULL
          AND h1.society_id IS NOT NULL AND h1.show IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM historical_results h2
            WHERE h2.year = h1.year AND h2.show = h1.show AND h2.society_id = h1.society_id
              AND h2.id != h1.id
          )
        UNION
        SELECT h.id, h.year, h.show, h.society_name
        FROM historical_results h
        WHERE h.category_name IS NULL AND h.result IS NULL
          AND h.society_id IS NOT NULL AND h.show IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM shows s
            WHERE s.society_id = h.society_id AND s.show = h.show
              AND substr(s.opening_date, 1, 4) = CAST(h.year AS TEXT)
          )
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

    # "Not adjudicated" is excluded - it's a deliberate, permanent state (that
    # show will never have a review), not a gap waiting to be filled in.
    needs_review_count = db.execute(
        """
        SELECT COUNT(*) FROM shows
        WHERE moderation_status = 'approved' AND show IS NOT NULL
          AND review_status NOT IN ('Published', 'Not adjudicated') AND season <= ?
        """,
        (current,),
    ).fetchone()[0]

    missing_dates_count = db.execute(
        """
        SELECT COUNT(*) FROM shows
        WHERE moderation_status = 'approved' AND show IS NOT NULL
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
        award_year = 2000 + int(concluded["season"].split("/")[1])
        has_awards = db.execute("SELECT 1 FROM historical_results WHERE year = ?", (award_year,)).fetchone()
        if not has_awards:
            awards_pending_season = concluded["season"]

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
        awards_pending_season=awards_pending_season,
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
    )


@bp.route("/data-quality/historical/<int:row_id>/delete", methods=("POST",))
@login_required
def delete_duplicate_historical_row(row_id):
    db = get_db()
    db.execute("DELETE FROM historical_results WHERE id = ?", (row_id,))
    db.commit()
    flash("Duplicate row deleted.", "success")
    return redirect(url_for("admin.data_quality"))


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
    db = get_db()
    q = request.args.get("q", "").strip()
    needs_review = request.args.get("needs_review", "")
    # "" (default) = current season and earlier only - keeps seasons still mostly
    # placeholder "TBA" slots (e.g. next season, signalled early) out of the way.
    # "all" = no season filter. Anything else = an exact season match.
    season = request.args.get("season", "")
    current = current_season(db)

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
        # "Not adjudicated" is a deliberate, permanent state - that show will
        # never have a review, so it's not something a moderator needs to
        # come back and fix. Excluding it here (and from the dashboard's
        # needs_review_count) keeps this filter meaning "still needs a link
        # added", not "isn't Published for any reason".
        query += " AND shows.review_status NOT IN ('Published', 'Not adjudicated') AND shows.show IS NOT NULL"
    if season == "":
        query += " AND shows.season <= ?"
        params.append(current)
    elif season != "all":
        query += " AND shows.season = ?"
        params.append(season)
    query += " ORDER BY shows.season DESC, societies.name"

    shows = db.execute(query, params).fetchall()

    seasons = [
        r["season"]
        for r in db.execute("SELECT DISTINCT season FROM shows ORDER BY season DESC").fetchall()
    ]

    return render_template(
        "admin/shows_list.html", shows=shows, q=q, needs_review=needs_review,
        season=season, seasons=seasons, current_season=current,
    )


@bp.route("/societies/<int:society_id>/shows/new", methods=("GET", "POST"))
@login_required
def new_show(society_id):
    db = get_db()
    society = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
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

        if not season:
            errors.append("Choose a season.")
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

        if review_url:
            review_status = "Published"
        elif review_status not in REVIEW_STATUSES:
            errors.append("Choose a valid review status.")

        poster_filename = None
        poster_file = request.files.get("poster")
        if poster_file and poster_file.filename:
            try:
                poster_filename = save_poster(poster_file, current_app.config["UPLOAD_DIR"])
            except ValueError as e:
                errors.append(str(e))

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/new_show.html", society=society, regions=REGIONS, sections=SHOW_SECTIONS,
                review_statuses=REVIEW_STATUSES, seasons=season_range(db), form=request.form,
            )

        try:
            db.execute(
                """
                INSERT INTO shows (
                    society_id, season, region, section, show,
                    opening_date, closing_date, adjudication_date,
                    venue, director, musical_director, choreographer,
                    review_url, review_status, ticket_url, poster_filename, status,
                    moderation_status, source, moderated_by, moderated_at
                ) VALUES (
                    :society_id, :season, :region, :section, :show,
                    :opening_date, :closing_date, :adjudication_date,
                    :venue, :director, :musical_director, :choreographer,
                    :review_url, :review_status, :ticket_url, :poster_filename, :status,
                    'approved', 'submission', :moderated_by, :moderated_at
                )
                """,
                {
                    "society_id": society_id,
                    "season": season,
                    "region": region,
                    "section": section,
                    "show": show_title,
                    "opening_date": opening_date,
                    "closing_date": closing_date,
                    "adjudication_date": adjudication_date,
                    "venue": venue or society["default_venue"],
                    "director": director,
                    "musical_director": musical_director,
                    "choreographer": choreographer,
                    "review_url": review_url,
                    "review_status": review_status,
                    "ticket_url": ticket_url,
                    "poster_filename": poster_filename,
                    "status": "Cancelled" if cancelled else None,
                    "moderated_by": current_user()["username"],
                    "moderated_at": datetime.utcnow().isoformat(),
                },
            )
        except sqlite3.IntegrityError:
            flash("This society already has a show with that exact title in that season.", "error")
            return render_template(
                "admin/new_show.html", society=society, regions=REGIONS, sections=SHOW_SECTIONS,
                review_statuses=REVIEW_STATUSES, seasons=season_range(db), form=request.form,
            )

        db.commit()
        flash("Show added.", "success")
        return redirect(url_for("admin.edit_society", society_id=society_id))

    return render_template(
        "admin/new_show.html", society=society, regions=REGIONS, sections=SHOW_SECTIONS,
        review_statuses=REVIEW_STATUSES, seasons=season_range(db),
        form={"region": society["region"]},
    )


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


@bp.route("/shows/<int:show_id>/delete", methods=("POST",))
@login_required
def delete_show(show_id):
    db = get_db()
    show = db.execute("SELECT id FROM shows WHERE id = ?", (show_id,)).fetchone()
    if show is None:
        abort(404)
    db.execute("DELETE FROM shows WHERE id = ?", (show_id,))
    db.commit()
    flash("Show deleted.", "success")
    return redirect(url_for("admin.shows_list"))


@bp.route("/invite-codes")
@admin_required
def invite_codes():
    db = get_db()
    codes = db.execute(
        """
        SELECT invite_codes.*, societies.name AS society_name
        FROM invite_codes LEFT JOIN societies ON societies.id = invite_codes.society_id
        ORDER BY invite_codes.created_at DESC
        """
    ).fetchall()
    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()
    return render_template(
        "admin/invite_codes.html", codes=codes, societies=societies, today=date.today().isoformat(),
        suggested_code=_generate_invite_code(db),
    )


@bp.route("/invite-codes/create", methods=("POST",))
@admin_required
def create_invite_code():
    code = request.form.get("code", "").strip()
    label = request.form.get("label", "").strip() or None
    expires_at = request.form.get("expires_at", "").strip() or None
    society_id = request.form.get("society_id", "").strip() or None

    if not code:
        flash("Enter a code.", "error")
        return redirect(url_for("admin.invite_codes"))

    db = get_db()
    existing = db.execute("SELECT id FROM invite_codes WHERE code = ? COLLATE NOCASE", (code,)).fetchone()
    if existing:
        flash("That code already exists.", "error")
        return redirect(url_for("admin.invite_codes"))

    if society_id and not db.execute("SELECT id FROM societies WHERE id = ?", (society_id,)).fetchone():
        flash("Choose a valid society.", "error")
        return redirect(url_for("admin.invite_codes"))

    db.execute(
        "INSERT INTO invite_codes (code, label, expires_at, society_id, created_by) VALUES (?, ?, ?, ?, ?)",
        (code, label, expires_at, society_id, current_user()["username"]),
    )
    db.commit()
    flash("Invite code created.", "success")
    return redirect(url_for("admin.invite_codes"))


@bp.route("/invite-codes/bulk-generate", methods=("POST",))
@admin_required
def bulk_generate_invite_codes():
    db = get_db()
    # "Recently active" = at least one show since the site's own data
    # coverage began (season 23/24 onwards - season strings sort correctly
    # as text, see schema.sql), and not already tagged Inactive - skips
    # societies that only ever show up in the pre-2024 awards archive.
    # Also skips anyone who already has a live code, so re-running this
    # only ever tops up whoever's missing one rather than piling up spares.
    societies = db.execute(
        """
        SELECT DISTINCT societies.id, societies.name
        FROM societies
        JOIN shows ON shows.society_id = societies.id
        WHERE societies.section != 'Inactive'
          AND shows.season >= '23/24'
          AND societies.id NOT IN (
              SELECT society_id FROM invite_codes
              WHERE society_id IS NOT NULL AND is_active = 1
          )
        ORDER BY societies.name
        """
    ).fetchall()

    label = f"Bulk-generated {date.today().isoformat()}"
    for society in societies:
        code = _generate_invite_code(db)
        db.execute(
            "INSERT INTO invite_codes (code, label, society_id, created_by) VALUES (?, ?, ?, ?)",
            (code, label, society["id"], current_user()["username"]),
        )
    db.commit()

    if societies:
        flash(f"Generated {len(societies)} new code(s) for recently active societies without one.", "success")
    else:
        flash("Every recently active society already has a live code - nothing to generate.", "success")
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


@bp.route("/invite-codes/<int:code_id>/delete", methods=("POST",))
@admin_required
def delete_invite_code(code_id):
    db = get_db()
    try:
        db.execute("DELETE FROM invite_codes WHERE id = ?", (code_id,))
        db.commit()
        flash("Code deleted.", "success")
    except sqlite3.IntegrityError:
        db.rollback()
        flash("Can't delete this code - it's already attached to a show. Revoke it instead.", "error")
    return redirect(url_for("admin.invite_codes"))


@bp.route("/invite-codes/delete-legacy", methods=("POST",))
@admin_required
def delete_legacy_invite_codes():
    # Matches the old alphanumeric generator's fixed "AIMS-" prefix, not the
    # "Bulk-generated ..." label - the generator itself is gone (replaced by
    # dictionary-word codes), so nothing will ever create a new AIMS-... code
    # again, and this can't accidentally sweep up some future manually-
    # created code that happens to reuse that label wording.
    db = get_db()
    rows = db.execute("SELECT id FROM invite_codes WHERE code LIKE 'AIMS-%'").fetchall()
    deleted = skipped = 0
    for row in rows:
        try:
            db.execute("DELETE FROM invite_codes WHERE id = ?", (row["id"],))
            db.commit()
            deleted += 1
        except sqlite3.IntegrityError:
            db.rollback()
            skipped += 1
    if deleted:
        flash(f"Deleted {deleted} old AIMS- style code(s).", "success")
    if skipped:
        flash(f"{skipped} old code(s) are already attached to a show and were left alone - revoke those instead.", "warning")
    if not deleted and not skipped:
        flash("No old AIMS- style codes found.", "success")
    return redirect(url_for("admin.invite_codes"))


@bp.route("/societies")
@login_required
def societies_list():
    q = request.args.get("q", "").strip()
    query = "SELECT * FROM societies WHERE 1=1"
    params = []
    if q:
        query += " AND name LIKE ? ESCAPE '\\'"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    query += " ORDER BY name"
    societies = get_db().execute(query, params).fetchall()
    return render_template("admin/societies_list.html", societies=societies, q=q)


@bp.route("/venues")
@login_required
def venues():
    db = get_db()
    societies = db.execute(
        "SELECT id, name, region, default_venue FROM societies "
        "WHERE section != 'Inactive' ORDER BY region, name"
    ).fetchall()
    by_region = {r: [] for r in REGIONS}
    for s in societies:
        by_region.setdefault(s["region"], []).append(s)
    filled_count = sum(1 for s in societies if s["default_venue"])
    return render_template(
        "admin/venues.html", by_region=by_region, regions=REGIONS,
        total=len(societies), filled_count=filled_count,
    )


@bp.route("/venues/save", methods=("POST",))
@login_required
def save_venue():
    db = get_db()
    society_id = request.form.get("society_id", type=int)
    if not society_id:
        return jsonify(ok=False, error="Missing society_id"), 400
    venue = request.form.get("venue", "").strip() or None
    updated = db.execute(
        "UPDATE societies SET default_venue = ? WHERE id = ?", (venue, society_id)
    ).rowcount
    db.commit()
    if not updated:
        return jsonify(ok=False, error="Society not found"), 404
    return jsonify(ok=True, venue=venue)


@bp.route("/societies/new", methods=("GET", "POST"))
@login_required
def new_society():
    db = get_db()

    if request.method == "POST":
        errors = []
        name = request.form.get("name", "").strip()
        region = request.form.get("region", "")
        section = request.form.get("section", "")
        section_as_of = request.form.get("section_as_of", "").strip() or None
        notes = request.form.get("notes", "").strip() or None
        default_venue = request.form.get("default_venue", "").strip() or None

        if not name:
            errors.append("Name is required.")
        elif db.execute("SELECT id FROM societies WHERE name = ?", (name,)).fetchone():
            errors.append("A society with that exact name already exists.")
        if region not in REGIONS:
            errors.append("Choose a valid region.")
        if section not in SOCIETY_SECTIONS:
            errors.append("Choose a valid tier.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/new_society.html", regions=REGIONS, sections=SOCIETY_SECTIONS, form=request.form
            )

        # societies.id is the stable id from the AIMS CSV export, not an
        # autoincrement column (see schema.sql) - keep manually-added societies
        # in their own id range so a future CSV re-import can never collide.
        max_id = db.execute("SELECT MAX(id) FROM societies").fetchone()[0] or 0
        new_id = max(10000, max_id + 1)

        db.execute(
            """
            INSERT INTO societies (id, name, region, section, section_as_of, notes, default_venue)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, name, region, section, section_as_of, notes, default_venue),
        )
        db.commit()
        flash(f'"{name}" added.', "success")
        return redirect(url_for("admin.edit_society", society_id=new_id))

    return render_template("admin/new_society.html", regions=REGIONS, sections=SOCIETY_SECTIONS, form={})


@bp.route("/societies/<int:society_id>/edit", methods=("GET", "POST"))
@login_required
def edit_society(society_id):
    db = get_db()
    society = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
        abort(404)

    if request.method == "POST":
        errors = []
        name = request.form.get("name", "").strip()
        region = request.form.get("region", "")
        section = request.form.get("section", "")
        section_as_of = request.form.get("section_as_of", "").strip() or None
        section_history = request.form.get("section_history", "").strip() or None
        notes = request.form.get("notes", "").strip() or None
        default_venue = request.form.get("default_venue", "").strip() or None
        hidden = 1 if request.form.get("hidden") else 0
        profile_fields = {
            "about": request.form.get("about", "").strip() or None,
            "website_url": request.form.get("website_url", "").strip() or None,
            "facebook_url": request.form.get("facebook_url", "").strip() or None,
            "instagram_url": request.form.get("instagram_url", "").strip() or None,
            "tiktok_url": request.form.get("tiktok_url", "").strip() or None,
            "other_url": request.form.get("other_url", "").strip() or None,
            "other_label": request.form.get("other_label", "").strip() or None,
        }

        logo_filename = society["logo_filename"]
        logo_file = request.files.get("logo")
        if logo_file and logo_file.filename:
            try:
                logo_filename = save_poster(logo_file, current_app.config["UPLOAD_DIR"])
            except ValueError as e:
                errors.append(str(e))
        elif request.form.get("remove_logo"):
            logo_filename = None

        if not name:
            errors.append("Name is required.")
        elif db.execute(
            "SELECT id FROM societies WHERE name = ? AND id != ?", (name, society_id)
        ).fetchone():
            errors.append("Another society already has that exact name.")
        if region not in REGIONS:
            errors.append("Choose a valid region.")
        if section not in SOCIETY_SECTIONS:
            errors.append("Choose a valid tier.")
        errors += [
            f"{label} must start with http:// or https://"
            for label, key in PROFILE_URL_FIELDS
            if profile_fields[key] and not URL_RE.match(profile_fields[key])
        ]

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/edit_society.html", society=society, regions=REGIONS, sections=SOCIETY_SECTIONS
            )

        db.execute(
            """
            UPDATE societies SET name = ?, region = ?, section = ?,
                section_as_of = ?, section_history = ?, notes = ?, default_venue = ?, logo_filename = ?,
                about = ?, website_url = ?, facebook_url = ?, instagram_url = ?,
                tiktok_url = ?, other_url = ?, other_label = ?, hidden = ?
            WHERE id = ?
            """,
            (
                name, region, section, section_as_of, section_history, notes, default_venue, logo_filename,
                profile_fields["about"], profile_fields["website_url"], profile_fields["facebook_url"],
                profile_fields["instagram_url"], profile_fields["tiktok_url"], profile_fields["other_url"],
                profile_fields["other_label"], hidden, society_id,
            ),
        )
        db.commit()
        flash("Society updated.", "success")
        return redirect(url_for("admin.societies_list"))

    return render_template(
        "admin/edit_society.html", society=society, regions=REGIONS, sections=SOCIETY_SECTIONS
    )


@bp.route("/societies/<int:society_id>/generate-code", methods=("POST",))
@admin_required
def generate_society_code(society_id):
    db = get_db()
    society = db.execute("SELECT id FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
        abort(404)
    code = _generate_invite_code(db)
    db.execute(
        "INSERT INTO invite_codes (code, society_id, created_by) VALUES (?, ?, ?)",
        (code, society_id, current_user()["username"]),
    )
    db.commit()
    flash(f'Login code for this society: "{code}" - share it with them.', "success")
    return redirect(url_for("public.society_detail", society_id=society_id))


@bp.route("/shows/dates", methods=("GET", "POST"))
@login_required
def fix_dates():
    db = get_db()

    if request.method == "POST":
        show_id = request.form.get("show_id", "")
        opening_date = request.form.get("opening_date", "").strip() or None
        closing_date = request.form.get("closing_date", "").strip() or None
        errors = []
        for label, value in (("Opening date", opening_date), ("Closing date", closing_date)):
            if value and not DATE_RE.match(value):
                errors.append(f"{label} must be a valid date.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db.execute(
                "UPDATE shows SET opening_date = ?, closing_date = ?, updated_at = ? WHERE id = ?",
                (opening_date, closing_date, datetime.utcnow().isoformat(), show_id),
            )
            db.commit()
            flash("Dates updated.", "success")
        return redirect(url_for("admin.fix_dates", **request.args))

    q = request.args.get("q", "").strip()
    season = request.args.get("season", "").strip()
    region = request.args.get("region", "")
    missing = request.args.get("missing", "")
    query = """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved' AND shows.show IS NOT NULL
    """
    params = []
    if q:
        query += " AND (shows.show LIKE ? ESCAPE '\\' OR societies.name LIKE ? ESCAPE '\\')"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        params += [like, like]
    if season:
        query += " AND shows.season = ?"
        params.append(season)
    if region in REGIONS:
        query += " AND shows.region = ?"
        params.append(region)
    if missing:
        query += " AND (shows.opening_date IS NULL OR shows.closing_date IS NULL)"
    query += " ORDER BY shows.season DESC, societies.name"
    shows = db.execute(query, params).fetchall()

    seasons = [
        r["season"]
        for r in db.execute(
            "SELECT DISTINCT season FROM shows WHERE show IS NOT NULL ORDER BY season DESC"
        ).fetchall()
    ]

    return render_template(
        "admin/fix_dates.html", shows=shows, q=q, season=season, region=region,
        seasons=seasons, regions=REGIONS, missing=missing,
    )


@bp.route("/suggestions")
@login_required
def suggestions():
    db = get_db()
    rows = db.execute("SELECT * FROM feature_suggestions ORDER BY created_at DESC").fetchall()
    # Done/Not planned are finished with - kept out of the main list so it
    # doesn't grow forever, but not deleted (still feeds the public Roadmap's
    # "Recently shipped"/reference list).
    needs_attention = [r for r in rows if r["triage_status"] in ("New", "Planned", "In Progress")]
    archived = [r for r in rows if r["triage_status"] in ("Done", "Not planned")]
    return render_template(
        "admin/suggestions.html", needs_attention=needs_attention, archived=archived,
        categories=SUGGESTION_CATEGORIES, statuses=SUGGESTION_STATUSES,
    )


@bp.route("/suggestions/<int:suggestion_id>/update", methods=("POST",))
@login_required
def update_suggestion(suggestion_id):
    db = get_db()
    row = db.execute("SELECT id FROM feature_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    if row is None:
        abort(404)
    category = request.form.get("category", "")
    triage_status = request.form.get("triage_status", "")
    if category not in SUGGESTION_CATEGORIES or triage_status not in SUGGESTION_STATUSES:
        flash("Choose a valid category and status.", "error")
        return redirect(url_for("admin.suggestions"))
    db.execute(
        "UPDATE feature_suggestions SET category = ?, triage_status = ?, triaged_at = datetime('now') WHERE id = ?",
        (category, triage_status, suggestion_id),
    )
    db.commit()
    flash("Suggestion updated.", "success")
    return redirect(url_for("admin.suggestions"))


@bp.route("/suggestions/<int:suggestion_id>/delete", methods=("POST",))
@login_required
def delete_suggestion(suggestion_id):
    db = get_db()
    db.execute("DELETE FROM feature_suggestions WHERE id = ?", (suggestion_id,))
    db.commit()
    flash("Suggestion deleted.", "success")
    return redirect(url_for("admin.suggestions"))


@bp.route("/changelog", methods=("GET", "POST"))
@login_required
def changelog():
    db = get_db()
    if request.method == "POST":
        entry = request.form.get("entry", "").strip()
        if not entry:
            flash("Enter some text for the changelog entry.", "error")
        else:
            db.execute("INSERT INTO changelog_entries (entry) VALUES (?)", (entry,))
            db.commit()
            flash("Changelog entry published.", "success")
        return redirect(url_for("admin.changelog"))
    entries = db.execute("SELECT * FROM changelog_entries ORDER BY created_at DESC").fetchall()
    return render_template("admin/changelog.html", entries=entries)


@bp.route("/changelog/<int:entry_id>/delete", methods=("POST",))
@login_required
def delete_changelog_entry(entry_id):
    db = get_db()
    db.execute("DELETE FROM changelog_entries WHERE id = ?", (entry_id,))
    db.commit()
    return redirect(url_for("admin.changelog"))


@bp.route("/show-links/set", methods=("POST",))
@login_required
def set_show_link():
    show = request.form.get("show", "").strip()
    url = request.form.get("url", "").strip()
    if show and url:
        get_db().execute(
            "INSERT INTO show_links (show, url, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(show) DO UPDATE SET url = excluded.url, updated_at = excluded.updated_at",
            (show, url),
        )
        get_db().commit()
        flash(f'Link set for "{show}".', "success")
    return redirect(url_for("public.titles_list"))


@bp.route("/show-links/clear", methods=("POST",))
@login_required
def clear_show_link():
    show = request.form.get("show", "").strip()
    if show:
        get_db().execute("DELETE FROM show_links WHERE show = ?", (show,))
        get_db().commit()
    return redirect(url_for("public.titles_list"))


@bp.route("/titles/<path:title>/info", methods=("GET", "POST"))
@login_required
def edit_show_info(title):
    db = get_db()
    info = db.execute("SELECT * FROM show_info WHERE show = ?", (title,)).fetchone()

    if request.method == "POST":
        synopsis = request.form.get("synopsis", "").strip() or None
        rights_url = request.form.get("rights_url", "").strip() or None
        rights_status = request.form.get("rights_status") or None
        premiere_year_raw = request.form.get("premiere_year", "").strip()
        premiere_place = request.form.get("premiere_place", "").strip() or None

        if rights_status and rights_status not in RIGHTS_STATUSES:
            flash("Choose a valid rights status.", "error")
            return render_template(
                "admin/show_info_form.html", title=title, statuses=RIGHTS_STATUSES, form=request.form
            )

        premiere_year = None
        if premiere_year_raw:
            try:
                premiere_year = int(premiere_year_raw)
            except ValueError:
                flash("World premiere year must be a number.", "error")
                return render_template(
                    "admin/show_info_form.html", title=title, statuses=RIGHTS_STATUSES, form=request.form
                )

        db.execute(
            """
            INSERT INTO show_info (show, synopsis, rights_url, rights_status, premiere_year, premiere_place, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(show) DO UPDATE SET
                synopsis = excluded.synopsis, rights_url = excluded.rights_url,
                rights_status = excluded.rights_status, premiere_year = excluded.premiere_year,
                premiere_place = excluded.premiere_place, updated_at = excluded.updated_at
            """,
            (title, synopsis, rights_url, rights_status, premiere_year, premiere_place),
        )
        db.commit()
        flash("Show info updated.", "success")
        return redirect(url_for("public.title_detail", title=title))

    return render_template(
        "admin/show_info_form.html", title=title, statuses=RIGHTS_STATUSES,
        form=dict(info) if info else {},
    )


@bp.route("/titles/<path:title>/info/clear", methods=("POST",))
@login_required
def clear_show_info(title):
    get_db().execute("DELETE FROM show_info WHERE show = ?", (title,))
    get_db().commit()
    flash("Show info cleared.", "success")
    return redirect(url_for("public.title_detail", title=title))


@bp.route("/traffic")
@login_required
def traffic():
    db = get_db()
    total_views = db.execute("SELECT COALESCE(SUM(views), 0) FROM page_views").fetchone()[0]
    pages = db.execute(
        "SELECT path, views, last_viewed FROM page_views ORDER BY views DESC LIMIT 30"
    ).fetchall()
    return render_template("admin/traffic.html", total_views=total_views, pages=pages)


DUPLICATE_TITLES_DISPLAY_LIMIT = 60


@bp.route("/duplicate-titles")
@login_required
def duplicate_titles():
    db = get_db()
    titles = {
        r[0]
        for r in db.execute(
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
    all_candidates = find_candidates(titles, dismissed)
    total_candidates = len(all_candidates)
    candidates = all_candidates[:DUPLICATE_TITLES_DISPLAY_LIMIT]

    relevant = {t for pair in candidates for t in pair[:2]}
    counts = {}
    for title in relevant:
        cur = db.execute("SELECT COUNT(*) FROM shows WHERE show = ?", (title,)).fetchone()[0]
        hist = db.execute("SELECT COUNT(*) FROM historical_results WHERE show = ?", (title,)).fetchone()[0]
        counts[title] = cur + hist

    return render_template(
        "admin/duplicate_titles.html", candidates=candidates, counts=counts, all_titles=sorted(titles),
        total_candidates=total_candidates, display_limit=DUPLICATE_TITLES_DISPLAY_LIMIT,
    )


def _merge_titles(db, canonical, other):
    # shows has a UNIQUE index on (society_id, season, show) - if the same
    # society already logged both the canonical and "other" title for the
    # same season (a real possibility, since that's exactly the situation
    # this tool exists to clean up), a blind UPDATE would collide with that
    # constraint and crash. Move rows one at a time instead: where renaming
    # would collide, the canonical row already covers that production, so
    # the "other" row is a redundant duplicate - delete it rather than
    # update it. Where there's no collision, rename as normal.
    rows = db.execute("SELECT id, society_id, season FROM shows WHERE show = ?", (other,)).fetchall()
    for row in rows:
        collision = db.execute(
            "SELECT 1 FROM shows WHERE society_id = ? AND season = ? AND show = ?",
            (row["society_id"], row["season"], canonical),
        ).fetchone()
        if collision:
            db.execute("DELETE FROM shows WHERE id = ?", (row["id"],))
        else:
            db.execute("UPDATE shows SET show = ? WHERE id = ?", (canonical, row["id"]))
    db.execute("UPDATE historical_results SET show = ? WHERE show = ?", (canonical, other))
    db.execute(
        "DELETE FROM dismissed_duplicate_pairs WHERE title_a IN (?, ?) OR title_b IN (?, ?)",
        (canonical, other, canonical, other),
    )


def _dismiss_pair(db, title_a, title_b):
    pair = tuple(sorted((title_a, title_b)))
    db.execute("INSERT OR IGNORE INTO dismissed_duplicate_pairs (title_a, title_b) VALUES (?, ?)", pair)


@bp.route("/duplicate-titles/merge", methods=("POST",))
@login_required
def merge_duplicate_titles():
    db = get_db()
    canonical = request.form.get("canonical", "").strip()
    other = request.form.get("other", "").strip()
    if not canonical or not other or canonical == other:
        flash("Something went wrong picking which title is correct - try again.", "error")
        return redirect(url_for("admin.duplicate_titles"))

    _merge_titles(db, canonical, other)
    db.commit()
    flash(f'Merged "{other}" into "{canonical}".', "success")
    return redirect(url_for("admin.duplicate_titles"))


@bp.route("/duplicate-titles/dismiss", methods=("POST",))
@login_required
def dismiss_duplicate_pair():
    db = get_db()
    title_a = request.form.get("title_a", "").strip()
    title_b = request.form.get("title_b", "").strip()
    if title_a and title_b:
        _dismiss_pair(db, title_a, title_b)
        db.commit()
    return redirect(url_for("admin.duplicate_titles"))


@bp.route("/duplicate-titles/bulk", methods=("POST",))
@login_required
def bulk_duplicate_titles():
    db = get_db()
    merged = 0
    dismissed = 0
    i = 0
    while f"pair_{i}_a" in request.form:
        a = request.form.get(f"pair_{i}_a", "").strip()
        b = request.form.get(f"pair_{i}_b", "").strip()
        decision = request.form.get(f"decision_{i}", "skip")
        if a and b:
            if decision == "keep_a":
                _merge_titles(db, a, b)
                merged += 1
            elif decision == "keep_b":
                _merge_titles(db, b, a)
                merged += 1
            elif decision == "dismiss":
                _dismiss_pair(db, a, b)
                dismissed += 1
        i += 1
    db.commit()
    if merged or dismissed:
        flash(f"Merged {merged} pair(s), dismissed {dismissed} pair(s).", "success")
    else:
        flash("No changes selected.", "warning")
    return redirect(url_for("admin.duplicate_titles"))


@bp.route("/historical-societies")
@login_required
def historical_societies():
    db = get_db()
    rows = db.execute(
        """
        SELECT hsr.society_name, hsr.suggested_region, hsr.note,
               COUNT(hr.id) AS record_count
        FROM historical_society_regions hsr
        LEFT JOIN historical_results hr ON hr.society_name = hsr.society_name
        WHERE hsr.confirmed_region IS NULL
        GROUP BY hsr.society_name
        ORDER BY record_count DESC, hsr.society_name
        """
    ).fetchall()
    confirmed_count = db.execute(
        "SELECT COUNT(*) FROM historical_society_regions WHERE confirmed_region IS NOT NULL"
    ).fetchone()[0]
    return render_template(
        "admin/historical_societies.html", rows=rows, regions=REGIONS, confirmed_count=confirmed_count
    )


@bp.route("/historical-societies/bulk", methods=("POST",))
@login_required
def bulk_historical_societies():
    db = get_db()
    confirmed = 0
    i = 0
    while f"name_{i}" in request.form:
        name = request.form.get(f"name_{i}", "").strip()
        region = request.form.get(f"region_{i}", "").strip()
        if name and region in REGIONS:
            db.execute(
                "UPDATE historical_society_regions SET confirmed_region = ?, updated_at = datetime('now') "
                "WHERE society_name = ?",
                (region, name),
            )
            confirmed += 1
        i += 1
    db.commit()
    if confirmed:
        flash(f"Confirmed a region for {confirmed} society name(s).", "success")
    else:
        flash("No changes selected.", "warning")
    return redirect(url_for("admin.historical_societies"))


def _award_categories(db):
    return [
        r[0] for r in db.execute(
            "SELECT DISTINCT category_name FROM historical_results "
            "WHERE category_name IS NOT NULL ORDER BY category_name"
        ).fetchall()
    ]


def _read_award_form(form):
    category = form.get("category", "")
    if category == "__other__":
        category = form.get("category_other", "").strip()
    return {
        "year": form.get("year", "").strip(),
        "tier": form.get("tier") or None,
        "category_name": category or None,
        "result": form.get("result") or None,
        "show": form.get("show", "").strip() or None,
        "society_id": form.get("society_id", "").strip() or None,
        "nominee_name": form.get("nominee_name", "").strip() or None,
        "role": form.get("role", "").strip() or None,
        "reason": form.get("reason", "").strip() or None,
    }


def _validate_award(fields):
    errors = []
    if not fields["year"].isdigit():
        errors.append("Enter a valid year.")
    if fields["tier"] and fields["tier"] not in ("Gilbert", "Sullivan"):
        errors.append("Choose a valid tier.")
    if fields["result"] and fields["result"] not in AWARD_RESULTS:
        errors.append("Choose a valid result.")
    if not fields["category_name"]:
        errors.append("Enter a category.")
    return errors


@bp.route("/awards")
@login_required
def awards_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    year = request.args.get("year", "").strip()
    category = request.args.get("category", "")
    tier = request.args.get("tier", "")
    result = request.args.get("result", "")
    unmatched = request.args.get("unmatched", "")

    years = [r[0] for r in db.execute("SELECT DISTINCT year FROM historical_results ORDER BY year DESC").fetchall()]
    categories = _award_categories(db)

    query = """
        SELECT historical_results.*, societies.id AS resolved_society_id
        FROM historical_results
        LEFT JOIN societies ON societies.id = historical_results.society_id
        WHERE 1=1
    """
    params = []
    if year.isdigit():
        query += " AND year = ?"
        params.append(int(year))
    if category:
        query += " AND category_name = ?"
        params.append(category)
    if tier in ("Gilbert", "Sullivan"):
        query += " AND tier = ?"
        params.append(tier)
    if result in AWARD_RESULTS:
        query += " AND result = ?"
        params.append(result)
    if unmatched:
        query += " AND historical_results.society_name IS NOT NULL AND historical_results.society_id IS NULL"
    if q:
        query += """ AND (society_name LIKE ? ESCAPE '\\' OR show LIKE ? ESCAPE '\\'
                     OR nominee_name LIKE ? ESCAPE '\\' OR reason LIKE ? ESCAPE '\\')"""
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        params += [like, like, like, like]
    query += " ORDER BY year DESC, category_name, society_name"

    rows = db.execute(query, params).fetchall()

    return render_template(
        "admin/awards_list.html", rows=rows, years=years, categories=categories, results=AWARD_RESULTS,
        selected_year=year, selected_category=category, selected_tier=tier, selected_result=result,
        unmatched=unmatched, q=q,
    )


BULK_AWARD_ROWS = 5


@bp.route("/awards/bulk", methods=("GET", "POST"))
@login_required
def bulk_award():
    db = get_db()
    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()
    categories = _award_categories(db)

    if request.method == "POST":
        year = request.form.get("year", "").strip()
        tier = request.form.get("tier") or None
        category = request.form.get("category", "")
        if category == "__other__":
            category = request.form.get("category_other", "").strip()
        category = category or None
        winner_row = request.form.get("winner_row", "")

        errors = []
        if not year.isdigit():
            errors.append("Enter a valid year.")
        if tier and tier not in ("Gilbert", "Sullivan"):
            errors.append("Choose a valid tier.")
        if not category:
            errors.append("Enter a category.")

        rows = []
        for i in range(BULK_AWARD_ROWS):
            society_id = request.form.get(f"society_id_{i}", "").strip() or None
            show = request.form.get(f"show_{i}", "").strip() or None
            nominee_name = request.form.get(f"nominee_name_{i}", "").strip() or None
            role = request.form.get(f"role_{i}", "").strip() or None

            if not any((society_id, show, nominee_name, role)):
                rows.append(None)
                continue

            society_name = None
            if society_id:
                society_row = db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()
                if society_row is None:
                    errors.append(f"Row {i + 1}: choose a valid society.")
                else:
                    society_name = society_row["name"]

            result = "Winner" if winner_row == str(i) else "Nominee"
            rows.append({
                "society_id": society_id, "society_name": society_name, "show": show,
                "nominee_name": nominee_name, "role": role, "result": result,
            })

        filled_rows = [r for r in rows if r is not None]
        if not filled_rows:
            errors.append("Fill in at least one row.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/award_bulk_form.html", societies=societies, categories=categories,
                bulk_rows=BULK_AWARD_ROWS, form=request.form,
            )

        for row in filled_rows:
            db.execute(
                """
                INSERT INTO historical_results (
                    year, tier, category_name, result, show, society_name, society_id,
                    nominee_name, role, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
                """,
                (
                    int(year), tier, category, row["result"], row["show"],
                    row["society_name"], row["society_id"], row["nominee_name"], row["role"],
                ),
            )
        db.commit()
        flash(f"Added {len(filled_rows)} award record{'s' if len(filled_rows) != 1 else ''}.", "success")
        return redirect(url_for("admin.awards_list"))

    return render_template(
        "admin/award_bulk_form.html", societies=societies, categories=categories,
        bulk_rows=BULK_AWARD_ROWS, form={},
    )


HISTORICAL_PRODUCTION_LINE_RE = re.compile(r"^\s*(\d{4})\s+(.+?)\s*$")
HISTORICAL_PRODUCTION_NOTE_RE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
# See bulk_historical_productions' docstring - "autumn" (Jul-Dec) shows are
# recorded under the following calendar year; "spring" (Jan-Jun) shows and
# already-AIMS-year input both need no adjustment.
HISTORICAL_YEAR_OFFSETS = {"autumn": 1, "spring": 0, "exact": 0}


@bp.route("/historical-productions/bulk", methods=("GET", "POST"))
@login_required
def bulk_historical_productions():
    """Paste a society's own "previous productions" list (one "YEAR Title"
    per line, straight off their website) and add whichever aren't already
    on record as bare historical_results rows - no award/category attached,
    just "this happened". Existing exact (year, show, society) rows are
    skipped rather than duplicated, so the same list can be re-pasted safely
    if it's ever extended.

    AIMS's own year convention is the season's *ending* calendar year, not
    the year the show actually opened (matches how season "23/24" maps to
    SHOWS_COVERAGE_START_YEAR = 2024) - for a society that stages its show
    July-December, that's one year after the production (season "25/26"
    ends in 2026, so an Oct 2025 show is recorded as 2026); for a society
    that stages Jan-June, the production year already IS the AIMS year, no
    adjustment needed. This is a per-society (sometimes per-show) fact, not
    a universal +1 - HISTORICAL_YEAR_OFFSETS below turns the moderator's
    plain-language choice into the right arithmetic."""
    db = get_db()
    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()

    if request.method == "POST":
        society_id = request.form.get("society_id", "").strip()
        lines_raw = request.form.get("lines", "")
        year_convention = request.form.get("year_convention", "autumn")
        if year_convention not in HISTORICAL_YEAR_OFFSETS:
            year_convention = "autumn"

        society = db.execute("SELECT id, name FROM societies WHERE id = ?", (society_id,)).fetchone()
        if society is None:
            flash("Choose a valid society.", "error")
            return render_template(
                "admin/historical_bulk_form.html", societies=societies, form=request.form
            )

        inserted, skipped, unparsed = 0, 0, []
        for raw_line in lines_raw.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = HISTORICAL_PRODUCTION_LINE_RE.match(line)
            if not match:
                unparsed.append(raw_line)
                continue

            year = int(match.group(1))
            title = match.group(2)
            note = None
            note_match = HISTORICAL_PRODUCTION_NOTE_RE.match(title)
            if note_match:
                title, note = note_match.group(1).strip(), note_match.group(2).strip()
            if not title:
                unparsed.append(raw_line)
                continue

            stored_year = year + HISTORICAL_YEAR_OFFSETS[year_convention]

            # Matches ANY existing row for this (year, show, society) - not just
            # a bare one. A society with award-archive coverage for some years
            # (e.g. a Best Overall Show nomination) already has that production
            # on record; inserting a second, bare "this happened" row for the
            # same show would double-count it in every production-count stat.
            already_present = db.execute(
                """
                SELECT 1 FROM historical_results
                WHERE year = ? AND show = ? AND society_id = ?
                """,
                (stored_year, title, society["id"]),
            ).fetchone()
            # Also check the shows table (23/24+) - it has no "year" column,
            # just opening_date, and this tool has no reliable way to know
            # which season a bare "YEAR Title" line would land in, so this
            # matches on title + either the typed or offset-adjusted year
            # appearing anywhere in that show's opening_date. A production
            # already recorded there shouldn't also get a bare
            # historical_results row - same show, counted twice.
            if not already_present:
                already_present = db.execute(
                    """
                    SELECT 1 FROM shows
                    WHERE society_id = ? AND show = ?
                      AND (substr(opening_date, 1, 4) = ? OR substr(opening_date, 1, 4) = ?)
                    """,
                    (society["id"], title, str(year), str(stored_year)),
                ).fetchone()
            if already_present:
                skipped += 1
                continue

            db.execute(
                """
                INSERT INTO historical_results (year, show, society_name, society_id, reason, source)
                VALUES (?, ?, ?, ?, ?, 'manual')
                """,
                (stored_year, title, society["name"], society["id"], note),
            )
            inserted += 1

        db.commit()
        flash(
            f"Added {inserted} production{'s' if inserted != 1 else ''} for {society['name']}"
            f"{f', skipped {skipped} already on record' if skipped else ''}.",
            "success" if inserted else "warning",
        )
        if unparsed:
            flash(
                "Couldn't parse " + str(len(unparsed)) + " line(s) (expected \"YEAR Title\") - "
                "nothing else was skipped because of these: " + "; ".join(unparsed[:5])
                + ("..." if len(unparsed) > 5 else ""),
                "error",
            )
        return redirect(url_for("admin.bulk_historical_productions"))

    return render_template("admin/historical_bulk_form.html", societies=societies, form={})


@bp.route("/awards/new", methods=("GET", "POST"))
@login_required
def new_award():
    db = get_db()
    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()
    categories = _award_categories(db)

    if request.method == "POST":
        fields = _read_award_form(request.form)
        errors = _validate_award(fields)

        society_id = fields["society_id"]
        society_name = None
        if society_id:
            society_row = db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()
            if society_row is None:
                errors.append("Choose a valid society.")
            else:
                society_name = society_row["name"]

        similar_title = None
        if fields["show"] and not request.form.get("confirm_new_title"):
            similar_title = find_close_title(db, fields["show"])
            if similar_title:
                flash(
                    f'A show already on record is titled "{similar_title}" - if that\'s this '
                    "production, use that exact spelling. If it's genuinely a different show, "
                    "tick the box below and save again.",
                    "warning",
                )

        if errors or similar_title:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
                form=request.form, similar_title=similar_title, mode="new",
            )

        db.execute(
            """
            INSERT INTO historical_results (
                year, tier, category_name, result, show, society_name, society_id,
                nominee_name, role, reason, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
            """,
            (
                int(fields["year"]), fields["tier"], fields["category_name"], fields["result"],
                fields["show"], society_name, society_id,
                fields["nominee_name"], fields["role"], fields["reason"],
            ),
        )
        db.commit()
        flash("Award result added.", "success")
        return redirect(url_for("admin.awards_list"))

    return render_template(
        "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
        form={}, mode="new",
    )


@bp.route("/awards/<int:award_id>/edit", methods=("GET", "POST"))
@login_required
def edit_award(award_id):
    db = get_db()
    award = db.execute("SELECT * FROM historical_results WHERE id = ?", (award_id,)).fetchone()
    if award is None:
        abort(404)

    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()
    categories = _award_categories(db)

    if request.method == "POST":
        fields = _read_award_form(request.form)
        errors = _validate_award(fields)

        society_id = fields["society_id"]
        society_name = None
        if society_id:
            society_row = db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()
            if society_row is None:
                errors.append("Choose a valid society.")
            else:
                society_name = society_row["name"]

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
                award=award, form=request.form, mode="edit",
            )

        # Editing through this form - regardless of where the row originally
        # came from - makes it 'manual' from now on, so a future re-run of
        # import_awards.py can never silently discard the edit.
        db.execute(
            """
            UPDATE historical_results SET
                year = ?, tier = ?, category_name = ?, result = ?, show = ?,
                society_name = ?, society_id = ?, nominee_name = ?, role = ?, reason = ?, source = 'manual'
            WHERE id = ?
            """,
            (
                int(fields["year"]), fields["tier"], fields["category_name"], fields["result"],
                fields["show"], society_name, society_id,
                fields["nominee_name"], fields["role"], fields["reason"], award_id,
            ),
        )
        db.commit()
        flash("Award result updated.", "success")
        return redirect(url_for("admin.awards_list"))

    return render_template(
        "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
        award=award, form=dict(award), mode="edit",
    )


@bp.route("/awards/<int:award_id>/delete", methods=("POST",))
@login_required
def delete_award(award_id):
    db = get_db()
    db.execute("DELETE FROM historical_results WHERE id = ?", (award_id,))
    db.commit()
    flash("Award result deleted.", "success")
    return redirect(url_for("admin.awards_list"))
