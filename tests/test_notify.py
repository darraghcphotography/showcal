"""Best-effort email notifications (app/notify.py): never raises, never
sends unless SMTP credentials are configured - see the module's own
docstring for why (a submission must always succeed regardless of mail
delivery)."""
from unittest.mock import MagicMock, patch

from app import notify


def test_send_does_nothing_when_unconfigured(monkeypatch, app):
    monkeypatch.setattr(notify, "SMTP_USER", None)
    monkeypatch.setattr(notify, "SMTP_PASSWORD", None)
    with patch("app.notify.smtplib.SMTP") as mock_smtp:
        with app.app_context():
            notify.send("Subject", "Body")
    mock_smtp.assert_not_called()


def test_send_calls_smtp_with_configured_credentials(monkeypatch, app):
    monkeypatch.setattr(notify, "SMTP_USER", "sender@example.com")
    monkeypatch.setattr(notify, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(notify, "NOTIFY_EMAIL", "info@darraghc.ie")

    mock_server = MagicMock()
    mock_smtp_cm = MagicMock()
    mock_smtp_cm.__enter__.return_value = mock_server

    with patch("app.notify.smtplib.SMTP", return_value=mock_smtp_cm) as mock_smtp:
        with app.app_context():
            notify.send("New show submission", "Details here")

    mock_smtp.assert_called_once_with(notify.SMTP_HOST, notify.SMTP_PORT, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("sender@example.com", "app-password")
    mock_server.send_message.assert_called_once()
    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["Subject"] == "New show submission"
    assert sent_msg["To"] == "info@darraghc.ie"
    assert sent_msg["From"] == "sender@example.com"


def test_send_swallows_smtp_failure(monkeypatch, app):
    monkeypatch.setattr(notify, "SMTP_USER", "sender@example.com")
    monkeypatch.setattr(notify, "SMTP_PASSWORD", "app-password")

    with patch("app.notify.smtplib.SMTP", side_effect=OSError("connection refused")):
        with app.app_context():
            notify.send("Subject", "Body")  # must not raise


def test_link_prefixes_site_url_when_set(monkeypatch):
    monkeypatch.setattr(notify, "SITE_URL", "https://darraghc.ie/showcal")
    assert notify.link("/admin/queue") == "https://darraghc.ie/showcal/admin/queue"


def test_link_returns_bare_path_when_site_url_unset(monkeypatch):
    monkeypatch.setattr(notify, "SITE_URL", "")
    assert notify.link("/admin/queue") == "/admin/queue"
