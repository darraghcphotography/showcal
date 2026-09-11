"""A show in the middle of its run is still on.

Thurles Musical Society's Come From Away opened on 10 September 2026 and closed
on the 12th. On the 11th it had vanished from the homepage, because the homepage
asked "has it not opened yet?" when it meant "can someone still go and see it?".
Its own show page had the same fault in a worse place: it hid the ticket link,
on the one night of the run someone was most likely to want it.

These pin the difference between the two questions (see app/shows.py) rather
than any one page, because the bug was the questions being conflated.
"""
from datetime import date, timedelta

from conftest import seed_society
from app.shows import is_still_on, is_upcoming

TODAY = date.today()
YESTERDAY = (TODAY - timedelta(days=1)).isoformat()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()
LAST_WEEK = (TODAY - timedelta(days=7)).isoformat()
NEXT_WEEK = (TODAY + timedelta(days=7)).isoformat()


def row(opening, closing):
    return {"opening_date": opening, "closing_date": closing}


# --- the two rules themselves ------------------------------------------------

def test_a_show_mid_run_is_still_on_but_not_upcoming():
    """The case that tells the two rules apart."""
    mid_run = row(YESTERDAY, TOMORROW)
    assert is_still_on(mid_run) is True
    assert is_upcoming(mid_run) is False


def test_a_show_on_its_last_night_is_still_on():
    assert is_still_on(row(LAST_WEEK, TODAY.isoformat())) is True


def test_a_show_that_closed_yesterday_is_not():
    assert is_still_on(row(LAST_WEEK, YESTERDAY)) is False


def test_a_one_night_show_with_no_closing_date_is_on_for_that_day_only():
    assert is_still_on(row(TODAY.isoformat(), None)) is True
    assert is_still_on(row(YESTERDAY, None)) is False


def test_a_show_with_no_dates_is_not_still_on():
    assert is_still_on(row(None, None)) is False


def test_a_future_show_is_both():
    future = row(NEXT_WEEK, NEXT_WEEK)
    assert is_still_on(future) is True
    assert is_upcoming(future) is True


# --- the pages ---------------------------------------------------------------

def seed_show(db, title, opening, closing, ticket_url=None, venue_id=None):
    cur = db.execute(
        """
        INSERT INTO shows (society_id, season, region, section, show, venue,
                           opening_date, closing_date, ticket_url, moderation_status, source)
        VALUES (1, '26/27', 'Eastern', 'Gilbert', ?, 'The Hall', ?, ?, ?, 'approved', 'import')
        """,
        (title, opening, closing, ticket_url),
    )
    db.commit()
    return cur.lastrowid


def test_a_show_mid_run_stays_on_the_homepage(client, db):
    """The reported bug."""
    seed_society(db, id=1, name="Thurles Musical Society")
    seed_show(db, "Come From Away", YESTERDAY, TOMORROW)

    assert "Come From Away" in client.get("/").get_data(as_text=True)


def test_a_show_that_has_closed_leaves_the_homepage(client, db):
    """The fix must not keep finished shows up."""
    seed_society(db, id=1)
    seed_show(db, "Long Finished", LAST_WEEK, YESTERDAY)

    assert "Long Finished" not in client.get("/").get_data(as_text=True)


def test_a_show_mid_run_keeps_its_buy_tickets_button(client, db):
    """The same bug in its worst place. It demoted "Buy tickets" to a small grey
    "Ticket link" - the treatment meant for a show that has finished - on the
    nights people were actually booking."""
    seed_society(db, id=1)
    show_id = seed_show(db, "Come From Away", YESTERDAY, TOMORROW,
                        ticket_url="https://tickets.example.com/cfa")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "ticket-cta" in body
    assert "Buy tickets" in body


def test_a_closed_show_keeps_only_a_quiet_record_of_its_ticket_link(client, db):
    """Deliberate and unchanged: once a show has closed the link is kept as a
    record, but it stops being a call to action."""
    seed_society(db, id=1)
    show_id = seed_show(db, "Done And Dusted", LAST_WEEK, YESTERDAY,
                        ticket_url="https://tickets.example.com/old")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Buy tickets" not in body
    assert "https://tickets.example.com/old" in body


def test_a_show_mid_run_can_still_be_added_to_a_calendar(client, db):
    """Someone deciding to go tomorrow night still wants the date."""
    seed_society(db, id=1)
    show_id = seed_show(db, "Come From Away", YESTERDAY, TOMORROW)

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "calendar.google.com" in body
