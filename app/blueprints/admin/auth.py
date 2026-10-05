import functools
import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ...auth import current_user, find_admin_reset, login_required
from ...clock import utcnow_iso
from ...db import get_db
from ...invite_words import ADJECTIVES, CODE_DIGITS, NOUNS
from ...rate_limit import limiter
from . import bp


def _generate_invite_code(db):
    while True:
        digits = secrets.randbelow(10 ** CODE_DIGITS)
        code = f"{secrets.choice(ADJECTIVES)}-{secrets.choice(NOUNS)}-{digits:0{CODE_DIGITS}d}"
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
            return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html")


# Long enough that guessing is hopeless, short enough to type on a phone.
MIN_PASSWORD_LENGTH = 12


@bp.route("/reset/<token>", methods=("GET", "POST"))
@limiter.limit("10 per minute")
def reset_password(token):
    """Set a new password from a one-time emailed link (admin_reset_link.py).
    Opening the link changes nothing - only the POST below spends it - so a
    mail scanner's prefetch can't use it up first."""
    db = get_db()
    reset = find_admin_reset(db, token)
    if reset is None:
        flash("This reset link has expired or has already been used. Ask for a new one.", "error")
        return redirect(url_for("admin.login"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Use at least {MIN_PASSWORD_LENGTH} characters.", "error")
        elif password != confirm:
            flash("The two passwords don't match.", "error")
        else:
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(password), reset["user_id"]),
            )
            db.execute(
                "UPDATE admin_password_resets SET used_at = ? WHERE id = ?",
                (utcnow_iso(), reset["reset_id"]),
            )
            db.commit()
            session.clear()
            flash("Password changed. Log in with your new password.", "success")
            return redirect(url_for("admin.login"))

    return render_template(
        "admin/reset_password.html", username=reset["username"], min_length=MIN_PASSWORD_LENGTH,
    )


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("public.index"))
