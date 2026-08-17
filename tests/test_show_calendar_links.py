"""Show page "Add to Google Calendar" link + the public "Adjudication
submission cut-off" date field - see public.show_detail(). The interactive
"remind me to check forms were submitted" calendar link moved to the
society's own edit-show page (see test_society_adjudication_reminder.py) -
only useful to that show's committee, not a random visitor."""
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


def test_adjudication_cutoff_is_exactly_6_weeks_before_opening(client, db):
    society_id = seed_society(db)
    opening = date(2026, 11, 10)
    show_id = _insert_show(db, society_id, opening.isoformat())

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    cutoff = opening - timedelta(weeks=6)
    assert cutoff.strftime("%d-%m-%Y") in body
    assert "Adjudication submission cut-off" in body
    # the interactive reminder link itself lives on the society edit page now, not here
    assert "CHECK+ADJUDICATION+FORMS" not in body


def test_adjudication_cutoff_hidden_when_not_adjudicated(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2026-11-10", review_status="Not adjudicated")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Adjudication submission cut-off" not in body
    # the plain "add to calendar" link should still be there
    assert "calendar.google.com/calendar/render" in body


def test_calendar_links_hidden_once_show_is_finished(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2020-01-06", "2020-01-10")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "calendar.google.com" not in body
    assert "Adjudication submission cut-off" not in body


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
    assert "Adjudication submission cut-off" not in body
