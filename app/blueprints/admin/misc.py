from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for

from ...auth import login_required
from ...constants import REGIONS, SUGGESTION_CATEGORIES, SUGGESTION_STATUSES
from ...db import get_db
from . import bp
from ._shared import DATE_RE


@bp.route("/shows/dates", methods=("GET", "POST"))
@login_required
def fix_dates():
    db = get_db()

    if request.method == "POST":
        # One shared form covers the whole visible batch (see fix_dates.html) -
        # every row's fields are always present, so this always processes
        # everything on the page, not just whichever row's button was clicked.
        # All-or-nothing: a bad date anywhere blocks the whole save rather than
        # silently skipping just that row.
        rows = []
        errors = []
        i = 0
        while f"show_id_{i}" in request.form:
            show_id = request.form.get(f"show_id_{i}", "")
            opening_date = request.form.get(f"opening_date_{i}", "").strip() or None
            closing_date = request.form.get(f"closing_date_{i}", "").strip() or None
            for label, value in (("Opening date", opening_date), ("Closing date", closing_date)):
                if value and not DATE_RE.match(value):
                    errors.append(f"Row {i + 1}: {label} must be a valid date.")
            rows.append((show_id, opening_date, closing_date))
            i += 1

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            updated = 0
            for show_id, opening_date, closing_date in rows:
                current = db.execute(
                    "SELECT opening_date, closing_date FROM shows WHERE id = ?", (show_id,)
                ).fetchone()
                if current and (current["opening_date"] != opening_date or current["closing_date"] != closing_date):
                    db.execute(
                        "UPDATE shows SET opening_date = ?, closing_date = ?, updated_at = ? WHERE id = ?",
                        (opening_date, closing_date, datetime.utcnow().isoformat(), show_id),
                    )
                    updated += 1
            db.commit()
            if updated:
                flash(f"Updated {updated} show{'' if updated == 1 else 's'}.", "success")
            else:
                flash("No changes to save.", "warning")
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
    admin_note = request.form.get("admin_note", "").strip() or None
    if category not in SUGGESTION_CATEGORIES or triage_status not in SUGGESTION_STATUSES:
        flash("Choose a valid category and status.", "error")
        return redirect(url_for("admin.suggestions"))
    db.execute(
        "UPDATE feature_suggestions SET category = ?, triage_status = ?, admin_note = ?, triaged_at = datetime('now') WHERE id = ?",
        (category, triage_status, admin_note, suggestion_id),
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
