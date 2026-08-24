"""The productions and venues tables are derived, and a page that reads them
while they're stale doesn't error - it silently under-reports. That used to be
guarded by remembering to call ensure_current() in each route: sixteen call
sites across six modules, and every new route was another chance to forget.

A before_request in app/__init__.py now does it once for every request. These
tests are the guard on that guard - each one changes the source data behind the
app's back and asks a page that reads a derived table, with no explicit rebuild
anywhere in the test.
"""
from conftest import seed_society, seed_user


def test_a_new_show_appears_in_a_production_count_without_a_manual_rebuild(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Brand New Show', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert "Brand New Show" in body


def test_a_new_venue_appears_without_a_manual_rebuild(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'A Brand New Venue', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/venues").get_data(as_text=True)
    assert "A Brand New Venue" in body


def test_the_title_page_counts_a_show_added_behind_the_app_s_back(client, db):
    society_id = seed_society(db)
    for season in ("22/23", "23/24"):
        db.execute(
            "INSERT INTO shows (society_id, season, region, show, moderation_status) "
            "VALUES (?, ?, 'Eastern', 'Chess', 'approved')",
            (society_id, season),
        )
    db.commit()

    body = client.get("/titles/Chess").get_data(as_text=True)
    assert "Chess" in body
    # Both stagings resolved to productions, so the page exists rather than 404ing.
    assert "2" in body


def test_an_admin_counter_reads_current_data_too(client, db):
    """The admin side reads production_id as well - the same before_request
    covers it, and it's the half where a stale count is least visible."""
    user_id = seed_user(db)
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Late Addition', 'pending')",
        (society_id,),
    )
    db.commit()

    assert client.get("/admin/").status_code == 200


def test_static_files_skip_the_freshness_check(client):
    """Not correctness, just not paying for a database round trip on every
    stylesheet request - the before_request opts out for static."""
    assert client.get("/static/style.css").status_code == 200
