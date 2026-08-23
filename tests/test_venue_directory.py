"""The venues table, the rebuild that fills it, and the moderator merge tool.

shows.venue records what someone typed and drifts badly - the point of the
table is a stable record a capacity or a map pin can hang off. See
app/venues.py, app/venues_build.py and /admin/venue-directory.
"""
import pytest

from app import venues_build
from app.venues import looks_unresolved, merge_candidates, normalize_venue, town_from_name, venue_slug
from conftest import seed_society, seed_user


def add_show(db, venue, show="Oliver!", season="24/25", society_id=1, region="Eastern"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue, opening_date, closing_date, "
        "moderation_status) VALUES (?, ?, ?, ?, ?, '2025-01-05', '2025-01-10', 'approved')",
        (society_id, season, region, show, venue),
    )
    db.commit()


def build(db):
    db.commit()
    return venues_build.build(db)


def venues(db):
    return db.execute("SELECT * FROM venues ORDER BY name").fetchall()


def login(client, db):
    user_id = seed_user(db)
    with client.session_transaction() as session:
        session["user_id"] = user_id


# ---------------------------------------------------------------- identity

def test_punctuation_and_case_are_the_same_venue(db):
    seed_society(db)
    add_show(db, "Civic Theatre Tallaght", show="A", season="24/25")
    add_show(db, "Civic Theatre, Tallaght", show="B", season="23/24")
    build(db)

    assert len(venues(db)) == 1
    assert db.execute("SELECT COUNT(DISTINCT venue_id) FROM shows").fetchone()[0] == 1


def test_accents_and_ampersands_fold(db):
    assert normalize_venue("Draíocht, Blanchardstown") == normalize_venue("Draiocht Blanchardstown")
    assert normalize_venue("Foo & Bar Hall") == normalize_venue("Foo and Bar Hall")


def test_different_towns_stay_different_venues(db):
    """Three real Town Hall Theatres. Nothing that merges these is safe."""
    seed_society(db)
    add_show(db, "Town Hall Theatre, Galway", show="A", season="24/25")
    add_show(db, "Town Hall Theatre, Claremorris", show="B", season="23/24")
    add_show(db, "Town Hall Theatre, Ballinasloe", show="C", season="22/23")
    build(db)

    assert len(venues(db)) == 3


def test_the_most_used_spelling_becomes_the_name(db):
    seed_society(db)
    for i, season in enumerate(["24/25", "23/24", "22/23"]):
        add_show(db, "Theatre Royal, Waterford", show=f"Show {i}", season=season)
    add_show(db, "theatre royal waterford", show="Odd one out", season="21/22")
    build(db)

    assert [v["name"] for v in venues(db)] == ["Theatre Royal, Waterford"]


def test_slugs_are_unique(db):
    """Two venues can be distinct and still slug the same - normalization
    writes "&" out as "and", the slug just drops it. The slug is a URL, not
    the identity, so the second one gets suffixed."""
    seed_society(db)
    add_show(db, "Foo & Bar Rooms", show="A", season="24/25")
    add_show(db, "Foo Bar Rooms", show="B", season="23/24")
    build(db)

    slugs = [v["slug"] for v in venues(db)]
    assert len(venues(db)) == 2
    assert len(slugs) == len(set(slugs)) == 2


def test_slug_helper_handles_awkward_names():
    assert venue_slug("dlr Mill Theatre, Dundrum") == "dlr-mill-theatre-dundrum"
    assert venue_slug("Draíocht") == "draiocht"
    assert venue_slug("!!!") == "venue"


# ---------------------------------------------------------------- seeding

def test_region_is_seeded_from_the_productions_staged_there(db):
    seed_society(db, id=1, name="A", region="Western")
    add_show(db, "Regional Venue", show="A", season="24/25", region="Western")
    add_show(db, "Regional Venue", show="B", season="23/24", region="Western")
    build(db)

    assert venues(db)[0]["region"] == "Western"


def test_a_majority_region_wins_a_single_stray_show(db):
    """19 venues in the live archive have shows in more than one region,
    nearly always one mis-tagged show against a clear majority."""
    seed_society(db)
    for i, season in enumerate(["24/25", "23/24", "22/23"]):
        add_show(db, "Mostly Eastern", show=f"S{i}", season=season, region="Eastern")
    add_show(db, "Mostly Eastern", show="Stray", season="21/22", region="Western")
    build(db)

    assert venues(db)[0]["region"] == "Eastern"


