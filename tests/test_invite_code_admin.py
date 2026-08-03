"""Admin invite-code cleanup routes: delete a single code, bulk-delete the
old AIMS-XXXXXX style codes, and generate/reveal a society's own login code
from its public page - all admin-only (see moderator-guide.md: "moderator -
queue and show editing, but not invite codes")."""
from conftest import seed_invite_code, seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_delete_invite_code_removes_unused_code(client, db):
    admin_id = seed_user(db, username="boss", role="admin")
    code_id = seed_invite_code(db, code="quiet-otter")
    login_as(client, admin_id)

    resp = client.post(f"/admin/invite-codes/{code_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert db.execute("SELECT 1 FROM invite_codes WHERE id = ?", (code_id,)).fetchone() is None


def test_delete_invite_code_blocks_non_admin(client, db):
    mod_id = seed_user(db, username="mod", role="moderator")
    code_id = seed_invite_code(db, code="quiet-otter")
    login_as(client, mod_id)

    resp = client.post(f"/admin/invite-codes/{code_id}/delete")
    assert resp.status_code == 403
    assert db.execute("SELECT 1 FROM invite_codes WHERE id = ?", (code_id,)).fetchone() is not None


def test_delete_invite_code_in_use_is_left_alone(client, db):
    admin_id = seed_user(db, username="boss", role="admin")
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="quiet-otter", society_id=society_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, invite_code_id, source, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', 'Test Show', ?, 'submission', 'approved')",
        (society_id, code_id),
    )
    db.commit()
    login_as(client, admin_id)

    resp = client.post(f"/admin/invite-codes/{code_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert db.execute("SELECT 1 FROM invite_codes WHERE id = ?", (code_id,)).fetchone() is not None


def test_delete_legacy_invite_codes_removes_only_aims_prefixed(client, db):
    admin_id = seed_user(db, username="boss", role="admin")
    legacy_id = seed_invite_code(db, code="AIMS-U7SYDT")
    word_id = seed_invite_code(db, code="silver-otter")
    manual_id = seed_invite_code(db, code="madness")
    login_as(client, admin_id)

    resp = client.post("/admin/invite-codes/delete-legacy", follow_redirects=False)
    assert resp.status_code == 302
    assert db.execute("SELECT 1 FROM invite_codes WHERE id = ?", (legacy_id,)).fetchone() is None
    assert db.execute("SELECT 1 FROM invite_codes WHERE id = ?", (word_id,)).fetchone() is not None
    assert db.execute("SELECT 1 FROM invite_codes WHERE id = ?", (manual_id,)).fetchone() is not None


def test_generate_society_code_creates_unlabeled_code(client, db):
    admin_id = seed_user(db, username="boss", role="admin")
    society_id = seed_society(db)
    login_as(client, admin_id)

    resp = client.post(f"/admin/societies/{society_id}/generate-code", follow_redirects=False)
    assert resp.status_code == 302

    row = db.execute(
        "SELECT * FROM invite_codes WHERE society_id = ?", (society_id,)
    ).fetchone()
    assert row is not None
    assert row["label"] is None
    assert "-" in row["code"]


def test_society_page_shows_generate_button_when_no_code(client, db):
    admin_id = seed_user(db, username="boss", role="admin")
    society_id = seed_society(db)
    login_as(client, admin_id)

    resp = client.get(f"/societies/{society_id}")
    body = resp.get_data(as_text=True)
    assert "Generate a login code for this society" in body


def test_society_page_shows_existing_code_instead_of_button(client, db):
    admin_id = seed_user(db, username="boss", role="admin")
    society_id = seed_society(db)
    seed_invite_code(db, code="golden-heron", society_id=society_id)
    login_as(client, admin_id)

    resp = client.get(f"/societies/{society_id}")
    body = resp.get_data(as_text=True)
    assert "golden-heron" in body
    assert "Generate a login code for this society" not in body


def test_society_page_hides_code_panel_from_non_admin(client, db):
    mod_id = seed_user(db, username="mod", role="moderator")
    society_id = seed_society(db)
    login_as(client, mod_id)

    resp = client.get(f"/societies/{society_id}")
    body = resp.get_data(as_text=True)
    assert "Generate a login code for this society" not in body
    assert "Login code for this society" not in body


def test_society_page_hides_code_panel_from_anonymous(client, db):
    society_id = seed_society(db)
    resp = client.get(f"/societies/{society_id}")
    body = resp.get_data(as_text=True)
    assert "Generate a login code for this society" not in body
    assert "Login code for this society" not in body
