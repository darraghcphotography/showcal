import re
from unittest.mock import patch

from conftest import seed_society, seed_user

from app.auth import hash_magic_token


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def token_from_email(mock_notify):
    """Pull the magic-link token out of the email body - the only place the
    plaintext exists once it has been minted. A test that reached into the
    database for it would be testing a leak, not a login."""
    body = mock_notify.call_args[0][1]
    match = re.search(r"/society/auth/([\w-]+)", body)
    assert match, f"no magic link in email body: {body!r}"
    return match.group(1)


def test_society_request_access_flow(client, db):
    seed_society(db, id=1, name="Clane Musical Society")

    # 1. Public user requests access for a society
    response = client.get("/society/request-access")
    assert response.status_code == 200
    assert b"Request 1-Click Society Access" in response.data

    with patch("app.notify.send") as mock_notify:
        post_resp = client.post(
            "/society/request-access",
            data={
                "society_id": "1",
                "requester_name": "Sarah Connor",
                "requester_email": "sarah@example.com",
                "requester_role": "Secretary",
            },
        )
        assert post_resp.status_code == 200
        assert b"Access Request Submitted" in post_resp.data
        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert "Clane Musical Society" in args[0]
        assert "Sarah Connor" in args[1]
        assert "sarah@example.com" in args[1]

    req = db.execute("SELECT * FROM society_access_requests WHERE requester_email = 'sarah@example.com'").fetchone()
    assert req is not None
    assert req["status"] == "pending"
    assert req["requester_name"] == "Sarah Connor"
    # Only a hash is stored, and a pending request's token is never emailed to
    # anyone - approval mints a fresh one. There is deliberately no way to get
    # a working link out of this row.
    assert "token" not in req.keys()
    assert re.fullmatch(r"[0-9a-f]{64}", req["token_hash"])


