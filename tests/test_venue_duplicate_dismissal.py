"""Dismissing a venue merge suggestion (2026-08-29).

The merge tool itself already existed at /admin/venue-directory. Two things
were missing: it was invisible (linked only from a plain list at the bottom
of the dashboard, with no count), and it had no way to say "no".

The second matters more than it looks. merge_candidates() is deliberately
loose - its own docstring says so - and proposes the Galway, Ballinasloe and
Claremorris Town Hall Theatres as one venue. Without a dismissal those false
positives sit in the queue permanently and its counter can never reach zero,
which is exactly the permanent-vs-fixable trap the dashboard's other counters
are written to avoid (see MISSING_DATES_WHERE, missing_venue_count).
"""
from conftest import seed_user
from app.venues import (
    dismiss_venue_pair,
    dismissed_venue_pairs,
    merge_candidates,
    normalize_venue,
    venue_slug,
)


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_venue(db, venue_id, name):
    # slug and name_key are both NOT NULL, and name_key is the venue's real
    # identity - derived with the app's own normalisers rather than a
    # hand-rolled slug, so these rows match what venues_build would create.
    db.execute(
        "INSERT INTO venues (id, name, slug, name_key) VALUES (?, ?, ?, ?)",
        (venue_id, name, venue_slug(name), normalize_venue(name)),
    )
    return venue_id


def test_merge_candidates_pairs_a_venue_with_its_longer_spelling(db):
    rows = [
        {"id": 1, "name": "Astra Hall"},
        {"id": 2, "name": "UCD Astra Hall"},
        {"id": 3, "name": "Watergate Theatre, Kilkenny"},
    ]
    suggestions = merge_candidates(rows)
    assert suggestions[1] == [2]
    assert suggestions[2] == [1]
    assert 3 not in suggestions


def test_a_dismissed_pair_stops_being_suggested(db):
    rows = [{"id": 1, "name": "Astra Hall"}, {"id": 2, "name": "UCD Astra Hall"}]
    assert merge_candidates(rows)
    # Both directions go, not just the one that was dismissed.
    assert merge_candidates(rows, dismissed={(1, 2)}) == {}


def test_dismissal_is_stored_lowest_id_first(db):
    """So dismissing B/A and A/B is one decision, not two."""
    _add_venue(db, 10, "Town Hall Theatre, Galway")
    _add_venue(db, 20, "Town Hall Theatre, Claremorris")
    db.commit()

    dismiss_venue_pair(db, 20, 10)
    dismiss_venue_pair(db, 10, 20)
    db.commit()

    assert dismissed_venue_pairs(db) == {(10, 20)}


def test_the_dismiss_route_removes_the_pair_from_the_queue(client, db):
    admin_id = seed_user(db)
    _add_venue(db, 10, "Astra Hall")
    _add_venue(db, 20, "UCD Astra Hall")
    db.commit()

    login_as(client, admin_id)
    before = client.get("/admin/venue-directory").get_data(as_text=True)
    assert "Merge into" in before

    resp = client.post(
        "/admin/venue-directory/dismiss",
        data={"venue_a_id": 10, "venue_b_id": 20},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    after = client.get("/admin/venue-directory").get_data(as_text=True)
    assert "Merge into" not in after


def test_dismissing_does_not_touch_the_venues_themselves(client, db):
    """It records an opinion about a pair, not a change to either record."""
    admin_id = seed_user(db)
    _add_venue(db, 10, "Astra Hall")
    _add_venue(db, 20, "UCD Astra Hall")
    db.commit()

    login_as(client, admin_id)
    client.post("/admin/venue-directory/dismiss", data={"venue_a_id": 10, "venue_b_id": 20})

    names = [r["name"] for r in db.execute("SELECT name FROM venues ORDER BY id")]
    assert names == ["Astra Hall", "UCD Astra Hall"]


def test_dismissing_a_venue_that_does_not_exist_is_a_404(client, db):
    admin_id = seed_user(db)
    _add_venue(db, 10, "Astra Hall")
    db.commit()

    login_as(client, admin_id)
    resp = client.post("/admin/venue-directory/dismiss", data={"venue_a_id": 10, "venue_b_id": 999})
    assert resp.status_code == 404


def test_dismissing_a_venue_against_itself_is_a_400(client, db):
    admin_id = seed_user(db)
    _add_venue(db, 10, "Astra Hall")
    db.commit()

    login_as(client, admin_id)
    resp = client.post("/admin/venue-directory/dismiss", data={"venue_a_id": 10, "venue_b_id": 10})
    assert resp.status_code == 400


def test_the_dashboard_counts_venues_awaiting_a_decision(client, db):
    admin_id = seed_user(db)
    _add_venue(db, 10, "Astra Hall")
    _add_venue(db, 20, "UCD Astra Hall")
    db.commit()

    login_as(client, admin_id)
    body = client.get("/admin/").get_data(as_text=True)
    assert "Venues that may be duplicates" in body
    assert "<td>2</td>" in body


def test_the_dashboard_count_reaches_zero_once_dismissed(client, db):
    """The whole point of the dismissal: this counter has to be clearable."""
    admin_id = seed_user(db)
    _add_venue(db, 10, "Astra Hall")
    _add_venue(db, 20, "UCD Astra Hall")
    db.commit()

    login_as(client, admin_id)
    client.post("/admin/venue-directory/dismiss", data={"venue_a_id": 10, "venue_b_id": 20})

    body = client.get("/admin/").get_data(as_text=True)
    # The count cell of this row specifically, not a 0 anywhere on the page.
    row = body.split("Venues that may be duplicates")[1].split("</tr>")[0]
    assert "<td>0</td>" in row
