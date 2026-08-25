"""/calendar.ics's optional ?section=Gilbert/Sullivan, ?region=<region>,
?society=<id> and ?season=<season> filters (combinable) - same feed
mechanism as the unfiltered subscribe link, just narrowed, so e.g. an
adjudicator covering only one tier, a visitor who only cares about their own
region, or a society wanting just its own production history can subscribe
to just their own shows."""
from conftest import seed_society


def _insert_show(db, society_id, show, section, region="Eastern", opening_date="2026-11-10",
                  season="26/27"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'approved')",
        (society_id, season, region, section, show, opening_date, opening_date),
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


def test_region_filter_excludes_other_regions(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert", region="Midlands")
    _insert_show(db, society_id, "Sister Act", "Sullivan", region="Western")

    body = client.get("/calendar.ics?region=Midlands").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "SUMMARY:Sister Act" not in body
    assert "X-WR-CALNAME:DC Show Tracker - Midlands" in body


def test_invalid_region_falls_back_to_unfiltered(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert", region="Midlands")

    body = client.get("/calendar.ics?region=Narnia").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "X-WR-CALNAME:DC Show Tracker\r\n" in body


def test_section_and_region_filters_combine(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert", region="Midlands")
    _insert_show(db, society_id, "Annie", "Sullivan", region="Midlands")
    _insert_show(db, society_id, "Sister Act", "Gilbert", region="Western")

    body = client.get("/calendar.ics?section=Gilbert&region=Midlands").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "SUMMARY:Annie" not in body
    assert "SUMMARY:Sister Act" not in body
    assert "X-WR-CALNAME:DC Show Tracker - Gilbert - Midlands" in body


def test_society_filter_excludes_other_societies(client, db):
    a = seed_society(db, id=1, name="Alpha Musical Society")
    b = seed_society(db, id=2, name="Beta Musical Society")
    _insert_show(db, a, "Oliver!", "Gilbert")
    _insert_show(db, b, "Sister Act", "Sullivan")

    body = client.get(f"/calendar.ics?society={a}").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "SUMMARY:Sister Act" not in body
    assert "X-WR-CALNAME:DC Show Tracker - Alpha Musical Society" in body


def test_invalid_society_falls_back_to_unfiltered(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert")

    body = client.get("/calendar.ics?society=99999").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "X-WR-CALNAME:DC Show Tracker\r\n" in body


def test_hidden_society_is_not_matched_by_society_filter(client, db):
    society_id = seed_society(db)
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.commit()
    _insert_show(db, society_id, "Oliver!", "Gilbert")

    body = client.get(f"/calendar.ics?society={society_id}").get_data(as_text=True)
    assert "SUMMARY:Oliver!" not in body
    # falls back to unfiltered, but the show is still hidden by the base query
    assert "X-WR-CALNAME:DC Show Tracker\r\n" in body


def test_season_filter_excludes_other_seasons(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert", season="25/26")
    _insert_show(db, society_id, "Sister Act", "Sullivan", season="26/27")

    body = client.get("/calendar.ics?season=25/26").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "SUMMARY:Sister Act" not in body
    assert "X-WR-CALNAME:DC Show Tracker - 25/26" in body


def test_invalid_season_falls_back_to_unfiltered(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Oliver!", "Gilbert", season="25/26")

    body = client.get("/calendar.ics?season=99/00").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "X-WR-CALNAME:DC Show Tracker\r\n" in body


def test_society_and_season_filters_combine(client, db):
    a = seed_society(db, id=1, name="Alpha Musical Society")
    b = seed_society(db, id=2, name="Beta Musical Society")
    _insert_show(db, a, "Oliver!", "Gilbert", season="25/26")
    _insert_show(db, a, "Annie", "Sullivan", season="26/27")
    _insert_show(db, b, "Sister Act", "Gilbert", season="25/26")

    body = client.get(f"/calendar.ics?society={a}&season=25/26").get_data(as_text=True)
    assert "SUMMARY:Oliver!" in body
    assert "SUMMARY:Annie" not in body
    assert "SUMMARY:Sister Act" not in body
