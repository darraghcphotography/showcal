"""The "remind me to check adjudication forms were submitted" calendar
link on the society's own edit-show page (society.edit_show) - moved here
from the public show page since it's only useful to that show's own
committee, not a random visitor - see app/blueprints/society.py's
_adjudication_reminder_url()."""
from datetime import date, timedelta

from conftest import seed_invite_code, seed_society


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def _insert_show(db, society_id, opening_date, review_status="None"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "review_status, moderation_status) VALUES (?, '26/27', 'Eastern', 'Oliver!', ?, ?, ?, 'approved')",
        (society_id, opening_date, opening_date, review_status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE society_id = ?", (society_id,)).fetchone()["id"]


def test_reminder_shown_for_own_upcoming_show(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC01", society_id=society_id)
    unlock_society(client, code_id)
    opening = date(2026, 11, 10)
    show_id = _insert_show(db, society_id, opening.isoformat())

    body = client.get(f"/society/shows/{show_id}/edit").get_data(as_text=True)
    reminder = opening - timedelta(weeks=8)
    assert "calendar.google.com/calendar/render" in body
    assert reminder.strftime("%Y%m%d") in body


def test_reminder_hidden_when_not_adjudicated(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC02", society_id=society_id)
    unlock_society(client, code_id)
    show_id = _insert_show(db, society_id, "2026-11-10", review_status="Not adjudicated")

    body = client.get(f"/society/shows/{show_id}/edit").get_data(as_text=True)
    assert "calendar.google.com" not in body


def test_reminder_hidden_for_finished_show(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC03", society_id=society_id)
    unlock_society(client, code_id)
    show_id = _insert_show(db, society_id, "2020-01-06")

    body = client.get(f"/society/shows/{show_id}/edit").get_data(as_text=True)
    assert "calendar.google.com" not in body


def test_reminder_not_visible_to_a_different_society(client, db):
    owner_id = seed_society(db, id=1, name="Owner Society")
    other_id = seed_society(db, id=2, name="Other Society")
    show_id = _insert_show(db, owner_id, "2026-11-10")

    other_code_id = seed_invite_code(db, code="AIMS-SOC04", society_id=other_id)
    unlock_society(client, other_code_id)

    resp = client.get(f"/society/shows/{show_id}/edit")
    assert resp.status_code == 404
