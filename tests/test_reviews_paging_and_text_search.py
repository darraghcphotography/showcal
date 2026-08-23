"""/reviews used to render every review on every visit - 1,086 rows and 460KB
measured live on 2026-08-24, on a page you read a screenful of at a time. It
also carried a notice telling you that to search the words *inside* a review you
had to go and use a different search box, which is the site apologising for a
split the visitor never needed to know about (site audit, finding 12).

Both are fixed here: one page at a time, and one search box that covers the
show, the society and the review's own wording.
"""
from conftest import seed_society

from app.blueprints.public import REVIEWS_PER_PAGE


def add_reviewed_show(db, society_id, show, season="12/13", review_text=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, moderation_status) "
        "VALUES (?, ?, 'Eastern', 'Gilbert', ?, 'approved')",
        (society_id, season, show),
    )
    show_id = db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]
    db.execute(
        "INSERT INTO adjudicators (name) VALUES ('Test Adjudicator') ON CONFLICT DO NOTHING"
    )
    adj_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Test Adjudicator'").fetchone()["id"]
    db.execute(
        "INSERT INTO historical_reviews (show_id, adjudicator_id, season, tier, show_raw, "
        "society_raw, review_text, moderation_status, source_issue) "
        "VALUES (?, ?, ?, 'Gilbert', ?, 'Test Society', ?, 'approved', 'Issue 1')",
        (show_id, adj_id, season, show, review_text or "A perfectly ordinary review."),
    )
    db.commit()
    return show_id


def test_only_one_page_of_reviews_is_rendered(client, db):
    society_id = seed_society(db)
    for i in range(REVIEWS_PER_PAGE + 5):
        add_reviewed_show(db, society_id, f"Show Number {i:03d}")

    body = client.get("/reviews").get_data(as_text=True)
    assert "Page 1 of 2" in body
    # The last few shows sort onto page 2, so they must not be here.
    assert "Show Number 104" not in body

    page_two = client.get("/reviews?page=2").get_data(as_text=True)
    assert "Show Number 104" in page_two


def test_the_count_is_of_everything_matching_not_just_this_page(client, db):
    society_id = seed_society(db)
    for i in range(REVIEWS_PER_PAGE + 5):
        add_reviewed_show(db, society_id, f"Show Number {i:03d}", review_text="findme please")

    body = client.get("/reviews?q=findme").get_data(as_text=True)
    assert f"{REVIEWS_PER_PAGE + 5} results" in body


def test_search_matches_words_inside_a_review(client, db):
    society_id = seed_society(db)
    add_reviewed_show(db, society_id, "Oliver!",
                      review_text="The chorus earned a standing ovation on the night.")
    add_reviewed_show(db, society_id, "Chess", review_text="A competent but quiet evening.")

    body = client.get("/reviews?q=standing+ovation").get_data(as_text=True)
    assert "Oliver!" in body
    assert "Chess" not in body


def test_search_still_matches_show_and_society_names(client, db):
    society_id = seed_society(db, name="Tullyvin Musical Society")
    add_reviewed_show(db, society_id, "Oliver!")

    assert "Oliver!" in client.get("/reviews?q=Oliver").get_data(as_text=True)
    assert "Oliver!" in client.get("/reviews?q=Tullyvin").get_data(as_text=True)


def test_the_go_and_search_elsewhere_notice_is_gone(client, db):
    body = client.get("/reviews").get_data(as_text=True)
    assert "This page is for browsing" not in body


def test_an_out_of_range_page_clamps_rather_than_erroring(client, db):
    society_id = seed_society(db)
    add_reviewed_show(db, society_id, "Oliver!")

    assert client.get("/reviews?page=999").status_code == 200
    assert client.get("/reviews?page=0").status_code == 200
    assert client.get("/reviews?page=notanumber").status_code == 200


def test_paging_keeps_the_active_filters(client, db):
    society_id = seed_society(db)
    for i in range(REVIEWS_PER_PAGE + 5):
        add_reviewed_show(db, society_id, f"Show Number {i:03d}", season="12/13")

    body = client.get("/reviews?season=12/13").get_data(as_text=True)
    assert "season=12%2F13" in body or "season=12/13" in body
