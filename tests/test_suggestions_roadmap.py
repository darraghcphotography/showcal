"""The suggestions system rebuild: submitter-chosen category, moderator
triage status, the public /suggestions Roadmap page, and the admin
changelog editor feeding its "Recently shipped" section."""
from conftest import seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_suggestion_requires_a_category(client, db):
    resp = client.post("/suggest", data={"message": "Add dark mode toggle"}, follow_redirects=False)
    assert resp.status_code == 200  # re-renders the form with an error
    assert db.execute("SELECT 1 FROM feature_suggestions").fetchone() is None


def test_suggestion_stores_category_and_optional_contact(client, db):
    resp = client.post(
        "/suggest",
        data={
            "message": "Add dark mode toggle", "category": "Idea/Feature",
            "submitted_name": "A Fan", "contact": "fan@example.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT * FROM feature_suggestions").fetchone()
    assert row["category"] == "Idea/Feature"
    assert row["contact"] == "fan@example.com"
    assert row["triage_status"] == "New"


def test_admin_can_update_category_and_status(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    db.execute(
        "INSERT INTO feature_suggestions (message, category) VALUES ('Prop rental listings', 'Idea/Feature')"
    )
    db.commit()
    suggestion_id = db.execute("SELECT id FROM feature_suggestions").fetchone()["id"]
    login_as(client, admin_id)

    resp = client.post(
        f"/admin/suggestions/{suggestion_id}/update",
        data={"category": "Idea/Feature", "triage_status": "In Progress"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT triage_status FROM feature_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    assert row["triage_status"] == "In Progress"


def test_update_suggestion_requires_login(client, db):
    db.execute("INSERT INTO feature_suggestions (message, category) VALUES ('X', 'Bug report')")
    db.commit()
    suggestion_id = db.execute("SELECT id FROM feature_suggestions").fetchone()["id"]

    resp = client.post(
        f"/admin/suggestions/{suggestion_id}/update",
        data={"category": "Bug report", "triage_status": "Done"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_roadmap_page_shows_triaged_and_hides_new(client, db):
    db.execute(
        "INSERT INTO feature_suggestions (message, category, triage_status) "
        "VALUES ('Untriaged idea', 'Idea/Feature', 'New')"
    )
    db.execute(
        "INSERT INTO feature_suggestions (message, category, triage_status) "
        "VALUES ('Prop rental listings', 'Idea/Feature', 'Planned')"
    )
    db.commit()

    resp = client.get("/suggestions")
    body = resp.get_data(as_text=True)
    assert "Prop rental listings" in body
    assert "Untriaged idea" not in body


def test_admin_can_publish_and_delete_changelog_entry(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    resp = client.post("/admin/changelog", data={"entry": "Shipped the new roadmap page."}, follow_redirects=False)
    assert resp.status_code == 302

    roadmap = client.get("/suggestions").get_data(as_text=True)
    assert "Shipped the new roadmap page." in roadmap

    entry_id = db.execute("SELECT id FROM changelog_entries").fetchone()["id"]
    client.post(f"/admin/changelog/{entry_id}/delete", follow_redirects=False)
    assert db.execute("SELECT 1 FROM changelog_entries").fetchone() is None

    roadmap_after = client.get("/suggestions").get_data(as_text=True)
    assert "Shipped the new roadmap page." not in roadmap_after


def test_changelog_page_requires_login(client):
    resp = client.get("/admin/changelog", follow_redirects=False)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]
