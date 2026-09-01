"""Best-effort email notifications for new submissions/suggestions - sent to
a single fixed inbox via SMTP. Deliberately never raises: nothing about a
visitor's actual submission should ever depend on an email successfully
going out (see call sites in submit.py/public.py).

Configured entirely through environment variables, same pattern as
SECRET_KEY in app/__init__.py - unset in local dev, set in docker-compose.yml
for production. Silently does nothing if SMTP_USER/SMTP_PASSWORD aren't set,
so local dev never needs real credentials just to try the app.
"""
import os
import smtplib
from email.message import EmailMessage

from flask import current_app

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "info@darraghc.ie")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")


def link(path):
    """Turn a url_for()-style path into a clickable link for an email body.
    Falls back to the bare path if SITE_URL isn't configured (local dev)."""
    return f"{SITE_URL}{path}" if SITE_URL else path


def send(subject, body, to=None):
    """Best-effort: silently does nothing if SMTP isn't configured (so local
    dev never needs real credentials), and never raises on failure - a
    submission/suggestion must always succeed regardless of mail delivery.

    Returns True if the message went out, False if sending was attempted and
    failed, and None if SMTP isn't configured so nothing was attempted.
    Most callers ignore this and should: a visitor's submission must not
    depend on mail. It exists for the one case where a human is standing
    there and needs to know - approving a society's magic link, where a
    silently-lost email means the moderator believes access was granted and
    the society never hears anything (see admin/access_requests.py)."""
    if not SMTP_USER or not SMTP_PASSWORD:
        return None
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to or NOTIFY_EMAIL
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        current_app.logger.exception("Failed to send notification email (subject=%r, to=%r)", subject, to or NOTIFY_EMAIL)
        return False
    return True
