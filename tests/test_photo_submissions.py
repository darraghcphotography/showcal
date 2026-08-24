"""/submit/photo - public, no invite code, no login: old review clippings and
production photos land in photo_submissions for a moderator to read and act
on by hand (see schema.sql and admin/photo_submissions.py). Nothing here is
expected to match an existing show/society."""
import io

from conftest import seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _photo_file(name="clipping.jpg"):
    return (io.BytesIO(b"fake image bytes"), name)


def test_get_renders_form(client):
    resp = client.get("/submit/photo")
    assert resp.status_code == 200
    assert b"Submit society history" in resp.data


def test_submission_with_no_notes_is_rejected(client, db):
    resp = client.post(
        "/submit/photo",
        data={"kind": "review", "notes": "", "photo": _photo_file()},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200  # re-renders the form with an error
    assert db.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 0


def test_submission_with_no_file_is_rejected(client, db):
    resp = client.post(
        "/submit/photo",
        data={"kind": "review", "notes": "An old ShowTimes clipping from 1998."},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert db.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 0


def test_valid_submission_is_stored_pending(client, db):
    resp = client.post(
        "/submit/photo",
        data={
            "kind": "production_photo",
            "notes": "Cast photo, think it's from the mid-90s.",
            "society_guess": "Test Society",
            "show_guess": "Oliver!",
            "date_guess": "sometime in the 90s",
            "submitter_name": "Jo",
            "submitter_email": "jo@example.com",
            "photo": _photo_file(),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT * FROM photo_submissions").fetchone()
    assert row["kind"] == "production_photo"
    assert row["status"] == "pending"
    assert row["show_guess"] == "Oliver!"
    assert row["filename"]


def test_honeypot_silently_drops_the_submission(client, db):
    resp = client.post(
        "/submit/photo",
        data={
            "kind": "review", "notes": "spam", "website": "http://spam.example",
            "photo": _photo_file(),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 0


def test_queue_requires_login(client):
    resp = client.get("/admin/photo-submissions")
    assert resp.status_code == 302


def test_queue_lists_pending_submission(client, db):
    admin_id = seed_user(db)
    db.execute(
        "INSERT INTO photo_submissions (kind, filename, notes) VALUES ('review', 'abc.jpg', 'An old clipping')"
    )
    db.commit()

    login_as(client, admin_id)
    body = client.get("/admin/photo-submissions").get_data(as_text=True)
    assert "An old clipping" in body


def test_mark_done_records_moderator_and_notes(client, db):
    admin_id = seed_user(db)
    db.execute(
        "INSERT INTO photo_submissions (kind, filename, notes) VALUES ('review', 'abc.jpg', 'An old clipping')"
    )
    db.commit()
    submission_id = db.execute("SELECT id FROM photo_submissions").fetchone()["id"]

    login_as(client, admin_id)
    resp = client.post(
        f"/admin/photo-submissions/{submission_id}/done",
        data={"moderator_notes": "Entered as a review on the 24/25 Chicago page."},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    row = db.execute("SELECT * FROM photo_submissions WHERE id = ?", (submission_id,)).fetchone()
    assert row["status"] == "done"
    assert row["moderator_notes"] == "Entered as a review on the 24/25 Chicago page."
    assert row["moderated_by"] == "mod"


def test_reject_sets_status(client, db):
    admin_id = seed_user(db)
    db.execute(
        "INSERT INTO photo_submissions (kind, filename, notes) VALUES ('production_photo', 'abc.jpg', 'blurry')"
    )
    db.commit()
    submission_id = db.execute("SELECT id FROM photo_submissions").fetchone()["id"]

    login_as(client, admin_id)
    client.post(f"/admin/photo-submissions/{submission_id}/reject", follow_redirects=False)

    row = db.execute("SELECT status FROM photo_submissions WHERE id = ?", (submission_id,)).fetchone()
    assert row["status"] == "rejected"


def test_cannot_action_an_already_actioned_submission_twice(client, db):
    admin_id = seed_user(db)
    db.execute(
        "INSERT INTO photo_submissions (kind, filename, notes, status) "
        "VALUES ('review', 'abc.jpg', 'x', 'done')"
    )
    db.commit()
    submission_id = db.execute("SELECT id FROM photo_submissions").fetchone()["id"]

    login_as(client, admin_id)
    resp = client.post(f"/admin/photo-submissions/{submission_id}/reject", follow_redirects=False)
    assert resp.status_code == 404
