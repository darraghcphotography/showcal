import re
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from ..auth import active_society_code, society_required
from ..calendar_links import google_calendar_url
from ..constants import SHOW_SECTIONS
from ..db import get_db
from ..rate_limit import limiter
from ..season import season_range
from ..shows import is_upcoming
from ..similarity import find_award_record_match, find_close_title
from ..uploads import save_poster

bp = Blueprint("society", __name__, url_prefix="/society")

SEASON_RE = re.compile(r"^\d{2}/\d{2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://")
BULK_ROWS = 10

PROFILE_URL_FIELDS = (
    ("Website", "website_url"), ("Facebook", "facebook_url"),
    ("Instagram", "instagram_url"), ("TikTok", "tiktok_url"),
    ("Other link", "other_url"),
)


def _current_society(db):
    code = active_society_code()
    return db.execute("SELECT * FROM societies WHERE id = ?", (code["society_id"],)).fetchone(), code


@bp.route("/login", methods=("GET", "POST"))
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        row = get_db().execute(
            "SELECT * FROM invite_codes WHERE code = ? COLLATE NOCASE AND is_active = 1 AND society_id IS NOT NULL",
            (code,),
        ).fetchone()
        if row is None:
            flash("That's not a valid society login code. Check with your site admin if you think this is wrong.", "error")
        else:
            session["society_code_id"] = row["id"]
            return redirect(url_for("society.dashboard"))
    return render_template("society_login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    session.pop("society_code_id", None)
    return redirect(url_for("public.index"))


@bp.route("/")
@society_required
def dashboard():
    db = get_db()
    society, _ = _current_society(db)
    shows = db.execute(
        "SELECT * FROM shows WHERE society_id = ? ORDER BY season DESC, show",
        (society["id"],),
    ).fetchall()
    return render_template("society_dashboard.html", society=society, shows=shows)


def _read_form(form):
    return {
        "season": form.get("season", "").strip(),
        "show": form.get("show", "").strip(),
        "section": form.get("section") or None,
        "opening_date": form.get("opening_date", "").strip() or None,
        "closing_date": form.get("closing_date", "").strip() or None,
        "venue": form.get("venue", "").strip() or None,
        "director": form.get("director", "").strip() or None,
        "musical_director": form.get("musical_director", "").strip() or None,
        "choreographer": form.get("choreographer", "").strip() or None,
        "ticket_url": form.get("ticket_url", "").strip() or None,
    }


def _validate(fields, require_title):
    errors = []
    if require_title and not fields["show"]:
        errors.append("Show title is required.")
    if not SEASON_RE.match(fields["season"]):
        errors.append("Season must be in the form YY/YY, e.g. 04/05.")
    for label, key in (("Opening date", "opening_date"), ("Closing date", "closing_date")):
        if fields[key] and not DATE_RE.match(fields[key]):
            errors.append(f"{label} must be a valid date.")
    if fields["section"] and fields["section"] not in SHOW_SECTIONS:
        errors.append("Choose a valid tier.")
    return errors


def _adjudication_reminder_url(show):
    """"Remind me to check adjudication forms were submitted" calendar link
    for the show's own committee - only useful while the show hasn't
    happened yet and it's actually being adjudicated at all. Public-page
    version of this was removed (see public.show_detail()) since a random
    visitor has no reason to want this reminder on their own calendar."""
    if not is_upcoming(show) or show["review_status"] == "Not adjudicated":
        return None
    opening = date.fromisoformat(show["opening_date"])
    reminder = opening - timedelta(weeks=8)
    return google_calendar_url(
        text=f"CHECK ADJUDICATION FORMS WERE SUBMITTED - {show['show']}",
        start=reminder,
        end_exclusive=reminder + timedelta(days=1),
        details=(
            f"AIMS requires an adjudication application at least 6 weeks before opening night. "
            f"{show['show']} opens {opening.isoformat()} - double check the forms are in."
        ),
    )


@bp.route("/logo", methods=("POST",))
@society_required
def set_logo():
    db = get_db()
    society, _ = _current_society(db)

    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        try:
            filename = save_poster(logo_file, current_app.config["UPLOAD_DIR"])
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("society.dashboard"))
        db.execute("UPDATE societies SET logo_filename = ? WHERE id = ?", (filename, society["id"]))
        db.commit()
        flash("Logo updated.", "success")
    return redirect(url_for("society.dashboard"))


