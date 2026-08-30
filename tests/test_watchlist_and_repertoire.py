import json
from conftest import seed_society


def seed_show(db, **kw):
    fields = {
        "society_id": 1, "season": "25/26", "show": "Test Show", "region": "Eastern",
        "section": "Gilbert", "moderation_status": "approved", "source": "import",
    }
    fields.update(kw)
    cols = ", ".join(fields)
    db.execute(
        f"INSERT INTO shows ({cols}) VALUES ({', '.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    db.commit()


def test_manifest_branding_and_theme_color(client):
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    data = json.loads(resp.get_data(as_text=True))
    assert data["name"] == "ShowCal — Irish Musical Society Tracker"
    assert data["short_name"] == "ShowCal"
    assert data["theme_color"] == "#d4af37"
    assert data["background_color"] == "#0b0f14"


def test_watchlist_page_renders_cleanly(client):
    resp = client.get("/watchlist")
    assert resp.status_code == 200
    assert b"My Season Watchlist" in resp.data
    assert b"Export to Calendar" in resp.data
    assert b"Your watchlist is empty" in resp.data


def test_titles_repertoire_displays_creative_credits_and_songs(client, db):
    seed_society(db, id=1, name="Clane Musical Society")
    seed_show(db, society_id=1, show="Sister Act", season="26/27", moderation_status="approved")

    db.execute("""
        INSERT INTO show_info (show, composer, lyricist, licensing_house, key_songs)
        VALUES ('Sister Act', 'Alan Menken', 'Glenn Slater', 'MTI Europe', 'Fabulous Baby!, Raise Your Voice')
        ON CONFLICT(show) DO UPDATE SET
            composer = excluded.composer,
            lyricist = excluded.lyricist,
            licensing_house = excluded.licensing_house,
            key_songs = excluded.key_songs
    """)
    db.commit()

    resp = client.get("/titles")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Alan Menken" in body
    assert "Glenn Slater" in body
    assert "MTI Europe" in body
    assert "Fabulous Baby!" in body


def test_title_detail_renders_no_date_on_record_for_past_seasons(client, db):
    seed_society(db, id=1, name="Clane Musical Society")
    seed_show(db, society_id=1, show="Sister Act", season="26/27", opening_date=None)  # Current/future -> TBA
    seed_show(db, society_id=1, show="Sister Act", season="22/23", opening_date=None)  # Historical -> No date on record

    resp = client.get("/titles/Sister%20Act")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "No date on record" in body
    assert "TBA" in body


def test_title_detail_orders_past_shows_most_recent_first(client, db):
    seed_society(db, id=1, name="Society A")
    seed_society(db, id=2, name="Society B")
    seed_society(db, id=3, name="Society C")

    # Three shows in same past season with different dates
    seed_show(db, society_id=1, show="All Shook Up", season="23/24", opening_date="2023-10-18", closing_date="2023-10-22")
    seed_show(db, society_id=2, show="All Shook Up", season="23/24", opening_date="2023-11-27", closing_date="2023-12-02")
    seed_show(db, society_id=3, show="All Shook Up", season="23/24", opening_date="2023-11-07", closing_date="2023-11-11")

    resp = client.get("/titles/All%20Shook%20Up")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Must appear in reverse chronological order: Society B (27 Nov) before Society C (7 Nov) before Society A (18 Oct)
    idx_soc_b = body.index("Society B")
    idx_soc_c = body.index("Society C")
    idx_soc_a = body.index("Society A")
    assert idx_soc_b < idx_soc_c < idx_soc_a

