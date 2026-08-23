import functools
import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ...auth import current_user, login_required
from ...db import get_db
from ...invite_words import ADJECTIVES, NOUNS
from ...rate_limit import limiter
from . import bp


def _generate_invite_code(db):
    while True:
        code = f"{secrets.choice(ADJECTIVES)}-{secrets.choice(NOUNS)}"
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
            return redirect(url_for("admin.queue"))
    return render_template("admin/login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("public.index"))
