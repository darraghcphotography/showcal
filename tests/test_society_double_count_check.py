"""The society self-service "add a show" form warns when the show being
added already has an award-archive record for this society and season
(app/similarity.py's find_award_record_match) - the same soft-warn-then-
confirm pattern as the existing near-duplicate-title check, so a real
production can't get silently double-counted between the old awards import
and a fresh self-service submission."""
from conftest import seed_invite_code, seed_society


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def test_warns_when_season_already_has_a_matching_award_record(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    # historical_results.year is the season's *second* calendar year (see
    # season.historical_results_year) - season '24/25' -> year 2025.
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (2025, 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={"season": "24/25", "show": "Oliver!", "opening_date": "", "closing_date": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "already has an award-archive record" in body
    assert "confirm_double_count" in body

    rows = db.execute("SELECT * FROM shows WHERE society_id = ?", (society_id,)).fetchall()
    assert len(rows) == 0  # nothing inserted yet - waiting on confirmation


def test_confirming_the_checkbox_saves_it_anyway(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC002", society_id=society_id)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (2025, 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={
            "season": "24/25", "show": "Oliver!", "opening_date": "", "closing_date": "",
            "confirm_double_count": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute("SELECT show FROM shows WHERE society_id = ?", (society_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["show"] == "Oliver!"


def test_no_warning_for_a_genuinely_new_show(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC003", society_id=society_id)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (2025, 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={"season": "24/25", "show": "Chess", "opening_date": "", "closing_date": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute("SELECT show FROM shows WHERE society_id = ?", (society_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["show"] == "Chess"


def test_no_warning_when_matching_award_record_is_a_different_season(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC004", society_id=society_id)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (2019, 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={"season": "24/25", "show": "Oliver!", "opening_date": "", "closing_date": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute("SELECT show FROM shows WHERE society_id = ?", (society_id,)).fetchall()
    assert len(rows) == 1


def test_no_warning_when_matching_award_record_belongs_to_another_society(client, db):
    society_id = seed_society(db, id=1, name="Society A")
    other_id = seed_society(db, id=2, name="Society B")
    code_id = seed_invite_code(db, code="AIMS-SOC005", society_id=society_id)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (2025, 'Oliver!', ?, 'manual')",
        (other_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={"season": "24/25", "show": "Oliver!", "opening_date": "", "closing_date": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302
