import sqlite3
from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for

from ...auth import current_user
from ...db import get_db
from . import bp
from .auth import _generate_invite_code, admin_required


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