def test_a_genuine_tie_leaves_the_region_blank(db):
    seed_society(db)
    add_show(db, "Ambiguous Hall", show="A", season="24/25", region="Eastern")
    add_show(db, "Ambiguous Hall", show="B", season="23/24", region="Western")
    build(db)

    assert venues(db)[0]["region"] is None


def test_town_is_parsed_from_a_comma_suffix_only():
    assert town_from_name("Theatre Royal, Waterford") == "Waterford"
    assert town_from_name("An Táin Arts Centre, Dundalk (75th Anniv.)") == "Dundalk"
    assert town_from_name("Millbank Theatre Rush") is None
    assert town_from_name("Somewhere, Unit 4") is None


def test_strings_that_name_no_building_are_flagged_not_dropped():
    """"Cork run" and "40th Anniversary (March run)" are both real entries.
    They stay on record - flagged so the merge queue leads with them."""
    assert looks_unresolved("Cork run")
    assert looks_unresolved("40th Anniversary (March run)")
    assert looks_unresolved("Dublin")
    assert not looks_unresolved("Gorey Little Theatre")
    assert not looks_unresolved("Theatre Royal, Waterford")


# ---------------------------------------------------------------- rebuilds

def test_rebuilding_is_idempotent(db):
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    build(db)
    before = [(v["id"], v["name"], v["slug"]) for v in venues(db)]

    build(db)
    build(db)

    assert [(v["id"], v["name"], v["slug"]) for v in venues(db)] == before


def test_a_rebuild_never_overwrites_what_a_moderator_set(db):
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    build(db)
    db.execute("UPDATE venues SET capacity = 220, region = 'South-East', town = 'Gorey'")
    db.commit()

    build(db)

    venue = venues(db)[0]
    assert (venue["capacity"], venue["region"], venue["town"]) == (220, "South-East", "Gorey")


def test_an_unused_venue_is_dropped_unless_it_has_been_edited(db):
    seed_society(db)
    add_show(db, "Forgettable Hall", show="A", season="24/25")
    add_show(db, "Researched Hall", show="B", season="23/24")
    build(db)
    db.execute("UPDATE venues SET capacity = 400 WHERE name = 'Researched Hall'")
    db.execute("UPDATE shows SET venue = NULL")
    db.commit()

    build(db)

    assert [v["name"] for v in venues(db)] == ["Researched Hall"]


def test_ensure_current_only_rebuilds_when_the_venue_strings_moved(db):
    seed_society(db)
    add_show(db, "Gorey Little Theatre")

    assert venues_build.ensure_current(db) is True
    assert venues_build.ensure_current(db) is False

    add_show(db, "dlr Mill Theatre", show="Another", season="23/24")
    assert venues_build.ensure_current(db) is True
    assert len(venues(db)) == 2


def test_verification_catches_an_unlinked_show(db, monkeypatch):
    seed_society(db)
    add_show(db, "Gorey Little Theatre")

    real_collect = venues_build.collect
    monkeypatch.setattr(venues_build, "collect", lambda conn: {})
    with pytest.raises(venues_build.VenueBuildError) as excinfo:
        venues_build.build(db)
    assert "no venue_id" in str(excinfo.value)
    monkeypatch.setattr(venues_build, "collect", real_collect)


# ---------------------------------------------------------------- merge suggestions

def test_merge_candidates_suggests_a_containment_pair():
    rows = [
        {"id": 1, "name": "Astra Hall"},
        {"id": 2, "name": "Astra Hall UCD"},
        {"id": 3, "name": "Gorey Little Theatre"},
    ]
    suggestions = merge_candidates(rows)
    assert suggestions[1] == [2]
    assert suggestions[2] == [1]
    assert 3 not in suggestions


def test_merge_candidates_ignores_the_generic_words():
    """Sharing "Theatre" is not evidence - 60 venues do."""
    rows = [{"id": 1, "name": "Gorey Little Theatre"}, {"id": 2, "name": "Watergate Theatre"}]
    assert merge_candidates(rows) == {}


# ---------------------------------------------------------------- the admin tool

