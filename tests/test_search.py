"""Sitewide search (Round 3 of the 2026-08-17 audit's plan) - one search box
spanning societies (via societies_fts), show titles (current shows + older
awards archive), the full text of ShowTimes reviews, and award nominees by
name, see app/blueprints/public.py's search()."""
from conftest import seed_society


def test_search_page_with_no_query_shows_prompt(client):
    body = client.get("/search").get_data(as_text=True)
    assert "Search across every society, show, ShowTimes review, and award nominee" in body


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


def test_search_finds_a_review_by_a_name_only_its_text_mentions(client, db):
    """The point of indexing review prose: a director/performer/venue named
    only inside a review is findable, when it exists in no column anywhere."""
    seed_society(db, id=1, name="Tullyvin Musical Society")
    db.execute(
        "INSERT INTO shows (id, society_id, season, region, section, show, source, moderation_status) "
        "VALUES (500, 1, '15/16', 'Eastern', 'Sullivan', 'Seussical', 'historical', 'approved')"
    )
    db.execute(
        """
        INSERT INTO historical_reviews
            (season, tier, show_raw, society_raw, review_text, source_issue, show_id, society_id, moderation_status)
        VALUES ('15/16', 'Sullivan', 'Seussical', 'Tullyvin Musical Society',
                'Director Fionnuala Brennan drew a warm performance from the whole company.',
                'Issue 100, December 2014', 500, 1, 'approved')
        """
    )
    db.commit()

    body = client.get("/search?q=Fionnuala+Brennan").get_data(as_text=True)
    assert "Seussical" in body
    assert "Fionnuala Brennan" in body  # the snippet shows why it matched


def test_search_does_not_leak_an_unapproved_or_hidden_review(client, db):
    seed_society(db, id=1, name="Hidden Society")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = 1")
    seed_society(db, id=2, name="Open Society")
    db.execute(
        "INSERT INTO shows (id, society_id, season, region, section, show, source, moderation_status) "
        "VALUES (501, 1, '15/16', 'Eastern', 'Sullivan', 'Chess', 'historical', 'approved')"
    )
    db.execute(
        "INSERT INTO shows (id, society_id, season, region, section, show, source, moderation_status) "
        "VALUES (502, 2, '15/16', 'Eastern', 'Sullivan', 'Carousel', 'historical', 'approved')"
    )
    db.execute(
        """
        INSERT INTO historical_reviews
            (season, tier, show_raw, society_raw, review_text, source_issue, show_id, society_id, moderation_status)
        VALUES ('15/16', 'Sullivan', 'Chess', 'Hidden Society', 'Zebediah Quirke was superb.',
                'Issue 100, December 2014', 501, 1, 'approved')
        """
    )
    db.execute(
        """
        INSERT INTO historical_reviews
            (season, tier, show_raw, society_raw, review_text, source_issue, show_id, society_id, moderation_status)
        VALUES ('15/16', 'Sullivan', 'Carousel', 'Open Society', 'Zebediah Quirke was superb.',
                'Issue 100, December 2014', 502, 2, 'pending')
        """
    )
    db.commit()

    body = client.get("/search?q=Zebediah").get_data(as_text=True)
    assert "Chess" not in body      # hidden society's review stays hidden
    assert "Carousel" not in body   # a pending review isn't public yet


def test_search_finds_an_award_nominee_by_name(client, db):
    seed_society(db, id=1, name="Tullyvin Musical Society")
    db.execute(
        """
        INSERT INTO historical_results
            (society_id, society_name, year, show, tier, category_name, result, nominee_name, role)
        VALUES (1, 'Tullyvin Musical Society', 2015, 'Chess', 'Sullivan',
                'Best Director', 'Winner', 'Aoibheann Nic Cárthaigh', 'Director')
        """
    )
    db.commit()

    body = client.get("/search?q=Aoibheann").get_data(as_text=True)
    assert "Aoibheann Nic Cárthaigh" in body
    assert "Best Director" in body
