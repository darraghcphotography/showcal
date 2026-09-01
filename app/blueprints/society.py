import re
from datetime import date, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from ..auth import active_society_code, society_required
from ..calendar_links import google_calendar_url
from ..clock import utcnow_iso
from ..constants import DATE_RE, SHOW_SECTIONS, WARDROBE_ITEM_TYPES, WARDROBE_TERMS, WARDROBE_STATUSES
from ..db import get_db
from .. import notify
from ..rate_limit import limiter
from ..season import season_range
from ..shows import is_upcoming
from ..similarity import find_award_record_match, find_close_title
from ..redirects import came_from, return_to
from ..uploads import save_poster

bp = Blueprint("society", __name__, url_prefix="/society")

SEASON_RE = re.compile(r"^\d{2}/\d{2}$")
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
# Two limits, not one. The per-minute cap stops a burst; the hourly cap is what
# stops patient, low-and-slow guessing, which a minute-only limit happily
# allows forever. Both matter more here than on most login routes because the
# thing being guessed is a short human-readable code rather than a password.
@limiter.limit("10 per minute;40 per hour")
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


@bp.route("/request-access", methods=("GET", "POST"))
@limiter.limit("5 per minute")
def request_access():
    db = get_db()
    if request.method == "POST":
        society_id = request.form.get("society_id", type=int)
        name = request.form.get("requester_name", "").strip()
        email = request.form.get("requester_email", "").strip()
        role = request.form.get("requester_role", "").strip() or "Committee Officer"

        soc = db.execute("SELECT id, name FROM societies WHERE id = ?", (society_id,)).fetchone() if society_id else None
        if not soc:
            flash("Please choose your society from the list.", "error")
            return redirect(url_for("society.request_access"))

        if not name or not email:
            flash("Please enter both your name and email address.", "error")
            return redirect(url_for("society.request_access"))

        import secrets
        token = secrets.token_urlsafe(32)
        db.execute(
            """
            INSERT INTO society_access_requests (
                society_id, requester_name, requester_email, requester_role, token, status
            ) VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (society_id, name, email, role, token),
        )
        db.commit()

        notify.send(
            f"New Society Access Request: {soc['name']}",
            f"{name} ({role}) has requested 1-click access to manage {soc['name']}.\n\n"
            f"Requester Email: {email}\n"
            f"Role: {role}\n\n"
            f"Approve or reject on your phone:\n{notify.link(url_for('admin.access_requests'))}\n",
        )

        return render_template("society_request_thanks.html", requester_name=name, requester_email=email)

    selected_society_id = request.args.get("society_id", type=int)
    societies = db.execute("SELECT id, name, region FROM societies WHERE NOT hidden ORDER BY name").fetchall()
    return render_template("society_request_access.html", societies=societies, selected_society_id=selected_society_id)


@bp.route("/auth/<token>")
@limiter.limit("15 per minute")
def auth_magic_link(token: str):
    db = get_db()
    req = db.execute(
        """
        SELECT req.*, societies.name AS society_name
        FROM society_access_requests req
        JOIN societies ON societies.id = req.society_id
        WHERE req.token = ?
        """,
        (token,),
    ).fetchone()

    if not req or req["status"] not in ("approved", "used"):
        flash("This login link is either invalid, expired, or pending approval. You can request a fresh link anytime.", "error")
        return redirect(url_for("society.login"))

    today_str = date.today().isoformat()
    if req["expires_at"] and req["expires_at"] < today_str:
        flash("This login link has expired. Please request a fresh link.", "error")
        return redirect(url_for("society.login"))

    if not req["invite_code_id"]:
        flash("Unable to authenticate session. Please contact the administrator.", "error")
        return redirect(url_for("society.login"))

    session["society_code_id"] = req["invite_code_id"]
    flash(f"Welcome, {req['requester_name']}! You are logged in to manage {req['society_name']}.", "success")
    return redirect(url_for("society.dashboard"))


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
    # Flagged per row rather than computed in the template, so "upcoming" is
    # one definition. Only upcoming shows are prompted: a poster is
    # promotional material for a run that hasn't happened, and nagging a
    # society about a 1998 production they'll never have artwork for is how a
    # prompt gets ignored entirely. Same reasoning as the admin counter's
    # MISSING_POSTER_WHERE.
    today = date.today().isoformat()
    shows = [
        dict(s, wants_poster=(
            s["show"] is not None
            and s["poster_filename"] is None
            and s["opening_date"] is not None
            and s["opening_date"] >= today
        ))
        for s in shows
    ]
    return render_template(
        "society_dashboard.html", society=society, shows=shows,
        poster_wanted_count=sum(1 for s in shows if s["wants_poster"]),
    )


def _read_form(form, suffix=""):
    """suffix lets the bulk-add form (society_bulk_form.html) reuse this on
    fields named e.g. "season_3" for row 3, rather than re-implementing its
    own field-by-field extraction."""
    def get(key):
        return form.get(f"{key}{suffix}", "").strip()

    return {
        "season": get("season"),
        "show": get("show"),
        "section": form.get(f"section{suffix}") or None,
        "opening_date": get("opening_date") or None,
        "closing_date": get("closing_date") or None,
        "venue": get("venue") or None,
        "director": get("director") or None,
        "musical_director": get("musical_director") or None,
        "choreographer": get("choreographer") or None,
        "ticket_url": get("ticket_url") or None,
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
                return_path=request.form.get("next"),
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
                utcnow_iso(), show_id,
            ),
        )
        db.commit()
        flash("Show updated.", "success")
        return redirect(return_to(url_for("society.dashboard")))

    return render_template(
        "society_show_form.html", society=society, sections=SHOW_SECTIONS, seasons=season_range(db),
        show=show, mode="edit", gcal_adjudication_url=gcal_adjudication_url,
        return_path=came_from(),
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
            fields = _read_form(request.form, suffix=f"_{i}")

            if not any(fields.values()):
                rows.append(None)
                continue

            errors = _validate(fields, require_title=True)

            similar_title = None
            if fields["show"] and not request.form.get(f"confirm_{i}"):
                similar_title = find_close_title(db, fields["show"])

            rows.append({
                **fields, "errors": errors, "similar_title": similar_title,
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


@bp.route("/bulk-credits", methods=("GET", "POST"))
@society_required
def bulk_credits():
    db = get_db()
    society, code = _current_society(db)

    if request.method == "POST":
        i = 0
        updated = 0
        errors = []
        updates = []
        while f"show_id_{i}" in request.form:
            show_id = request.form.get(f"show_id_{i}")
            director = request.form.get(f"director_{i}", "").strip() or None
            musical_director = request.form.get(f"musical_director_{i}", "").strip() or None
            choreographer = request.form.get(f"choreographer_{i}", "").strip() or None
            venue = request.form.get(f"venue_{i}", "").strip() or None
            opening_date = request.form.get(f"opening_date_{i}", "").strip() or None
            closing_date = request.form.get(f"closing_date_{i}", "").strip() or None

            for label, val in (("Opening date", opening_date), ("Closing date", closing_date)):
                if val and not DATE_RE.match(val):
                    errors.append(f"Row {i + 1}: {label} '{val}' must be YYYY-MM-DD.")

            updates.append({
                "id": show_id,
                "director": director,
                "musical_director": musical_director,
                "choreographer": choreographer,
                "venue": venue,
                "opening_date": opening_date,
                "closing_date": closing_date,
            })
            i += 1

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            for u in updates:
                current = db.execute(
                    "SELECT director, musical_director, choreographer, venue, opening_date, closing_date FROM shows WHERE id = ? AND society_id = ?",
                    (u["id"], society["id"]),
                ).fetchone()
                if current and (
                    current["director"] != u["director"] or
                    current["musical_director"] != u["musical_director"] or
                    current["choreographer"] != u["choreographer"] or
                    current["venue"] != u["venue"] or
                    current["opening_date"] != u["opening_date"] or
                    current["closing_date"] != u["closing_date"]
                ):
                    db.execute(
                        """
                        UPDATE shows SET
                            director = ?, musical_director = ?, choreographer = ?,
                            venue = ?, opening_date = ?, closing_date = ?, updated_at = ?
                        WHERE id = ? AND society_id = ?
                        """,
                        (u["director"], u["musical_director"], u["choreographer"], u["venue"], u["opening_date"], u["closing_date"], utcnow_iso(), u["id"], society["id"]),
                    )
                    updated += 1
            db.commit()
            if updated:
                flash(f"Successfully saved credits for {updated} production{'s' if updated != 1 else ''}.", "success")
            else:
                flash("No changes detected.", "info")
        return redirect(url_for("society.bulk_credits"))

    shows = db.execute(
        """
        SELECT id, season, show, section, opening_date, closing_date, venue, director, musical_director, choreographer
        FROM shows
        WHERE society_id = ? AND moderation_status = 'approved'
        ORDER BY season DESC, opening_date DESC
        """,
        (society["id"],),
    ).fetchall()

    venues = [r[0] for r in db.execute("SELECT DISTINCT name FROM venues ORDER BY name").fetchall()]
    return render_template("society_bulk_credits.html", society=society, shows=shows, venues=venues)


# --- Society Wardrobe & Props Vault ---

@bp.route("/vault")
@society_required
def vault():
    db = get_db()
    society, code = _current_society(db)
    items = db.execute(
        """
        SELECT wi.*, 
               (SELECT COUNT(*) FROM wardrobe_photos WHERE item_id = wi.id) AS photo_count
        FROM wardrobe_items wi
        WHERE wi.society_id = ?
        ORDER BY wi.created_at DESC
        """,
        (society["id"],),
    ).fetchall()
    return render_template(
        "society_vault.html",
        society=society,
        items=items,
        item_types=WARDROBE_ITEM_TYPES,
        terms_labels=WARDROBE_TERMS,
        status_labels=WARDROBE_STATUSES,
    )


@bp.route("/vault/new", methods=("GET", "POST"))
@society_required
def vault_new():
    db = get_db()
    society, code = _current_society(db)

    past_shows = [
        row["show"]
        for row in db.execute(
            "SELECT DISTINCT show FROM shows WHERE society_id = ? AND show IS NOT NULL ORDER BY show",
            (society["id"],),
        ).fetchall()
    ]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        item_type = request.form.get("item_type", "").strip()
        show_title = request.form.get("show_title", "").strip() or None
        description = request.form.get("description", "").strip() or None
        sizing_quantity = request.form.get("sizing_quantity", "").strip() or None
        terms = request.form.get("terms", "hire").strip()
        status = request.form.get("status", "available").strip()
        # A listing carries the society's own shared address and nothing else.
        # It used to collect a named individual and a personal mobile, which
        # were then rendered on a public, indexable page - see the exchange
        # privacy fix. The narrower the field, the less there is to protect.
        contact_email = request.form.get("contact_email", "").strip() or None
        agree_terms = request.form.get("agree_terms")

        if not title:
            flash("Please enter a title / name for this item or wardrobe set.", "error")
            return redirect(url_for("society.vault_new"))

        if item_type not in WARDROBE_ITEM_TYPES:
            flash("Please choose a valid category.", "error")
            return redirect(url_for("society.vault_new"))

        if terms not in WARDROBE_TERMS:
            terms = "hire"

        if status not in WARDROBE_STATUSES:
            status = "available"

        if not agree_terms:
            flash("Please confirm the community guideline & non-liability acknowledgment.", "error")
            return redirect(url_for("society.vault_new"))

        photos = request.files.getlist("photos")
        primary_photo = None
        saved_filenames = []
        upload_dir = current_app.config["UPLOAD_DIR"]

        for p in photos:
            if p and p.filename:
                fn = save_poster(p, upload_dir)
                if fn:
                    saved_filenames.append(fn)
                    if not primary_photo:
                        primary_photo = fn

        cur = db.execute(
            """
            INSERT INTO wardrobe_items (
                society_id, show_title, title, item_type, description,
                sizing_quantity, terms, status, contact_email,
                primary_photo, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                society["id"], show_title, title, item_type, description,
                sizing_quantity, terms, status, contact_email, primary_photo,
            ),
        )
        item_id = cur.lastrowid

        for idx, fn in enumerate(saved_filenames):
            db.execute(
                "INSERT INTO wardrobe_photos (item_id, filename, display_order) VALUES (?, ?, ?)",
                (item_id, fn, idx),
            )

        db.commit()
        flash(f"Listed '{title}' in your society's vault!", "success")
        return redirect(url_for("society.vault"))

    return render_template(
        "society_vault_form.html",
        society=society,
        item=None,
        photos=[],
        past_shows=past_shows,
        item_types=WARDROBE_ITEM_TYPES,
        terms_labels=WARDROBE_TERMS,
        status_labels=WARDROBE_STATUSES,
    )


