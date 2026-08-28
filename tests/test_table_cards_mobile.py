"""V1 (small-items queue): table.table-wide is display:none below 600px, on
the assumption a sibling div.table-cards is shown instead (style.css). Five
templates used table-wide with no .table-cards sibling at all, so their
content simply vanished on any phone - two of them public (show_detail's
Awards & nominations, search's Award nominees). pytest can't assert a media
query, but it can assert the .table-cards markup exists at all, which is what
the query needs in order to work."""
from conftest import seed_society


def _add_award(db, year, show, society_id=1, society_name="Test Society",
               category_name="Best Overall Show", result="Nominee", tier="Gilbert",
               nominee_name=None):
    db.execute(
        "INSERT INTO historical_results "
        "(year, tier, category_name, result, show, society_name, society_id, nominee_name, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual')",
        (year, tier, category_name, result, show, society_name, society_id, nominee_name),
    )


def _add_show(db, season, show, society_id=1, moderation_status="approved",
              source="import", region="Eastern"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (society_id, season, region, show, source, moderation_status),
    )


def test_show_detail_awards_table_has_a_card_sibling(client, db):
    seed_society(db)
    _add_show(db, "23/24", "Chicago")
    _add_award(db, 2024, "Chicago", category_name="Best Director", result="Winner")
    db.commit()

    body = client.get("/shows/1").get_data(as_text=True)
    assert "Best Director" in body
    assert '<div class="table-cards">' in body


def test_search_award_nominees_table_has_a_card_sibling(client, db):
    seed_society(db)
    _add_award(db, 2019, "Chess", nominee_name="Jane Doe")
    db.commit()

    body = client.get("/search?q=Jane Doe").get_data(as_text=True)
    assert '<table class="data-table table-wide">' in body
    assert '<div class="table-cards">' in body
    assert "Jane Doe" in body
