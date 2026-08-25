"""/venues/map (public.venues_map, app/blueprints/public.py) - added
2026-08-25, a real Leaflet map of every venue with coordinates on record,
replacing the fabricated-data parked prototype (mockups/ireland_theatre_map.html
used 9 invented venues/shows). Also covers the /venues card grid's mapped-count
line and pin indicator, and the per-route CSP relaxation the map needs to load
Leaflet/CartoDB from a CDN (see app/__init__.py's set_security_headers)."""
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


def set_coords(db, venue_name, lat, lng):
    # A venue row only exists once a request has triggered the shows->venues
    # derive step (ensure_current) - the caller must GET a page first.
    db.execute("UPDATE venues SET latitude = ?, longitude = ? WHERE name = ?", (lat, lng, venue_name))
    db.commit()


def test_venues_page_shows_mapped_count_and_pin_dot(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Pinned Theatre")
    add_show(db, society_id, "Oklahoma!", "Unpinned Hall")
    client.get("/venues")  # trigger the venues-table derive
    set_coords(db, "Pinned Theatre", 53.35, -6.26)

    body = client.get("/venues").get_data(as_text=True)
    assert "<strong>1</strong> of 2 have a map pin" in body
    assert 'class="pin-dot"' in body


def test_mapped_count_reflects_the_full_filtered_set_not_just_the_current_page(client, db):
    """Regression guard: mapped_count used to be computed after the list was
    already sliced to one page, so it silently undercounted whenever there
    were more venues than fit on a page - a bug that existed but was invisible
    before this line was ever actually rendered anywhere."""
    society_id = seed_society(db)
    for i in range(55):  # more than the smallest page size (50)
        add_show(db, society_id, f"Show {i}", f"Venue {i:03d}", season=f"{i % 30:02d}/{(i % 30) + 1:02d}")
    client.get("/venues")
    set_coords(db, "Venue 000", 53.0, -7.0)
    set_coords(db, "Venue 054", 53.1, -7.1)  # sorts onto a later page (n-ordered)

    body = client.get("/venues?per_page=50").get_data(as_text=True)
    assert "<strong>2</strong> of 55 have a map pin" in body


def test_map_page_lists_only_venues_with_coordinates(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Pinned Theatre")
    add_show(db, society_id, "Oklahoma!", "Unpinned Hall")
    client.get("/venues")
    set_coords(db, "Pinned Theatre", 53.35, -6.26)

    body = client.get("/venues/map").get_data(as_text=True)
    assert "Pinned Theatre" in body
    assert "Unpinned Hall" not in body
    assert "53.35" in body


def test_map_page_pin_data_includes_real_counts_and_venue_url(client, db):
    a = seed_society(db, id=1, name="Society A")
    b = seed_society(db, id=2, name="Society B")
    add_show(db, a, "Oliver!", "Shared Theatre", season="24/25")
    add_show(db, b, "Oklahoma!", "Shared Theatre", season="23/24")
    client.get("/venues")
    set_coords(db, "Shared Theatre", 53.35, -6.26)

    body = client.get("/venues/map").get_data(as_text=True)
    assert '"n": 2' in body or '"n":2' in body
    assert '"soc_n": 2' in body or '"soc_n":2' in body
    assert "/venues/shared-theatre" in body


def test_map_route_relaxes_csp_for_the_map_libraries_only(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Pinned Theatre")
    client.get("/venues")
    set_coords(db, "Pinned Theatre", 53.35, -6.26)

    map_csp = client.get("/venues/map").headers["Content-Security-Policy"]
    assert "unpkg.com" in map_csp
    assert "basemaps.cartocdn.com" in map_csp


def test_other_routes_keep_the_strict_csp_with_no_map_hosts(client, db):
    home_csp = client.get("/").headers["Content-Security-Policy"]
    assert "unpkg.com" not in home_csp
    assert "basemaps.cartocdn.com" not in home_csp

    venues_csp = client.get("/venues").headers["Content-Security-Policy"]
    assert "unpkg.com" not in venues_csp
    assert "basemaps.cartocdn.com" not in venues_csp
