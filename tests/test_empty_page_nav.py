"""The Costumes & Props exchange and the FAQ are only linked once they have
something on them.

Both shipped as fully-built but completely empty pages, linked from the header
dropdown and the footer - so on a site whose whole value is being a real record
of what happened, a visitor could click twice from the homepage and find an
empty room. Found 2026-09-06 against production, where /exchange and /faq were
both live, both linked, and both had zero rows.

The links are hidden rather than the routes deleted, so each page comes back on
its own the moment there is content and nobody has to remember to re-add it -
which is what most of these tests are actually pinning.
"""
from conftest import seed_society


def add_faq(db, status="published"):
    db.execute(
        "INSERT INTO faq_entries (question, answer, status) VALUES (?, ?, ?)",
        ("Is this thing on?", "Yes.", status),
    )
    db.commit()


def add_item(db, status="available", hidden=0):
    seed_society(db, id=1, name="Wardrobe Society")
    if hidden:
        db.execute("UPDATE societies SET hidden = 1 WHERE id = 1")
    db.execute(
        """
        INSERT INTO wardrobe_items (society_id, title, item_type, terms, status)
        VALUES (1, 'Oliver! workhouse coats', 'costume_full_set', 'hire', ?)
        """,
        (status,),
    )
    db.commit()


def test_empty_exchange_and_faq_are_not_linked(client):
    body = client.get("/").get_data(as_text=True)
    assert "Costumes &amp; Props" not in body
    assert ">FAQ<" not in body


def test_the_mobile_more_page_drops_them_too(client):
    """/more is the whole menu on a phone - the header dropdown is not shown
    there, so gating base.html alone would have left both links reachable for
    exactly the visitors who see them most."""
    body = client.get("/more").get_data(as_text=True)
    assert "Costumes, Props &amp; Sets Exchange" not in body
    assert ">FAQ<" not in body


def test_a_title_page_does_not_invite_you_into_an_empty_exchange(client, db):
    """The "Staging X? Check the Exchange" banner appears precisely when that
    title has nothing listed, so on an empty exchange it is an invitation to an
    empty page."""
    seed_society(db, id=1)
    db.execute("INSERT INTO shows (society_id, season, region, show, opening_date, "
               "closing_date, moderation_status) VALUES (1, '26/27', 'Eastern', "
               "'Oliver!', '2099-01-01', '2099-01-05', 'approved')")
    db.commit()
    body = client.get("/titles/Oliver!").get_data(as_text=True)
    assert "Search Exchange" not in body


def test_the_pages_themselves_still_work_when_unlinked(client):
    """Hidden from the nav, not taken away - an existing bookmark or an inbound
    link must not start 404ing because the page is quiet."""
    assert client.get("/exchange").status_code == 200
    assert client.get("/faq").status_code == 200


def test_faq_link_returns_once_an_answer_is_published(client, db):
    add_faq(db)
    body = client.get("/").get_data(as_text=True)
    assert ">FAQ<" in body


def test_a_draft_answer_does_not_bring_the_faq_link_back(client, db):
    """/faq lists published entries only, so a draft would put the empty page
    straight back into the nav."""
    add_faq(db, status="draft")
    assert ">FAQ<" not in client.get("/").get_data(as_text=True)


def test_exchange_link_returns_once_an_item_is_listed(client, db):
    add_item(db)
    body = client.get("/").get_data(as_text=True)
    assert "Costumes &amp; Props" in body


def test_a_delisted_item_does_not_bring_the_exchange_link_back(client, db):
    add_item(db, status="delisted")
    assert "Costumes &amp; Props" not in client.get("/").get_data(as_text=True)


def test_a_hidden_societys_item_does_not_bring_the_exchange_link_back(client, db):
    """/exchange excludes hidden societies, so their items must not count
    towards the page having content either."""
    add_item(db, hidden=1)
    assert "Costumes &amp; Props" not in client.get("/").get_data(as_text=True)
