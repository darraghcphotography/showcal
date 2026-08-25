"""/admin/data-quality's "Orphaned title data" section can now do what its own
hint text always promised. show_info/show_links are keyed by the title string
itself (`show` is the PRIMARY KEY on both), so a casing/punctuation drift
stranded the row with no way to fix it short of a database shell - "Edit" only
edits contents, "Clear" only deletes.

Also covers the cause: _merge_titles was manufacturing these orphans on every
merge by retitling shows/historical_results and leaving the title-keyed tables
behind."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _seed_show(db, society_id, title, season="24/25"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, ?, 'Eastern', ?, 'approved', 'import')",
        (society_id, season, title),
    )
    db.commit()


# --- the rename action ------------------------------------------------------

def test_rename_repoints_an_orphaned_show_info_row(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    _seed_show(db, society_id, "Fiddler on the Roof")
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('Fiddler On The Roof', 'A synopsis')")
    db.commit()
    login_as(client, admin_id)

    resp = client.post("/admin/data-quality/orphaned/rename", data={
        "table": "show_info", "old": "Fiddler On The Roof", "new": "Fiddler on the Roof",
    }, follow_redirects=False)
    assert resp.status_code == 302

    assert db.execute("SELECT 1 FROM show_info WHERE show = 'Fiddler On The Roof'").fetchone() is None
    row = db.execute("SELECT synopsis FROM show_info WHERE show = 'Fiddler on the Roof'").fetchone()
    assert row["synopsis"] == "A synopsis"


def test_rename_works_for_show_links_too(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    _seed_show(db, society_id, "Oliver!")
    db.execute("INSERT INTO show_links (show, url) VALUES ('Oliver', 'http://example.com')")
    db.commit()
    login_as(client, admin_id)

    client.post("/admin/data-quality/orphaned/rename", data={
        "table": "show_links", "old": "Oliver", "new": "Oliver!",
    })
    row = db.execute("SELECT url FROM show_links WHERE show = 'Oliver!'").fetchone()
    assert row["url"] == "http://example.com"


def test_rename_into_an_existing_row_drops_the_orphan_rather_than_500ing(client, db):
    """`show` is the PRIMARY KEY, so renaming onto a title that already has a
    row is a collision - the orphan is the redundant one."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    _seed_show(db, society_id, "Annie")
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('Annie', 'The real one')")
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('annie', 'The orphan')")
    db.commit()
    login_as(client, admin_id)

    resp = client.post("/admin/data-quality/orphaned/rename", data={
        "table": "show_info", "old": "annie", "new": "Annie",
    }, follow_redirects=False)
    assert resp.status_code == 302

    assert db.execute("SELECT 1 FROM show_info WHERE show = 'annie'").fetchone() is None
    row = db.execute("SELECT synopsis FROM show_info WHERE show = 'Annie'").fetchone()
    assert row["synopsis"] == "The real one"  # the survivor wasn't overwritten


def test_rename_rejects_a_target_that_is_not_a_real_title(client, db):
    admin_id = seed_user(db)
    seed_society(db, name="Test Society")
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('Orphan', 'x')")
    db.commit()
    login_as(client, admin_id)

    client.post("/admin/data-quality/orphaned/rename", data={
        "table": "show_info", "old": "Orphan", "new": "Not A Real Show",
    })
    # Untouched - a free-text rename would just create a second orphan.
    assert db.execute("SELECT 1 FROM show_info WHERE show = 'Orphan'").fetchone() is not None


def test_rename_rejects_an_arbitrary_table_name(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    resp = client.post("/admin/data-quality/orphaned/rename", data={
        "table": "societies", "old": "x", "new": "y",
    })
    assert resp.status_code == 400


def test_rename_requires_login(client, db):
    resp = client.post("/admin/data-quality/orphaned/rename", data={
        "table": "show_info", "old": "x", "new": "y",
    })
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


# --- the cause: merges used to manufacture orphans --------------------------

def test_merging_titles_carries_show_info_across(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    _seed_show(db, society_id, "Fame", season="23/24")
    _seed_show(db, society_id, "Fame: The Musical", season="24/25")
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('Fame', 'Performing arts school')")
    db.commit()
    login_as(client, admin_id)

    client.post("/admin/duplicate-titles/merge",
                data={"canonical": "Fame: The Musical", "other": "Fame"})

    assert db.execute("SELECT 1 FROM show_info WHERE show = 'Fame'").fetchone() is None
    row = db.execute("SELECT synopsis FROM show_info WHERE show = 'Fame: The Musical'").fetchone()
    assert row["synopsis"] == "Performing arts school"


def test_merging_keeps_the_canonical_row_when_both_sides_have_one(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    _seed_show(db, society_id, "Sugar", season="23/24")
    _seed_show(db, society_id, "Sugar The Musical", season="24/25")
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('Sugar', 'Canonical')")
    db.execute("INSERT INTO show_info (show, synopsis) VALUES ('Sugar The Musical', 'Duplicate')")
    db.commit()
    login_as(client, admin_id)

    client.post("/admin/duplicate-titles/merge",
                data={"canonical": "Sugar", "other": "Sugar The Musical"})

    assert db.execute("SELECT 1 FROM show_info WHERE show = 'Sugar The Musical'").fetchone() is None
    row = db.execute("SELECT synopsis FROM show_info WHERE show = 'Sugar'").fetchone()
    assert row["synopsis"] == "Canonical"
