"""Admin bulk-add for historical productions with no award data attached -
paste a society's own "previous productions" list and get bare
historical_results rows, deduped against what's already on record. See
admin.bulk_historical_productions for the year-convention rationale (the
recorded year is the season's *ending* calendar year - +1 from the
production year for an autumn/winter show, unchanged for a spring one)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_bulk_add_autumn_convention_adds_one_year(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Marian Choral Society, Tuam")
    login_as(client, admin_id)

    resp = client.post(
        "/admin/historical-productions/bulk",
        data={
            "society_id": society_id,
            "year_convention": "autumn",
            "lines": "1998 Ham\n2017 Crazy For You",
        },
    )
    assert resp.status_code == 302

    rows = db.execute(
        "SELECT year, show, category_name, result, source FROM historical_results ORDER BY year"
    ).fetchall()
    assert [(r["year"], r["show"]) for r in rows] == [(1999, "Ham"), (2018, "Crazy For You")]
    assert rows[0]["category_name"] is None
    assert rows[0]["result"] is None
    assert rows[0]["source"] == "manual"


def test_bulk_add_spring_convention_keeps_year_as_typed(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Spring Show Society")
    login_as(client, admin_id)

    client.post(
        "/admin/historical-productions/bulk",
        data={"society_id": society_id, "year_convention": "spring", "lines": "2017 Crazy For You"},
    )

    row = db.execute("SELECT year FROM historical_results WHERE show = 'Crazy For You'").fetchone()
    assert row["year"] == 2017


def test_bulk_add_exact_convention_also_keeps_year_as_typed(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    client.post(
        "/admin/historical-productions/bulk",
        data={"society_id": society_id, "year_convention": "exact", "lines": "2017 Crazy For You"},
    )

    row = db.execute("SELECT year FROM historical_results WHERE show = 'Crazy For You'").fetchone()
    assert row["year"] == 2017


def test_bulk_add_extracts_trailing_parenthetical_as_a_note(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Marian Choral Society, Tuam")
    login_as(client, admin_id)

    client.post(
        "/admin/historical-productions/bulk",
        data={"society_id": society_id, "year_convention": "autumn", "lines": "2005 Jekyll & Hyde (Irish Premiere)"},
    )

    row = db.execute("SELECT show, reason FROM historical_results").fetchone()
    assert row["show"] == "Jekyll & Hyde"
    assert row["reason"] == "Irish Premiere"


def test_bulk_add_skips_already_present_rows(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Marian Choral Society, Tuam")
    login_as(client, admin_id)

    lines = "1998 Ham"
    client.post("/admin/historical-productions/bulk", data={"society_id": society_id, "year_convention": "autumn", "lines": lines})
    client.post("/admin/historical-productions/bulk", data={"society_id": society_id, "year_convention": "autumn", "lines": lines})

    count = db.execute("SELECT COUNT(*) FROM historical_results WHERE show = 'Ham'").fetchone()[0]
    assert count == 1


def test_bulk_add_skips_a_production_already_on_record_as_an_award_row(client, db):
    """A society with award-archive coverage for a year (e.g. a Best Overall
    Show nomination) already has that production on record - pasting the
    same show/year shouldn't add a second, bare duplicate row that would
    double-count it in production-count stats."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Carrick-on-Suir Musical Society")
    login_as(client, admin_id)

    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_id, source) "
        "VALUES (1994, 'Gilbert', 'Best Overall Show', 'Nominee', 'Chess', ?, 'manual')",
        (society_id,),
    )
    db.commit()

    client.post(
        "/admin/historical-productions/bulk",
        data={"society_id": society_id, "year_convention": "exact", "lines": "1994 Chess"},
    )

    count = db.execute("SELECT COUNT(*) FROM historical_results WHERE show = 'Chess'").fetchone()[0]
    assert count == 1


def test_bulk_add_requires_login(client, db):
    society_id = seed_society(db)
    resp = client.get("/admin/historical-productions/bulk")
    assert resp.status_code in (302, 401, 403)
    resp = client.post(
        "/admin/historical-productions/bulk",
        data={"society_id": society_id, "year_convention": "autumn", "lines": "1998 Ham"},
    )
    assert resp.status_code in (302, 401, 403)
    assert db.execute("SELECT COUNT(*) FROM historical_results").fetchone()[0] == 0


def test_bulk_add_unparsed_line_does_not_block_the_rest(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Marian Choral Society, Tuam")
    login_as(client, admin_id)

    resp = client.post(
        "/admin/historical-productions/bulk",
        data={
            "society_id": society_id,
            "year_convention": "autumn",
            "lines": "not a valid line\n1998 Ham",
        },
        follow_redirects=True,
    )
    # Apostrophe renders HTML-escaped ("Couldn&#x27;t"), so match around it.
    assert "parse 1 line" in resp.get_data(as_text=True)
    row = db.execute("SELECT year FROM historical_results WHERE show = 'Ham'").fetchone()
    assert row["year"] == 1999
