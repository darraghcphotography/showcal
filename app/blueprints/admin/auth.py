import functools
import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ...auth import current_user, login_required
from ...db import get_db
from ...invite_words import ADJECTIVES, NOUNS
from ...rate_limit import limiter
from . import bp


# Digits appended to the adjective-noun pair, and the reason is guessing, not
# collisions. The word lists give 40 x 40 = 1,600 pairs, which invite_words.py
# correctly calls "comfortable headroom for issuing codes to every AIMS
# society" - that is a collision argument. It is not a guessing argument: with
# ~21 codes live, roughly 1 in 76 guesses at /society/login was a valid code,
# so at that route's rate limit somebody was into *a* society in about eight
# minutes. A society code is not a read-only key either - it can edit that
# society's shows and upload posters (2026-09-01 audit).
#
# Four digits takes the space to ~16 million, i.e. about 1 in 760,000 with the
# same number of codes live. Digits rather than a third word because the whole
# point of these codes is being read aloud down a phone or across a committee
# room, and "golden-otter-4821" survives that better than three adjectives do.
CODE_DIGITS = 4


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


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("public.index"))