@bp.route("/vault/<int:item_id>/edit", methods=("GET", "POST"))
@society_required
def vault_edit(item_id):
    db = get_db()
    society, code = _current_society(db)

    item = db.execute(
        "SELECT * FROM wardrobe_items WHERE id = ? AND society_id = ?",
        (item_id, society["id"]),
    ).fetchone()
    if not item:
        abort(404)

    past_shows = [
        row["show"]
        for row in db.execute(
            "SELECT DISTINCT show FROM shows WHERE society_id = ? AND show IS NOT NULL ORDER BY show",
            (society["id"],),
        ).fetchall()
    ]
    photos = db.execute(
        "SELECT * FROM wardrobe_photos WHERE item_id = ? ORDER BY display_order, id",
        (item_id,),
    ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        item_type = request.form.get("item_type", "").strip()
        show_title = request.form.get("show_title", "").strip() or None
        description = request.form.get("description", "").strip() or None
        sizing_quantity = request.form.get("sizing_quantity", "").strip() or None
        terms = request.form.get("terms", "hire").strip()
        status = request.form.get("status", "available").strip()
        contact_email = request.form.get("contact_email", "").strip() or None

        if not title:
            flash("Please enter a title for this item.", "error")
            return redirect(url_for("society.vault_edit", item_id=item_id))

        if item_type not in WARDROBE_ITEM_TYPES:
            item_type = item["item_type"]

        primary_photo = item["primary_photo"]
        upload_dir = current_app.config["UPLOAD_DIR"]
        new_photos = request.files.getlist("photos")

        for p in new_photos:
            if p and p.filename:
                fn = save_poster(p, upload_dir)
                if fn:
                    if not primary_photo:
                        primary_photo = fn
                    db.execute(
                        "INSERT INTO wardrobe_photos (item_id, filename) VALUES (?, ?)",
                        (item_id, fn),
                    )

        db.execute(
            """
            UPDATE wardrobe_items SET
                show_title = ?, title = ?, item_type = ?, description = ?,
                sizing_quantity = ?, terms = ?, status = ?,
                contact_email = ?, primary_photo = ?,
                -- Cleared, not merely left alone: an item edited after this
                -- change should shed any personal details it was created with
                -- under the old form, without anyone having to remember to.
                contact_name = NULL, contact_phone = NULL,
                updated_at = datetime('now')
            WHERE id = ? AND society_id = ?
            """,
            (
                show_title, title, item_type, description,
                sizing_quantity, terms, status,
                contact_email, primary_photo,
                item_id, society["id"],
            ),
        )
        db.commit()
        flash(f"Updated '{title}'.", "success")
        return redirect(url_for("society.vault"))

    return render_template(
        "society_vault_form.html",
        society=society,
        item=item,
        photos=photos,
        past_shows=past_shows,
        item_types=WARDROBE_ITEM_TYPES,
        terms_labels=WARDROBE_TERMS,
        status_labels=WARDROBE_STATUSES,
    )


@bp.route("/vault/<int:item_id>/status", methods=("POST",))
@society_required
def vault_toggle_status(item_id):
    db = get_db()
    society, code = _current_society(db)
    new_status = request.form.get("status", "available").strip()
    if new_status not in WARDROBE_STATUSES:
        new_status = "available"

    db.execute(
        "UPDATE wardrobe_items SET status = ?, updated_at = datetime('now') WHERE id = ? AND society_id = ?",
        (new_status, item_id, society["id"]),
    )
    db.commit()
    flash(f"Status updated to '{WARDROBE_STATUSES[new_status]}'.", "success")
    return redirect(url_for("society.vault"))


@bp.route("/vault/<int:item_id>/delete", methods=("POST",))
@society_required
def vault_delete(item_id):
    db = get_db()
    society, code = _current_society(db)
    db.execute("DELETE FROM wardrobe_items WHERE id = ? AND society_id = ?", (item_id, society["id"]))
    db.commit()
    flash("Item removed from your vault.", "success")
    return redirect(url_for("society.vault"))

