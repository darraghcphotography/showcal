import sqlite3
from pathlib import Path
from scripts.backfills.backfill_upcoming_venue_coordinates import run_backfill, VENUE_COORDINATES


def test_venue_coordinates_dry_run_and_live(tmp_path):
    db_path = tmp_path / "test_aims.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE venues (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            town TEXT,
            county TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    conn.execute("INSERT INTO venues (id, name, slug) VALUES (141, 'The Civic Theatre', 'the-civic-theatre-tallaght')")
    conn.commit()
    conn.close()

    # Test Dry Run
    count = run_backfill(db_path, dry_run=True)
    assert count >= 1
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT latitude FROM venues WHERE id = 141").fetchone()
    assert row["latitude"] is None
    conn.close()

    # Test Live Run
    count = run_backfill(db_path, dry_run=False)
    assert count >= 1
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT latitude, longitude, town, county FROM venues WHERE id = 141").fetchone()
    assert row["latitude"] == 53.2872
    assert row["longitude"] == -6.3705
    assert row["town"] == "Tallaght"
    assert row["county"] == "Dublin"
    conn.close()
