import sqlite3
from pathlib import Path
from scripts.backfills.backfill_show_credits_and_songs import run_backfill


def test_show_credits_backfill_dry_run_and_live(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE show_info (
            show TEXT PRIMARY KEY,
            synopsis TEXT,
            rights_url TEXT,
            rights_status TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            premiere_year INTEGER,
            premiere_place TEXT,
            composer TEXT,
            lyricist TEXT,
            book_author TEXT,
            licensing_house TEXT,
            key_songs TEXT
        )
    """)
    conn.commit()
    conn.close()

    # 1. Dry run
    count = run_backfill(db_path, dry_run=True)
    assert count > 40

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM show_info").fetchone()[0] == 0
    conn.close()

    # 2. Live run
    count = run_backfill(db_path, dry_run=False)
    assert count > 40

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM show_info WHERE show = 'Sister Act'").fetchone()
    assert row is not None
    assert row["composer"] == "Alan Menken"
    assert row["lyricist"] == "Glenn Slater"
    assert "Fabulous Baby!" in row["key_songs"]
    conn.close()