def test_request_access_rejects_a_malformed_email(client, db):
    """A typo here means the approved magic link goes nowhere and nobody finds
    out - notify.send cannot see a bounce."""
    seed_society(db, id=1, name="Clane Musical Society")

    with patch("app.notify.send") as mock_notify:
        resp = client.post(
            "/society/request-access",
            data={
                "society_id": "1",
                "requester_name": "Sarah Connor",
                "requester_email": "sarah@example",
                "requester_role": "Secretary",
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    assert b"look right" in resp.data
    mock_notify.assert_not_called()
    assert db.execute("SELECT COUNT(*) FROM society_access_requests").fetchone()[0] == 0


def test_request_access_honeypot_swallows_a_bot(client, db):
    seed_society(db, id=1, name="Clane Musical Society")

    with patch("app.notify.send") as mock_notify:
        resp = client.post(
            "/society/request-access",
            data={
                "society_id": "1",
                "requester_name": "Spam Bot",
                "requester_email": "bot@example.com",
                "requester_role": "Secretary",
                "website": "http://spam.example",
            },
        )
    # Looks identical to a real submission from the bot's side, but nothing was
    # written and Darragh's inbox stays quiet.
    assert resp.status_code == 200
    assert b"Access Request Submitted" in resp.data
    mock_notify.assert_not_called()
    assert db.execute("SELECT COUNT(*) FROM society_access_requests").fetchone()[0] == 0


def test_admin_approve_and_magic_login(client, db):
    seed_society(db, id=1, name="Clane Musical Society")
    user_id = seed_user(db)

    # 1. Create a pending request
    db.execute(
        """
        INSERT INTO society_access_requests (society_id, requester_name, requester_email, requester_role, token_hash, status)
        VALUES (1, 'John Doe', 'john@example.com', 'PRO', ?, 'pending')
        """,
        (hash_magic_token("placeholder-never-sent"),),
    )
    db.commit()
    req_id = db.execute("SELECT id FROM society_access_requests").fetchone()["id"]

    # 2. Admin views queue
    login_as(client, user_id)
    dash_resp = client.get("/admin/")
    assert b"Society access requests" in dash_resp.data

    queue_resp = client.get("/admin/access-requests")
    assert queue_resp.status_code == 200
    assert b"John Doe" in queue_resp.data
    assert b"john@example.com" in queue_resp.data

    # 3. Admin approves request - sends magic link email to requester
    with patch("app.notify.send") as mock_notify:
        mock_notify.return_value = True
        approve_resp = client.post(f"/admin/access-requests/{req_id}/approve", follow_redirects=True)
        assert approve_resp.status_code == 200
        assert b"Approved - magic link emailed to john@example.com" in approve_resp.data
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        assert "Your access to Clane Musical Society on ShowCal is approved!" in args[0]
        assert kwargs.get("to") == "john@example.com"
        token = token_from_email(mock_notify)

    # Approval rotates the token, so the placeholder the row was created with
    # is dead and the stored hash matches only what actually went out.
    row = db.execute("SELECT * FROM society_access_requests WHERE id = ?", (req_id,)).fetchone()
    assert row["token_hash"] == hash_magic_token(token)
    assert row["token_hash"] != hash_magic_token("placeholder-never-sent")

    # 4. User logs out of admin and clicks Magic Link
    with client.session_transaction() as sess:
        sess.clear()

    magic_resp = client.get(f"/society/auth/{token}", follow_redirects=True)
    assert magic_resp.status_code == 200
    assert b"Welcome, John Doe!" in magic_resp.data
    assert b"Clane Musical Society" in magic_resp.data

    row = db.execute("SELECT * FROM society_access_requests WHERE id = ?", (req_id,)).fetchone()
    assert row["status"] == "used"
    assert row["used_at"] is not None
    assert row["use_count"] == 1


def test_magic_link_is_reusable_within_its_lifetime(client, db):
    """Deliberate: an email scanner's prefetch, or a second click from another
    committee member's phone, must not lock the society out. The link is an
    alias for the 30-day invite code it activates, so single-use here would buy
    nothing - see auth_magic_link's comment."""
    seed_society(db, id=1, name="Clane Musical Society")
    user_id = seed_user(db)
    login_as(client, user_id)

    with patch("app.notify.send") as mock_notify:
        mock_notify.return_value = True
        client.post(
            "/admin/access-requests/create-direct",
            data={"society_id": "1", "requester_name": "Repeat Clicker", "requester_email": "repeat@example.com"},
            follow_redirects=True,
        )
        token = token_from_email(mock_notify)

    for _ in range(2):
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.get(f"/society/auth/{token}", follow_redirects=True)
        assert b"Welcome, Repeat Clicker!" in resp.data

    row = db.execute("SELECT * FROM society_access_requests WHERE requester_email = 'repeat@example.com'").fetchone()
    assert row["use_count"] == 2
    # used_at records the *first* click, not the latest.
    assert row["used_at"] is not None


def test_magic_link_rejects_an_unknown_token(client, db):
    seed_society(db, id=1, name="Clane Musical Society")
    resp = client.get("/society/auth/not-a-real-token", follow_redirects=True)
    assert resp.status_code == 200
    assert b"invalid, expired, or pending approval" in resp.data


def test_admin_told_when_the_magic_link_email_fails(client, db):
    """notify.send never raises, so without this the moderator sees the same
    success message whether the society got its link or not."""
    seed_society(db, id=1, name="Clane Musical Society")
    user_id = seed_user(db)
    login_as(client, user_id)

    db.execute(
        """
        INSERT INTO society_access_requests (society_id, requester_name, requester_email, requester_role, token_hash, status)
        VALUES (1, 'Jane Roe', 'jane@example.com', 'Secretary', ?, 'pending')
        """,
        (hash_magic_token("placeholder-never-sent"),),
    )
    db.commit()
    req_id = db.execute("SELECT id FROM society_access_requests").fetchone()["id"]

    with patch("app.notify.send") as mock_notify:
        mock_notify.return_value = False
        resp = client.post(f"/admin/access-requests/{req_id}/approve", follow_redirects=True)

    assert b"FAILED to send" in resp.data
    assert b"jane@example.com" in resp.data
    # The link is still in the message, so the moderator can finish by hand.
    assert b"/society/auth/" in resp.data


def test_admin_direct_magic_link_generation(client, db):
    seed_society(db, id=1, name="Clane Musical Society")
    user_id = seed_user(db)
    login_as(client, user_id)

    with patch("app.notify.send") as mock_notify:
        mock_notify.return_value = True
        direct_resp = client.post(
            "/admin/access-requests/create-direct",
            data={
                "society_id": "1",
                "requester_name": "Direct Officer",
                "requester_email": "direct@example.com",
                "requester_role": "Chairperson",
            },
            follow_redirects=True,
        )
        assert direct_resp.status_code == 200
        assert b"Clane Musical Society: Link generated" in direct_resp.data
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        assert "Your access to Clane Musical Society on ShowCal is ready!" in args[0]
        assert kwargs.get("to") == "direct@example.com"
        token = token_from_email(mock_notify)

    req = db.execute("SELECT * FROM society_access_requests WHERE requester_email = 'direct@example.com'").fetchone()
    assert req is not None
    assert req["status"] == "approved"
    assert req["token_hash"] == hash_magic_token(token)

    # Log out of admin and use link
    with client.session_transaction() as sess:
        sess.clear()

    login_resp = client.get(f"/society/auth/{token}", follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Welcome, Direct Officer!" in login_resp.data
