"""A historical_results row with no category/result attached (a bare "this
production happened" entry, e.g. from admin.bulk_historical_productions)
isn't an award record - it belongs in its own "Earlier show history"
section on a society's page, not padding out "Awards & nominations" with
rows full of "—" placeholders (app/blueprints/public.py:society_detail)."""
from conftest import seed_society


def test_bare_production_row_appears_under_earlier_show_history_not_awards(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (?, ?, ?, 'manual')",
        (1999, "Ham", society_id),
    )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Earlier show history" in body
    assert "Ham" in body
    # No Awards & nominations *heading* - the mention inside the Earlier
    # show history blurb ("see Awards & nominations below") is fine, an h2
    # for that section specifically is not.
    assert "<h2>Awards" not in body


def test_award_row_still_appears_under_awards_not_earlier_show_history(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_id, source) "
        "VALUES (2019, 'Best Director', 'Nominee', 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Awards &amp; nominations" in body
    assert "Earlier show history" not in body


def test_bare_row_and_award_row_together_split_into_both_sections(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (1999, 'Ham', ?, 'manual')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_id, source) "
        "VALUES (2019, 'Best Director', 'Nominee', 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Earlier show history" in body
    assert "Awards &amp; nominations" in body
