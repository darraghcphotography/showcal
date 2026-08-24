"""A source='historical' skeleton row (show/society/season/tier only) will
never have real dates on record, so it belongs in neither the "Shows missing a
date" dashboard counter nor the "Fix dates" page that counter links to. The two
disagreed on real data (30 vs 812) until they shared one definition."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_show(db, society_id, show, source, season="24/25"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?, 'approved')",
        (society_id, season, show, source),
    )


def test_historical_skeletons_excluded_from_dashboard_count(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    _add_show(db, society_id, "Skeleton Row", "historical")
    _add_show(db, society_id, "Genuinely Undated", "import")
    db.commit()

    body = client.get("/admin/").get_data(as_text=True)
    # The label can also appear in the "quick win" banner above the table
    # (if this happens to be the smallest nonzero count on the page), so
    # scope to the "Missing data" table first. The label itself sits inside
    # an .admin-row-label span (with an on/off urgency dot) rather than
    # directly in the <td> - see dashboard.html, Second Act backlog item 8.
    missing_data_table = body.split("Missing data</h2>")[1]
    row = missing_data_table.split("Shows missing a date")[1].split("</tr>")[0]
    assert "<td>1</td>" in row


def test_historical_skeletons_excluded_from_fix_dates_page(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    _add_show(db, society_id, "Skeleton Row", "historical")
    _add_show(db, society_id, "Genuinely Undated", "import")
    db.commit()

    body = client.get("/admin/shows/dates?missing=1").get_data(as_text=True)
    assert "Genuinely Undated" in body
    assert "Skeleton Row" not in body


def test_dated_shows_not_listed_as_missing(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, "
        "opening_date, closing_date) VALUES (?, '24/25', 'Eastern', 'Fully Dated', 'import', "
        "'approved', '2025-03-01', '2025-03-05')",
        (society_id,),
    )
    db.commit()

    body = client.get("/admin/shows/dates?missing=1").get_data(as_text=True)
    assert "Fully Dated" not in body
