"""The society self-service "add a show" form warns when the show being
added already has an award-archive record for this society and season
(app/similarity.py's find_award_record_match) - the same soft-warn-then-
confirm pattern as the existing near-duplicate-title check, so a real
production can't get silently double-counted between the old awards import
and a fresh self-service submission.

The warning only fires when the award record already has an approved `shows`
row. An award record on its own is a gap the society is entitled to fill -
see test_award_record_without_a_shows_row_does_not_block below."""
from conftest import seed_invite_code, seed_society


def seed_award_and_show(db, society_id, season="24/25", year=2025, show="Oliver!"):
    """An award record that already has its own approved `shows` row - the
    real double-count case. The `productions` rebuild links the two on the
    next request, which is what find_award_record_match tests for."""
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (?, ?, ?, 'manual')",
        (year, show, society_id),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, 'historical', 'approved')",
        (society_id, season, show),
    )


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def test_warns_when_season_already_has_a_matching_award_record(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    # historical_results.year is the season's *second* calendar year (see
    # season.historical_results_year) - season '24/25' -> year 2025.
    seed_award_and_show(db, society_id)
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

    # Nothing new inserted yet - waiting on confirmation. The one row present
    # is the seeded 'historical' skeleton, not the submission.
    rows = db.execute(
        "SELECT * FROM shows WHERE society_id = ? AND source = 'submission'", (society_id,)
    ).fetchall()
    assert len(rows) == 0


def test_confirming_the_checkbox_saves_it_anyway(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC002", society_id=society_id)
    seed_award_and_show(db, society_id)
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={
            # Normalizes the same as the seeded "Oliver!" (so the guard fires)
            # but is a distinct natural key, so confirming can actually insert.
            # That also trips the separate near-duplicate-title check, hence
            # both confirmations.
            "season": "24/25", "show": "Oliver", "opening_date": "", "closing_date": "",
            "confirm_double_count": "1", "confirm_new_title": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute(
        "SELECT show FROM shows WHERE society_id = ? AND source = 'submission'", (society_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["show"] == "Oliver"


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


def test_award_record_without_a_shows_row_does_not_block(client, db):
    """The Maynooth bug. Into the Woods 22/23 existed only as award records,
    never as a `shows` row. The society page's Show history reads `shows`, so
    the production was invisible there - and this guard then told the PRO it
    was "already counted" and refused the submission. A society filling that
    exact gap must go straight through, with no warning and no checkbox."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC006", society_id=society_id)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) "
        "VALUES (2023, 'Into the Woods', ?, 'manual')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={"season": "22/23", "show": "Into the Woods", "opening_date": "", "closing_date": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute("SELECT show FROM shows WHERE society_id = ?", (society_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["show"] == "Into the Woods"


def test_unapproved_shows_row_still_counts_as_a_gap(client, db):
    """A pending/rejected `shows` row doesn't appear in Show history either,
    so it leaves the same gap - the guard must not fire on it."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC007", society_id=society_id)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (2025, 'Chess', ?, 'manual')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Chess!', 'submission', 'rejected')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/new",
        data={
            "season": "24/25", "show": "Chess", "opening_date": "", "closing_date": "",
            "confirm_new_title": "1",  # "Chess!" is on record; that check is separate
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
