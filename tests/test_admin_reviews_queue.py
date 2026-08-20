"""/admin/reviews-queue - one row per show that's already finished, isn't
marked Not adjudicated, and has no review link yet (see admin.py's
reviews_queue()). Paste-and-save per row, same shape as
/admin/society-corrections."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_show(db, society_id, show, review_status="None", review_url=None,
              closing_date="2025-01-10", opening_date="2025-01-05", source="import",
              moderation_status="approved", season="24/25"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, review_status, review_url, "
        "closing_date, opening_date, source, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?, ?, ?, ?, ?, ?)",
        (society_id, season, show, review_status, review_url, closing_date, opening_date, source, moderation_status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]


def test_requires_login(client):
    resp = client.get("/admin/reviews-queue")
    assert resp.status_code in (302, 401, 403)


def test_lists_finished_show_with_no_review_link(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    _add_show(db, society_id, "Needs A Link")

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Needs A Link" in body


def test_excludes_show_already_marked_not_adjudicated(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    _add_show(db, society_id, "Never Reviewed", review_status="Not adjudicated")

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Never Reviewed" not in body


def test_excludes_show_that_already_has_a_review_link(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    _add_show(db, society_id, "Already Linked", review_status="Published", review_url="https://www.aims.ie/x")

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Already Linked" not in body


def test_includes_show_marked_published_but_missing_the_actual_link(client, db):
    """A real gap seen in production - review_status says Published but
    review_url is still blank."""
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    _add_show(db, society_id, "Published But Blank", review_status="Published", review_url=None)

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Published But Blank" in body


def test_excludes_show_that_has_not_closed_yet(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    _add_show(db, society_id, "Not Yet Closed", closing_date="2099-01-01", opening_date="2099-01-01")

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Not Yet Closed" not in body


def test_excludes_skeleton_shows(client, db):
    """A skeleton show's review lives in historical_reviews, not review_url -
    it should never show up here."""
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    _add_show(db, society_id, "Skeleton Show", source="historical")

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Skeleton Show" not in body


def test_excludes_show_with_an_approved_historical_review_already(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    show_id = _add_show(db, society_id, "Has Full Text Review")
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, show_id, moderation_status) "
        "VALUES ('24/25', 'Has Full Text Review', 'Test Society', 'A review.', ?, 'approved')",
        (show_id,),
    )
    db.commit()

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Has Full Text Review" not in body


def test_save_review_link_sets_url_and_published(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    show_id = _add_show(db, society_id, "To Be Linked")

    resp = client.post(
        f"/admin/reviews-queue/{show_id}/save",
        data={"review_url": "https://www.aims.ie/post/review-to-be-linked"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    row = db.execute("SELECT review_url, review_status FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["review_url"] == "https://www.aims.ie/post/review-to-be-linked"
    assert row["review_status"] == "Published"


def test_save_review_link_rejects_non_url(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    show_id = _add_show(db, society_id, "Bad Input")

    client.post(f"/admin/reviews-queue/{show_id}/save", data={"review_url": "not a url"})
    row = db.execute("SELECT review_url, review_status FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["review_url"] is None
    assert row["review_status"] == "None"


def test_mark_not_adjudicated_removes_it_from_the_queue(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)
    show_id = _add_show(db, society_id, "Turns Out Not Adjudicated")

    client.post(f"/admin/reviews-queue/{show_id}/not-adjudicated", follow_redirects=True)
    row = db.execute("SELECT review_status FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["review_status"] == "Not adjudicated"

    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    assert "Turns Out Not Adjudicated" not in body


def test_dashboard_links_to_reviews_queue(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    body = client.get("/admin/").get_data(as_text=True)
    assert 'href="/admin/reviews-queue"' in body
