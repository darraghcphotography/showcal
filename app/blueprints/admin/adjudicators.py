from flask import abort, current_app, flash, redirect, render_template, request, url_for

from ...auth import login_required
from ...db import get_db
from ...season import next_season, season_range
from ...uploads import save_poster
from . import bp
from .auth import admin_required

# A season/tier is normally one adjudicator, but a real mid-season change
# (see ROADMAP) needs a second - the grid offers exactly two slots per tier
# per season rather than an open-ended add-more control, since AIMS has
# never had more than one substitution in a season and a fixed two keeps
# the form (and this code) simple.
ASSIGNMENT_SLOTS = (1, 2)

# The ShowTimes PDF archive backfill goes back to 09/10, further than the
# awards archive (season_range()'s own anchor) currently does on production -
# without this floor, a season with confirmed adjudicator data could be
# impossible to enter because it's simply missing from the dropdown.
ADJUDICATOR_GRID_FLOOR_SEASON = "09/10"


def _assignment_field(season, section, slot=1):
    # "/" in a season string (e.g. "23/24") is a perfectly valid form-field
    # name, no escaping needed either side of the request. Slot 1 keeps the
    # bare "section|season" name from before multi-slot support existed.
    base = f"{section}|{season}"
    return base if slot == 1 else f"{base}|{slot}"


def _adjudicator_grid_seasons(db):
    """season_range() already reaches back to the real awards-archive start
    (1977, historical_results' own earliest year) - this floor only ever
    needs to pad anything when that archive is thinner than 09/10. Checked
    by plain membership rather than comparing season strings with <=/< - a
    two-digit season string doesn't sort correctly across the 1999/2000
    rollover ('76/77' sorts after '09/10' as plain text despite being an
    earlier season), which silently duplicated every season from 09/10
    onward once the archive actually reached back to 1977 (found while
    reworking this page's layout, not a new gap - the padding logic below
    only ever runs on the century-safe case, where the archive is too
    recent to reach 09/10 at all)."""
    seasons = season_range(db)
    if not seasons or ADJUDICATOR_GRID_FLOOR_SEASON in seasons:
        return seasons
    extra = []
    s = ADJUDICATOR_GRID_FLOOR_SEASON
    while s < seasons[-1]:
        extra.append(s)
        s = next_season(s)
    return seasons + list(reversed(extra))


@bp.route("/adjudicators", methods=("GET", "POST"))
@login_required
def adjudicators():
    db = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        notes = request.form.get("notes", "").strip() or None
        if not name:
            flash("Name is required.", "error")
        elif db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone():
            flash(f'"{name}" is already on the list.', "error")
        else:
            db.execute("INSERT INTO adjudicators (name, notes) VALUES (?, ?)", (name, notes))
            db.commit()
            flash(f'"{name}" added.', "success")
        return redirect(url_for("admin.adjudicators"))

    seasons = _adjudicator_grid_seasons(db)
    adjudicator_list = db.execute(
        """
        SELECT adjudicators.*, COUNT(adjudicator_assignments.id) AS season_count
        FROM adjudicators
        LEFT JOIN adjudicator_assignments ON adjudicator_assignments.adjudicator_id = adjudicators.id
        GROUP BY adjudicators.id ORDER BY adjudicators.name
        """
    ).fetchall()
    assignments = {}
    for row in db.execute(
        "SELECT season, section, adjudicator_id, notes FROM adjudicator_assignments ORDER BY id"
    ).fetchall():
        assignments.setdefault((row["season"], row["section"]), []).append(
            {"adjudicator_id": row["adjudicator_id"], "notes": row["notes"] or ""}
        )

    # A season with both tiers already filled in is "done" - collapsing those
    # behind a disclosure (same pattern as the suggestions board's archived
    # lane / stats page's earlier-seasons collapse) keeps the still-blank/
    # partial seasons that actually need attention on screen without a long
    # scroll past ones that don't, regardless of whether "done" happens to be
    # a recent season or one from the historical backfill.
    seasons_incomplete, seasons_complete = [], []
    for season in seasons:
        complete = assignments.get((season, "Gilbert")) and assignments.get((season, "Sullivan"))
        (seasons_complete if complete else seasons_incomplete).append(season)

    return render_template(
        "admin/adjudicators.html", adjudicators=adjudicator_list,
        seasons_incomplete=seasons_incomplete, seasons_complete=seasons_complete,
        assignments=assignments, field=_assignment_field, slots=ASSIGNMENT_SLOTS,
    )


