"""Two empty-state gaps from the 2026-08-23 UX audit: a search on /titles
with no matches rendered the intro paragraph and a completely empty table
with no "nothing found" message, and /stats' "One-off productions" section
rendered its heading and blurb above an empty list with nothing saying so
either. Every other filtered list on the site already says something when
it comes back empty - these two just hadn't been given the same treatment."""
from conftest import seed_society


def test_titles_search_with_no_matches_says_so(client, db):
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (1, '24/25', 'Eastern', 'Oliver!', 'approved', 'import')"
    )
    db.commit()

    body = client.get("/titles?q=zzz_no_such_show").get_data(as_text=True)
    assert 'No shows match "zzz_no_such_show".' in body


def test_titles_list_has_no_empty_message_when_results_exist(client, db):
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (1, '24/25', 'Eastern', 'Oliver!', 'approved', 'import')"
    )
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert "No shows match" not in body


def test_one_off_productions_empty_state(client, db):
    """No shows on record at all, so the section has nothing to list."""
    body = client.get("/stats").get_data(as_text=True)
    assert "No one-off productions on record." in body


def test_homepage_links_to_the_full_season(client):
    """2026-08-23 audit finding: the homepage showed 6 upcoming shows (of
    however many are really announced) with no way to see the rest -
    /season is exactly that fuller list and nothing pointed at it."""
    body = client.get("/").get_data(as_text=True)
    assert 'href="/season"' in body


def test_one_off_productions_empty_state_names_the_region(client, db):
    seed_society(db, region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (1, '24/25', 'Eastern', 'Oliver!', 'approved', 'import')"
    )
    db.commit()

    body = client.get("/stats?region=Western").get_data(as_text=True)
    assert "No one-off productions on record for Western." in body


# ------------------------------------------------------------------------
# V2 (small-items queue): twelve public empty states said only "No X match"
# with no way onward. Filtered lists now offer "Clear filters"; unfiltered
# ones link to a fuller listing - following index.html's own "See
# everything ->" pattern.

def test_societies_list_empty_state_offers_clear_filters(client, db):
    seed_society(db, region="Eastern")
    db.commit()

    body = client.get("/societies?region=Western").get_data(as_text=True)
    assert "No societies match those filters." in body
    assert "Clear filters" in body


def test_venues_list_empty_state_offers_clear_filters(client, db):
    body = client.get("/venues?q=zzz_no_such_venue").get_data(as_text=True)
    assert "No venues match." in body
    assert "Clear filters" in body


def test_reviews_index_empty_state_offers_clear_filters(client, db):
    body = client.get("/reviews?q=zzz_no_such_review").get_data(as_text=True)
    assert "Clear filters" in body


def test_awards_empty_state_offers_clear_filters(client, db):
    body = client.get("/awards?year=1900").get_data(as_text=True)
    assert "No award records match those filters." in body
    assert "Clear filters" in body


def test_adjudicators_empty_state_links_to_reviews(client, db):
    body = client.get("/adjudicators").get_data(as_text=True)
    assert "No adjudicators on record yet." in body
    assert 'href="/reviews"' in body


def test_faq_empty_state_links_to_suggest(client, db):
    body = client.get("/faq").get_data(as_text=True)
    assert "Nothing here yet" in body
    assert 'href="/suggest"' in body


def test_suggestions_board_empty_lane_links_to_suggest(client, db):
    body = client.get("/suggestions").get_data(as_text=True)
    assert body.count('href="/suggest"') >= 2  # intro paragraph + at least one empty lane


def test_stats_trends_empty_state_links_to_awards(client, db):
    body = client.get("/stats/trends").get_data(as_text=True)
    assert "No awards-archive data on record yet." in body
    assert 'href="/awards"' in body


def test_society_with_no_shows_links_to_titles(client, db):
    society_id = seed_society(db)
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "No shows on record yet." in body
    assert 'href="/titles"' in body
