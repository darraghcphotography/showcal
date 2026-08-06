""""Not adjudicated" is a deliberate, permanent review_status - that show
will never have a review link, so it shouldn't count toward (or appear in)
the "needs a review link" dashboard metric/filter, unlike "None" (genuinely
not filled in yet) or "Scheduled" (expected soon)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_show(db, society_id, show, review_status, season="24/25"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, review_status, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?, 'approved')",
        (society_id, season, show, review_status),
    )


def test_not_adjudicated_shows_excluded_from_dashboard_count(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    _add_show(db, society_id, "Never Reviewed", "Not adjudicated")
    _add_show(db, society_id, "Genuinely Missing", "None")
    db.commit()

    body = client.get("/admin/").get_data(as_text=True)
    # Only "Genuinely Missing" should count - extract the row's count cell.
    assert ">1<" in body.split("Shows missing a review link")[1].split("</tr>")[0]


def test_not_adjudicated_shows_excluded_from_needs_review_filter(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    _add_show(db, society_id, "Never Reviewed", "Not adjudicated")
    _add_show(db, society_id, "Genuinely Missing", "None")
    db.commit()

    body = client.get("/admin/shows?needs_review=1").get_data(as_text=True)
    assert "Genuinely Missing" in body
    assert "Never Reviewed" not in body


def test_scheduled_shows_still_counted(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    _add_show(db, society_id, "Coming Soon", "Scheduled")
    db.commit()

    body = client.get("/admin/shows?needs_review=1").get_data(as_text=True)
    assert "Coming Soon" in body
