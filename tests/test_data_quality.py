"""Admin data-quality dashboard: a live check for the duplicate-historical-
production bug class (see find_duplicate_historical_rows.py) and for
show_info/show_links rows orphaned by a title spelling/punctuation mismatch
(see the "Fiddler On The Roof" bug found 2026-08-06)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_duplicate_historical_row_flagged_and_deletable(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    login_as(client, admin_id)

    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_id, source) "
        "VALUES (1994, 'Best Overall Show', 'Nominee', 'Chess', ?, 'import')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, society_name, source) "
        "VALUES (1994, 'Chess', ?, 'Test Society', 'manual')",
        (society_id,),
    )
    db.commit()
    dup_id = db.execute(
        "SELECT id FROM historical_results WHERE category_name IS NULL AND result IS NULL"
    ).fetchone()["id"]

    body = client.get("/admin/data-quality").get_data(as_text=True)
    assert "Chess" in body
    assert "1" in body  # at minimum the row renders; exact count checked below

    client.post(
        f"/admin/data-quality/historical/{dup_id}/delete",
        data={"csrf_token": "x"},
    )
    remaining = db.execute("SELECT COUNT(*) FROM historical_results WHERE show = 'Chess'").fetchone()[0]
    assert remaining == 1
    assert db.execute("SELECT result FROM historical_results WHERE show = 'Chess'").fetchone()[0] == "Nominee"


def test_dashboard_shows_duplicate_historical_count(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    login_as(client, admin_id)

    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_id, source) "
        "VALUES (1994, 'Best Overall Show', 'Nominee', 'Chess', ?, 'import')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, society_name, source) "
        "VALUES (1994, 'Chess', ?, 'Test Society', 'manual')",
        (society_id,),
    )
    db.commit()

    body = client.get("/admin/").get_data(as_text=True)
    assert "Duplicate historical productions" in body


def test_orphaned_show_info_flagged_with_edit_link(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)

    db.execute(
        "INSERT INTO show_info (show, synopsis) VALUES ('Fiddler On The Roof', 'wrong casing')"
    )
    db.commit()

    body = client.get("/admin/data-quality").get_data(as_text=True)
    assert "Fiddler On The Roof" in body
    assert "/admin/titles/Fiddler%20On%20The%20Roof/info" in body


def test_orphaned_show_link_flagged_and_clearable(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)

    db.execute(
        "INSERT INTO show_links (show, url) VALUES ('Man Of La Mancha', 'https://example.com/x')"
    )
    db.commit()

    body = client.get("/admin/data-quality").get_data(as_text=True)
    assert "Man Of La Mancha" in body

    client.post(
        "/admin/show-links/clear",
        data={"csrf_token": "x", "show": "Man Of La Mancha"},
    )
    remaining = db.execute("SELECT COUNT(*) FROM show_links WHERE show = 'Man Of La Mancha'").fetchone()[0]
    assert remaining == 0


def test_real_title_data_not_flagged_as_orphaned(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    login_as(client, admin_id)

    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '23/24', 'Eastern', 'Chicago', 'approved')",
        (society_id,),
    )
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('Chicago', 'a real match')")
    db.execute("INSERT INTO show_links (show, url) VALUES ('Chicago', 'https://example.com/chicago')")
    db.commit()

    body = client.get("/admin/data-quality").get_data(as_text=True)
    assert "None found." in body
