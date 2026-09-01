"""The Costumes & Props Exchange must not publish volunteers' contact details.

Found in the 2026-09-01 audit: `/exchange/<id>` rendered a named individual, a
personal mobile as a clickable `tel:` link, and an email on a fully public,
crawlable page (`robots.txt` is `Allow: /`, disallowing only /admin/ and
/submit/). The vault form's own placeholders invited exactly that - "e.g. Mary
Kelly (Wardrobe Head)", "e.g. 087 123 4567" - and said nothing about any of it
becoming public.

Darragh's decision: contact details are visible only to a signed-in society,
and a listing holds a society address only - no personal name, no mobile.

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


def test_a_signed_in_society_does_see_the_contact_address(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    item_id = seed_item(db, society_id, contact_email="wardrobe@testsociety.ie")
    unlock_society(client, code_id)

    body = client.get(f"/exchange/{item_id}").get_data(as_text=True)
    assert "wardrobe@testsociety.ie" in body


def test_the_listing_form_does_not_ask_for_a_person_or_a_mobile(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    unlock_society(client, code_id)

    body = client.get("/society/vault/new").get_data(as_text=True)
    assert 'name="contact_name"' not in body
    assert 'name="contact_phone"' not in body
    assert 'name="contact_email"' in body
    # And it says who will see it, which the original form never did.
    assert "signed in to ShowCal" in body


def test_a_posted_name_or_phone_is_ignored_on_create(client, db):
    """Removing the inputs is not enough - the form is just HTML, and a POST
    can carry any field. The route must not store them either."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    unlock_society(client, code_id)

    client.post("/society/vault/new", data={
        "title": "Chorus Coats", "item_type": "costume_full_set", "terms": "hire",
        "status": "available", "contact_email": "wardrobe@testsociety.ie",
        "agree_terms": "1",
        "contact_name": "Mary Kelly", "contact_phone": "087 123 4567",
    })

    row = db.execute("SELECT * FROM wardrobe_items WHERE title = 'Chorus Coats'").fetchone()
    assert row is not None
    assert row["contact_name"] is None
    assert row["contact_phone"] is None
    assert row["contact_email"] == "wardrobe@testsociety.ie"


def test_editing_an_old_listing_sheds_details_it_was_created_with(client, db):
    """Listings created under the old form still hold personal data. Editing
    one clears it, so the fix reaches existing rows through normal use as well
    as through the one-off backfill."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    item_id = seed_item(
        db, society_id, contact_name="Mary Kelly", contact_phone="087 123 4567",
    )
    unlock_society(client, code_id)

    client.post(f"/society/vault/{item_id}/edit", data={
        "title": "Victorian Chorus Coats", "item_type": "costume_full_set",
        "terms": "hire", "status": "available",
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
