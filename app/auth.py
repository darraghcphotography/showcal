import functools
from datetime import date

from flask import redirect, session, url_for

from .db import get_db


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    """Gate an admin route behind a logged-in moderator/admin session."""

    @functools.wraps(view)
    def wrapped(**kwargs):
        if current_user() is None:
            return redirect(url_for("admin.login"))
        return view(**kwargs)

    return wrapped


def active_invite_code():
    """Return the invite_codes row unlocked in this session, if it's still valid.

    Re-checked on every use (not just at unlock time) so revoking or expiring
    a code takes effect immediately, even for someone mid-session.
    """
    code_id = session.get("invite_code_id")
    if code_id is None:
        return None
    row = get_db().execute(
        "SELECT * FROM invite_codes WHERE id = ? AND is_active = 1", (code_id,)
    ).fetchone()
    if row is None:
        session.pop("invite_code_id", None)
        return None
    if row["expires_at"] and row["expires_at"] < date.today().isoformat():
        session.pop("invite_code_id", None)
        return None
    return row


def invite_required(view):
    """Gate the submission form behind either a logged-in moderator session
    or an unlocked, still-valid invite code."""

    @functools.wraps(view)
    def wrapped(**kwargs):
        if current_user() is None and active_invite_code() is None:
            return redirect(url_for("submit.unlock"))
        return view(**kwargs)

    return wrapped


def active_society_code():
    """Return the invite_codes row for a society login, if one's unlocked in
    this session and still valid. Distinct from active_invite_code()'s
    session key - a browser could plausibly hold both a one-off submission
    code and a society login at once, no reason to make them collide."""
    code_id = session.get("society_code_id")
    if code_id is None:
        return None
    row = get_db().execute(
        "SELECT * FROM invite_codes WHERE id = ? AND is_active = 1 AND society_id IS NOT NULL",
        (code_id,),
    ).fetchone()
    if row is None:
        session.pop("society_code_id", None)
        return None
    if row["expires_at"] and row["expires_at"] < date.today().isoformat():
        session.pop("society_code_id", None)
        return None
    return row


def society_required(view):
    """Gate a society-dashboard route behind an unlocked, still-valid society
    login code."""

    @functools.wraps(view)
    def wrapped(**kwargs):
        if active_society_code() is None:
            return redirect(url_for("society.login"))
        return view(**kwargs)

    return wrapped