def test_the_directory_lists_venues_and_flags_the_ones_needing_a_look(client, db):
    login(client, db)
    seed_society(db)
    add_show(db, "Gorey Little Theatre", show="A", season="24/25")
    add_show(db, "Cork run", show="B", season="23/24")
    db.commit()

    body = client.get("/admin/venue-directory").get_data(as_text=True)
    assert "Gorey Little Theatre" in body
    assert "Cork run" in body
    assert "Not a building?" in body


def test_place_name_entries_are_kept_out_of_the_clearable_queue(client, db):
    """"Cork" can't be traced to a building - it belongs in its own section,
    not at the top of the job list where it can never be cleared."""
    login(client, db)
    seed_society(db)
    add_show(db, "Astra Hall", show="A", season="24/25")
    add_show(db, "Astra Hall UCD", show="B", season="23/24")
    add_show(db, "Cork", show="C", season="22/23")
    db.commit()

    body = client.get("/admin/venue-directory").get_data(as_text=True)
    assert "Possible duplicates (2)" in body
    assert "Recorded as a place, not a venue (1)" in body


def test_a_bare_place_name_never_suggests_a_merge(client, db):
    """"Dublin" is a subset of every Dublin venue's words. Left in, it alone
    proposed dozens of merges and pushed the real ones off the page."""
    rows = [
        {"id": 1, "name": "Dublin"},
        {"id": 2, "name": "The Helix, Dublin"},
        {"id": 3, "name": "O'Reilly Theatre, Belvedere, Dublin"},
    ]
    assert merge_candidates(rows) == {}


def test_merging_moves_every_show_and_removes_the_source(client, db):
    login(client, db)
    seed_society(db)
    add_show(db, "Astra Hall", show="A", season="24/25")
    add_show(db, "Astra Hall UCD", show="B", season="23/24")
    db.commit()
    client.get("/admin/venue-directory")

    source, target = db.execute("SELECT id FROM venues ORDER BY name").fetchall()
    client.post("/admin/venue-directory/merge",
                data={"source_id": source["id"], "target_id": target["id"]})

    remaining = venues(db)
    assert len(remaining) == 1
    assert remaining[0]["id"] == target["id"]
    assert db.execute("SELECT COUNT(*) FROM shows WHERE venue_id = ?", (target["id"],)).fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM venue_aliases WHERE venue_id = ?",
                      (target["id"],)).fetchone()[0] == 2


def test_a_merge_survives_the_next_rebuild(client, db):
    """The alias is what makes this safe - without it the next rebuild would
    see the other spelling and recreate the venue that was just merged away."""
    login(client, db)
    seed_society(db)
    add_show(db, "Astra Hall", show="A", season="24/25")
    add_show(db, "Astra Hall UCD", show="B", season="23/24")
    db.commit()
    client.get("/admin/venue-directory")
    source, target = db.execute("SELECT id FROM venues ORDER BY name").fetchall()
    client.post("/admin/venue-directory/merge",
                data={"source_id": source["id"], "target_id": target["id"]})

    build(db)

    assert len(venues(db)) == 1


def test_a_merge_carries_across_detail_the_target_is_missing(client, db):
    login(client, db)
    seed_society(db)
    add_show(db, "Astra Hall", show="A", season="24/25")
    add_show(db, "Astra Hall UCD", show="B", season="23/24")
    db.commit()
    client.get("/admin/venue-directory")
    source, target = db.execute("SELECT id FROM venues ORDER BY name").fetchall()
    db.execute("UPDATE venues SET capacity = 500, county = 'Dublin' WHERE id = ?", (source["id"],))
    db.execute("UPDATE venues SET county = 'Co. Dublin' WHERE id = ?", (target["id"],))
    db.commit()

    client.post("/admin/venue-directory/merge",
                data={"source_id": source["id"], "target_id": target["id"]})

    merged = venues(db)[0]
    assert merged["capacity"] == 500          # target had none, so the source's is kept
    assert merged["county"] == "Co. Dublin"   # target had its own, so it wins


def test_merging_a_venue_into_itself_is_rejected(client, db):
    login(client, db)
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    db.commit()
    client.get("/admin/venue-directory")
    venue_id = venues(db)[0]["id"]

    resp = client.post("/admin/venue-directory/merge",
                       data={"source_id": venue_id, "target_id": venue_id})
    assert resp.status_code == 400


