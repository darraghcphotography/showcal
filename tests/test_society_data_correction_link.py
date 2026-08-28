"""V4 (small-items queue): every data correction so far arrived because a
human got in touch off-platform (e.g. Oyster Lane's incorrect pre-2018
history, only caught because the society emailed). Societies looking at
their own page are best placed to spot an error and, until now, the least
prompted to report one - /more.html signposts /suggest, but that's a page
people reach deliberately, not the page where they'd actually notice."""
from conftest import seed_society


def test_society_page_links_to_suggest(client, db):
    society_id = seed_society(db)
    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert '/suggest?' in body


def test_the_link_prefills_the_data_error_category(client, db):
    society_id = seed_society(db)
    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "category=Data+error" in body or "category=Data%20error" in body

    resp = client.get("/suggest?category=Data error&message=On the Test Society page: ")
    assert resp.status_code == 200
    assert 'value="Data error"' in resp.get_data(as_text=True) or "selected" in resp.get_data(as_text=True)