@bp.route("/adjudicators/assign", methods=("POST",))
@login_required
def save_adjudicator_assignments():
    db = get_db()
    for season in _adjudicator_grid_seasons(db):
        for section in ("Gilbert", "Sullivan"):
            db.execute("DELETE FROM adjudicator_assignments WHERE season = ? AND section = ?", (season, section))
            seen_ids = set()
            for slot in ASSIGNMENT_SLOTS:
                value = request.form.get(_assignment_field(season, section, slot), "")
                if not value:
                    continue
                adjudicator_id = int(value)
                if adjudicator_id in seen_ids:
                    continue  # same person picked in both slots - one row is enough
                seen_ids.add(adjudicator_id)
                notes = request.form.get(_assignment_field(season, section, slot) + "|notes", "").strip() or None
                db.execute(
                    "INSERT INTO adjudicator_assignments (season, section, adjudicator_id, notes) VALUES (?, ?, ?, ?)",
                    (season, section, adjudicator_id, notes),
                )
    db.commit()
    flash("Adjudicator assignments saved.", "success")
    return redirect(url_for("admin.adjudicators"))


@bp.route("/adjudicators/<int:adjudicator_id>")
@login_required
def adjudicator_detail(adjudicator_id):
    db = get_db()
    adjudicator = db.execute("SELECT * FROM adjudicators WHERE id = ?", (adjudicator_id,)).fetchone()
    if adjudicator is None:
        abort(404)

    seasons_judged = db.execute(
        "SELECT season, section FROM adjudicator_assignments WHERE adjudicator_id = ? ORDER BY season DESC",
        (adjudicator_id,),
    ).fetchall()
    reviews = db.execute(
        """
        SELECT shows.id, shows.show, shows.season, shows.section, shows.opening_date,
               shows.review_status, shows.review_url, societies.name AS society_name
        FROM shows
        JOIN adjudicator_assignments
            ON adjudicator_assignments.season = shows.season AND adjudicator_assignments.section = shows.section
        JOIN societies ON societies.id = shows.society_id
        WHERE adjudicator_assignments.adjudicator_id = ?
        ORDER BY shows.opening_date DESC
        """,
        (adjudicator_id,),
    ).fetchall()
    return render_template(
        "admin/adjudicator_detail.html", adjudicator=adjudicator, seasons_judged=seasons_judged, reviews=reviews,
    )


@bp.route("/adjudicators/<int:adjudicator_id>/edit", methods=("POST",))
@login_required
def edit_adjudicator(adjudicator_id):
    """Bio (adjudicators.notes) and photo, editable after creation - the
    add-a-new-adjudicator form on /admin/adjudicators could set notes once
    at creation but never again, and there was no photo field at all (19
    Aug 2026 feedback review, item 7). notes already rendered on the public
    page if present; this is what actually lets a moderator set/change it."""
    db = get_db()
    adjudicator = db.execute("SELECT * FROM adjudicators WHERE id = ?", (adjudicator_id,)).fetchone()
    if adjudicator is None:
        abort(404)

    name = request.form.get("name", "").strip()
    notes = request.form.get("notes", "").strip() or None
    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("admin.adjudicator_detail", adjudicator_id=adjudicator_id))

    photo_filename = adjudicator["photo_filename"]
    photo_file = request.files.get("photo")
    if photo_file and photo_file.filename:
        try:
            photo_filename = save_poster(photo_file, current_app.config["UPLOAD_DIR"])
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("admin.adjudicator_detail", adjudicator_id=adjudicator_id))
    elif request.form.get("remove_photo"):
        photo_filename = None

    db.execute(
        "UPDATE adjudicators SET name = ?, notes = ?, photo_filename = ? WHERE id = ?",
        (name, notes, photo_filename, adjudicator_id),
    )
    db.commit()
    flash("Adjudicator updated.", "success")
    return redirect(url_for("admin.adjudicator_detail", adjudicator_id=adjudicator_id))


@bp.route("/adjudicators/<int:adjudicator_id>/delete", methods=("POST",))
@admin_required
def delete_adjudicator(adjudicator_id):
    db = get_db()
    in_use = db.execute(
        "SELECT 1 FROM adjudicator_assignments WHERE adjudicator_id = ?", (adjudicator_id,)
    ).fetchone()
    if in_use:
        flash("Can't delete - this adjudicator is still assigned to a season. Clear those first.", "error")
    else:
        db.execute("DELETE FROM adjudicators WHERE id = ?", (adjudicator_id,))
        db.commit()
        flash("Adjudicator deleted.", "success")
    return redirect(url_for("admin.adjudicators"))
