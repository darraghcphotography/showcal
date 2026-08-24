"""Second Act backlog item 6 - a floating "back to top" button on the three
longest list pages (societies, titles, reviews), no way back to the filter
form right now except a long thumb-scroll. See _back_to_top.html: it's a
plain #page-top anchor that works with zero JavaScript (always visible,
jumps instantly); base.html's scroll listener only adds fading it out near
the top as a nicety."""
from conftest import seed_society


def test_societies_page_has_the_button_and_target(client):
    body = client.get("/societies").get_data(as_text=True)
    assert '<a href="#page-top" class="back-to-top" aria-label="Back to top">' in body
    assert '<h1 id="page-top">Societies</h1>' in body


def test_titles_page_has_the_button_and_target(client):
    body = client.get("/titles").get_data(as_text=True)
    assert '<a href="#page-top" class="back-to-top" aria-label="Back to top">' in body
    assert '<h1 id="page-top">Shows A-Z</h1>' in body


def test_reviews_page_has_the_button_and_target(client):
    body = client.get("/reviews").get_data(as_text=True)
    assert '<a href="#page-top" class="back-to-top" aria-label="Back to top">' in body
    assert '<h1 id="page-top">Reviews</h1>' in body


def test_other_pages_do_not_get_the_button(client, db):
    society_id = seed_society(db)
    for path in ("/", "/awards", "/stats", f"/societies/{society_id}"):
        body = client.get(path).get_data(as_text=True)
        assert 'class="back-to-top"' not in body, f"{path} unexpectedly has the back-to-top button"
