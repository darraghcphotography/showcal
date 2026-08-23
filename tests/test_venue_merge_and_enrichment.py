"""Merging two venue spellings, and the researched detail (capacity, website,
map pin) that enrich_venues.py writes.

The property everything here rests on: venues is a *derived* table rebuilt from
shows.venue on startup and whenever the source moves, but the researched columns
are authored. A rebuild must never overwrite them, and must never delete a venue
that carries them - otherwise a researched capacity would quietly disappear the
first time the last show using that spelling got retitled. See
CURATED_COLUMNS in app/venues_build.py.
"""
from conftest import seed_society
from test_venues import add_show

from app import venues_build
from app.venues import merge_venue_into


def venue_id(db, name):
    return db.execute("SELECT id FROM venues WHERE name = ?", (name,)).fetchone()["id"]


def test_merge_moves_shows_and_aliases_and_drops_the_source(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Town Hall Theare Galway")
    add_show(db, society_id, "Chess", "Town Hall Theatre, Galway", season="23/24")
    venues_build.ensure_current(db)

    source, target = venue_id(db, "Town Hall Theare Galway"), venue_id(db, "Town Hall Theatre, Galway")
    merge_venue_into(db, source, target)
    db.commit()

    assert db.execute("SELECT 1 FROM venues WHERE id = ?", (source,)).fetchone() is None
    assert db.execute("SELECT COUNT(*) FROM shows WHERE venue_id = ?", (target,)).fetchone()[0] == 2
    # The alias survives pointing at the target, which is what makes the merge
    # stick: the rebuild resolves that spelling here rather than re-creating it.
    assert db.execute(
        "SELECT venue_id FROM venue_aliases WHERE name_key = 'town hall theare galway'"
    ).fetchone()["venue_id"] == target


def test_merge_carries_researched_detail_across_but_never_overwrites(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Premier Hall")
    add_show(db, society_id, "Chess", "The Premier Hall", season="23/24")
    venues_build.ensure_current(db)

    source, target = venue_id(db, "Premier Hall"), venue_id(db, "The Premier Hall")
    db.execute("UPDATE venues SET capacity = 400, county = 'Tipperary' WHERE id = ?", (source,))
    db.execute("UPDATE venues SET capacity = 380 WHERE id = ?", (target,))
    merge_venue_into(db, source, target)
    db.commit()

    kept = db.execute("SELECT capacity, county FROM venues WHERE id = ?", (target,)).fetchone()
    assert kept["capacity"] == 380, "the target's own value wins"
    assert kept["county"] == "Tipperary", "a blank on the target is filled from the source"


def test_rebuild_does_not_resurrect_a_merged_away_venue(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Town Hall Theare Galway")
    add_show(db, society_id, "Chess", "Town Hall Theatre, Galway", season="23/24")
    venues_build.ensure_current(db)
    merge_venue_into(db, venue_id(db, "Town Hall Theare Galway"),
                     venue_id(db, "Town Hall Theatre, Galway"))
    db.commit()

    venues_build.mark_stale(db)
    venues_build.ensure_current(db)

    assert db.execute(
        "SELECT 1 FROM venues WHERE name = 'Town Hall Theare Galway'"
    ).fetchone() is None


def test_rebuild_preserves_researched_columns(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Moat Theatre, Naas")
    venues_build.ensure_current(db)

    db.execute(
        "UPDATE venues SET capacity = 200, county = 'Kildare', latitude = 53.218531, "
        "longitude = -6.664107, website_url = 'https://www.moattheatre.com/' WHERE name = ?",
        ("Moat Theatre, Naas",),
    )
    db.commit()

    venues_build.mark_stale(db)
    venues_build.ensure_current(db)

    row = db.execute(
        "SELECT capacity, county, latitude, website_url FROM venues WHERE name = ?",
        ("Moat Theatre, Naas",),
    ).fetchone()
    assert (row["capacity"], row["county"], row["latitude"]) == (200, "Kildare", 53.218531)
    assert row["website_url"] == "https://www.moattheatre.com/"


def test_rebuild_keeps_an_enriched_venue_whose_last_show_is_gone(client, db):
    """The trade CURATED_COLUMNS exists to make: an un-referenced venue is
    normally cleaned up, but not one somebody researched."""
    society_id = seed_society(db)
    show_id = add_show(db, society_id, "Oliver!", "Strand Theatre")
    venues_build.ensure_current(db)
    db.execute("UPDATE venues SET capacity = 360 WHERE name = 'Strand Theatre'")
    db.execute("DELETE FROM shows WHERE id = ?", (show_id,))
    db.commit()

    venues_build.mark_stale(db)
    venues_build.ensure_current(db)

    assert db.execute("SELECT 1 FROM venues WHERE name = 'Strand Theatre'").fetchone() is not None


def test_researched_detail_appears_on_the_public_page(client, db):
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Theatre Royal, Waterford")
    venues_build.ensure_current(db)
    db.execute(
        "UPDATE venues SET capacity = 432, county = 'Waterford', auditorium_type = 'Proscenium', "
        "website_url = 'https://theatreroyal.ie/', latitude = 52.2597854, longitude = -7.1069047 "
        "WHERE name = ?", ("Theatre Royal, Waterford",),
    )
    db.commit()
    slug = db.execute("SELECT slug FROM venues WHERE name = ?", ("Theatre Royal, Waterford",)).fetchone()["slug"]

    body = client.get(f"/venues/{slug}").get_data(as_text=True)
    assert "432" in body
    assert "Proscenium" in body
    assert "https://theatreroyal.ie/" in body
    assert "openstreetmap.org" in body


def test_a_venue_with_no_detail_still_renders_cleanly(client, db):
    """The whole design is drip-feed: an un-researched venue must show no empty
    scaffolding, or 118 of them would look broken."""
    society_id = seed_society(db)
    add_show(db, society_id, "Oliver!", "Some Parish Hall")
    venues_build.ensure_current(db)
    slug = db.execute("SELECT slug FROM venues WHERE name = ?", ("Some Parish Hall",)).fetchone()["slug"]

    body = client.get(f"/venues/{slug}").get_data(as_text=True)
    assert body.count("Seating capacity") == 0
    assert "openstreetmap.org" not in body
    assert "Some Parish Hall" in body
