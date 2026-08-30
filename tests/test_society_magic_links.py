from unittest.mock import patch

from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


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
    assert req["token"] is not None


def test_admin_approve_and_magic_login(client, db):
    seed_society(db, id=1, name="Clane Musical Society")
    user_id = seed_user(db)

    # 1. Create a pending request
    db.execute(
        """
        INSERT INTO society_access_requests (society_id, requester_name, requester_email, requester_role, token, status)
        VALUES (1, 'John Doe', 'john@example.com', 'PRO', 'magic-token-xyz-123', 'pending')
        """
    )
    db.commit()
    req = db.execute("SELECT id FROM society_access_requests WHERE token = 'magic-token-xyz-123'").fetchone()
    req_id = req["id"]

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
        approve_resp = client.post(f"/admin/access-requests/{req_id}/approve", follow_redirects=True)
        assert approve_resp.status_code == 200
        assert b"Approved access for John Doe" in approve_resp.data
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        assert "Your access to Clane Musical Society on ShowCal is approved!" in args[0]
        assert "magic-token-xyz-123" in args[1]
        assert kwargs.get("to") == "john@example.com"

    # 4. User logs out of admin and clicks Magic Link
    with client.session_transaction() as sess:
        sess.clear()

    magic_resp = client.get("/society/auth/magic-token-xyz-123", follow_redirects=True)
    assert magic_resp.status_code == 200
    assert b"Welcome, John Doe!" in magic_resp.data
    assert b"Clane Musical Society" in magic_resp.data


def test_admin_direct_magic_link_generation(client, db):
    seed_society(db, id=1, name="Clane Musical Society")
    user_id = seed_user(db)
    login_as(client, user_id)

    with patch("app.notify.send") as mock_notify:
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
        assert b"Generated Magic Login Link" in direct_resp.data
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        assert "Your access to Clane Musical Society on ShowCal is ready!" in args[0]
        assert kwargs.get("to") == "direct@example.com"

    req = db.execute("SELECT * FROM society_access_requests WHERE requester_email = 'direct@example.com'").fetchone()
    assert req is not None
    assert req["status"] == "approved"
    token = req["token"]

    # Log out of admin and use link
    with client.session_transaction() as sess:
        sess.clear()

    login_resp = client.get(f"/society/auth/{token}", follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Welcome, Direct Officer!" in login_resp.data
