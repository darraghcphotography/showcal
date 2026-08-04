import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from .. import notify
from ..auth import active_invite_code, invite_required
from ..db import get_db
from ..rate_limit import limiter
from ..season import current_season, next_season
from ..similarity import find_close_title
from ..uploads import save_poster

bp = Blueprint("submit", __name__, url_prefix="/submit")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _season_options(db):
    current = current_season(db)
    return [current, next_season(current)]


@bp.route("/unlock", methods=("GET", "POST"))
@limiter.limit("10 per minute")
def unlock():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        row = get_db().execute(
            "SELECT * FROM invite_codes WHERE code = ? COLLATE NOCASE AND is_active = 1", (code,)
        ).fetchone()
        if row is None:
            flash("That invite code isn't valid. Check with your society secretary or AIMS.", "error")
        else:
            session["invite_code_id"] = row["id"]
            return redirect(url_for("submit.new"))
    return render_template("submit_unlock.html")


@bp.route("/new", methods=("GET", "POST"))
@invite_required
@limiter.limit("5 per minute")
def new():
    db = get_db()
    societies = db.execute("SELECT id, name, region, section FROM societies ORDER BY name").fetchall()
    season_options = _season_options(db)

    if request.method == "POST":
        # Honeypot: a real visitor never fills this hidden field in.
        if request.form.get("website", ""):
            return redirect(url_for("submit.thanks"))

        errors = []
        society_name = request.form.get("society", "").strip()
        season = request.form.get("season", "").strip()
        show_title = request.form.get("show", "").strip()
        opening_date = request.form.get("opening_date", "").strip()
        closing_date = request.form.get("closing_date", "").strip()
        venue = request.form.get("venue", "").strip()
        director = request.form.get("director", "").strip()
        musical_director = request.form.get("musical_director", "").strip()
        choreographer = request.form.get("choreographer", "").strip()
        ticket_url = request.form.get("ticket_url", "").strip()
        adjudicated = request.form.get("adjudicated", "yes")

        # society is a free-text input backed by a <datalist> (searchable on
        # mobile, unlike a 179-option <select>) - so unlike a dropdown, the
        # browser doesn't guarantee the value is actually one of the options.
        society = db.execute("SELECT * FROM societies WHERE name = ?", (society_name,)).fetchone()
        if society is None:
            errors.append("Choose a society from the list (start typing and pick a suggestion).")
        if not show_title:
            errors.append("Show title is required.")
        if season not in season_options:
            errors.append("Choose a valid season.")
        for label, value in (("Opening date", opening_date), ("Closing date", closing_date)):
            if value and not DATE_RE.match(value):
                errors.append(f"{label} must be a valid date.")
        if adjudicated not in ("yes", "no"):
            errors.append("Choose whether this show is being adjudicated.")

        similar_title = None
        if show_title and not request.form.get("confirm_new_title"):
            similar_title = find_close_title(db, show_title)
            if similar_title:
                flash(
                    f'A show already on record is titled "{similar_title}" - if that\'s this '
                    "production, please use that exact spelling. If it's genuinely a different "
                    "show, tick the box below and submit again.",
                    "warning",
                )

        poster_filename = None
        poster_file = request.files.get("poster")
        if poster_file and poster_file.filename:
            try:
                poster_filename = save_poster(poster_file, current_app.config["UPLOAD_DIR"])
            except ValueError as e:
                errors.append(str(e))

        if errors or similar_title:
            for e in errors:
                flash(e, "error")
            return render_template(
                "submit_new.html", societies=societies, form=request.form, season_options=season_options,
                similar_title=similar_title,
            )

        invite_code = active_invite_code()
        # A blank "TBA" placeholder (e.g. from the CSV import - "society
        # slotted for this season, title TBA") shares this submission's
        # natural key (society + season) only when its own title is also
        # blank, so a real title here would otherwise insert a *second* row
        # alongside the stale placeholder instead of replacing it. Delete it
        # first so this submission takes its place - moderation still
        # applies as normal below, so the show simply won't show anywhere
        # publicly until approved, same as any other new submission.
        db.execute(
            "DELETE FROM shows WHERE society_id = ? AND season = ? AND show IS NULL AND moderation_status = 'approved'",
            (society["id"], season),
        )
        db.execute(
            """
            INSERT INTO shows (
                society_id, season, region, section, show,
                opening_date, closing_date,
                venue, director, musical_director, choreographer,
                ticket_url, poster_filename, review_status, moderation_status, source, invite_code_id
            ) VALUES (
                :society_id, :season, :region, :section, :show,
                :opening_date, :closing_date,
                :venue, :director, :musical_director, :choreographer,
                :ticket_url, :poster_filename, :review_status, 'pending', 'submission', :invite_code_id
            )
            """,
            {
                "society_id": society["id"],
                "season": season,
                "region": society["region"],
                "section": society["section"] if society["section"] != "Inactive" else None,
                "show": show_title,
                "opening_date": opening_date or None,
                "closing_date": closing_date or None,
                "venue": venue or society["default_venue"],
                "director": director or None,
                "musical_director": musical_director or None,
                "choreographer": choreographer or None,
                "ticket_url": ticket_url or None,
                "poster_filename": poster_filename,
                "review_status": "Scheduled" if adjudicated == "yes" else "Not adjudicated",
                "invite_code_id": invite_code["id"] if invite_code else None,
            },
        )
        db.commit()
        notify.send(
            f"New show submission: {society['name']} - {show_title}",
            f'{society["name"]} submitted "{show_title}" for season {season}.\n\n'
            f"Review it: {notify.link(url_for('admin.queue'))}",
        )
        return redirect(url_for("submit.thanks"))

    return render_template("submit_new.html", societies=societies, form={}, season_options=season_options)


@bp.route("/thanks")
def thanks():
    return render_template("submit_thanks.html")
