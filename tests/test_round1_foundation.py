"""Round 1 foundation fixes from the 2026-08-17 site audit:
- url_for(_external=True) trusts X-Forwarded-Proto (app/__init__.py's ProxyFix)
- a custom 500 page, matching the existing 404
- a plain <meta name="description"> alongside the existing og:description
- Referrer-Policy/Permissions-Policy headers
- app/shows.py's is_upcoming() shared by public.py and society.py
"""
from datetime import date, timedelta

from conftest import seed_society

from app.shows import is_upcoming


def test_sitemap_uses_forwarded_https_scheme(client):
    resp = client.get("/sitemap.xml", environ_overrides={"HTTP_X_FORWARDED_PROTO": "https"})
    body = resp.get_data(as_text=True)
    assert "<loc>https://" in body
    assert "<loc>http://" not in body


def test_sitemap_falls_back_to_plain_http_without_forwarded_header(client):
    resp = client.get("/sitemap.xml")
    body = resp.get_data(as_text=True)
    assert "<loc>http://" in body


def test_500_page_renders_site_chrome(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/_boom")
    def _boom():
        raise RuntimeError("deliberate test failure")

    resp = client.get("/_boom")
    assert resp.status_code == 500
    assert "Technical difficulties" in resp.get_data(as_text=True)


def test_homepage_has_meta_description(client):
    body = client.get("/").get_data(as_text=True)
    assert '<meta name="description" content="Browse AIMS member societies' in body


def test_referrer_and_permissions_policy_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")


def _show(status=None, opening_date=None):
    return {"status": status, "opening_date": opening_date}


def test_is_upcoming_true_for_future_open_show():
    future = (date.today() + timedelta(days=10)).isoformat()
    assert is_upcoming(_show(opening_date=future)) is True


def test_is_upcoming_false_for_past_show():
    past = (date.today() - timedelta(days=10)).isoformat()
    assert is_upcoming(_show(opening_date=past)) is False


def test_is_upcoming_false_for_cancelled_show():
    future = (date.today() + timedelta(days=10)).isoformat()
    assert is_upcoming(_show(status="Cancelled", opening_date=future)) is False


def test_is_upcoming_false_when_no_opening_date():
    assert is_upcoming(_show(opening_date=None)) is False


def test_society_adjudication_reminder_still_uses_shared_helper(client, db):
    # Regression check for the society.py refactor - reminder still shows for
    # an upcoming, adjudicated show.
    from conftest import seed_invite_code

    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    future = (date.today() + timedelta(days=60)).isoformat()
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, review_status) "
        "VALUES (?, '26/27', 'Eastern', 'Anything Goes', ?, 'Scheduled')",
        (society_id, future),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Anything Goes'").fetchone()["id"]

    code_id = seed_invite_code(db, code="test-code", society_id=society_id)
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id

    body = client.get(f"/society/shows/{show_id}/edit").get_data(as_text=True)
    assert "check adjudication forms" in body.lower()
