"""Show page "Add to Google Calendar" + adjudication-forms reminder links -
plain URLs, no auth/API integration, no schema/backend needed - see
public.show_detail()'s _google_calendar_url()."""
from datetime import date, timedelta

from conftest import seed_society


def _insert_show(db, society_id, opening_date, closing_date=None, review_status="None"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "review_status, moderation_status) VALUES (?, '26/27', 'Eastern', 'Oliver!', ?, ?, ?, 'approved')",
        (society_id, opening_date, closing_date or opening_date, review_status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE society_id = ?", (society_id,)).fetchone()["id"]


def test_show_calendar_link_covers_opening_to_closing(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2026-11-10", "2026-11-14")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "calendar.google.com/calendar/render" in body
    # end date in a Google Calendar all-day link is exclusive (day after closing)
    assert "20261110%2F20261115" in body


def test_adjudication_reminder_is_exactly_8_weeks_before_opening(client, db):
    society_id = seed_society(db)
    opening = date(2026, 11, 10)
    show_id = _insert_show(db, society_id, opening.isoformat())

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    reminder = opening - timedelta(weeks=8)
    assert reminder.strftime("%Y%m%d") in body
    assert "CHECK+ADJUDICATION+FORMS" in body or "CHECK%20ADJUDICATION%20FORMS" in body


def test_adjudication_reminder_hidden_when_not_adjudicated(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2026-11-10", review_status="Not adjudicated")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "check adjudication forms" not in body.lower()
    # the plain "add to calendar" link should still be there
    assert "calendar.google.com/calendar/render" in body


def test_calendar_links_hidden_once_show_is_finished(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2020-01-06", "2020-01-10")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "calendar.google.com" not in body


def test_no_calendar_links_when_opening_date_unset(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', 'TBA Show', 'approved')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE society_id = ?", (society_id,)).fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "calendar.google.com" not in body
