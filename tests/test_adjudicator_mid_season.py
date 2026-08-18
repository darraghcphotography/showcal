"""A season/tier can now hold a second adjudicator for a real mid-season
change (see ROADMAP) - the admin grid offers two slots each with an
optional note, and the public "reviewed by" credit deliberately declines to
guess which of the two actually wrote a specific show's review."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_adjudicator(db, name="Jane Smith", notes=None):
    db.execute("INSERT INTO adjudicators (name, notes) VALUES (?, ?)", (name, notes))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def test_grid_offers_a_second_slot_with_notes_field(client, db):
    admin_id = seed_user(db)
    seed_adjudicator(db, name="Jane Smith")
    login_as(client, admin_id)

    body = client.get("/admin/adjudicators").get_data(as_text=True)
    assert 'name="Gilbert|09/10|2"' in body
    assert 'name="Gilbert|09/10|2|notes"' in body


def test_grid_covers_09_10_even_with_no_awards_archive_data(client, db):
    # season_range() alone anchors to MIN(year) FROM historical_results, which
    # is empty in a fresh test db - the grid must still offer 09/10, the
    # ShowTimes-archive floor, regardless of what the awards archive has.
    admin_id = seed_user(db)
    seed_adjudicator(db, name="Jane Smith")
    login_as(client, admin_id)

    body = client.get("/admin/adjudicators").get_data(as_text=True)
    assert ">09/10<" in body


def test_save_two_slots_creates_two_rows_with_notes(client, db):
    admin_id = seed_user(db)
    jane_id = seed_adjudicator(db, name="Jane Smith")
    john_id = seed_adjudicator(db, name="John Byrne")
    login_as(client, admin_id)

    resp = client.post("/admin/adjudicators/assign", data={
        "Gilbert|13/14": str(jane_id),
        "Gilbert|13/14|notes": "early season",
        "Gilbert|13/14|2": str(john_id),
        "Gilbert|13/14|2|notes": "took over mid-season",
    })
    assert resp.status_code == 302

    rows = db.execute(
        "SELECT adjudicator_id, notes FROM adjudicator_assignments WHERE season = '13/14' AND section = 'Gilbert' "
        "ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["adjudicator_id"] == jane_id
    assert rows[0]["notes"] == "early season"
    assert rows[1]["adjudicator_id"] == john_id
    assert rows[1]["notes"] == "took over mid-season"


def test_save_blank_second_slot_leaves_only_one_row(client, db):
    admin_id = seed_user(db)
    jane_id = seed_adjudicator(db, name="Jane Smith")
    login_as(client, admin_id)

    client.post("/admin/adjudicators/assign", data={"Gilbert|13/14": str(jane_id)})

    rows = db.execute(
        "SELECT adjudicator_id FROM adjudicator_assignments WHERE season = '13/14' AND section = 'Gilbert'"
    ).fetchall()
    assert len(rows) == 1


def test_resaving_clears_a_previously_set_second_slot(client, db):
    admin_id = seed_user(db)
    jane_id = seed_adjudicator(db, name="Jane Smith")
    john_id = seed_adjudicator(db, name="John Byrne")
    login_as(client, admin_id)

    client.post("/admin/adjudicators/assign", data={
        "Gilbert|13/14": str(jane_id), "Gilbert|13/14|2": str(john_id),
    })
    client.post("/admin/adjudicators/assign", data={"Gilbert|13/14": str(jane_id)})

    rows = db.execute(
        "SELECT adjudicator_id FROM adjudicator_assignments WHERE season = '13/14' AND section = 'Gilbert'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["adjudicator_id"] == jane_id


def test_show_detail_credits_the_only_adjudicator_for_that_season_tier(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
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
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Oliver!'").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by" in body.lower()
    assert "Jane Smith" in body


def test_show_detail_does_not_guess_between_two_adjudicators(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    john_id = seed_adjudicator(db, name="John Byrne")
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id, notes) VALUES ('23/24', 'Gilbert', ?, 'early season')",
        (jane_id,),
    )
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id, notes) VALUES ('23/24', 'Gilbert', ?, 'took over')",
        (john_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Oliver!'").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by" not in body.lower()
