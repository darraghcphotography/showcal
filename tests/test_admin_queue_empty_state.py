"""F1 (small-items queue, plan item 5): Darragh followed an email link to
/admin/queue, found "0 submissions pending" and no explanation - not a
broken link, the item had already been actioned. photo_submissions_queue.html
already had a "Recently actioned" section; queue.html had none. Ported it
across, and the empty state now points at the other queues/dashboard
instead of dead-ending."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_show(db, society_id, show, moderation_status="pending", moderated_by=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, moderated_by, moderated_at) "
        "VALUES (?, '26/27', 'Eastern', ?, 'submission', ?, ?, CASE WHEN ? IS NOT NULL THEN datetime('now') END)",
        (society_id, show, moderation_status, moderated_by, moderated_by),
    )


def test_empty_queue_links_elsewhere_instead_of_dead_ending(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)

    body = client.get("/admin/queue").get_data(as_text=True)
    assert "Historical reviews" in body
    assert "Photo submissions" in body
    assert "admin dashboard" in body or "/admin" in body


def test_recently_actioned_section_lists_approved_and_rejected_shows(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db)
    _add_show(db, society_id, "Approved Show", moderation_status="approved", moderated_by="mod")
    _add_show(db, society_id, "Rejected Show", moderation_status="rejected", moderated_by="mod")
    _add_show(db, society_id, "Still Pending Show", moderation_status="pending")
    db.commit()

    login_as(client, admin_id)
    body = client.get("/admin/queue").get_data(as_text=True)

    assert "Recently actioned" in body
    assert "Approved Show" in body
    assert "Rejected Show" in body
    assert "Still Pending Show" in body  # in the pending list above, not excluded entirely
