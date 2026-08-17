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


def test_admin_note_shown_publicly_only_for_done_suggestions(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    db.execute(
        "INSERT INTO feature_suggestions (message, category, triage_status) "
        "VALUES ('Prop rental listings', 'Idea/Feature', 'Planned')"
    )
    db.commit()
    suggestion_id = db.execute("SELECT id FROM feature_suggestions").fetchone()["id"]
    login_as(client, admin_id)

    client.post(
        f"/admin/suggestions/{suggestion_id}/update",
        data={
            "category": "Idea/Feature", "triage_status": "Planned",
            "admin_note": "Scoped down to just costume listings for now",
        },
        follow_redirects=False,
    )
    row = db.execute("SELECT admin_note FROM feature_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    assert row["admin_note"] == "Scoped down to just costume listings for now"

    # Saved, but not shown publicly yet - still in the Planned lane, not Done.
    roadmap = client.get("/suggestions").get_data(as_text=True)
    assert "Scoped down to just costume listings for now" not in roadmap

    client.post(
        f"/admin/suggestions/{suggestion_id}/update",
        data={
            "category": "Idea/Feature", "triage_status": "Done",
            "admin_note": "Shipped as a costume/prop listings section on society pages",
        },
        follow_redirects=False,
    )
    roadmap = client.get("/suggestions").get_data(as_text=True)
    assert "Shipped as a costume/prop listings section on society pages" in roadmap


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


def test_roadmap_shows_done_suggestions_in_their_own_lane(client, db):
    db.execute(
        "INSERT INTO feature_suggestions (message, category, triage_status) "
        "VALUES ('Delete/archive suggestions in admin', 'Idea/Feature', 'Done')"
    )
    db.commit()

    body = client.get("/suggestions").get_data(as_text=True)
    assert "Delete/archive suggestions in admin" in body
    done_lane = body.split('class="lane lane-done"')[1].split("</div>\n  <div class=\"lane")[0]
    assert "Delete/archive suggestions in admin" in done_lane


def test_roadmap_does_not_double_list_done_suggestion_in_recently_shipped(client, db):
    db.execute(
        "INSERT INTO feature_suggestions (message, category, triage_status) "
        "VALUES ('Fix a 404 on the awards page', 'Bug report', 'Done')"
    )
    db.commit()

    body = client.get("/suggestions").get_data(as_text=True)
    shipped_section = body.split("Recently shipped</h2>")[1]
    assert "Fix a 404 on the awards page" not in shipped_section


def test_roadmap_shows_deployed_at_timestamp(client):
    body = client.get("/suggestions").get_data(as_text=True)
    assert "Latest version deployed:" in body


def test_changelog_entry_renders_each_line_as_a_bullet(client, db):
    db.execute(
        "INSERT INTO changelog_entries (entry) VALUES (?)",
        ("Roadmap page redesign\nStatus lanes with a Done column\nColour-coded by category",),
    )
    db.commit()

    body = client.get("/suggestions").get_data(as_text=True)
    assert "<li>Roadmap page redesign</li>" in body
    assert "<li>Status lanes with a Done column</li>" in body
    assert "<li>Colour-coded by category</li>" in body


def test_roadmap_category_dot_matches_category(client, db):
    db.execute(
        "INSERT INTO feature_suggestions (message, category, triage_status) "
        "VALUES ('Fix mobile nav overlap', 'Bug report', 'In Progress')"
    )
    db.commit()

    body = client.get("/suggestions").get_data(as_text=True)
    progress_lane = body.split('class="lane lane-progress"')[1].split("</div>\n  <div class=\"lane")[0]
    assert 'cat-dot cat-bug' in progress_lane
