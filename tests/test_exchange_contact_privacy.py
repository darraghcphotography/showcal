"""The Costumes & Props Exchange must not publish volunteers' contact details.

Found in the 2026-09-01 audit: `/exchange/<id>` rendered a named individual, a
personal mobile as a clickable `tel:` link, and an email on a fully public,
crawlable page (`robots.txt` is `Allow: /`, disallowing only /admin/ and
/submit/). The vault form's own placeholders invited exactly that - "e.g. Mary
Kelly (Wardrobe Head)", "e.g. 087 123 4567" - and said nothing about any of it
becoming public.

Darragh's decision, revised 2026-09-02: a listing may carry a coordinator and a
phone again, because an enquiry about hiring a set of costumes needs to reach a
person rather than an inbox - but they are shown only to a signed-in society,
and the form now states that plainly. What was wrong was never that the fields
existed; it was that they were published from a form that didn't say so.

The distinction these tests are really protecting is between *hidden* and *not
sent*. A template-only guard still ships the phone number inside the HTML for
anyone who views source. So the assertions below check the response body, not
the rendered page: what the browser never receives cannot be scraped.
"""
from conftest import seed_invite_code, seed_society


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def seed_item(db, society_id, **kw):
    fields = {
        "society_id": society_id,
        "title": "Victorian Chorus Coats",
        "item_type": "costume_full_set",
        "status": "available",
        "terms": "hire",
        "contact_email": "wardrobe@testsociety.ie",
    }
    fields.update(kw)
    cols = ", ".join(fields)
    db.execute(
        f"INSERT INTO wardrobe_items ({cols}) VALUES ({', '.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    db.commit()
    return db.execute("SELECT id FROM wardrobe_items ORDER BY id DESC LIMIT 1").fetchone()["id"]


def test_a_public_visitor_never_receives_contact_details(client, db):
    society_id = seed_society(db)
    item_id = seed_item(
        db, society_id,
        contact_name="Mary Kelly", contact_phone="087 123 4567",
        contact_email="mary.kelly@example.com",
    )

    body = client.get(f"/exchange/{item_id}").get_data(as_text=True)
    assert body.count("Victorian Chorus Coats") >= 1      # the listing itself still works
    assert "Mary Kelly" not in body
    assert "087 123 4567" not in body
    assert "mary.kelly@example.com" not in body
    assert "tel:" not in body


def test_a_public_visitor_is_told_how_to_get_them(client, db):
    """Protecting the details is only half of it - a real society arriving from
    a search result has to be able to find its way to a login."""
    society_id = seed_society(db)
    item_id = seed_item(db, society_id)

    body = client.get(f"/exchange/{item_id}").get_data(as_text=True)
    assert "Sign in to see contact details" in body
    assert "/society/login" in body
    assert "/society/request-access" in body


def test_a_signed_in_society_sees_all_three(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    item_id = seed_item(
        db, society_id,
        contact_name="Wardrobe Head", contact_phone="01 234 5678",
        contact_email="wardrobe@testsociety.ie",
    )
    unlock_society(client, code_id)

    body = client.get(f"/exchange/{item_id}").get_data(as_text=True)
    assert "wardrobe@testsociety.ie" in body
    assert "Wardrobe Head" in body
    assert "01 234 5678" in body


def test_the_listing_form_says_where_the_details_will_show_up(client, db):
    """The original form's failure was silence, not the fields themselves - it
    collected a person and a mobile while saying nothing about publishing
    them."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    unlock_society(client, code_id)

    body = client.get("/society/vault/new").get_data(as_text=True)
    assert 'name="contact_name"' in body
    assert 'name="contact_phone"' in body
    assert 'name="contact_email"' in body
    assert "shown only to societies signed in to ShowCal" in body
    assert "never on the public listing" in body


def test_a_name_and_phone_are_stored_but_still_never_reach_the_public_page(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    unlock_society(client, code_id)

    client.post("/society/vault/new", data={
        "title": "Chorus Coats", "item_type": "costume_full_set", "terms": "hire",
        "status": "available", "contact_email": "wardrobe@testsociety.ie",
        "agree_terms": "1",
        "contact_name": "Wardrobe Head", "contact_phone": "01 234 5678",
    })

    row = db.execute("SELECT * FROM wardrobe_items WHERE title = 'Chorus Coats'").fetchone()
    assert row is not None
    assert row["contact_name"] == "Wardrobe Head"
    assert row["contact_phone"] == "01 234 5678"
    assert row["contact_email"] == "wardrobe@testsociety.ie"

    # Stored is not published. Same listing, signed out:
    with client.session_transaction() as sess:
        sess.clear()
    body = client.get(f"/exchange/{row['id']}").get_data(as_text=True)
    assert "Wardrobe Head" not in body
    assert "01 234 5678" not in body


def test_clearing_the_contact_fields_on_an_edit_actually_clears_them(client, db):
    """A society that wants a name off a listing must be able to take it off by
    emptying the box - not have the old value quietly survive the save."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    item_id = seed_item(
        db, society_id, contact_name="Mary Kelly", contact_phone="087 123 4567",
    )
    unlock_society(client, code_id)

    client.post(f"/society/vault/{item_id}/edit", data={
        "title": "Victorian Chorus Coats", "item_type": "costume_full_set",
        "terms": "hire", "status": "available",
        "contact_name": "", "contact_phone": "",
        "contact_email": "wardrobe@testsociety.ie",
    })

    row = db.execute("SELECT * FROM wardrobe_items WHERE id = ?", (item_id,)).fetchone()
    assert row["contact_name"] is None
    assert row["contact_phone"] is None


def test_another_society_still_cannot_edit_the_listing(client, db):
    """Guarding the read path must not have loosened the write path."""
    owner_id = seed_society(db)
    other_id = seed_society(db, id=2, name="Other Society")
    code_id = seed_invite_code(db, code="AIMS-SOC002", society_id=other_id)
    item_id = seed_item(db, owner_id)
    unlock_society(client, code_id)

    assert client.get(f"/society/vault/{item_id}/edit").status_code == 404