def test_editing_a_venue_saves_every_detail_field(client, db):
    login(client, db)
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    db.commit()
    client.get("/admin/venue-directory")
    venue_id = venues(db)[0]["id"]

    client.post(f"/admin/venue-directory/{venue_id}/edit", data={
        "name": "Gorey Little Theatre", "town": "Gorey", "county": "Co. Wexford",
        "region": "South-East", "capacity": "220", "auditorium_type": "Proscenium",
        "latitude": "52.6759", "longitude": "-6.2937",
        "website_url": "https://example.com", "tech_spec_url": "https://example.com/spec.pdf",
        "notes": "Checked against the venue's own site.",
    })

    venue = venues(db)[0]
    assert venue["capacity"] == 220
    assert venue["auditorium_type"] == "Proscenium"
    assert venue["latitude"] == pytest.approx(52.6759)
    assert venue["county"] == "Co. Wexford"


def test_a_bad_capacity_is_rejected_rather_than_saved_as_junk(client, db):
    login(client, db)
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    db.commit()
    client.get("/admin/venue-directory")
    venue_id = venues(db)[0]["id"]

    body = client.post(f"/admin/venue-directory/{venue_id}/edit",
                       data={"name": "Gorey Little Theatre", "capacity": "big"}).get_data(as_text=True)
    assert "must be a number" in body
    assert venues(db)[0]["capacity"] is None


def test_a_website_must_be_a_real_link(client, db):
    login(client, db)
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    db.commit()
    client.get("/admin/venue-directory")
    venue_id = venues(db)[0]["id"]

    body = client.post(f"/admin/venue-directory/{venue_id}/edit",
                       data={"name": "Gorey Little Theatre", "website_url": "not a url"}).get_data(as_text=True)
    assert "full http(s) link" in body


# ---------------------------------------------------------------- the public page

def test_detail_shows_only_the_fields_that_are_filled_in(client, db):
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    venues_build.ensure_current(db)

    body = client.get("/venues/gorey-little-theatre").get_data(as_text=True)
    assert "Seating capacity" not in body
    assert "Auditorium type" not in body
    assert "not collected" not in body.lower()

    db.execute("UPDATE venues SET capacity = 220, auditorium_type = 'Proscenium'")
    db.commit()
    body = client.get("/venues/gorey-little-theatre").get_data(as_text=True)
    assert "Seating capacity" in body
    assert "220" in body
    assert "Proscenium" in body


def test_the_exact_pin_needs_both_coordinates(client, db):
    """Directions work for any venue by name, so they're always offered. The
    exact-spot link is what coordinates buy, and half a coordinate pair is no
    use - it would drop a pin somewhere in the Atlantic."""
    seed_society(db)
    add_show(db, "Gorey Little Theatre")
    venues_build.ensure_current(db)
    db.execute("UPDATE venues SET latitude = 52.6759")
    db.commit()

    body = client.get("/venues/gorey-little-theatre").get_data(as_text=True)
    assert "Get directions" in body
    assert "See the exact spot" not in body

    db.execute("UPDATE venues SET longitude = -6.2937")
    db.commit()
    assert "See the exact spot" in client.get("/venues/gorey-little-theatre").get_data(as_text=True)


def test_directions_are_offered_even_without_coordinates(client, db):
    """Most venues still have no pin - they should not be the ones you can't
    get directions to."""
    seed_society(db)
    add_show(db, "Some Parish Hall")
    venues_build.ensure_current(db)

    body = client.get("/venues/some-parish-hall").get_data(as_text=True)
    assert "google.com/maps/dir" in body


def test_the_index_can_be_filtered_by_region(client, db):
    seed_society(db)
    add_show(db, "Eastern Venue", show="A", season="24/25", region="Eastern")
    add_show(db, "Western Venue", show="B", season="23/24", region="Western")

    body = client.get("/venues?region=Eastern").get_data(as_text=True)
    assert "Eastern Venue" in body
    assert "Western Venue" not in body


def test_the_detail_page_names_the_other_spellings_on_record(client, db):
    seed_society(db)
    add_show(db, "Civic Theatre Tallaght", show="A", season="24/25")
    add_show(db, "Civic Theatre, Tallaght", show="B", season="23/24")
    venues_build.ensure_current(db)

    slug = venues(db)[0]["slug"]
    body = client.get(f"/venues/{slug}").get_data(as_text=True)
    assert "Also recorded as" in body
