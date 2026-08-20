"""/venues and /venues/<venue> - deliberately thin: name, resident
societies, and stage history only, computed live from shows.venue. No
capacity/type/map fields - that structured data doesn't exist anywhere in
the schema (see ROADMAP.md's Venues Explorer scoping, 2026-08-21). Exact
string match on venue name, same "not fuzzy" policy as title matching
elsewhere on the site - see public.py's venues_index()/venue_detail()."""
from conftest import seed_society


def add_show(db, society_id, show, venue, season="24/25", opening_date="2025-01-05",
             closing_date="2025-01-10", status=None, moderation_status="approved"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue, opening_date, closing_date, "
        "status, moderation_status) VALUES (?, ?, 'Eastern', ?, ?, ?, ?, ?, ?)",
        (society_id, season, show, venue, opening_date, closing_date, status, moderation_status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE show = ? AND season = ?", (show, season)).fetchone()["id"]


def test_index_lists_venue_with_counts(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Gorey Little Theatre")

    body = client.get("/venues").get_data(as_text=True)
    assert "Gorey Little Theatre" in body
    assert "<strong>1</strong> production" in body
    assert "<strong>1</strong> society" in body


def test_index_counts_multiple_productions_and_societies(client, db):
    a = seed_society(db, id=1, name="Society A")
    b = seed_society(db, id=2, name="Society B")
    add_show(db, a, "Oliver!", "Shared Theatre", season="24/25")
    add_show(db, b, "Oklahoma!", "Shared Theatre", season="23/24")

    body = client.get("/venues").get_data(as_text=True)
    assert "<strong>2</strong> productions" in body
    assert "<strong>2</strong> societies" in body


def test_search_filters_by_venue_name(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Gorey Little Theatre")
    add_show(db, society_id, "Oklahoma!", "dlr Mill Theatre", season="23/24")

    body = client.get("/venues?q=Gorey").get_data(as_text=True)
    assert "Gorey Little Theatre" in body
    assert "dlr Mill Theatre" not in body


def test_venue_name_matching_is_exact_not_fuzzy(client, db):
    """A casing/spelling variant of the same real venue stays a separate
    entry - deliberate, matches the site's title-matching policy."""
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Gorey Little Theatre", season="24/25")
    add_show(db, society_id, "Oklahoma!", "gorey little theatre", season="23/24")

    body = client.get("/venues").get_data(as_text=True)
    assert "<strong>1</strong> production" in body  # each venue string is its own card


def test_hidden_society_excluded(client, db):
    society_id = seed_society(db)
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.commit()
    add_show(db, society_id, "Hidden Show", "Hidden Venue")

    body = client.get("/venues").get_data(as_text=True)
    assert "Hidden Venue" not in body


def test_pending_show_excluded(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Not Yet Approved", "Pending Venue", moderation_status="pending")

    body = client.get("/venues").get_data(as_text=True)
    assert "Pending Venue" not in body


def test_unknown_venue_404s(client):
    resp = client.get("/venues/Nowhere%20At%20All")
    assert resp.status_code == 404


def test_detail_shows_resident_societies_with_counts(client, db):
    a = seed_society(db, id=1, name="Frequent Flyers")
    b = seed_society(db, id=2, name="One Timer")
    add_show(db, a, "Oliver!", "The Venue", season="24/25")
    add_show(db, a, "Oklahoma!", "The Venue", season="22/23")
    add_show(db, b, "Chicago", "The Venue", season="21/22")

    body = client.get("/venues/The Venue").get_data(as_text=True)
    assert "Frequent Flyers" in body
    assert "2 productions here" in body
    assert "One Timer" in body
    assert "1 production here" in body


def test_detail_splits_upcoming_and_past(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Past Show", "The Venue", season="22/23",
             opening_date="2020-01-01", closing_date="2020-01-05")
    add_show(db, society_id, "Future Show", "The Venue", season="26/27",
             opening_date="2099-01-01", closing_date="2099-01-05")

    body = client.get("/venues/The Venue").get_data(as_text=True)
    upcoming_section = body.split("Upcoming here")[1].split("Stage history")[0]
    history_section = body.split("Stage history")[1]
    assert "Future Show" in upcoming_section
    assert "Past Show" not in upcoming_section
    assert "Past Show" in history_section
    assert "Future Show" not in history_section


def test_cancelled_upcoming_show_treated_as_not_upcoming(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Cancelled Show", "The Venue", season="26/27",
             opening_date="2099-01-01", closing_date="2099-01-05", status="Cancelled")

    body = client.get("/venues/The Venue").get_data(as_text=True)
    assert "Upcoming here" not in body


def test_span_shows_single_season_without_a_dash_when_theres_only_one(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Only Show", "One Season Venue", season="23/24")

    body = client.get("/venues/One Season Venue").get_data(as_text=True)
    assert '<span class="stat-value">23/24</span>' in body
    assert "23/24–23/24" not in body


def test_index_sorts_by_most_productions_first_not_alphabetical(client, db):
    """The free-text venue field has real noise (data-entry slips, near-
    duplicate spellings) - alphabetical order put exactly that noise first.
    Most-used venues should lead instead."""
    society_id = seed_society(db)
    add_show(db, society_id, "One-off", "40th Anniversary (March run)", season="20/21")
    add_show(db, society_id, "Show A", "Popular Theatre", season="24/25")
    add_show(db, society_id, "Show B", "Popular Theatre", season="23/24")

    body = client.get("/venues").get_data(as_text=True)
    assert body.index("Popular Theatre") < body.index("40th Anniversary (March run)")


def test_more_page_links_to_venues(client):
    body = client.get("/more").get_data(as_text=True)
    assert 'href="/venues"' in body


def test_footer_links_to_venues(client):
    body = client.get("/").get_data(as_text=True)
    assert 'href="/venues"' in body
