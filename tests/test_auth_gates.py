"""Auth gates actually block unauthenticated (or under-privileged) access.

Covers the four decorators in app/auth.py + admin.py's admin_required:
login_required, admin_required, society_required, invite_required.
"""
from conftest import seed_invite_code, seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def unlock_invite(client, code_id):
    with client.session_transaction() as sess:
        sess["invite_code_id"] = code_id


def test_login_required_blocks_unauthenticated(client):
    resp = client.get("/admin/")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_login_required_allows_authenticated(client, db):
    user_id = seed_user(db, role="moderator")
    login_as(client, user_id)
    resp = client.get("/admin/")
    assert resp.status_code == 200


def test_admin_required_blocks_unauthenticated(client):
    resp = client.get("/admin/invite-codes")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_admin_required_blocks_non_admin(client, db):
    user_id = seed_user(db, username="mod", role="moderator")
    login_as(client, user_id)
    resp = client.get("/admin/invite-codes")
    assert resp.status_code == 403


def test_admin_required_allows_admin(client, db):
    user_id = seed_user(db, username="boss", role="admin")
    login_as(client, user_id)
    resp = client.get("/admin/invite-codes")
    assert resp.status_code == 200


def test_society_required_blocks_unauthenticated(client):
    resp = client.get("/society/")
    assert resp.status_code == 302
    assert "/society/login" in resp.headers["Location"]


def test_society_required_allows_valid_code(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    unlock_society(client, code_id)
    resp = client.get("/society/")
    assert resp.status_code == 200


def test_society_required_rejects_revoked_code(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC002", society_id=society_id)
    db.execute("UPDATE invite_codes SET is_active = 0 WHERE id = ?", (code_id,))
    db.commit()
    unlock_society(client, code_id)
    resp = client.get("/society/")
    assert resp.status_code == 302
    assert "/society/login" in resp.headers["Location"]


def test_invite_required_blocks_unauthenticated(client):
    resp = client.get("/submit/new")
    assert resp.status_code == 302
    assert "/submit/unlock" in resp.headers["Location"]


def test_invite_required_allows_valid_code(client, db):
    code_id = seed_invite_code(db, code="AIMS-GEN001", society_id=None)
    unlock_invite(client, code_id)
    resp = client.get("/submit/new")
    assert resp.status_code == 200
