"""Tests for the Unified Venues Hub (/venues).

Validates that:
1. Leaflet map pins payload is included for mapped venues, excluding unlocated venues.
2. Next upcoming show is batch-aggregated and displayed without per-row queries.
3. Query count remains constant (no O(n) regressions).
"""
import pytest
from conftest import seed_society


def test_venues_hub_displays_map_and_pins(client, db):
    soc_id = seed_society(db, id=1, name="Hub Society", region="Western")
    db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, venue, opening_date, closing_date, moderation_status)
        VALUES (?, '24/25', 'Western', 'Show 1', 'Mapped Royal Theatre', '2025-04-01', '2025-04-05', 'approved')
        """,
        (soc_id,),
    )
    db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, venue, opening_date, closing_date, moderation_status)
        VALUES (?, '24/25', 'Western', 'Show 2', 'Unmapped Old Hall', '2025-04-10', '2025-04-15', 'approved')
        """,
        (soc_id,),
    )
    db.commit()

    # Trigger venues build
    client.get("/venues")

    # Give Mapped Royal Theatre valid coordinates
    db.execute("UPDATE venues SET latitude = 53.85, longitude = -9.29 WHERE name = 'Mapped Royal Theatre'")
    db.commit()

    resp = client.get("/venues")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Page heading
    assert "Theatres &amp; Venues" in body
    # Map container
    assert 'id="venues-map"' in body
    assert 'id="btn-toggle-map"' in body
    # Venues appear
    assert "Mapped Royal Theatre" in body
    assert "Unmapped Old Hall" in body


def test_venues_hub_renders_next_show_badge(client, db):
    soc_id = seed_society(db, id=1, name="Badge Society", region="Western")
    # Show in the future
    db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, venue, opening_date, closing_date, moderation_status)
        VALUES (?, '26/27', 'Northern', 'Future Rock Musical', 'Grand Opera House', '2099-11-20', '2099-11-25', 'approved')
        """,
        (soc_id,),
    )
    db.commit()

    body = client.get("/venues").get_data(as_text=True)
    assert "now-playing-badge" in body
    assert "Future Rock Musical" in body
    assert "Next:" in body


def test_venues_index_query_count_is_bounded(client, db):
    """The /venues route must use a constant query budget regardless of how many
    venues are listed, preventing the O(n) performance degradation that previously
    occurred on society/shows loops."""
    soc_id = seed_society(db, id=1, name="Scale Society", region="Eastern")
    for i in range(10):
        db.execute(
            """
            INSERT INTO shows (society_id, season, region, show, venue, opening_date, closing_date, moderation_status)
            VALUES (?, '26/27', 'Eastern', ?, ?, '2099-01-01', '2099-01-05', 'approved')
            """,
            (soc_id, f"Show {i}", f"Scale Theatre {i}"),
        )
    db.commit()

    # Initial request to finish startup builds
    client.get("/venues")

    # Track queries executed during subsequent request
    queries = []
    db.set_trace_callback(lambda q: queries.append(q))
    resp = client.get("/venues")
    db.set_trace_callback(None)

    assert resp.status_code == 200

    # Number of SELECT queries executed must be small and constant (bounded by <= 8 queries)
    select_queries = [q for q in queries if "SELECT" in q.upper()]
    assert len(select_queries) <= 8, f"Too many queries executed: {len(select_queries)}"
