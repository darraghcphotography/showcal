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


def test_venues_page_splits_out_societies_with_no_venue_evidence(client, db):
    """A society with none of its own shows recording a venue can't have a
    default inferred from data on hand - it should land in the separate
    "no evidence" section, not the main region-grouped table, and shouldn't
    count toward the progress bar's denominator."""
    admin_id = seed_user(db, username="mod", role="moderator")
    seed_society(db, id=1, name="Has Venue History", region="Eastern")
    seed_society(db, id=2, name="No Venue History", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue) "
        "VALUES (1, '25/26', 'Eastern', 'Oklahoma!', 'Town Hall Theatre')"
    )
    db.commit()
    login_as(client, admin_id)

    body = client.get("/admin/venues").get_data(as_text=True)
    has_evidence_pos = body.index("Has Venue History")
    no_evidence_pos = body.index("No Venue History")
    details_pos = body.index("No venue history on record yet")
    # The evidenced society renders before the "no evidence" <details>
    # section; the unevidenced one renders inside it.
    assert has_evidence_pos < details_pos < no_evidence_pos
    # Progress bar denominator (total) excludes the no-evidence society -
    # only "Has Venue History" counts, so it reads "0 / 1" not "0 / 2".
    assert "0</span> / 1" in body


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
