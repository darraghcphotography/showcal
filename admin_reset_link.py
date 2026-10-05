"""Email a one-time "set a new password" link for a moderator/admin login.

The admin login is a username and password with no "forgot password" page,
so a lost password used to mean running seed_admin.py by hand. This mints a
link that works once, for 30 minutes, and emails it through the site's own
SMTP settings. The link is never printed: it is a credential, and anything
printed here ends up in a terminal, a chat or a log.

Usage (in the container - --db is not optional, see CLAUDE.md):
    docker exec aims-web python admin_reset_link.py darraghc \\
        --email you@example.com --db /data/aims.db

Exits non-zero, and says why, if the user doesn't exist or the email didn't
go out - in which case the link it minted is cancelled again.
"""
import argparse
import os
import sqlite3
import sys

from flask import Flask

from app import notify
from app.auth import ADMIN_RESET_MINUTES, create_admin_reset
from app.clock import utcnow_iso


def reset_url(token):
    """The link as a visitor reaches it: SITE_URL, then the path prefix the
    app is mounted under (wsgi.py's PrefixMiddleware), then the route."""
    prefix = os.environ.get("URL_PREFIX", "").rstrip("/")
    return f"{notify.SITE_URL}{prefix}/admin/reset/{token}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("username")
    parser.add_argument("--email", required=True, help="where to send the link")
    parser.add_argument("--db", default="aims.db")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    user = db.execute("SELECT id FROM users WHERE username = ?", (args.username,)).fetchone()
    if user is None:
        sys.exit(f"No login called {args.username!r} in {args.db}.")

    token = create_admin_reset(db, user["id"])
    db.commit()

    body = (
        f"Someone asked to reset the password for the ShowCal moderator login "
        f"'{args.username}'.\n\n"
        f"Set a new password here - the link works once, for {ADMIN_RESET_MINUTES} minutes:\n"
        f"{reset_url(token)}\n\n"
        f"If you didn't ask for this, ignore this email. Your current password still works.\n"
    )
    # notify.send logs through current_app on failure, so it needs an app context.
    with Flask(__name__).app_context():
        sent = notify.send("Reset your ShowCal moderator password", body, to=args.email)

    if not sent:
        db.execute(
            "UPDATE admin_password_resets SET used_at = ? "
            "WHERE user_id = ? AND used_at IS NULL",
            (utcnow_iso(), user["id"]),
        )
        db.commit()
        reason = "SMTP isn't configured" if sent is None else "sending failed (see the log above)"
        sys.exit(f"No email went out - {reason}. The link was cancelled.")

    print(f"Reset link for {args.username!r} emailed to {args.email}. "
          f"It works once, for {ADMIN_RESET_MINUTES} minutes.")
    db.close()


if __name__ == "__main__":
    main()
