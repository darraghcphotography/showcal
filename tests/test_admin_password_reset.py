"""One-time emailed links for setting a new moderator/admin password.

See app/auth.py (create_admin_reset / find_admin_reset), the /admin/reset
route in app/blueprints/admin/auth.py, and admin_reset_link.py, which mints
and emails the link.
"""
from werkzeug.security import check_password_hash

from conftest import seed_user

from app.auth import create_admin_reset, hash_magic_token

NEW = "a-long-new-password"


def _reset(db, user_id, minutes=30):
    token = create_admin_reset(db, user_id, minutes=minutes)
    db.commit()
    return token


def _password_ok(db, user_id, password):
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    return check_password_hash(row["password_hash"], password)


def test_only_the_hash_is_stored(db):
    user_id = seed_user(db)
    token = _reset(db, user_id)
    stored = db.execute("SELECT token_hash FROM admin_password_resets").fetchone()["token_hash"]
    assert stored == hash_magic_token(token)
    assert token not in stored


def test_the_link_sets_a_new_password_and_works_once(client, db):
    user_id = seed_user(db)
    token = _reset(db, user_id)

    assert "Set a new password" in client.get(f"/admin/reset/{token}").get_data(as_text=True)
    client.post(f"/admin/reset/{token}", data={"password": NEW, "confirm": NEW})
    assert _password_ok(db, user_id, NEW)

    again = client.post(f"/admin/reset/{token}", data={"password": "another-long-one", "confirm": "another-long-one"})
    assert again.status_code == 302
    assert _password_ok(db, user_id, NEW)


def test_opening_the_link_does_not_spend_it(client, db):
    user_id = seed_user(db)
    token = _reset(db, user_id)
    client.get(f"/admin/reset/{token}")
    client.get(f"/admin/reset/{token}")
    client.post(f"/admin/reset/{token}", data={"password": NEW, "confirm": NEW})
    assert _password_ok(db, user_id, NEW)


def test_an_expired_link_changes_nothing(client, db):
    user_id = seed_user(db)
    token = _reset(db, user_id, minutes=-1)
    response = client.post(f"/admin/reset/{token}", data={"password": NEW, "confirm": NEW})
    assert response.status_code == 302
    assert _password_ok(db, user_id, "password123")


def test_a_newer_link_cancels_the_older_one(client, db):
    user_id = seed_user(db)
    old = _reset(db, user_id)
    _reset(db, user_id)
    client.post(f"/admin/reset/{old}", data={"password": NEW, "confirm": NEW})
    assert _password_ok(db, user_id, "password123")


def test_short_or_mismatched_passwords_are_refused_and_the_link_survives(client, db):
    user_id = seed_user(db)
    token = _reset(db, user_id)
    client.post(f"/admin/reset/{token}", data={"password": "short", "confirm": "short"})
    client.post(f"/admin/reset/{token}", data={"password": NEW, "confirm": NEW + "x"})
    assert _password_ok(db, user_id, "password123")
    client.post(f"/admin/reset/{token}", data={"password": NEW, "confirm": NEW})
    assert _password_ok(db, user_id, NEW)


def test_an_unknown_token_is_turned_away(client, db):
    seed_user(db)
    response = client.get("/admin/reset/not-a-real-token")
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_the_emailed_url_carries_the_site_and_path_prefix(monkeypatch):
    import admin_reset_link
    monkeypatch.setattr(admin_reset_link.notify, "SITE_URL", "https://darraghc.ie")
    monkeypatch.setenv("URL_PREFIX", "/showcal")
    assert admin_reset_link.reset_url("abc") == "https://darraghc.ie/showcal/admin/reset/abc"
