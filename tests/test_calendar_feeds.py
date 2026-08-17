"""/calendar.ics's optional ?section=Gilbert/Sullivan filter - same feed
mechanism as the unfiltered subscribe link, just narrowed, so e.g. an
adjudicator covering only one tier can subscribe to just their own shows."""
from conftest import seed_society


def _insert_show(db, society_id, show, section, opening_date="2026-11-10"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', ?, ?, ?, ?, 'approved')",
        (society_id, section, show, opening_date, opening_date),
    )
    db.commit()


def test_unfiltered_feed_includes_both_tiers(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert")
    _insert_show(db, society_id, "Sister Act", "Sullivan")

    body = client.get("/calendar.ics").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "SUMMARY:Sister Act" in body
    assert "X-WR-CALNAME:DC Show Tracker\r\n" in body


def test_gilbert_filter_excludes_sullivan(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert")
    _insert_show(db, society_id, "Sister Act", "Sullivan")

    body = client.get("/calendar.ics?section=Gilbert").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "SUMMARY:Sister Act" not in body
    assert "X-WR-CALNAME:DC Show Tracker - Gilbert" in body


def test_sullivan_filter_excludes_gilbert(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert")
    _insert_show(db, society_id, "Sister Act", "Sullivan")

    body = client.get("/calendar.ics?section=Sullivan").get_data(as_text=True)
    assert "SUMMARY:Sister Act" in body
    assert "SUMMARY:Oliver!" not in body
    assert "X-WR-CALNAME:DC Show Tracker - Sullivan" in body


def test_invalid_section_falls_back_to_unfiltered(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert")

    body = client.get("/calendar.ics?section=bogus").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "X-WR-CALNAME:DC Show Tracker\r\n" in body
