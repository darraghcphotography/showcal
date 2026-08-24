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


def test_sitemap_includes_the_previously_missing_index_pages(client):
    """2026-08-23 audit finding: /titles, /venues, /awards, /reviews,
    /stats/trends and /about were all missing, despite being some of the
    site's best content and linked from the main nav."""
    body = client.get("/sitemap.xml").get_data(as_text=True)
    for path in ("/titles</loc>", "/venues</loc>", "/awards</loc>", "/reviews</loc>",
                 "/stats/trends</loc>", "/about</loc>"):
        assert path in body


def test_sitemap_includes_a_title_page(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/titles/Oliver" in body


def test_sitemap_includes_a_venue_page(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'Gorey Little Theatre', 'approved')",
        (society_id,),
    )
    db.commit()
    client.get("/venues")  # triggers venues_build.ensure_current() so the venue row exists

    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/venues/gorey-little-theatre</loc>" in body


def test_sitemap_includes_an_assigned_adjudicator_but_not_an_unassigned_one(client, db):
    """Same rule adjudicators_list() already applies to its own roster - an
    adjudicator with no season/tier assignment 404s on their own page, so
    listing them in the sitemap would just hand search engines a dead link."""
    db.execute("INSERT INTO adjudicators (name) VALUES ('Assigned Judge')")
    db.execute("INSERT INTO adjudicators (name) VALUES ('Unassigned Judge')")
    assigned_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Assigned Judge'").fetchone()["id"]
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES ('25/26', 'Gilbert', ?)",
        (assigned_id,),
    )
    db.commit()

    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert f"/adjudicators/{assigned_id}</loc>" in body
    unassigned_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Unassigned Judge'").fetchone()["id"]
    assert f"/adjudicators/{unassigned_id}</loc>" not in body


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


def _show(opening_date=None):
    return {"opening_date": opening_date}


def test_is_upcoming_true_for_future_open_show():
    future = (date.today() + timedelta(days=10)).isoformat()
    assert is_upcoming(_show(opening_date=future)) is True


def test_is_upcoming_false_for_past_show():
    past = (date.today() - timedelta(days=10)).isoformat()
    assert is_upcoming(_show(opening_date=past)) is False


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
