"""Adding one show to your own calendar.

Darragh asked for "Add to Google Calendar instead of the downloadable .ics"
(2026-09-04), on the reasoning that it opens better on a phone. Two things were
wrong with that as stated, and this file exists because both are easy to undo
by accident later:

  1. **The Google link already existed** - a small text link inside the Dates
     row, which is why he had never noticed it. The gap was presentation.

  2. **Dropping the .ics would have made mobile worse, not better.** Tapping an
     .ics on iOS opens Apple Calendar natively. Apple Calendar has no
     "pre-filled event URL" equivalent at all, so the .ics is the *only* route
     that reaches it - and a large share of Irish committee members are on
     iPhones. Google-only excludes them.

So the answer was four routes behind one control, not a swap. The separate
`/calendar.ics` feed is a different thing again - a *subscription* to many
shows that keeps updating - and is deliberately untouched.
"""
from conftest import seed_society


def _seed_show(db, opening="2099-09-10", closing="2099-09-13",
               show="Come From Away", venue="The Premier Hall, Thurles",
               status="approved", hidden=0):
    society_id = seed_society(db, name="Thurles Musical Society")
    if hidden:
        db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "venue, moderation_status) VALUES (?, '26/27', 'Eastern', ?, ?, ?, ?, ?)",
        (society_id, show, opening, closing, venue, status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows ORDER BY id DESC LIMIT 1").fetchone()["id"]


def test_a_single_show_downloads_as_its_own_calendar_file(client, db):
    show_id = _seed_show(db)
    r = client.get(f"/shows/{show_id}/calendar.ics")

    assert r.status_code == 200
    assert r.mimetype == "text/calendar"
    body = r.get_data(as_text=True)
    assert body.count("BEGIN:VEVENT") == 1, "a single-show download must hold exactly one event"
    assert "SUMMARY:Come From Away - Thurles Musical Society" in body
    assert "DTSTART;VALUE=DATE:20990910" in body


def test_it_carries_a_filename_a_person_can_find_again(client, db):
    """"calendar.ics" in a downloads folder is unfindable a week later."""
    show_id = _seed_show(db)
    r = client.get(f"/shows/{show_id}/calendar.ics")
    assert 'filename="come-from-away.ics"' in r.headers["Content-Disposition"]


def test_the_end_date_is_exclusive_so_the_run_is_not_a_day_short(client, db):
    """RFC 5545's DTEND for an all-day event is the day *after* the last day.
    Getting this wrong drops closing night off the calendar entry - and it is
    the single easiest thing to "fix" incorrectly, because the off-by-one looks
    like a bug in the other direction."""
    show_id = _seed_show(db, opening="2099-09-10", closing="2099-09-13")
    body = client.get(f"/shows/{show_id}/calendar.ics").get_data(as_text=True)
    assert "DTEND;VALUE=DATE:20990914" in body


def test_a_one_night_run_still_gets_a_whole_day(client, db):
    show_id = _seed_show(db, opening="2099-09-10", closing=None)
    body = client.get(f"/shows/{show_id}/calendar.ics").get_data(as_text=True)
    assert "DTSTART;VALUE=DATE:20990910" in body
    assert "DTEND;VALUE=DATE:20990911" in body


def test_the_single_event_matches_the_feeds_event_exactly(client, db):
    """Both come from `_vevent`. If they ever diverge, someone subscribed to
    the feed who also added this show by hand gets it twice - the UID is what
    prevents that, so it has to be identical."""
    show_id = _seed_show(db)
    single = client.get(f"/shows/{show_id}/calendar.ics").get_data(as_text=True)
    feed = client.get("/calendar.ics").get_data(as_text=True)

    uid = f"UID:show-{show_id}@aims-show-tracker"
    assert uid in single and uid in feed

    def event(text):
        start = text.index("BEGIN:VEVENT")
        return [ln for ln in text[start:text.index("END:VEVENT", start)].splitlines()
                if not ln.startswith("DTSTAMP")]

    assert event(single) == event(feed)


def test_an_unapproved_show_has_no_calendar_file(client, db):
    show_id = _seed_show(db, status="pending")
    assert client.get(f"/shows/{show_id}/calendar.ics").status_code == 404


def test_a_hidden_societys_show_has_no_calendar_file(client, db):
    show_id = _seed_show(db, hidden=1)
    assert client.get(f"/shows/{show_id}/calendar.ics").status_code == 404


def test_a_show_with_no_date_has_no_calendar_file(client, db):
    show_id = _seed_show(db, opening=None, closing=None)
    assert client.get(f"/shows/{show_id}/calendar.ics").status_code == 404


def test_the_show_page_offers_every_calendar_route_not_just_google(client, db):
    """The whole point of the change. Google-only silently excluded Apple."""
    show_id = _seed_show(db)
    html = client.get(f"/shows/{show_id}").get_data(as_text=True)

    assert "calendar.google.com" in html, "Google route missing"
    assert "outlook.live.com" in html, "Outlook route missing"
    assert f"/shows/{show_id}/calendar.ics" in html, "the .ics route - the only one Apple can use - is missing"
    assert "Add to calendar" in html


def test_outlook_gets_the_same_exclusive_end_date_as_google(client, db):
    """Outlook also treats an all-day `enddt` as exclusive, so the same value
    is correct for both. Someone "fixing" one of them to look right in
    isolation breaks the other."""
    show_id = _seed_show(db, opening="2099-09-10", closing="2099-09-13")
    html = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "2099-09-14" in html or "2099-09-14".replace("-", "%2D") in html
    assert "20990910%2F20990914" in html or "20990910/20990914" in html


def test_the_subscribable_feed_is_untouched(client, db):
    """It answers a different question - "keep me up to date with all of
    these" - and swapping it for per-show links would lose that quietly."""
    _seed_show(db)
    r = client.get("/calendar.ics")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "BEGIN:VCALENDAR" in body and "X-WR-CALNAME:DC Show Tracker" in body
