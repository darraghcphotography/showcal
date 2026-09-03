"""/venues/map (public.venues_map, app/blueprints/public.py) - added
2026-08-25, a real Leaflet map of every venue with coordinates on record,
replacing the fabricated-data parked prototype (mockups/ireland_theatre_map.html
used 9 invented venues/shows). Also covers the /venues card grid's mapped-count
line and pin indicator, and the per-route CSP relaxation the map needs to load
Leaflet and the Esri basemap from a CDN (see app/__init__.py's set_security_headers)."""
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
    assert "server.arcgisonline.com" in map_csp


def test_other_routes_keep_the_strict_csp_with_no_map_hosts(client, db):
    """Routes that don't render a map (/ and /societies) must keep the strict CSP
    without unpkg.com or server.arcgisonline.com, while /venues and /venues/map have it."""
    for path in ("/", "/societies", "/stats"):
        csp = client.get(path).headers["Content-Security-Policy"]
        assert "unpkg.com" not in csp
        assert "server.arcgisonline.com" not in csp

    for map_path in ("/venues", "/venues/map"):
        csp = client.get(map_path).headers["Content-Security-Policy"]
        assert "unpkg.com" in csp
        assert "server.arcgisonline.com" in csp


def test_map_page_has_region_county_and_society_quick_filters(client, db):
    a = seed_society(db, id=1, name="Alpha Musical Society")
    b = seed_society(db, id=2, name="Beta Musical Society")
    add_show(db, a, "Oliver!", "Alpha Theatre", season="24/25")
    add_show(db, b, "Oklahoma!", "Beta Hall", season="24/25")
    client.get("/venues")
    db.execute("UPDATE venues SET latitude = 53.35, longitude = -6.26, county = 'Wicklow' WHERE name = 'Alpha Theatre'")
    db.execute("UPDATE venues SET latitude = 53.40, longitude = -6.30, county = 'Wexford' WHERE name = 'Beta Hall'")
    db.commit()

    body = client.get("/venues/map").get_data(as_text=True)
    # Region/county dropdowns, populated from the real mapped set.
    assert 'id="map-filter-region"' in body
    assert 'id="map-filter-county"' in body
    assert '<option value="Wicklow">Wicklow</option>' in body
    assert '<option value="Wexford">Wexford</option>' in body
    # Society is a free-text search, not a dropdown - real per-venue resident
    # society names are baked into the pin data for the JS filter to search.
    assert 'id="map-filter-society"' in body
    assert "Alpha Musical Society" in body
    assert "Beta Musical Society" in body
    assert '"county": "Wicklow"' in body or '"county":"Wicklow"' in body


def test_map_page_picks_theme_at_load_and_reacts_to_a_live_toggle(client, db):
    """Added after real feedback: the map tiles were hardcoded to light-only,
    so unlike the rest of the page (which follows CSS custom properties and
    repaints for free) the actual map background stayed light in dark mode.
    Esri ships separate World_Light_Gray_Base/World_Dark_Gray_Base tile sets, so this has to be
    picked in JS - both at initial load and live if the toggle is used while
    the page is already open."""
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Pinned Theatre")
    client.get("/venues")
    set_coords(db, "Pinned Theatre", 53.35, -6.26)

    body = client.get("/venues/map").get_data(as_text=True)
    assert "World_Dark_Gray_Base" in body and "World_Light_Gray_Base" in body
    assert "currentTheme" in body
    # The toggle listener must be attached, or a live theme switch while
    # already on the map page would leave the tiles stuck on whichever
    # theme was active at load.
    assert "theme-toggle" in body
    assert "tiles.setUrl" in body
    # Marker colour uses a live var() reference, not a JS-computed value
    # baked in once - the opposite bug (going stale on live toggle) for the
    # pin colour specifically.
    assert "var(--accent)" in body
    assert "getComputedStyle" not in body
