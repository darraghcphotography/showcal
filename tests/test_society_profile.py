"""A society's self-service "about + social links" profile
(society.edit_profile), the matching admin form, and the public display -
including the URL-scheme validation that keeps a javascript:/data: URL out
of an <a href="..."> rendered for every visitor on the society's public page.
"""
from conftest import seed_invite_code, seed_society, seed_user


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


PROFILE_DATA = {
    "about": "We're always looking for new members - no experience needed!",
    "website_url": "https://example.com",
    "facebook_url": "https://facebook.com/example",
    "instagram_url": "https://instagram.com/example",
    "tiktok_url": "https://tiktok.com/@example",
    "other_url": "https://chat.whatsapp.com/example",
    "other_label": "WhatsApp group",
}


def test_society_can_update_own_profile(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    unlock_society(client, code_id)

    resp = client.post("/society/profile", data=PROFILE_DATA, follow_redirects=False)
    assert resp.status_code == 302

    row = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["about"] == PROFILE_DATA["about"]
    assert row["facebook_url"] == PROFILE_DATA["facebook_url"]
    assert row["other_label"] == "WhatsApp group"


def test_public_page_shows_about_and_links(client, db):
    society_id = seed_society(db)
    db.execute(
        "UPDATE societies SET about = ?, website_url = ?, facebook_url = ?, other_url = ?, other_label = ? WHERE id = ?",
        ("Join us!", "https://example.com", "https://facebook.com/example", "https://chat.example", "WhatsApp group", society_id),
    )
    db.commit()

    resp = client.get(f"/societies/{society_id}")
    body = resp.get_data(as_text=True)
    assert "Join us!" in body
    assert 'href="https://example.com"' in body
    assert 'href="https://facebook.com/example"' in body
    assert "WhatsApp group" in body


def test_public_page_shows_nothing_extra_when_profile_empty(client, db):
    society_id = seed_society(db)
    resp = client.get(f"/societies/{society_id}")
    body = resp.get_data(as_text=True)
    assert "Website" not in body
    assert "Facebook" not in body


def test_javascript_url_is_rejected(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC002", society_id=society_id)
    unlock_society(client, code_id)

    bad_data = dict(PROFILE_DATA, website_url="javascript:alert(1)")
    resp = client.post("/society/profile", data=bad_data, follow_redirects=False)
    assert resp.status_code == 200  # re-renders the form with an error, no redirect

    row = db.execute("SELECT website_url FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["website_url"] is None


def test_valid_https_url_is_accepted(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC003", society_id=society_id)
    unlock_society(client, code_id)

    resp = client.post(
        "/society/profile",
        data=dict(PROFILE_DATA, website_url="https://valid-example.com"),
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT website_url FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["website_url"] == "https://valid-example.com"


def test_one_society_login_cannot_edit_another_societys_profile(client, db):
    society_a = seed_society(db, id=1, name="Society A")
    society_b = seed_society(db, id=2, name="Society B")
    code_id = seed_invite_code(db, code="AIMS-SOC004", society_id=society_a)
    unlock_society(client, code_id)

    client.post("/society/profile", data=PROFILE_DATA, follow_redirects=False)

    row_a = db.execute("SELECT about FROM societies WHERE id = ?", (society_a,)).fetchone()
    row_b = db.execute("SELECT about FROM societies WHERE id = ?", (society_b,)).fetchone()
    assert row_a["about"] == PROFILE_DATA["about"]
    assert row_b["about"] is None


def test_admin_can_also_update_profile_fields(client, db):
    admin_id = seed_user(db, username="boss", role="admin")
    society_id = seed_society(db)
    login_as(client, admin_id)

    form_data = {
        "name": "Test Society", "region": "Eastern", "section": "Gilbert",
        "section_as_of": "", "section_history": "", "notes": "", "default_venue": "",
        **PROFILE_DATA,
    }
    resp = client.post(f"/admin/societies/{society_id}/edit", data=form_data, follow_redirects=False)
    assert resp.status_code == 302

    row = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["instagram_url"] == PROFILE_DATA["instagram_url"]
