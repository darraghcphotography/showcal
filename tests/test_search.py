"""Sitewide search (Round 3 of the 2026-08-17 audit's plan) - one search box
spanning societies (via societies_fts) and show titles (current shows +
older awards archive), see app/blueprints/public.py's search()."""
from conftest import seed_society


def test_search_page_with_no_query_shows_prompt(client):
    body = client.get("/search").get_data(as_text=True)
    assert "Search across every society and show" in body


def test_search_finds_society_by_name(client, db):
    seed_society(db, id=1, name="Wexford Light Opera Society", region="South-East")
    seed_society(db, id=2, name="Tullamore Musical Society", region="Midlands")

    body = client.get("/search?q=wexford").get_data(as_text=True)
    assert "Wexford Light Opera Society" in body
    assert "Tullamore Musical Society" not in body


def test_search_excludes_hidden_and_inactive_societies(client, db):
    seed_society(db, id=1, name="Hidden Society", region="Eastern")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = 1")
    seed_society(db, id=2, name="Inactive Society", region="Eastern", section="Inactive")
    db.commit()

    body = client.get("/search?q=society").get_data(as_text=True)
    assert "Hidden Society" not in body
    assert "Inactive Society" not in body


def test_search_finds_show_titles_from_current_and_archive(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '25/26', 'Eastern', 'Oliver!', 'approved')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO historical_results (year, show, society_name) VALUES (2010, 'Oliver Twist', 'Old Society')"
    )
    db.commit()

    body = client.get("/search?q=oliver").get_data(as_text=True)
    assert "Oliver!" in body
    assert "Oliver Twist" in body


def test_search_shows_title_link_to_title_detail(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '25/26', 'Eastern', 'Cabaret', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/search?q=cabaret").get_data(as_text=True)
    assert '/titles/Cabaret' in body


def test_header_search_box_present_on_every_page(client):
    body = client.get("/").get_data(as_text=True)
    assert 'class="site-search"' in body
    assert 'action="/search"' in body
