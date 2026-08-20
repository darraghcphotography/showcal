"""Round 4 of the 2026-08-17 audit's plan: replace every inline
onsubmit="return confirm(...)"/onclick="..." handler with data-confirm/
data-copy-target attributes plus one delegated listener in base.html, then
ship a real nonce-gated Content-Security-Policy header (app/__init__.py)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_csp_header_present_and_nonce_gated(client):
    resp = client.get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "script-src 'self' 'nonce-" in csp
    assert "'unsafe-inline'" not in csp.split("style-src")[0]  # not in script-src
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_every_script_tag_carries_the_response_nonce(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)
    csp = resp.headers["Content-Security-Policy"]
    nonce = csp.split("'nonce-")[1].split("'")[0]
    assert body.count("<script") == body.count(f'<script nonce="{nonce}"')


def test_nonce_changes_between_requests(client):
    csp_a = client.get("/").headers["Content-Security-Policy"]
    csp_b = client.get("/").headers["Content-Security-Policy"]
    nonce_a = csp_a.split("'nonce-")[1].split("'")[0]
    nonce_b = csp_b.split("'nonce-")[1].split("'")[0]
    assert nonce_a != nonce_b


def test_no_inline_event_handlers_remain(client, db):
    """onchange was missing from this check for weeks - five auto-submit
    filter dropdowns (index.html, stats.html) and two admin category
    toggles carried onchange="..." the whole time, silently inert under the
    CSP above, and this test would have caught it on day one if it checked
    for it. See the "Feedback review" writeup, 19 Aug 2026."""
    admin_id = seed_user(db, role="admin")
    login_as(client, admin_id)
    for path in ("/admin/venues", "/admin/invite-codes", "/admin/changelog", "/", "/stats",
                 "/admin/awards/new", "/admin/awards/bulk"):
        body = client.get(path).get_data(as_text=True)
        assert "onsubmit=" not in body
        assert "onclick=" not in body
        assert "onchange=" not in body


def test_filter_dropdowns_use_data_auto_submit(client):
    body = client.get("/").get_data(as_text=True)
    assert '<select name="upcoming_region" data-auto-submit>' in body

    body = client.get("/stats").get_data(as_text=True)
    assert 'name="region" data-auto-submit' in body
    assert 'id="award_category" name="award_category" data-auto-submit' in body
    assert 'id="award_tier" name="award_tier" data-auto-submit' in body


def test_award_category_select_uses_data_toggle_attributes(client, db):
    admin_id = seed_user(db, role="admin")
    login_as(client, admin_id)
    for path in ("/admin/awards/new", "/admin/awards/bulk"):
        body = client.get(path).get_data(as_text=True)
        assert 'data-toggle-target="category-other" data-toggle-value="__other__"' in body


def test_delete_form_carries_data_confirm_attribute(client, db):
    admin_id = seed_user(db, role="admin")
    login_as(client, admin_id)

    body = client.get("/admin/invite-codes").get_data(as_text=True)
    assert 'data-confirm="Delete every old AIMS-XXXXXX style code' in body


def test_society_copy_button_uses_data_copy_target(client, db):
    admin_id = seed_user(db, role="admin")
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    from conftest import seed_invite_code
    seed_invite_code(db, code="test-code", society_id=society_id)
    login_as(client, admin_id)

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert 'data-copy-target="society-code-message"' in body
