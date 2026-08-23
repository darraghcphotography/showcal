"""A show's venue is now a link to its own /venues/<slug> page, on both the
show detail page and the homepage's Upcoming shows list - previously plain
text (show page) or a Google Maps link only (homepage), so the venue pages
built earlier were unreachable from anywhere a visitor would actually land.
See public.py's show_detail()/index() and app/venues_build.py.

Both routes now call venues_build.ensure_current(db) themselves, matching
the ensure_current() convention already used elsewhere (see ROADMAP.md) -
without it, shows.venue_id stays stale until something else (a /venues hit)
happens to rebuild it, and the link would silently not appear."""
from conftest import seed_society


def add_show(db, society_id, show, venue, season="24/25", opening_date="2025-01-05",
             closing_date="2025-01-10", moderation_status="approved"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue, opening_date, closing_date, "
        "moderation_status) VALUES (?, ?, 'Eastern', ?, ?, ?, ?, ?)",
        (society_id, season, show, venue, opening_date, closing_date, moderation_status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE show = ? AND season = ?", (show, season)).fetchone()["id"]


def test_show_detail_links_its_venue(client, db):
    society_id = seed_society(db)
    show_id = add_show(db, society_id, "Oliver!", "Gorey Little Theatre")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert 'href="/venues/gorey-little-theatre"' in body
    assert "Gorey Little Theatre" in body


def test_show_detail_shows_plain_dash_with_no_venue(client, db):
    society_id = seed_society(db)
    show_id = add_show(db, society_id, "Oliver!", None)

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "/venues/" not in body


def test_homepage_upcoming_show_links_its_venue_and_keeps_the_map_link(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Gorey Little Theatre", opening_date="2099-01-05", closing_date="2099-01-10")

    body = client.get("/").get_data(as_text=True)
    assert 'href="/venues/gorey-little-theatre"' in body
    # The Maps link answers a different question (where is it) than the
    # on-site link (what's on there) - both stay, not one replacing the other.
    assert "maps" in body.lower()
