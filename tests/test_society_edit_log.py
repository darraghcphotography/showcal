"""Every change a society login makes is recorded, with the value it replaced.

Societies edit their own history through /society/ and it goes live with no
moderation queue. That is deliberate, but until now nothing recorded what a
value used to be, so a wrong edit to a decades-old production was silent and
unrecoverable - on a site whose entire value is being a record of what really
happened.

These tests drive the real routes rather than calling the helper directly: the
failure mode worth guarding against is a write path that quietly does not log,
not a helper that computes a diff wrongly.
"""
from conftest import seed_invite_code, seed_society, seed_user


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def setup(db, client):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    unlock_society(client, code_id)
    return society_id, code_id


def log(db, **where):
    sql = "SELECT * FROM society_edit_log"
    if where:
        sql += " WHERE " + " AND ".join(f"{k} = ?" for k in where)
    return db.execute(sql + " ORDER BY id", tuple(where.values())).fetchall()


def add_show(client, **overrides):
    data = {
        "season": "26/27", "section": "Gilbert", "show": "Oliver!",
        "opening_date": "2099-03-01", "closing_date": "2099-03-05",
        "venue": "Town Hall", "director": "A Director",
        "musical_director": "", "choreographer": "", "ticket_url": "",
    }
    data.update(overrides)
    return client.post("/society/shows/new", data=data, follow_redirects=False)


def test_adding_a_show_is_recorded_as_a_creation(client, db):
    society_id, code_id = setup(db, client)

    add_show(client)

    rows = log(db, table_name="shows")
    assert rows, "adding a show recorded nothing"
    assert {r["action"] for r in rows} == {"create"}
    assert all(r["society_id"] == society_id for r in rows)
    assert all(r["invite_code_id"] == code_id for r in rows)
    by_field = {r["field"]: r for r in rows}
    assert by_field["show"]["new_value"] == "Oliver!"
    # Nothing was there before, and the log must say that rather than leaving it
    # to be read as "unchanged".
    assert by_field["show"]["old_value"] is None


def test_editing_a_show_records_the_value_it_replaced(client, db):
    setup(db, client)
    add_show(client)
    show_id = db.execute("SELECT id FROM shows").fetchone()[0]
    db.execute("DELETE FROM society_edit_log")
    db.commit()

    client.post(f"/society/shows/{show_id}/edit", data={
        "season": "26/27", "section": "Gilbert", "show": "Oliver!",
        "opening_date": "2099-03-01", "closing_date": "2099-03-05",
        "venue": "Town Hall", "director": "A Different Director",
        "musical_director": "", "choreographer": "", "ticket_url": "",
    })

    rows = log(db, table_name="shows", field="director")
    assert len(rows) == 1
    assert rows[0]["action"] == "update"
    assert rows[0]["old_value"] == "A Director"
    assert rows[0]["new_value"] == "A Different Director"


def test_only_the_fields_that_actually_changed_are_logged(client, db):
    """Otherwise every edit logs 12 rows and the real change is buried."""
    setup(db, client)
    add_show(client)
    show_id = db.execute("SELECT id FROM shows").fetchone()[0]
    db.execute("DELETE FROM society_edit_log")
    db.commit()

    client.post(f"/society/shows/{show_id}/edit", data={
        "season": "26/27", "section": "Gilbert", "show": "Oliver!",
        "opening_date": "2099-03-01", "closing_date": "2099-03-05",
        "venue": "A New Venue", "director": "A Director",
        "musical_director": "", "choreographer": "", "ticket_url": "",
    })

    assert [r["field"] for r in log(db, table_name="shows")] == ["venue"]


def test_resubmitting_an_unchanged_form_records_nothing(client, db):
    setup(db, client)
    add_show(client)
    show_id = db.execute("SELECT id FROM shows").fetchone()[0]
    db.execute("DELETE FROM society_edit_log")
    db.commit()

    form = {
        "season": "26/27", "section": "Gilbert", "show": "Oliver!",
        "opening_date": "2099-03-01", "closing_date": "2099-03-05",
        "venue": "Town Hall", "director": "A Director",
        "musical_director": "", "choreographer": "", "ticket_url": "",
    }
    client.post(f"/society/shows/{show_id}/edit", data=form)

    assert log(db) == []


def test_updated_at_alone_is_not_a_change(client, db):
    """It moves on every single edit and says nothing about what was edited."""
    setup(db, client)
    add_show(client)

    assert "updated_at" not in {r["field"] for r in log(db)}


def test_profile_edits_are_recorded(client, db):
    society_id, _ = setup(db, client)

    client.post("/society/profile", data={
        "about": "We rehearse on Tuesdays.",
        "website_url": "https://example.com",
        "facebook_url": "", "instagram_url": "", "tiktok_url": "",
        "other_url": "", "other_label": "",
    })

    fields = {r["field"]: r for r in log(db, table_name="societies")}
    assert fields["about"]["new_value"] == "We rehearse on Tuesdays."
    assert fields["website_url"]["new_value"] == "https://example.com"


