"""Stats page: pre-23/24 seasons collapse behind a <details> disclosure
instead of cluttering the main "Shows by season" table (see info.py's
stats() and stats.html). Season Archive page: a "hide cancelled shows"
filter and a soonest/latest sort toggle."""
from conftest import seed_society


def test_stats_splits_seasons_at_coverage_boundary(client, db):
    society_id = seed_society(db)
    # One recent (in-coverage) show, one from well before 23/24.
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Chicago', '2024-11-01', '2024-11-05', 'approved')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '10/11', 'Eastern', 'Oliver!', '2010-11-01', '2010-11-05', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert "Show 1 earlier season" in body

    before_details = body.split("<details>")[0]
    inside_details = body.split("<details>")[1].split("</details>")[0]
    assert "24/25" in before_details
    assert "10/11" not in before_details
    assert "10/11" in inside_details


def test_stats_defines_distinct_titles(client):
    body = client.get("/stats").get_data(as_text=True)
    assert "distinct titles" in body.lower()
    assert "counts once" in body


def test_season_page_hides_cancelled_shows_when_requested(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status, status) "
        "VALUES (?, '26/27', 'Eastern', 'Cancelled Show', '2026-09-01', '2026-09-05', 'approved', 'Cancelled')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', 'Still On', '2026-09-10', '2026-09-14', 'approved')",
        (society_id,),
    )
    db.commit()

    resp = client.get("/season?season=26/27")
    body = resp.get_data(as_text=True)
    assert "Cancelled Show" in body
    assert "Still On" in body

    resp = client.get("/season?season=26/27&hide_cancelled=1")
    body = resp.get_data(as_text=True)
    assert "Cancelled Show" not in body
    assert "Still On" in body


def test_season_page_sort_toggle_reverses_order(client, db):
    society_id = seed_society(db)
    for show, opening in [("Early Bird", "2026-09-01"), ("Late Bloomer", "2026-09-20")]:
        db.execute(
            "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
            "VALUES (?, '26/27', 'Eastern', ?, ?, ?, 'approved')",
            (society_id, show, opening, opening),
        )
    db.commit()

    asc_body = client.get("/season?season=26/27&sort=asc").get_data(as_text=True)
    assert asc_body.index("Early Bird") < asc_body.index("Late Bloomer")

    desc_body = client.get("/season?season=26/27&sort=desc").get_data(as_text=True)
    assert desc_body.index("Late Bloomer") < desc_body.index("Early Bird")
