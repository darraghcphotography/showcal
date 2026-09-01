"""Tests for Bulk Production Credits Workbench (Society & Admin)."""
import pytest
from conftest import seed_society, seed_user


def test_society_bulk_credits_flow(client, db):
    """Society committee can view and batch update credits for their productions."""
    soc_id = seed_society(db, id=1, name="Credits Society")
    db.execute(
        "INSERT INTO invite_codes (code, society_id, is_active) VALUES ('TESTCREDITS', ?, 1)",
        (soc_id,),
    )
    cur = db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status)
        VALUES (?, '24/25', 'Eastern', 'Credits Test Musical', '2024-11-20', '2024-11-24', 'approved')
        """,
        (soc_id,),
    )
    show_id = cur.lastrowid
    db.commit()

    # Login as society
    client.post("/society/login", data={"code": "TESTCREDITS"}, follow_redirects=True)

    # View bulk credits page
    resp = client.get("/society/bulk-credits")
    assert resp.status_code == 200
    assert b"Batch Fill Credits" in resp.data
    assert b"Credits Test Musical" in resp.data

    # Submit batch update
    post_resp = client.post(
        "/society/bulk-credits",
        data={
            "show_id_0": str(show_id),
            "director_0": "Jane Director",
            "musical_director_0": "John Maestro",
            "choreographer_0": "Mary Dancer",
            "venue_0": "Grand Opera House",
            "opening_date_0": "2024-11-20",
            "closing_date_0": "2024-11-24",
        },
        follow_redirects=True,
    )
    assert post_resp.status_code == 200
    assert b"Successfully saved credits for 1 production" in post_resp.data

    row = db.execute(
        "SELECT director, musical_director, choreographer, venue FROM shows WHERE id = ?",
        (show_id,),
    ).fetchone()
    assert row["director"] == "Jane Director"
    assert row["musical_director"] == "John Maestro"
    assert row["choreographer"] == "Mary Dancer"
    assert row["venue"] == "Grand Opera House"


def test_society_bulk_credits_tamper_isolation(client, db):
    """Society cannot modify credits of a show belonging to another society."""
    soc1_id = seed_society(db, id=1, name="Soc 1")
    soc2_id = seed_society(db, id=2, name="Soc 2")
    db.execute(
        "INSERT INTO invite_codes (code, society_id, is_active) VALUES ('SOC1CODE', ?, 1)",
        (soc1_id,),
    )
    cur = db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, director, moderation_status)
        VALUES (?, '24/25', 'Eastern', 'Soc 2 Show', 'Original Director', 'approved')
        """,
        (soc2_id,),
    )
    soc2_show_id = cur.lastrowid
    db.commit()

    # Login as Soc 1
    client.post("/society/login", data={"code": "SOC1CODE"}, follow_redirects=True)

    # Attempt to post updates for Soc 2's show
    client.post(
        "/society/bulk-credits",
        data={
            "show_id_0": str(soc2_show_id),
            "director_0": "Hacked Director",
        },
        follow_redirects=True,
    )

    row = db.execute("SELECT director FROM shows WHERE id = ?", (soc2_show_id,)).fetchone()
    assert row["director"] == "Original Director"


def test_admin_bulk_credits_flow(client, db):
    """Admin can view and update bulk credits for any selected society."""
    seed_user(db, username="mod", password="password123")
    soc_id = seed_society(db, id=1, name="Admin Credits Soc")
    cur = db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, moderation_status)
        VALUES (?, '23/24', 'Eastern', 'Admin Credits Test Show', 'approved')
        """,
        (soc_id,),
    )
    show_id = cur.lastrowid
    db.commit()

    client.post("/admin/login", data={"username": "mod", "password": "password123"})

    # Access admin workbench
    resp = client.get(f"/admin/shows/bulk-credits?society_id={soc_id}")
    assert resp.status_code == 200
    assert b"Bulk Production Credits Workbench" in resp.data
    assert b"Admin Credits Test Show" in resp.data

    # Save changes as admin
    post_resp = client.post(
        f"/admin/shows/bulk-credits?society_id={soc_id}",
        data={
            "society_id": str(soc_id),
            "show_id_0": str(show_id),
            "director_0": "Admin Director",
            "musical_director_0": "Admin MD",
            "choreographer_0": "Admin Choreo",
            "venue_0": "Civic Hall",
            "opening_date_0": "2024-04-10",
            "closing_date_0": "2024-04-14",
        },
        follow_redirects=True,
    )
    assert post_resp.status_code == 200
    assert b"Successfully saved credits for 1 production" in post_resp.data

    row = db.execute(
        "SELECT director, musical_director, choreographer, venue, opening_date FROM shows WHERE id = ?",
        (show_id,),
    ).fetchone()
    assert row["director"] == "Admin Director"
    assert row["musical_director"] == "Admin MD"
    assert row["choreographer"] == "Admin Choreo"
    assert row["venue"] == "Civic Hall"
    assert row["opening_date"] == "2024-04-10"
