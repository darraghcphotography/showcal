import secrets
from datetime import date, datetime, timedelta

from flask import flash, redirect, render_template, request, url_for

from ...auth import current_user, login_required
from ...clock import utcnow_iso
from ...db import get_db
from . import bp
from .auth import _generate_invite_code


def _generate_magic_token() -> str:
    return secrets.token_urlsafe(32)


@bp.route("/access-requests")
@login_required
def access_requests():
    db = get_db()
    pending = db.execute(
        """
        SELECT req.*, societies.name AS society_name
        FROM society_access_requests req
        JOIN societies ON societies.id = req.society_id
        WHERE req.status = 'pending'
        ORDER BY req.created_at DESC
        """
    ).fetchall()

    history = db.execute(
        """
        SELECT req.*, societies.name AS society_name,
               invite_codes.code AS invite_code
        FROM society_access_requests req
        JOIN societies ON societies.id = req.society_id
        LEFT JOIN invite_codes ON invite_codes.id = req.invite_code_id
        WHERE req.status != 'pending'
        ORDER BY COALESCE(req.approved_at, req.created_at) DESC
        LIMIT 50
        """
    ).fetchall()

    societies = db.execute("SELECT id, name FROM societies WHERE NOT hidden ORDER BY name").fetchall()

    return render_template(
        "admin/access_requests.html",
        pending=pending,
        history=history,
        societies=societies,
    )


@bp.route("/access-requests/<int:req_id>/approve", methods=("POST",))
@login_required
def approve_access_request(req_id: int):
    db = get_db()
    req = db.execute(
        """
        SELECT req.*, societies.name AS society_name
        FROM society_access_requests req
        JOIN societies ON societies.id = req.society_id
        WHERE req.id = ?
        """,
        (req_id,),
    ).fetchone()

    if not req:
        flash("Access request not found.", "error")
        return redirect(url_for("admin.access_requests"))

    # 1. Create or get 30-day invite code for this society
    expires_date = (date.today() + timedelta(days=30)).isoformat()
    code_str = _generate_invite_code(db)
    label = f"Magic Link: {req['requester_name']} ({req['requester_role']})"

    cur = db.execute(
        """
        INSERT INTO invite_codes (code, label, society_id, is_active, expires_at, created_by)
        VALUES (?, ?, ?, 1, ?, ?)
        """,
        (code_str, label, req["society_id"], expires_date, current_user()["username"]),
    )
    code_id = cur.lastrowid

    # 2. Update request status to approved
    db.execute(
        """
        UPDATE society_access_requests
        SET status = 'approved', approved_at = ?, invite_code_id = ?, expires_at = ?
        WHERE id = ?
        """,
        (utcnow_iso(), code_id, expires_date, req_id),
    )
    db.commit()

    magic_url = url_for("society.auth_magic_link", token=req["token"], _external=True)
    flash(
        f"Approved access for {req['requester_name']} ({req['society_name']})! Magic Login Link: {magic_url}",
        "success",
    )
    return redirect(url_for("admin.access_requests"))


@bp.route("/access-requests/<int:req_id>/reject", methods=("POST",))
@login_required
def reject_access_request(req_id: int):
    db = get_db()
    req = db.execute("SELECT * FROM society_access_requests WHERE id = ?", (req_id,)).fetchone()
    if not req:
        flash("Access request not found.", "error")
        return redirect(url_for("admin.access_requests"))

    db.execute(
        "UPDATE society_access_requests SET status = 'rejected' WHERE id = ?",
        (req_id,),
    )
    db.commit()
    flash(f"Rejected access request from {req['requester_name']}.", "info")
    return redirect(url_for("admin.access_requests"))


@bp.route("/access-requests/create-direct", methods=("POST",))
@login_required
def create_direct_magic_link():
    society_id = request.form.get("society_id", type=int)
    name = request.form.get("requester_name", "").strip() or "Society Officer"
    email = request.form.get("requester_email", "").strip() or "unknown@email.com"
    role = request.form.get("requester_role", "").strip() or "Committee Member"

    if not society_id:
        flash("Please select a society.", "error")
        return redirect(url_for("admin.access_requests"))

    db = get_db()
    soc = db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()
    if not soc:
        flash("Society not found.", "error")
        return redirect(url_for("admin.access_requests"))

    token = _generate_magic_token()
    expires_date = (date.today() + timedelta(days=30)).isoformat()
    code_str = _generate_invite_code(db)
    label = f"Direct Magic Link: {name} ({role})"

    cur = db.execute(
        """
        INSERT INTO invite_codes (code, label, society_id, is_active, expires_at, created_by)
        VALUES (?, ?, ?, 1, ?, ?)
        """,
        (code_str, label, society_id, expires_date, current_user()["username"]),
    )
    code_id = cur.lastrowid

    db.execute(
        """
        INSERT INTO society_access_requests (
            society_id, requester_name, requester_email, requester_role,
            token, invite_code_id, status, approved_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, ?)
        """,
        (society_id, name, email, role, token, code_id, utcnow_iso(), expires_date),
    )
    db.commit()

    magic_url = url_for("society.auth_magic_link", token=token, _external=True)
    flash(f"Generated Magic Login Link for {soc['name']}: {magic_url}", "success")
    return redirect(url_for("admin.access_requests"))
