"""/admin/logo-candidates - review queue for candidate society logos staged
by import_logo_candidates.py (see schema.sql's logo_candidates table). A
candidate is already fetched/decoded/saved locally before it ever reaches
this queue (app/uploads.py's fetch_logo_candidate) - approve just points
societies.logo_filename at that already-validated file; nothing here fetches
anything live."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_candidate(db, society_id, filename="abc123.webp", fetch_error=None,
                    source_url="https://example.com/logo.png", status="pending"):
    db.execute(
        "INSERT INTO logo_candidates (society_id, source_url, source_page_url, notes, filename, fetch_error, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (society_id, source_url, "https://example.com/", "Header logo", filename, fetch_error, status),
    )
    db.commit()
    return db.execute("SELECT id FROM logo_candidates WHERE society_id = ?", (society_id,)).fetchone()["id"]


def test_queue_requires_login(client):
    resp = client.get("/admin/logo-candidates")
    assert resp.status_code == 302


def test_queue_lists_a_pending_candidate(client, db):
    user_id = seed_user(db)
    society_id = seed_society(db, name="Baldoyle Musical Society")
    seed_candidate(db, society_id)
    login_as(client, user_id)

    body = client.get("/admin/logo-candidates").get_data(as_text=True)
    assert "Baldoyle Musical Society" in body
    assert "abc123.webp" in body


def test_a_candidate_with_no_filename_shows_the_fetch_error_and_no_image(client, db):
    user_id = seed_user(db)
    society_id = seed_society(db)
    seed_candidate(db, society_id, filename=None, fetch_error="Could not fetch: 404")
    login_as(client, user_id)

    body = client.get("/admin/logo-candidates").get_data(as_text=True)
    assert "Could not fetch: 404" in body
    assert "<img" not in body


def test_approve_sets_the_society_logo_and_marks_the_candidate_approved(client, db):
    user_id = seed_user(db)
    society_id = seed_society(db)
    candidate_id = seed_candidate(db, society_id, filename="the-real-logo.webp")
    login_as(client, user_id)

    resp = client.post(f"/admin/logo-candidates/{candidate_id}/approve",
                        data={"csrf_token": "x"})
    assert resp.status_code == 302

    society = db.execute("SELECT logo_filename FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert society["logo_filename"] == "the-real-logo.webp"

    candidate = db.execute("SELECT status, moderated_by FROM logo_candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate["status"] == "approved"
    assert candidate["moderated_by"] == "mod"


def test_approve_refuses_a_candidate_with_no_fetched_file(client, db):
    user_id = seed_user(db)
    society_id = seed_society(db)
    candidate_id = seed_candidate(db, society_id, filename=None, fetch_error="Could not fetch: timeout")
    login_as(client, user_id)

    client.post(f"/admin/logo-candidates/{candidate_id}/approve", data={"csrf_token": "x"})

    society = db.execute("SELECT logo_filename FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert society["logo_filename"] is None
    candidate = db.execute("SELECT status FROM logo_candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate["status"] == "pending"


def test_reject_marks_the_candidate_rejected_without_touching_the_society(client, db):
    user_id = seed_user(db)
    society_id = seed_society(db)
    candidate_id = seed_candidate(db, society_id)
    login_as(client, user_id)

    resp = client.post(f"/admin/logo-candidates/{candidate_id}/reject",
                        data={"csrf_token": "x", "moderator_notes": "wrong crest"})
    assert resp.status_code == 302

    society = db.execute("SELECT logo_filename FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert society["logo_filename"] is None
    candidate = db.execute(
        "SELECT status, moderator_notes FROM logo_candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate["status"] == "rejected"
    assert candidate["moderator_notes"] == "wrong crest"


def test_approved_and_rejected_candidates_no_longer_show_in_the_pending_list(client, db):
    user_id = seed_user(db)
    society_id = seed_society(db)
    candidate_id = seed_candidate(db, society_id)
    login_as(client, user_id)

    client.post(f"/admin/logo-candidates/{candidate_id}/reject", data={"csrf_token": "x"})

    body = client.get("/admin/logo-candidates").get_data(as_text=True)
    assert "Nothing waiting for review" in body


def test_dashboard_shows_pending_logo_candidate_count(client, db):
    user_id = seed_user(db)
    society_id = seed_society(db)
    seed_candidate(db, society_id)
    login_as(client, user_id)

    body = client.get("/admin/").get_data(as_text=True)
    assert "Logo candidates" in body
