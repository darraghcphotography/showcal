"""venues.venue_type - the /venues directory's type filter and the badge on a
venue's page. Classified from the venue's own name (classify_venue_types.py),
moderator-correctable, and NULL where nobody has looked yet."""
from classify_venue_types import classify
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _seed_venue(client, db, society_id, venue_name, show="Test Show", season="25/26"):
    """Venues are derived, never hand-inserted (schema.sql) - a show carrying
    the venue text plus a request to trigger the rebuild is how one appears."""
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue, moderation_status, source) "
        "VALUES (?, ?, 'Eastern', ?, ?, 'approved', 'import')",
        (society_id, season, show, venue_name),
    )
    db.commit()
    client.get("/")
    return db.execute("SELECT * FROM venues WHERE name = ?", (venue_name,)).fetchone()


# --- the name-based classifier ---------------------------------------------

def test_classifier_reads_the_obvious_cases():
    assert classify("Town Hall Theatre, Galway") == "Theatre"
    assert classify("Solstice Arts Centre") == "Arts Centre"
    assert classify("St. Jarlath's College, Tuam") == "School or College"
    assert classify("Aghada Community Centre") == "Community or Parish Hall"
    assert classify("Kilcock GAA") == "Other"


def test_theatre_beats_hall_and_arts_centre_beats_theatre():
    # "Town Hall Theatre" is a theatre, not a parish hall.
    assert classify("Town Hall Theatre, Ballinasloe") == "Theatre"
    # A school hall is a school, not a hall.
    assert classify("St. Mary's Secondary School Hall, Baldoyle") == "School or College"


def test_a_church_hall_is_a_parish_hall_not_other():
    assert classify("St. Brigid's Church Hall, Kill, Kildare") == "Community or Parish Hall"


def test_bare_centre_does_not_swallow_arts_venues_or_schools():
    assert classify("The Barbican Centre, Drogheda") == "Arts Centre"
    assert classify("Coláiste Bríde / IFA Centre, Enniscorthy") == "School or College"


def test_place_name_artifacts_are_never_classified():
    # These name no building at all, and venue_type is a CURATED_COLUMN - typing
    # one would make it a permanent survivor of the venues rebuild's stale sweep.
    for name in ("Cork", "Wexford", "Cork run", "40th Anniversary (March run)"):
        assert classify(name) is None


def test_an_unrecognisable_name_is_left_blank():
    assert classify("Somewhere Nobody Named") is None


# --- filter + display -------------------------------------------------------

def test_filter_returns_only_matching_venues(client, db):
    society_id = seed_society(db, name="Test Society")
    _seed_venue(client, db, society_id, "Test Theatre", show="A", season="25/26")
    _seed_venue(client, db, society_id, "Test Community Centre", show="B", season="24/25")
    db.execute("UPDATE venues SET venue_type = 'Theatre' WHERE name = 'Test Theatre'")
    db.execute("UPDATE venues SET venue_type = 'Community or Parish Hall' WHERE name = 'Test Community Centre'")
    db.commit()

    body = client.get("/venues?venue_type=Theatre").get_data(as_text=True)
    assert "Test Theatre" in body
    assert "Test Community Centre" not in body


def test_unclassified_is_a_selectable_filter(client, db):
    society_id = seed_society(db, name="Test Society")
    _seed_venue(client, db, society_id, "Test Theatre", show="A", season="25/26")
    _seed_venue(client, db, society_id, "Mystery Place", show="B", season="24/25")
    db.execute("UPDATE venues SET venue_type = 'Theatre' WHERE name = 'Test Theatre'")
    db.commit()

    body = client.get("/venues?venue_type=unclassified").get_data(as_text=True)
    assert "Mystery Place" in body
    assert "Test Theatre" not in body


def test_a_bogus_venue_type_is_ignored_rather_than_erroring(client, db):
    society_id = seed_society(db, name="Test Society")
    _seed_venue(client, db, society_id, "Test Theatre")

    resp = client.get("/venues?venue_type=Nonsense")
    assert resp.status_code == 200
    assert "Test Theatre" in resp.get_data(as_text=True)


def test_badge_renders_on_the_venue_page(client, db):
    society_id = seed_society(db, name="Test Society")
    venue = _seed_venue(client, db, society_id, "Test Theatre")
    db.execute("UPDATE venues SET venue_type = 'Theatre' WHERE id = ?", (venue["id"],))
    db.commit()

    body = client.get(f"/venues/{venue['slug']}").get_data(as_text=True)
    assert "Theatre" in body


def test_an_unclassified_venue_renders_no_badge_rather_than_unknown(client, db):
    society_id = seed_society(db, name="Test Society")
    venue = _seed_venue(client, db, society_id, "Mystery Place")

    body = client.get(f"/venues/{venue['slug']}").get_data(as_text=True)
    assert "Unknown" not in body
    assert "Unclassified" not in body


# --- admin ------------------------------------------------------------------

def test_admin_can_set_and_correct_a_venue_type(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    venue = _seed_venue(client, db, society_id, "Test Theatre")
    login_as(client, admin_id)

    resp = client.post(
        f"/admin/venue-directory/{venue['id']}/edit",
        data={"name": "Test Theatre", "venue_type": "Arts Centre"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT venue_type FROM venues WHERE id = ?", (venue["id"],)).fetchone()
    assert row["venue_type"] == "Arts Centre"


def test_admin_rejects_a_venue_type_outside_the_list(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    venue = _seed_venue(client, db, society_id, "Test Theatre")
    login_as(client, admin_id)

    resp = client.post(
        f"/admin/venue-directory/{venue['id']}/edit",
        data={"name": "Test Theatre", "venue_type": "Nightclub"},
    )
    assert resp.status_code == 200  # re-renders with an error
    row = db.execute("SELECT venue_type FROM venues WHERE id = ?", (venue["id"],)).fetchone()
    assert row["venue_type"] is None


def test_a_classified_venue_survives_the_rebuild_stale_sweep(client, db):
    """venue_type is a CURATED_COLUMN, so classifying a venue keeps it even once
    no show points at it - the same trade already made for capacity."""
    from app import venues_build
    society_id = seed_society(db, name="Test Society")
    venue = _seed_venue(client, db, society_id, "Test Theatre")
    db.execute("UPDATE venues SET venue_type = 'Theatre' WHERE id = ?", (venue["id"],))
    db.execute("DELETE FROM shows WHERE venue_id = ?", (venue["id"],))
    db.commit()

    venues_build.build(db)
    assert db.execute("SELECT 1 FROM venues WHERE id = ?", (venue["id"],)).fetchone() is not None
