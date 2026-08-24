import json

from flask import abort, current_app, flash, redirect, render_template, request, url_for

from ...auth import current_user, login_required
from ...constants import REGIONS, SOCIETY_SECTIONS
from ...db import get_db
from ...uploads import save_poster
from . import bp
from ._shared import URL_RE
from .auth import _generate_invite_code, admin_required

# The historical-regions form's third answer, alongside a real region and
# leaving it on skip. Can't collide with a region name or with the empty string
# that means skip.
NO_REGION = "__none__"

PROFILE_URL_FIELDS = (
    ("Website", "website_url"), ("Facebook", "facebook_url"),
    ("Instagram", "instagram_url"), ("TikTok", "tiktok_url"),
    ("Other link", "other_url"),
)


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
        founded_year_raw = request.form.get("founded_year", "").strip()
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

        founded_year = None
        if founded_year_raw:
            try:
                founded_year = int(founded_year_raw)
            except ValueError:
                errors.append("Founded year must be a number.")

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
                tiktok_url = ?, other_url = ?, other_label = ?, hidden = ?, founded_year = ?
            WHERE id = ?
            """,
            (
                name, region, section, section_as_of, section_history, notes, default_venue, logo_filename,
                profile_fields["about"], profile_fields["website_url"], profile_fields["facebook_url"],
                profile_fields["instagram_url"], profile_fields["tiktok_url"], profile_fields["other_url"],
                profile_fields["other_label"], hidden, founded_year, society_id,
            ),
        )

        # shows.section is a deliberate snapshot (schema.sql), not a live
        # mirror - so this cascade is scoped tightly to the one season this
        # edit actually claims to speak for (section_as_of), and only to
        # shows that haven't happened yet. A show that's already run keeps
        # the section it actually ran under; a re-tiering discovered after
        # the fact (this one: 23 shows across 23 societies, all season
        # 26/27, all still to come) shouldn't rewrite settled history.
        if section != society["section"] and section_as_of:
            updated = db.execute(
                """
                UPDATE shows SET section = ?
                 WHERE society_id = ? AND season = ? AND section IS NOT NULL AND section != ?
                   AND (opening_date IS NULL OR opening_date >= date('now'))
                """,
                (section, society_id, section_as_of, section),
            ).rowcount
            if updated:
                flash(f"Also updated {updated} not-yet-run show{'s' if updated != 1 else ''} "
                      f"for {section_as_of} to match.", "success")

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
        WHERE hsr.confirmed_region IS NULL AND hsr.no_region = 0
        GROUP BY hsr.society_name
        ORDER BY record_count DESC, hsr.society_name
        """
    ).fetchall()
    confirmed_count = db.execute(
        "SELECT COUNT(*) FROM historical_society_regions WHERE confirmed_region IS NOT NULL"
    ).fetchone()[0]
    no_region_count = db.execute(
        "SELECT COUNT(*) FROM historical_society_regions WHERE no_region = 1"
    ).fetchone()[0]
    return render_template(
        "admin/historical_societies.html", rows=rows, regions=REGIONS,
        confirmed_count=confirmed_count, no_region_count=no_region_count,
        no_region_value=NO_REGION,
    )


@bp.route("/historical-societies/bulk", methods=("POST",))
@login_required
def bulk_historical_societies():
    db = get_db()
    confirmed = 0
    marked_none = 0
    i = 0
    while f"name_{i}" in request.form:
        name = request.form.get(f"name_{i}", "").strip()
        region = request.form.get(f"region_{i}", "").strip()
        if name and region == NO_REGION:
            # Not a region, and not a skip: a settled answer of "there isn't
            # one". Leaves confirmed_region NULL so nothing downstream starts
            # treating it as a region - see schema.sql.
            db.execute(
                "UPDATE historical_society_regions SET no_region = 1, updated_at = datetime('now') "
                "WHERE society_name = ?",
                (name,),
            )
            marked_none += 1
        elif name and region in REGIONS:
            db.execute(
                "UPDATE historical_society_regions SET confirmed_region = ?, updated_at = datetime('now') "
                "WHERE society_name = ?",
                (region, name),
            )
            confirmed += 1
        i += 1
    db.commit()
    parts = []
    if confirmed:
        parts.append(f"confirmed a region for {confirmed} society name(s)")
    if marked_none:
        parts.append(f"marked {marked_none} as having no region")
    if parts:
        flash(f"Done - {', '.join(parts)}.", "success")
    else:
        flash("No changes selected.", "warning")
    return redirect(url_for("admin.historical_societies"))