@bp.route("/profile", methods=("GET", "POST"))
@society_required
def edit_profile():
    db = get_db()
    society, _ = _current_society(db)

    if request.method == "POST":
        fields = {
            "about": request.form.get("about", "").strip() or None,
            "website_url": request.form.get("website_url", "").strip() or None,
            "facebook_url": request.form.get("facebook_url", "").strip() or None,
            "instagram_url": request.form.get("instagram_url", "").strip() or None,
            "tiktok_url": request.form.get("tiktok_url", "").strip() or None,
            "other_url": request.form.get("other_url", "").strip() or None,
            "other_label": request.form.get("other_label", "").strip() or None,
        }
        # A link typed in here ends up in an <a href="..."> on this
        # society's public page for every visitor - Jinja's autoescaping
        # protects the text content but not the URL scheme, so a
        # javascript:/data: URL must be rejected outright rather than
        # silently stripped.
        errors = [
            f"{label} must start with http:// or https://"
            for label, key in PROFILE_URL_FIELDS
            if fields[key] and not URL_RE.match(fields[key])
        ]
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("society_profile_form.html", society=society, form=request.form)

        db.execute(
            """
            UPDATE societies SET
                about = :about, website_url = :website_url, facebook_url = :facebook_url,
                instagram_url = :instagram_url, tiktok_url = :tiktok_url,
                other_url = :other_url, other_label = :other_label
            WHERE id = :id
            """,
            {**fields, "id": society["id"]},
        )
        db.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("society.dashboard"))

    return render_template("society_profile_form.html", society=society, form=society)


@bp.route("/shows/new", methods=("GET", "POST"))
@society_required
def new_show():
    db = get_db()
    society, code = _current_society(db)

    if request.method == "POST":
        if request.form.get("website", ""):  # honeypot
            return redirect(url_for("society.dashboard"))

        fields = _read_form(request.form)
        errors = _validate(fields, require_title=True)

        similar_title = None
        if fields["show"] and not request.form.get("confirm_new_title"):
            similar_title = find_close_title(db, fields["show"])
            if similar_title:
                flash(
                    f'A show already on record is titled "{similar_title}" - if that\'s this '
                    "production, please use that exact spelling. If it's genuinely a different "
                    "show, tick the box below and save again.",
                    "warning",
                )

        # A separate check from the title-duplicate one above: this catches
        # the same production already sitting in the older awards archive
        # under this same society and season (see similarity.find_award_
        # record_match) - adding it again here would double-count it in any
        # production total that sums both sources.
        award_match = None
        if fields["show"] and SEASON_RE.match(fields["season"]) and not request.form.get("confirm_double_count"):
            award_match = find_award_record_match(db, society["id"], fields["show"], fields["season"])
            if award_match:
                flash(
                    f'Your society already has an award-archive record for "{award_match}" in this '
                    "season - if that's this production, no need to add it again (it's already "
                    "counted). If it's genuinely a different show, tick the box below and save again.",
                    "warning",
                )

        poster_filename = None
        poster_file = request.files.get("poster")
        if poster_file and poster_file.filename:
            try:
                poster_filename = save_poster(poster_file, current_app.config["UPLOAD_DIR"])
            except ValueError as e:
                errors.append(str(e))

        if errors or similar_title or award_match:
            for e in errors:
                flash(e, "error")
            return render_template(
                "society_show_form.html", society=society, sections=SHOW_SECTIONS, seasons=season_range(db),
                form=request.form, similar_title=similar_title, award_match=award_match, mode="new",
            )

        db.execute(
            """
            INSERT INTO shows (
                society_id, season, region, section, show,
                opening_date, closing_date, venue, director, musical_director, choreographer,
                ticket_url, poster_filename, review_status, moderation_status, source, invite_code_id
            ) VALUES (
                :society_id, :season, :region, :section, :show,
                :opening_date, :closing_date, :venue, :director, :musical_director, :choreographer,
                :ticket_url, :poster_filename, 'None', 'approved', 'submission', :invite_code_id
            )
            """,
            {
                "society_id": society["id"],
                "season": fields["season"],
                "region": society["region"],
                "section": fields["section"],
                "show": fields["show"],
                "opening_date": fields["opening_date"],
                "closing_date": fields["closing_date"],
                "venue": fields["venue"] or society["default_venue"],
                "director": fields["director"],
                "musical_director": fields["musical_director"],
                "choreographer": fields["choreographer"],
                "ticket_url": fields["ticket_url"],
                "poster_filename": poster_filename,
                "invite_code_id": code["id"],
            },
        )
        db.commit()
        flash("Show added - it's live now.", "success")
        return redirect(url_for("society.dashboard"))

    return render_template(
        "society_show_form.html", society=society, sections=SHOW_SECTIONS, seasons=season_range(db),
        form={}, mode="new",
    )


