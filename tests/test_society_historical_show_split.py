"""A society's pre-23/24 history is one unified per-production timeline
(app/blueprints/public.py:society_detail) - a historical_results row with no
category/result attached (a bare "this production happened" entry, e.g. from
admin.bulk_historical_productions) gets its own timeline row same as an
award-linked one, just with "No award record" instead of a category badge,
rather than living in a separate table (see ROADMAP, 20 Aug 2026 - "integrate
award wins/nominations into the show-history rows instead of a separate
table below")."""
from conftest import seed_society


def test_bare_production_row_appears_with_no_award_record(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, source) VALUES (?, ?, ?, 'manual')",
        (1999, "Ham", society_id),
    )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Ham" in body
    assert "No award record" in body


def test_award_row_shows_category_inline_on_the_same_timeline(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_id, source) "
        "VALUES (2019, 'Best Director', 'Nominee', 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Oliver!" in body
    assert "Best Director" in body
    assert "No award record" not in body


def test_bare_row_and_award_row_for_different_shows_both_appear_on_one_timeline(client, db):
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
    assert "Ham" in body
    assert "Oliver!" in body
    assert "No award record" in body
    assert "Best Director" in body


def test_multiple_award_categories_for_one_show_group_onto_a_single_row(client, db):
    """Two category rows for the same (year, show) must produce one timeline
    row with two badges, not two separate rows - the exact grouping this
    change exists to do."""
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_id, source) "
        "VALUES (2019, 'Best Director', 'Winner', 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_id, source) "
        "VALUES (2019, 'Best Overall Show', 'Nominee', 'Oliver!', ?, 'manual')",
        (society_id,),
    )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    # Renders twice site-wide by design (the desktop table and the mobile
    # table-cards fallback - see test_awards_page.py's equivalent check) -
    # the actual assertion is one row per rendering, not one per category.
    assert body.count(">Oliver!<") == 2
    assert "Best Director" in body
    assert "Best Overall Show" in body


def test_person_award_with_no_show_listed_separately(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, nominee_name, society_id, source) "
        "VALUES (2019, 'Unsung Hero Award', 'Winner', 'Jane Doe', ?, 'manual')",
        (society_id,),
    )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Person &amp; company awards" in body
    assert "Unsung Hero Award" in body
    assert "Jane Doe" in body
