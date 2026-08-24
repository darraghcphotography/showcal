"""Round 5 of the 2026-08-17 audit's plan: a public /adjudicators directory
and per-adjudicator reviews page, plus a "reviewed by" credit on a published-
review show page - see app/blueprints/public.py's adjudicators_list()/
adjudicator_detail()/show_detail()."""
from conftest import seed_society

from app.season import current_season


def seed_adjudicator(db, name="Jane Smith", notes=None):
    db.execute("INSERT INTO adjudicators (name, notes) VALUES (?, ?)", (name, notes))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def assign(db, season, section, adjudicator_id):
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES (?, ?, ?)",
        (season, section, adjudicator_id),
    )
    db.commit()


def test_adjudicators_list_excludes_unassigned(client, db):
    seed_adjudicator(db, name="Assigned Jane")
    unassigned_id = seed_adjudicator(db, name="Unassigned Jack")
    assigned_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Assigned Jane'").fetchone()["id"]
    assign(db, "23/24", "Gilbert", assigned_id)

    body = client.get("/adjudicators").get_data(as_text=True)
    assert "Assigned Jane" in body
    assert "Unassigned Jack" not in body


def test_current_season_adjudicator_gets_the_hero_card_not_the_roster(client, db):
    this_season = current_season(db)
    current_id = seed_adjudicator(db, name="Current Cara")
    assign(db, this_season, "Gilbert", current_id)
    past_id = seed_adjudicator(db, name="Past Pete")
    assign(db, "12/13", "Sullivan", past_id)

    body = client.get("/adjudicators").get_data(as_text=True)
    hero, _, rest = body.partition("Previous adjudicators")
    assert "Current Cara" in hero
    assert "First season" in hero  # her only assignment, worded for a debut
    assert "Past Pete" not in hero
    assert "Past Pete" in rest
    assert "Current Cara" not in rest


def test_adjudicator_detail_404_for_unknown_id(client):
    assert client.get("/adjudicators/999").status_code == 404


def test_adjudicator_detail_404_for_unassigned_adjudicator(client, db):
    unassigned_id = seed_adjudicator(db, name="Unassigned Jack")
    assert client.get(f"/adjudicators/{unassigned_id}").status_code == 404


def test_adjudicator_detail_shows_only_published_reviews(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "23/24", "Gilbert", jane_id)

    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    # Same season/tier but no review yet - must not appear.
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Scheduled Show', 'Scheduled')",
        (society_id,),
    )
    # Different tier, same season - must not appear.
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Sullivan', 'Cabaret', 'Published', 'https://example.com/other')",
        (society_id,),
    )
    db.commit()
    jane_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Jane Smith'").fetchone()["id"]

    body = client.get(f"/adjudicators/{jane_id}").get_data(as_text=True)
    assert "Oliver!" in body
    assert "Scheduled Show" not in body
    assert "Cabaret" not in body


def test_adjudicator_detail_reviews_render_as_a_card_grid(client, db):
    """Shares the same .review-card/.review-grid classes as /reviews (Second
    Act backlog item 4), so an adjudicator's own review list picked up the
    same card treatment automatically."""
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "23/24", "Gilbert", jane_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()
    jane_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Jane Smith'").fetchone()["id"]

    body = client.get(f"/adjudicators/{jane_id}").get_data(as_text=True)
    assert 'class="queue-item-body review-grid"' in body
    assert '<a class="review-card"' in body
    assert '<div class="review-card-top">' in body


def test_adjudicator_detail_excludes_hidden_society(client, db):
    society_id = seed_society(db, id=1, name="Hidden Society", region="Eastern")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "23/24", "Gilbert", jane_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Secret Show', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()

    body = client.get(f"/adjudicators/{jane_id}").get_data(as_text=True)
    assert "Secret Show" not in body
    assert "No published reviews" in body


def test_show_page_credits_the_assigned_adjudicator(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "23/24", "Gilbert", jane_id)
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


def test_show_page_no_credit_without_assignment(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Oliver!'").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by" not in body.lower()


def seed_showtimes_review(db, adjudicator_id, society_id, show="Annie", season="12/13", tier="Gilbert"):
    """An approved ShowTimes archive review on its skeleton show - the shape
    every pre-23/24 review has (see ROADMAP's Step 4 / Round 24)."""
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, source, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?, 'historical', 'approved')",
        (society_id, season, tier, show),
    )
    show_id = db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]
    db.execute(
        "INSERT INTO historical_reviews "
        "(season, tier, show_raw, society_raw, adjudicator_id, review_text, source_issue, "
        " show_id, society_id, moderation_status) "
        "VALUES (?, ?, ?, 'Test Society', ?, 'A fine production.', 'Issue 82, December 2012', "
        "        ?, ?, 'approved')",
        (season, tier, show, adjudicator_id, show_id, society_id),
    )
    db.commit()
    return show_id


def test_list_counts_showtimes_reviews_not_just_aims_links(client, db):
    """The whole extracted ShowTimes archive used to be uncounted here, so an
    adjudicator with 100+ reviews in it read "0 published reviews". 12/13 is
    not the fixture's current season, so Jane lands in the roster table."""
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "12/13", "Gilbert", jane_id)
    seed_showtimes_review(db, jane_id, society_id)

    body = client.get("/adjudicators").get_data(as_text=True)
    assert "Jane Smith" in body
    assert '<td class="num">1</td>' in body
    assert '<td class="num">0</td>' not in body


def test_list_sums_both_review_sources(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "12/13", "Gilbert", jane_id)
    assign(db, "23/24", "Gilbert", jane_id)
    seed_showtimes_review(db, jane_id, society_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()

    body = client.get("/adjudicators").get_data(as_text=True)
    assert '<td class="num">2</td>' in body
    assert "12/13–23/24" in body  # the coverage-span label, both her seasons


def test_list_excludes_showtimes_review_on_hidden_society(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "12/13", "Gilbert", jane_id)
    seed_showtimes_review(db, jane_id, society_id)

    body = client.get("/adjudicators").get_data(as_text=True)
    assert "Jane Smith" in body
    assert '<td class="num">0</td>' in body


def test_detail_lists_showtimes_reviews_linking_to_the_show_page(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "12/13", "Gilbert", jane_id)
    show_id = seed_showtimes_review(db, jane_id, society_id)

    body = client.get(f"/adjudicators/{jane_id}").get_data(as_text=True)
    assert "Annie" in body
    assert f'href="/shows/{show_id}"' in body
    assert "Full review" in body


def test_detail_credits_reviews_the_assignment_table_does_not_cover(client, db):
    """16/17 in production has reviews signed on a tier nobody is assigned to.
    Grouping on the review's own season/tier keeps those visible."""
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "17/18", "Gilbert", jane_id)
    seed_showtimes_review(db, jane_id, society_id, show="Carousel", season="16/17", tier="Sullivan")

    body = client.get(f"/adjudicators/{jane_id}").get_data(as_text=True)
    assert "Carousel" in body


def test_adjudicators_link_present_in_footer_and_more_page(client):
    footer = client.get("/").get_data(as_text=True)
    assert 'href="/adjudicators"' in footer
    more_page = client.get("/more").get_data(as_text=True)
    assert 'href="/adjudicators"' in more_page


def test_sitemap_includes_adjudicators_page(client):
    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/adjudicators</loc>" in body
