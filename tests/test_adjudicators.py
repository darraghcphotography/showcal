"""/admin/adjudicators - defining who adjudicated Gilbert/Sullivan each
season, and matching that back to shows for review-author cross-checking
(see app/blueprints/admin.py's adjudicators()/save_adjudicator_assignments()/
adjudicator_detail())."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_adjudicator(db, name="Jane Smith", notes=None):
    db.execute("INSERT INTO adjudicators (name, notes) VALUES (?, ?)", (name, notes))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def test_adjudicators_page_requires_login(client):
    resp = client.get("/admin/adjudicators")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_add_adjudicator(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)

    resp = client.post("/admin/adjudicators", data={"name": "Jane Smith", "notes": "Eastern region regular"})
    assert resp.status_code == 302

    row = db.execute("SELECT * FROM adjudicators WHERE name = 'Jane Smith'").fetchone()
    assert row is not None
    assert row["notes"] == "Eastern region regular"


def test_add_adjudicator_rejects_duplicate_name(client, db):
    admin_id = seed_user(db)
    seed_adjudicator(db, name="Jane Smith")
    login_as(client, admin_id)

    client.post("/admin/adjudicators", data={"name": "Jane Smith"})

    count = db.execute("SELECT COUNT(*) FROM adjudicators WHERE name = 'Jane Smith'").fetchone()[0]
    assert count == 1


def _anchor_current_season_at_2324(db):
    # season_range() derives "current season" from the most recent real show
    # on record - with no shows seeded at all it falls back to a guess off
    # today's date, which would make "23/24" fall outside the assignable
    # range and silently ignored by save_adjudicator_assignments(). Anchor it
    # with a real show so 23/24 is always in range regardless of when the
    # test suite runs.
    society_id = seed_society(db, id=1, name="Anchor Society", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date) "
        "VALUES (?, '23/24', 'Eastern', 'Anchor Show', '2023-10-01')",
        (society_id,),
    )
    db.commit()


def test_save_assignments_creates_and_updates(client, db):
    admin_id = seed_user(db)
    jane_id = seed_adjudicator(db, name="Jane Smith")
    _anchor_current_season_at_2324(db)
    login_as(client, admin_id)

    resp = client.post("/admin/adjudicators/assign", data={"Gilbert|23/24": str(jane_id)})
    assert resp.status_code == 302

    row = db.execute(
        "SELECT adjudicator_id FROM adjudicator_assignments WHERE season = '23/24' AND section = 'Gilbert'"
    ).fetchone()
    assert row["adjudicator_id"] == jane_id


def test_save_assignments_blank_clears_existing(client, db):
    admin_id = seed_user(db)
    jane_id = seed_adjudicator(db, name="Jane Smith")
    _anchor_current_season_at_2324(db)
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES ('23/24', 'Gilbert', ?)",
        (jane_id,),
    )
    db.commit()
    login_as(client, admin_id)

    client.post("/admin/adjudicators/assign", data={"Gilbert|23/24": ""})

    row = db.execute(
        "SELECT * FROM adjudicator_assignments WHERE season = '23/24' AND section = 'Gilbert'"
    ).fetchone()
    assert row is None


def test_adjudicator_detail_lists_shows_in_their_seasons(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern", section="Gilbert")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES ('23/24', 'Gilbert', ?)",
        (jane_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    # A different tier/season the same society also produced - must not appear.
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show) VALUES (?, '24/25', 'Eastern', 'Sullivan', 'Cabaret')",
        (society_id,),
    )
    db.commit()
    login_as(client, admin_id)

    body = client.get(f"/admin/adjudicators/{jane_id}").get_data(as_text=True)
    assert "Oliver!" in body
    assert "Cabaret" not in body


def test_adjudicator_detail_404_for_unknown_id(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)

    resp = client.get("/admin/adjudicators/999")
    assert resp.status_code == 404


def test_delete_adjudicator_blocked_when_assigned(client, db):
    admin_id = seed_user(db, role="admin")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES ('23/24', 'Gilbert', ?)",
        (jane_id,),
    )
    db.commit()
    login_as(client, admin_id)

    client.post(f"/admin/adjudicators/{jane_id}/delete")

    row = db.execute("SELECT * FROM adjudicators WHERE id = ?", (jane_id,)).fetchone()
    assert row is not None


def test_delete_adjudicator_removes_when_unassigned(client, db):
    admin_id = seed_user(db, role="admin")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    login_as(client, admin_id)

    client.post(f"/admin/adjudicators/{jane_id}/delete")

    row = db.execute("SELECT * FROM adjudicators WHERE id = ?", (jane_id,)).fetchone()
    assert row is None
