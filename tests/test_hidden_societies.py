"""societies.hidden - a society asked not to be publicly associated with
AIMS. 404s the public page and drops them from /societies, but leaves
historical stats/awards/Season Archive untouched (see schema.sql's comment
on the column, and app/blueprints/public.py's society_detail/societies_list)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_hidden_society_404s_for_anonymous_visitor(client, db):
    society_id = seed_society(db, name="Wants To Be Forgotten")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.commit()

    resp = client.get(f"/societies/{society_id}")
    assert resp.status_code == 404


def test_hidden_society_still_visible_to_logged_in_moderator(client, db):
    society_id = seed_society(db, name="Wants To Be Forgotten")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.commit()
    mod_id = seed_user(db, username="mod", role="moderator")
    login_as(client, mod_id)

    resp = client.get(f"/societies/{society_id}")
    assert resp.status_code == 200
    assert "Wants To Be Forgotten" in resp.get_data(as_text=True)


def test_non_hidden_society_unaffected(client, db):
    society_id = seed_society(db, name="Perfectly Visible Society")
    resp = client.get(f"/societies/{society_id}")
    assert resp.status_code == 200


def test_hidden_society_excluded_from_directory_for_anonymous(client, db):
    seed_society(db, id=1, name="Hidden Society")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = 1")
    seed_society(db, id=2, name="Visible Society")
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    assert "Hidden Society" not in body
    assert "Visible Society" in body


def test_hidden_society_visible_to_moderator_via_show_inactive_toggle(client, db):
    seed_society(db, id=1, name="Hidden Society")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = 1")
    db.commit()
    mod_id = seed_user(db, username="mod", role="moderator")
    login_as(client, mod_id)

    body = client.get("/societies?show_inactive=1").get_data(as_text=True)
    assert "Hidden Society" in body


def test_admin_can_toggle_hidden_via_edit_society(client, db):
    admin_id = seed_user(db, username="admin", role="admin")
    society_id = seed_society(db, name="Test Society")
    login_as(client, admin_id)

    resp = client.post(
        f"/admin/societies/{society_id}/edit",
        data={"name": "Test Society", "region": "Eastern", "section": "Gilbert", "hidden": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT hidden FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["hidden"] == 1

    # Unchecking the box (omitted from form data, same as a real unchecked checkbox) un-hides it.
    client.post(
        f"/admin/societies/{society_id}/edit",
        data={"name": "Test Society", "region": "Eastern", "section": "Gilbert"},
        follow_redirects=False,
    )
    row = db.execute("SELECT hidden FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["hidden"] == 0


def test_hidden_society_still_counted_in_stats(client, db):
    """Hiding a society's public page must not rewrite historical stats -
    their past productions still count. Used to be checked by name, via a
    society-name leaderboard that included hidden societies on purpose -
    those leaderboards were cut 20 Aug 2026 (redundant with Award Explorer),
    so this now checks the same invariant the numeric way: the aggregate
    count still includes their production."""
    society_id = seed_society(db, name="Hidden But Historic")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '23/24', 'Eastern', 'Oliver!', '2023-11-01', '2023-11-05', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert '<span class="stat-value">1</span><span class="stat-label">Shows since 23/24</span>' in body
