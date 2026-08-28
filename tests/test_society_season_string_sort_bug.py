"""Reported 2026-08-28 (Thurles Musical Society's live page): a society with
old dateless skeleton rows from the 1970s/80s - season strings like "79/80" -
had them wrongly listed as "Also announced" future productions, above the
society's real current-season show. Plain string comparison on "yy/yy"
breaks across the 1999/2000 rollover ('79/80' > '26/27' as text, since '7' >
'2'), exactly the bug season_start_year()'s own docstring warns about - it
just hadn't been applied to society_detail()'s future-show split or its
show-history sort yet. Both now decode the real year before comparing."""
from conftest import seed_society


def _add_show(db, society_id, season, show, opening_date=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, opening_date) "
        "VALUES (?, ?, 'Eastern', ?, 'historical', 'approved', ?)",
        (society_id, season, show, opening_date),
    )


def test_an_old_dateless_show_is_not_treated_as_a_future_production(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "79/80", "My Fair Lady")
    _add_show(db, society_id, "26/27", "Come From Away", opening_date="2026-09-10")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Come From Away" in body
    assert "Also announced" not in body
    assert "My Fair Lady" not in body.split("Show history")[0]  # not in the future-shows callout


def test_an_old_dateless_show_appears_in_history_not_the_future_callout(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "79/80", "My Fair Lady")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "My Fair Lady" in body.split("Show history")[1]


def test_show_history_orders_by_real_year_not_season_text(client, db):
    """'79/80' must not outrank '26/27' - text comparison would put it first
    since '7' > '2'."""
    society_id = seed_society(db)
    _add_show(db, society_id, "79/80", "My Fair Lady")
    _add_show(db, society_id, "24/25", "Oliver!")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    history = body.split("Show history")[1]
    assert history.index("Oliver!") < history.index("My Fair Lady")