def _match_society_exact(db, society_raw):
    """Same exact-match convention as load_historical_reviews.py's
    match_society - the raw name as printed, then the part before a comma
    (some issues append a location that isn't part of the society's actual
    name on record)."""
    for candidate in (society_raw, society_raw.split(",")[0].strip()):
        row = db.execute("SELECT id FROM societies WHERE name = ?", (candidate,)).fetchone()
        if row:
            return row["id"]
    return None


@bp.route("/society-corrections")
@login_required
def society_corrections():
    """One-time review queue for society_gate_suggestions.json - proposed
    historical_reviews.society_raw corrections from the extractor-society-
    gate branch's fix (see ROADMAP.md's "Near-identical-society audit").
    Generated offline (needs PyMuPDF and the PDF archive, neither available
    here), not recomputed live - this page only cross-references it against
    the real database and lets a moderator approve or reject each one.
    Nothing is applied automatically."""
    db = get_db()
    with open(current_app.config["SOCIETY_CORRECTIONS_PATH"], encoding="utf-8") as f:
        all_suggestions = json.load(f)

    dismissed = {
        (r["source_issue"], r["show_raw"], r["adjudicator"])
        for r in db.execute(
            "SELECT source_issue, show_raw, adjudicator FROM dismissed_society_corrections"
        ).fetchall()
    }

    actionable = []
    dismissed_count = 0
    stale_count = 0
    for s in all_suggestions:
        key = (s["source_issue"], s["show_raw"], s["adjudicator"])
        if key in dismissed:
            dismissed_count += 1
            continue
        row = db.execute(
            """
            SELECT historical_reviews.id AS review_id, historical_reviews.moderation_status
            FROM historical_reviews
            JOIN adjudicators ON adjudicators.id = historical_reviews.adjudicator_id
            WHERE historical_reviews.source_issue = ? AND historical_reviews.show_raw = ?
              AND adjudicators.name = ? AND historical_reviews.society_raw = ?
            """,
            (s["source_issue"], s["show_raw"], s["adjudicator"], s["old_society_raw"]),
        ).fetchone()
        # No matching row left with the *old* value means this one's already
        # been handled some other way (or was never loaded into this
        # database) - nothing actionable here, not an error.
        if row is None:
            stale_count += 1
            continue
        entry = dict(s)
        entry["review_id"] = row["review_id"]
        entry["already_approved"] = row["moderation_status"] == "approved"
        actionable.append(entry)

    return render_template(
        "admin/society_corrections.html", suggestions=actionable,
        total_suggested=len(all_suggestions), dismissed_count=dismissed_count, stale_count=stale_count,
    )


@bp.route("/society-corrections/apply", methods=("POST",))
@login_required
def apply_society_corrections():
    db = get_db()
    applied = 0
    dismissed = 0
    i = 0
    while f"review_id_{i}" in request.form:
        review_id = request.form.get(f"review_id_{i}", "")
        new_value = request.form.get(f"new_value_{i}", "").strip()
        source_issue = request.form.get(f"source_issue_{i}", "")
        show_raw = request.form.get(f"show_raw_{i}", "")
        adjudicator = request.form.get(f"adjudicator_{i}", "")
        decision = request.form.get(f"decision_{i}", "skip")

        if decision == "approve" and review_id and new_value:
            # society_raw/society_id are internal citation fields, never
            # rendered publicly - an approved review's public society comes
            # from historical_reviews.show_id -> shows.society_id instead
            # (set once, at moderation time), which this never touches. Safe
            # to correct regardless of moderation_status - unlike review_text
            # (load_historical_reviews.py's caution), there's no moderator-
            # authored content here to accidentally clobber.
            society_id = _match_society_exact(db, new_value)
            db.execute(
                "UPDATE historical_reviews SET society_raw = ?, society_id = ? WHERE id = ?",
                (new_value, society_id, review_id),
            )
            applied += 1
        elif decision == "dismiss" and source_issue and show_raw and adjudicator:
            db.execute(
                "INSERT OR IGNORE INTO dismissed_society_corrections (source_issue, show_raw, adjudicator) "
                "VALUES (?, ?, ?)",
                (source_issue, show_raw, adjudicator),
            )
            dismissed += 1
        i += 1

    db.commit()
    parts = []
    if applied:
        parts.append(f"corrected {applied}")
    if dismissed:
        parts.append(f"dismissed {dismissed}")
    flash(", ".join(parts).capitalize() + "." if parts else "No changes selected.", "success" if parts else "warning")
    return redirect(url_for("admin.society_corrections"))
