from datetime import date, timedelta

from flask import flash, redirect, render_template, request, url_for

from ... import notify
from ...auth import current_user, generate_magic_token, hash_magic_token, login_required
from ...clock import utcnow_iso
from ...db import get_db
from . import bp
from .auth import _generate_invite_code


def _delivery_note(verb, sent, email, magic_url):
    """What to tell the moderator about the email that just went out. The
    failure case is the one that matters: notify.send never raises, so
    without this a lost email looks exactly like a delivered one and the
    moderator walks away believing a society has access it never got. The
    link is in every variant, so there is always a way to finish the job by
    hand."""
    if sent is False:
        return (
            f"{verb}, but the email to {email} FAILED to send - copy this link and pass it on "
            f"yourself: {magic_url}",
            "error",
        )
    if sent is None:
        return (f"{verb}. No email was sent - pass this link on yourself: {magic_url}", "info")
    return (f"{verb} - magic link emailed to {email}. Link: {magic_url}", "success")


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
               codes.code AS invite_code_str
        FROM society_access_requests req
        JOIN societies ON societies.id = req.society_id
        LEFT JOIN invite_codes codes ON codes.id = req.invite_code_id
        WHERE req.status != 'pending'
        ORDER BY COALESCE(req.approved_at, req.created_at) DESC
        LIMIT 50
        """
    ).fetchall()

    societies = db.execute("SELECT id, name, region FROM societies WHERE NOT hidden ORDER BY name").fetchall()

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
    # The token is minted here, at approval, not when the request came in -
    # only the hash is stored, so the plaintext exists exactly once, in the
    # email below and in this flash. A pending request therefore never holds
    # a usable credential, and there is nothing to recover if one is denied.
    token = generate_magic_token()
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
        SET status = 'approved', approved_at = ?, invite_code_id = ?, expires_at = ?,
            token_hash = ?
        WHERE id = ?
        """,
        (utcnow_iso(), code_id, expires_date, hash_magic_token(token), req_id),
    )
    db.commit()

    magic_url = url_for("society.auth_magic_link", token=token, _external=True)

    # 3. Send magic link email to the requester
    sent = None
    if req["requester_email"]:
        sent = notify.send(
            f"Your access to {req['society_name']} on ShowCal is approved!",
            f"Hi {req['requester_name']},\n\n"
            f"Your request to manage {req['society_name']} on ShowCal has been approved.\n\n"
            f"Click your 1-click Magic Login Link below to log in directly:\n"
            f"{magic_url}\n\n"
            f"This link is valid for 30 days. You can also use your society access code '{code_str}' on the login page anytime.\n\n"
            f"Best regards,\nShowCal Team\nhttps://darraghc.ie/showcal/",
            to=req["requester_email"],
        )

    message, category = _delivery_note("Approved", sent, req["requester_email"], magic_url)
    flash(f"{req['requester_name']} ({req['society_name']}): {message}", category)
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

    token = generate_magic_token()
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
            token_hash, invite_code_id, status, approved_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, ?)
        """,
        (society_id, name, email, role, hash_magic_token(token), code_id, utcnow_iso(), expires_date),
    )
    db.commit()

    magic_url = url_for("society.auth_magic_link", token=token, _external=True)

    sent = None
    if email and email != "unknown@email.com":
        sent = notify.send(
            f"Your access to {soc['name']} on ShowCal is ready!",
            f"Hi {name},\n\n"
            f"A 1-click Magic Login Link has been generated for you to manage {soc['name']} on ShowCal.\n\n"
            f"Click the link below to log in directly:\n"
            f"{magic_url}\n\n"
            f"This link is valid for 30 days. You can also use your society access code '{code_str}' on the login page anytime.\n\n"
            f"Best regards,\nShowCal Team\nhttps://darraghc.ie/showcal/",
            to=email,
        )

    message, category = _delivery_note("Link generated", sent, email, magic_url)
    flash(f"{soc['name']}: {message}", category)
    return redirect(url_for("admin.access_requests"))
