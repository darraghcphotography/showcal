"""/reviews - a browsable index of every adjudicator review on the site,
combining AIMS's own link-out reviews (shows.review_url) and the extracted
ShowTimes archive (historical_reviews). See public.py's reviews_index().

Key behaviour: a show/society text search matches across every season and
tier by default - the season/tier dropdowns only narrow a search, they never
implicitly scope one (this was the specific fix requested after the first
mockup draft, which had a season pre-selected)."""
from conftest import seed_society

from app.season import current_season


def seed_adjudicator(db, name="Jane Smith"):
    db.execute("INSERT INTO adjudicators (name) VALUES (?)", (name,))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def assign(db, season, section, adjudicator_id):
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES (?, ?, ?)",
        (season, section, adjudicator_id),
    )
    db.commit()


def add_linked_show(db, society_id, show, season, section="Gilbert", review_status="Published",
                     review_url="https://www.aims.ie/post/x", moderation_status="approved"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, section, review_status, review_url, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?, ?, ?, ?)",
        (society_id, season, show, section, review_status, review_url, moderation_status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE show = ? AND season = ?", (show, season)).fetchone()["id"]


def add_full_text_review(db, society_id, show, season, tier="Gilbert", adjudicator_id=None,
                          moderation_status="approved", review_text="A fine production."):
    show_id = db.execute(
        "INSERT INTO shows (society_id, season, region, show, section, moderation_status, source) "
        "VALUES (?, ?, 'Eastern', ?, ?, 'approved', 'historical')",
        (society_id, season, show, tier),
    ).lastrowid
    db.execute(
        "INSERT INTO historical_reviews (season, tier, show_raw, society_raw, review_text, show_id, "
        "adjudicator_id, moderation_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (season, tier, show, "Test Society", review_text, show_id, adjudicator_id, moderation_status),
    )
    db.commit()
    return show_id


def test_search_matches_across_every_season_and_tier_by_default(client, db):
    """The exact fix requested after the first mockup draft - a show/society
    search must not be implicitly scoped to whatever season happens to be
    selected (or the default)."""
    society_id = seed_society(db)
    add_linked_show(db, society_id, "Calamity Jane", season="25/26", section="Sullivan")
    add_full_text_review(db, society_id, "Calamity Jane", season="16/17", tier="Sullivan")
    add_full_text_review(db, society_id, "Calamity Jane", season="10/11", tier="Gilbert")

    body = client.get("/reviews?q=calamity").get_data(as_text=True)
    assert "3 results" in body
    assert "25/26" in body or "16/17" in body  # sanity - real season text present somewhere
    for season in ("25/26", "16/17", "10/11"):
        assert season in body


def test_default_browse_groups_by_season(client, db):
    society_id = seed_society(db)
    add_linked_show(db, society_id, "Show One", season="25/26")
    add_full_text_review(db, society_id, "Show Two", season="16/17")

    body = client.get("/reviews").get_data(as_text=True)
    assert '<details class="queue-item" open>' in body
    assert "25/26" in body
    assert "16/17" in body


def test_reviews_render_as_a_card_grid(client, db):
    """Second Act backlog item 4 - /reviews used to be a bare flex-row list
    (almost no visual weight difference row to row); it's a card grid now,
    same treatment /societies already got."""
    society_id = seed_society(db)
    add_full_text_review(db, society_id, "The Addams Family", season="22/23")

    body = client.get("/reviews").get_data(as_text=True)
    assert 'class="queue-item-body review-grid"' in body
    assert '<div class="review-card">' in body
    assert '<div class="review-card-top">' in body


def test_search_result_card_shows_season_in_the_meta_line(client, db):
    """Search-result mode has no season <details> grouping to carry the
    season/tier, so it's folded into the card's own society/meta line
    instead of a separate badge."""
    society_id = seed_society(db)
    add_full_text_review(db, society_id, "The Addams Family", season="22/23", tier="Sullivan")

    body = client.get("/reviews?q=addams").get_data(as_text=True)
    assert "22/23" in body
    assert "Sullivan" in body


def test_full_text_review_shown_with_full_review_tag_and_show_page_link(client, db):
    society_id = seed_society(db)
    show_id = add_full_text_review(db, society_id, "The Addams Family", season="22/23")

    body = client.get("/reviews?q=addams").get_data(as_text=True)
    assert "Full review" in body
    assert f'href="/shows/{show_id}#showtimes-review"' in body


def test_linked_review_shown_with_aims_ie_tag_and_external_link(client, db):
    society_id = seed_society(db)
    add_linked_show(db, society_id, "Oklahoma!", season="25/26", review_url="https://www.aims.ie/post/oklahoma")

    body = client.get("/reviews?q=oklahoma").get_data(as_text=True)
    assert "aims.ie" in body
    assert 'href="https://www.aims.ie/post/oklahoma"' in body


def test_full_text_review_credits_adjudicator_directly(client, db):
    society_id = seed_society(db)
    adj_id = seed_adjudicator(db, "Peter Kennedy")
    add_full_text_review(db, society_id, "Sister Act", season="22/23", adjudicator_id=adj_id)

    body = client.get("/reviews?q=sister").get_data(as_text=True)
    assert "Peter Kennedy" in body


def test_adjudicator_name_links_to_their_own_page(client, db):
    """Previously plain text, despite /adjudicators/<id> existing - the whole
    row used to be one <a>, which is why the name couldn't be its own link
    (HTML doesn't allow a nested <a>); the row is a <div> now, with the show
    title carrying the row's original destination instead."""
    society_id = seed_society(db)
    adj_id = seed_adjudicator(db, "Peter Kennedy")
    show_id = add_full_text_review(db, society_id, "Sister Act", season="22/23", adjudicator_id=adj_id)

    body = client.get("/reviews?q=sister").get_data(as_text=True)
    assert f'href="/adjudicators/{adj_id}">Peter Kennedy</a>' in body
    # The show title still goes straight to the review, same as before.
    assert f'href="/shows/{show_id}#showtimes-review">Sister Act</a>' in body


def test_linked_review_credits_adjudicator_only_when_exactly_one_assigned(client, db):
    society_id = seed_society(db)
    adj_id = seed_adjudicator(db, "Solo Judge")
    assign(db, "25/26", "Gilbert", adj_id)
    add_linked_show(db, society_id, "Solo Credited", season="25/26", section="Gilbert")

    body = client.get("/reviews?q=solo+credited").get_data(as_text=True)
    assert "Solo Judge" in body


def test_linked_review_uncredited_when_two_adjudicators_assigned_that_season(client, db):
    """A recorded mid-season change - never guess which of the two wrote
    this specific review."""
    society_id = seed_society(db)
    first_id = seed_adjudicator(db, "First Judge")
    second_id = seed_adjudicator(db, "Second Judge")
    assign(db, "25/26", "Gilbert", first_id)
    assign(db, "25/26", "Gilbert", second_id)
    add_linked_show(db, society_id, "Ambiguous Show", season="25/26", section="Gilbert")

    body = client.get("/reviews?q=ambiguous").get_data(as_text=True)
    results = body.split("result")[1]  # after "N results for..." - drop the filter dropdowns above it
    assert "First Judge" not in results
    assert "Second Judge" not in results


def test_season_filter_narrows_results(client, db):
    society_id = seed_society(db)
    add_linked_show(db, society_id, "Recent Show", season="25/26")
    add_full_text_review(db, society_id, "Old Show", season="16/17")

    body = client.get("/reviews?season=25%2F26").get_data(as_text=True)
    assert "Recent Show" in body
    assert "Old Show" not in body


def test_tier_filter_narrows_results(client, db):
    society_id = seed_society(db)
    add_full_text_review(db, society_id, "Gilbert Show", season="22/23", tier="Gilbert")
    add_full_text_review(db, society_id, "Sullivan Show", season="22/23", tier="Sullivan")

    body = client.get("/reviews?tier=Gilbert").get_data(as_text=True)
    assert "Gilbert Show" in body
    assert "Sullivan Show" not in body


def test_adjudicator_filter_narrows_results(client, db):
    society_id = seed_society(db)
    adj_a = seed_adjudicator(db, "Judge A")
    adj_b = seed_adjudicator(db, "Judge B")
    add_full_text_review(db, society_id, "Show A", season="22/23", adjudicator_id=adj_a)
    add_full_text_review(db, society_id, "Show B", season="22/23", adjudicator_id=adj_b)

    body = client.get(f"/reviews?adjudicator={adj_a}").get_data(as_text=True)
    assert "Show A" in body
    assert "Show B" not in body


def test_hidden_society_excluded(client, db):
    society_id = seed_society(db)
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.commit()
    add_full_text_review(db, society_id, "Hidden Society Show", season="22/23")

    body = client.get("/reviews?q=hidden").get_data(as_text=True)
    assert "Hidden Society Show" not in body


def test_pending_historical_review_excluded(client, db):
    society_id = seed_society(db)
    add_full_text_review(db, society_id, "Not Yet Approved", season="22/23", moderation_status="pending")

    body = client.get("/reviews?q=not+yet").get_data(as_text=True)
    assert "Not Yet Approved" not in body


def test_stat_tiles_reflect_totals_not_the_active_filter(client, db):
    society_id = seed_society(db)
    add_linked_show(db, society_id, "Show One", season="25/26")
    add_full_text_review(db, society_id, "Show Two", season="16/17")

    body = client.get("/reviews?season=25%2F26").get_data(as_text=True)
    assert '<span class="stat-value">2</span>' in body


def test_nav_links_to_reviews(client):
    body = client.get("/").get_data(as_text=True)
    assert 'href="/reviews"' in body