def test_a_rejected_edit_records_nothing(client, db):
    """A javascript: URL is refused before the UPDATE runs. The log must not
    claim a change that never happened."""
    setup(db, client)

    client.post("/society/profile", data={
        "about": "", "website_url": "javascript:alert(1)",
        "facebook_url": "", "instagram_url": "", "tiktok_url": "",
        "other_url": "", "other_label": "",
    })

    assert log(db) == []


def test_bulk_add_records_every_row(client, db):
    setup(db, client)

    data = {}
    for i in range(2):
        data.update({
            f"season_{i}": "26/27", f"show_{i}": f"Show {i}",
            f"opening_date_{i}": "2099-04-0%d" % (i + 1),
            f"closing_date_{i}": "2099-04-0%d" % (i + 5),
            f"venue_{i}": "Town Hall", f"director_{i}": "",
            f"musical_director_{i}": "", f"choreographer_{i}": "",
        })
    client.post("/society/shows/bulk", data=data)

    logged = {r["row_id"] for r in log(db, table_name="shows", action="create")}
    shows = {r[0] for r in db.execute("SELECT id FROM shows")}
    assert logged == shows, "a bulk-added show went unrecorded"


def test_deleting_a_vault_item_keeps_what_it_said(client, db):
    """The row is gone, so if the log did not capture it before the DELETE there
    would be nothing left to show."""
    society_id, _ = setup(db, client)
    db.execute(
        """
        INSERT INTO wardrobe_items (society_id, title, item_type, terms, status)
        VALUES (?, 'Oliver! workhouse coats', 'costume_full_set', 'hire', 'available')
        """,
        (society_id,),
    )
    db.commit()
    item_id = db.execute("SELECT id FROM wardrobe_items").fetchone()[0]

    client.post(f"/society/vault/{item_id}/delete")

    rows = {r["field"]: r for r in log(db, table_name="wardrobe_items", action="delete")}
    assert rows["title"]["old_value"] == "Oliver! workhouse coats"
    assert rows["title"]["new_value"] is None


def test_contact_details_are_recorded_as_changed_but_not_quoted(client, db):
    """A log outlives the row it came from and is read by different eyes. That a
    phone number changed is worth knowing; keeping a copy of it here is not."""
    society_id, _ = setup(db, client)
    db.execute(
        """
        INSERT INTO wardrobe_items (society_id, title, item_type, terms, status, contact_email)
        VALUES (?, 'Props', 'prop', 'hire', 'available', 'secretary@example.com')
        """,
        (society_id,),
    )
    db.commit()
    item_id = db.execute("SELECT id FROM wardrobe_items").fetchone()[0]

    client.post(f"/society/vault/{item_id}/delete")

    row = log(db, table_name="wardrobe_items", field="contact_email")[0]
    assert row["old_value"] == "(not recorded)"
    assert "secretary@example.com" not in str(dict(row))


def test_admin_page_shows_an_edit(client, db):
    society_id, _ = setup(db, client)
    add_show(client)
    user_id = seed_user(db)
    login_as(client, user_id)

    body = client.get("/admin/society-edits").get_data(as_text=True)
    assert "Oliver!" in body
    assert "AIMS-SOC001" in body
    # It must not imply it knows who did it.
    assert "identifies a login, not a person" in body


def test_admin_page_is_not_public(client, db):
    resp = client.get("/admin/society-edits")
    assert resp.status_code in (302, 401, 403)


def test_admin_page_survives_an_empty_log(client, db):
    login_as(client, seed_user(db))
    resp = client.get("/admin/society-edits")
    assert resp.status_code == 200
    assert "No society edits recorded yet" in resp.get_data(as_text=True)


def test_a_creation_is_one_line_naming_what_was_created(client, db):
    """Not one row per column. A show has a dozen fields, and logging all of them
    on creation buries the real edits underneath - and they are recoverable from
    the row itself anyway, since a society cannot delete a show."""
    setup(db, client)
    add_show(client)

    rows = log(db, table_name="shows", action="create")
    assert len(rows) == 1
    assert rows[0]["field"] == "show"
    assert rows[0]["new_value"] == "Oliver!"


def test_a_deletion_still_records_every_field(client, db):
    """The opposite case, and the reason the two are treated differently: the row
    is gone, so the log is the only copy left."""
    society_id, _ = setup(db, client)
    db.execute(
        """
        INSERT INTO wardrobe_items (society_id, title, item_type, description, terms, status)
        VALUES (?, 'Coats', 'costume_full_set', 'Twenty of them', 'hire', 'available')
        """,
        (society_id,),
    )
    db.commit()
    item_id = db.execute("SELECT id FROM wardrobe_items").fetchone()[0]

    client.post(f"/society/vault/{item_id}/delete")

    fields = {r["field"] for r in log(db, table_name="wardrobe_items", action="delete")}
    assert {"title", "description", "item_type", "terms"} <= fields