@bp.route("/shows/<int:show_id>/edit", methods=("GET", "POST"))
@society_required
def edit_show(show_id):
    db = get_db()
    society, _ = _current_society(db)
    show = db.execute(
        "SELECT * FROM shows WHERE id = ? AND society_id = ?", (show_id, society["id"])
    ).fetchone()
    if show is None:
        abort(404)

    gcal_adjudication_url = _adjudication_reminder_url(show)

    if request.method == "POST":
        fields = _read_form(request.form)
        errors = _validate(fields, require_title=False)

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
            return render_template(
                "society_show_form.html", society=society, sections=SHOW_SECTIONS, seasons=season_range(db),
                show=show, mode="edit", gcal_adjudication_url=gcal_adjudication_url,
            )

        # Deliberately no review_status/review_url here - a society login can
        # never touch those, regardless of what a tampered POST body sends.
        db.execute(
            """
            UPDATE shows SET
                season = ?, section = ?, show = ?, opening_date = ?, closing_date = ?,
                venue = ?, director = ?, musical_director = ?, choreographer = ?,
                ticket_url = ?, poster_filename = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                fields["season"], fields["section"], fields["show"] or None,
                fields["opening_date"], fields["closing_date"],
                fields["venue"], fields["director"], fields["musical_director"], fields["choreographer"],
                fields["ticket_url"], poster_filename,
                datetime.utcnow().isoformat(), show_id,
            ),
        )
        db.commit()
        flash("Show updated.", "success")
        return redirect(url_for("society.dashboard"))

    return render_template(
        "society_show_form.html", society=society, sections=SHOW_SECTIONS, seasons=season_range(db),
        show=show, mode="edit", gcal_adjudication_url=gcal_adjudication_url,
    )


@bp.route("/shows/bulk", methods=("GET", "POST"))
@society_required
def bulk_add():
    db = get_db()
    society, code = _current_society(db)

    if request.method == "POST":
        if request.form.get("website", ""):  # honeypot
            return redirect(url_for("society.dashboard"))

        rows = []
        has_problems = False
        for i in range(BULK_ROWS):
            season = request.form.get(f"season_{i}", "").strip()
            show = request.form.get(f"show_{i}", "").strip()
            opening_date = request.form.get(f"opening_date_{i}", "").strip() or None
            closing_date = request.form.get(f"closing_date_{i}", "").strip() or None
            venue = request.form.get(f"venue_{i}", "").strip() or None
            director = request.form.get(f"director_{i}", "").strip() or None
            musical_director = request.form.get(f"musical_director_{i}", "").strip() or None
            choreographer = request.form.get(f"choreographer_{i}", "").strip() or None

            if not any((season, show, opening_date, closing_date, venue, director, musical_director, choreographer)):
                rows.append(None)
                continue

            errors = []
            if not show:
                errors.append("Show title is required.")
            if not SEASON_RE.match(season):
                errors.append("Season must be in the form YY/YY, e.g. 04/05.")
            for label, value in (("Opening date", opening_date), ("Closing date", closing_date)):
                if value and not DATE_RE.match(value):
                    errors.append(f"{label} must be a valid date.")

            similar_title = None
            if show and not request.form.get(f"confirm_{i}"):
                similar_title = find_close_title(db, show)

            rows.append({
                "season": season, "show": show, "opening_date": opening_date, "closing_date": closing_date,
                "venue": venue, "director": director, "musical_director": musical_director,
                "choreographer": choreographer, "errors": errors, "similar_title": similar_title,
            })
            if errors or similar_title:
                has_problems = True

        if has_problems:
            for i, row in enumerate(rows):
                if row is None:
                    continue
                for e in row["errors"]:
                    flash(f"Row {i + 1}: {e}", "error")
                if row["similar_title"]:
                    flash(
                        f'Row {i + 1}: a show already on record is titled "{row["similar_title"]}" - '
                        "tick that row's confirm box if it's genuinely a different show, or fix the spelling.",
                        "warning",
                    )
            return render_template(
                "society_bulk_form.html", society=society, rows=rows, bulk_rows=BULK_ROWS,
                seasons=season_range(db),
            )

        inserted = 0
        for row in rows:
            if row is None:
                continue
            db.execute(
                """
                INSERT INTO shows (
                    society_id, season, region, show, opening_date, closing_date, venue,
                    director, musical_director, choreographer,
                    review_status, moderation_status, source, invite_code_id
                ) VALUES (
                    :society_id, :season, :region, :show, :opening_date, :closing_date, :venue,
                    :director, :musical_director, :choreographer,
                    'None', 'approved', 'submission', :invite_code_id
                )
                """,
                {
                    "society_id": society["id"],
                    "season": row["season"],
                    "region": society["region"],
                    "show": row["show"],
                    "opening_date": row["opening_date"],
                    "closing_date": row["closing_date"],
                    "venue": row["venue"] or society["default_venue"],
                    "director": row["director"],
                    "musical_director": row["musical_director"],
                    "choreographer": row["choreographer"],
                    "invite_code_id": code["id"],
                },
            )
            inserted += 1
        db.commit()
        flash(
            f"Added {inserted} show{'s' if inserted != 1 else ''} - keep going below, or head back to the dashboard.",
            "success",
        )
        return redirect(url_for("society.bulk_add"))

    return render_template(
        "society_bulk_form.html", society=society, rows=[None] * BULK_ROWS, bulk_rows=BULK_ROWS,
        seasons=season_range(db),
    )
