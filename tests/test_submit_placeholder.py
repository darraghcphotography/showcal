"""Submitting a show for a society+season that already has a blank "TBA"
placeholder (e.g. from the CSV import) must replace that row instead of
inserting a second one alongside it - see submit.py's new()."""
from conftest import seed_invite_code, seed_society


def unlock_invite(client, code_id):
    with client.session_transaction() as sess:
        sess["invite_code_id"] = code_id


def test_submission_replaces_existing_blank_placeholder(client, db):
    society_id = seed_society(db, name="Test Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '26/27', 'Eastern', NULL, 'approved', 'import')",
        (society_id,),
    )
    db.commit()
    code_id = seed_invite_code(db, code="AIMS-GEN01", society_id=None)
    unlock_invite(client, code_id)

    resp = client.post(
        "/submit/new",
        data={
            "society": "Test Society", "season": "26/27", "show": "Chicago",
            "opening_date": "", "closing_date": "", "adjudicated": "no",
            "confirm_new_title": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute(
        "SELECT show, moderation_status FROM shows WHERE society_id = ? AND season = '26/27'", (society_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["show"] == "Chicago"
    assert rows[0]["moderation_status"] == "pending"


def test_submission_with_no_placeholder_still_inserts_normally(client, db):
    society_id = seed_society(db, name="Test Society")
    code_id = seed_invite_code(db, code="AIMS-GEN02", society_id=None)
    unlock_invite(client, code_id)

    resp = client.post(
        "/submit/new",
        data={
            "society": "Test Society", "season": "26/27", "show": "Annie",
            "opening_date": "", "closing_date": "", "adjudicated": "no",
            "confirm_new_title": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute(
        "SELECT show FROM shows WHERE society_id = ? AND season = '26/27'", (society_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["show"] == "Annie"


def test_placeholder_for_a_different_season_is_untouched(client, db):
    society_id = seed_society(db, name="Test Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '27/28', 'Eastern', NULL, 'approved', 'import')",
        (society_id,),
    )
    db.commit()
    code_id = seed_invite_code(db, code="AIMS-GEN03", society_id=None)
    unlock_invite(client, code_id)

    resp = client.post(
        "/submit/new",
        data={
            "society": "Test Society", "season": "26/27", "show": "Chicago",
            "opening_date": "", "closing_date": "", "adjudicated": "no",
            "confirm_new_title": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    placeholder = db.execute(
        "SELECT 1 FROM shows WHERE society_id = ? AND season = '27/28' AND show IS NULL", (society_id,)
    ).fetchone()
    assert placeholder is not None
