"""/admin/venues - a per-field autosave grid for backfilling
societies.default_venue, grouped by region (see app/blueprints/admin.py's
venues()/save_venue())."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_venues_page_groups_by_region_and_excludes_inactive(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    seed_society(db, id=1, name="Active Eastern Society", region="Eastern", section="Gilbert")
    seed_society(db, id=2, name="Retired Society", region="Eastern", section="Inactive")
    login_as(client, admin_id)

    body = client.get("/admin/venues").get_data(as_text=True)
    assert "Active Eastern Society" in body
    assert "Retired Society" not in body


def test_venues_page_requires_login(client):
    resp = client.get("/admin/venues")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_save_venue_updates_default_venue(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    login_as(client, admin_id)

    resp = client.post("/admin/venues/save", data={"society_id": society_id, "venue": "Town Hall Theatre"})
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "venue": "Town Hall Theatre"}

    row = db.execute("SELECT default_venue FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["default_venue"] == "Town Hall Theatre"


def test_save_venue_blank_clears_it(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    db.execute("UPDATE societies SET default_venue = 'Old Venue' WHERE id = ?", (society_id,))
    db.commit()
    login_as(client, admin_id)

    resp = client.post("/admin/venues/save", data={"society_id": society_id, "venue": "  "})
    assert resp.status_code == 200
    assert resp.get_json()["venue"] is None

    row = db.execute("SELECT default_venue FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["default_venue"] is None


def test_save_venue_requires_login(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    resp = client.post("/admin/venues/save", data={"society_id": society_id, "venue": "Somewhere"})
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_save_venue_unknown_society_returns_404(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    resp = client.post("/admin/venues/save", data={"society_id": 999, "venue": "Somewhere"})
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False
