"""/submit/photo - public, no invite code, no login: old review clippings and
production photos land in photo_submissions for a moderator to read and act
on by hand (see schema.sql and admin/photo_submissions.py). Nothing here is
expected to match an existing show/society."""
import io

from PIL import Image

from conftest import seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _photo_file(name="clipping.jpg"):
    """A real (tiny) JPEG, not a placeholder byte string. Uploads are decoded
    on the way in as of 2026-08-25 (app/uploads.py's _viewable_bytes), so
    b"fake image bytes" named .jpg is now correctly rejected - which is the
    whole point of that change, and used to be what this fixture handed in."""
    buf = io.BytesIO()
    Image.new("RGB", (40, 60), color=(120, 30, 30)).save(buf, format="JPEG")
    buf.seek(0)
    return (buf, name)


def test_get_renders_form(client):
    resp = client.get("/submit/photo")
    assert resp.status_code == 200
    assert b"Submit society history" in resp.data


def test_submission_with_no_notes_is_rejected(client, db):
    resp = client.post(
        "/submit/photo",
        data={"kind": "programme_history", "notes": "", "photo": _photo_file()},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200  # re-renders the form with an error
    assert db.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 0


def test_submission_with_no_file_is_rejected(client, db):
    resp = client.post(
        "/submit/photo",
        data={"kind": "programme_history", "notes": "An old ShowTimes clipping from 1998."},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert db.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 0


def test_valid_submission_is_stored_pending(client, db):
    resp = client.post(
        "/submit/photo",
        data={
            "kind": "poster",
            "notes": "Vintage show poster from 1995.",
            "society_guess": "Test Society",
            "show_guess": "Oliver!",
            "submitter_name": "Jo",
            "submitter_email": "jo@example.com",
            "photo": _photo_file(),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT * FROM photo_submissions").fetchone()
    assert row["kind"] == "poster"
    assert row["status"] == "pending"
    assert row["show_guess"] == "Oliver!"
    assert row["filename"]


def test_multiple_photos_create_one_row_each_sharing_notes(client, db):
    """M1: a phone submission with several photos used to keep only one
    (see #6/#7, #8/#9 in the small-items queue) - now every file becomes its
    own photo_submissions row, all sharing the same notes/guesses."""
    resp = client.post(
        "/submit/photo",
        data={
            "kind": "programme_history",
            "notes": "Three pages from the same 1994 programme.",
            "photo": [_photo_file("a.jpg"), _photo_file("b.jpg"), _photo_file("c.jpg")],
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    rows = db.execute("SELECT * FROM photo_submissions").fetchall()
    assert len(rows) == 3
    filenames = {row["filename"] for row in rows}
    assert len(filenames) == 3  # each file saved under its own name
    assert all(row["notes"] == "Three pages from the same 1994 programme." for row in rows)


def test_one_bad_file_rejects_the_whole_batch(client, db):
    """A partial success that looks like a full one is how the data loss this
    feature fixes started - so one undecodable file must reject everything,
    not just skip that file."""
    bad_file = (io.BytesIO(b"not actually an image"), "fake.jpg")
    resp = client.post(
        "/submit/photo",
        data={
            "kind": "programme_history",
            "notes": "A batch with one bad file in it.",
            "photo": [_photo_file("a.jpg"), bad_file, _photo_file("c.jpg")],
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200  # re-renders the form with an error
    assert db.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 0


def test_honeypot_silently_drops_the_submission(client, db):
    resp = client.post(
        "/submit/photo",
        data={
            "kind": "poster", "notes": "spam", "website": "http://spam.example",
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
        "INSERT INTO photo_submissions (kind, filename, notes) VALUES ('programme_history', 'abc.jpg', 'An old clipping')"
    )
    db.commit()

    login_as(client, admin_id)
    body = client.get("/admin/photo-submissions").get_data(as_text=True)
    assert "An old clipping" in body


def test_mark_done_records_moderator_and_notes(client, db):
    admin_id = seed_user(db)
    db.execute(
        "INSERT INTO photo_submissions (kind, filename, notes) VALUES ('poster', 'abc.jpg', 'An old clipping')"
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
        "INSERT INTO photo_submissions (kind, filename, notes) VALUES ('other', 'abc.jpg', 'blurry')"
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
        "VALUES ('programme_history', 'abc.jpg', 'x', 'done')"
    )
    db.commit()
    submission_id = db.execute("SELECT id FROM photo_submissions").fetchone()["id"]

    login_as(client, admin_id)
    resp = client.post(f"/admin/photo-submissions/{submission_id}/reject", follow_redirects=False)
    assert resp.status_code == 404

def test_programme_history_and_posters_are_offered(client, db):
    form = client.get("/submit/photo").get_data(as_text=True)
    assert 'value="programme_history"' in form
    assert 'value="poster"' in form
    assert 'value="other"' in form

    resp = client.post(
        "/submit/photo",
        data={
            "kind": "programme_history",
            "notes": "Page 12 lists every show they did from 1971 on.",
            "photo": _photo_file(),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    assert db.execute("SELECT kind FROM photo_submissions").fetchone()[0] == "programme_history"


def test_an_unknown_kind_is_still_rejected(client, db):
    resp = client.post(
        "/submit/photo",
        data={"kind": "unknown_invalid_kind", "notes": "Something else.", "photo": _photo_file()},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert db.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 0


def test_the_kind_migration_widens_the_check_and_keeps_old_rows(app):
    """The migration rebuilds photo_submissions to widen its CHECK constraint,
    which SQLite cannot ALTER in place. Rows submitted under the old two-kind
    vocabulary keep the kind they were sent under - re-sorting them is a
    judgement only a moderator looking at the photo can make."""
    import sqlite3

    from app.db import _migrate_photo_submission_kinds

    with app.app_context():
        from app.db import get_db

        live = get_db()
        # Put the table back in its pre-migration shape, then migrate it.
        live.execute("DROP TABLE photo_submissions")
        live.execute(
            "CREATE TABLE photo_submissions ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " kind TEXT NOT NULL CHECK (kind IN ('review', 'production_photo')),"
            " filename TEXT NOT NULL, society_guess TEXT, show_guess TEXT,"
            " date_guess TEXT, notes TEXT, submitter_name TEXT, submitter_email TEXT,"
            " status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'rejected')),"
            " moderator_notes TEXT, moderated_by TEXT, moderated_at TEXT,"
            " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        live.execute(
            "INSERT INTO photo_submissions (id, kind, filename, notes) "
            "VALUES (900, 'production_photo', 'old.jpg', 'pre-split submission')"
        )
        try:
            live.execute(
                "INSERT INTO photo_submissions (kind, filename) VALUES ('programme_history', 'x.jpg')"
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("the old CHECK should not have accepted programme_history")

        _migrate_photo_submission_kinds(live)

        row = live.execute("SELECT kind, notes FROM photo_submissions WHERE id = 900").fetchone()
        assert row["kind"] == "production_photo"
        assert row["notes"] == "pre-split submission"

        live.execute(
            "INSERT INTO photo_submissions (kind, filename) VALUES ('programme_history', 'x.jpg')"
        )
        # ...and running it again is a no-op rather than a second rebuild.
        _migrate_photo_submission_kinds(live)
        assert live.execute("SELECT COUNT(*) FROM photo_submissions").fetchone()[0] == 2
        live.commit()
