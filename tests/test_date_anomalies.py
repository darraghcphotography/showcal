"""Tests for Date & Season Chronology Anomaly Auditor."""
import pytest
from app.season import season_for_date
from conftest import seed_society, seed_user


def test_season_for_date_boundaries():
    """Verify AIMS season boundaries (Mid-June to Early May)."""
    assert season_for_date("2024-06-20") == "24/25"
    assert season_for_date("2024-08-15") == "24/25"
    assert season_for_date("2024-09-01") == "24/25"
    assert season_for_date("2024-11-20") == "24/25"
    assert season_for_date("2024-12-31") == "24/25"
    assert season_for_date("2025-01-01") == "24/25"
    assert season_for_date("2025-04-30") == "24/25"
    assert season_for_date("2025-05-10") == "24/25"
    assert season_for_date("2025-05-25") == "25/26"
    assert season_for_date("2025-06-20") == "25/26"
    assert season_for_date("") is None
    assert season_for_date("invalid") is None


def test_date_anomalies_audit_and_swap_dates(client, db):
    """Detects inverted dates and swaps them correctly via POST."""
    seed_user(db, username="mod", password="password123")
    soc_id = seed_society(db, id=1, name="Inverted Society")
    cur = db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status)
        VALUES (?, '24/25', 'Eastern', 'Inverted Test Show', '2024-11-25', '2024-11-20', 'approved')
        """,
        (soc_id,),
    )
    show_id = cur.lastrowid
    db.commit()

    client.post("/admin/login", data={"username": "mod", "password": "password123"})
    resp = client.get("/admin/shows/date-anomalies")
    assert resp.status_code == 200
    assert b"Inverted Test Show" in resp.data
    assert b"Inverted Dates" in resp.data

    # Perform swap
    swap_resp = client.post(
        "/admin/shows/date-anomalies",
        data={"action": "swap_dates", "show_id": show_id},
        follow_redirects=True,
    )
    assert swap_resp.status_code == 200
    assert b"Swapped opening and closing dates." in swap_resp.data

    row = db.execute("SELECT opening_date, closing_date FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["opening_date"] == "2024-11-20"
    assert row["closing_date"] == "2024-11-25"


def test_date_anomalies_fix_single_and_batch_seasons(client, db):
    """Detects mismatched seasons and fixes single or all seasons."""
    seed_user(db, username="mod", password="password123")
    soc_id = seed_society(db, id=1, name="Mismatch Society")

    # April 2024 belongs to season 23/24, but recorded as 24/25
    cur1 = db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status)
        VALUES (?, '24/25', 'Eastern', 'Mismatch Show 1', '2024-04-10', '2024-04-15', 'approved')
        """,
        (soc_id,),
    )
    show1_id = cur1.lastrowid
    cur2 = db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status)
        VALUES (?, '22/23', 'Eastern', 'Mismatch Show 2', '2024-11-10', '2024-11-15', 'approved')
        """,
        (soc_id,),
    )
    show2_id = cur2.lastrowid
    db.commit()

    client.post("/admin/login", data={"username": "mod", "password": "password123"})
    resp = client.get("/admin/shows/date-anomalies")
    assert resp.status_code == 200
    assert b"Mismatch Show 1" in resp.data
    assert b"Mismatch Show 2" in resp.data

    # Fix single season
    fix1_resp = client.post(
        "/admin/shows/date-anomalies",
        data={"action": "fix_season", "show_id": show1_id, "target_season": "23/24"},
        follow_redirects=True,
    )
    assert fix1_resp.status_code == 200
    assert b"Updated season to 23/24." in fix1_resp.data

    # Fix all seasons batch
    batch_resp = client.post(
        "/admin/shows/date-anomalies",
        data={"action": "fix_all_seasons"},
        follow_redirects=True,
    )
    assert batch_resp.status_code == 200

    r1 = db.execute("SELECT season FROM shows WHERE id = ?", (show1_id,)).fetchone()
    r2 = db.execute("SELECT season FROM shows WHERE id = ?", (show2_id,)).fetchone()
    assert r1["season"] == "23/24"
    assert r2["season"] == "24/25"
