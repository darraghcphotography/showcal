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
