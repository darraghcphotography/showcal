"""shows.status ('Cancelled'/NULL) was removed entirely - the field was
unreliable and import_csv.py used to upsert it unconditionally on every
import, with no protection against resurrecting a wrong flag (see ROADMAP,
2026-08-24). app.db._migrate_drop_shows_status() is what removes the column
from a database that still has it from before this change; this checks that
migration directly against an old-shaped database, since no other test in
this repo builds one deliberately out of date."""
import sqlite3
from pathlib import Path

from app.db import _migrate_drop_shows_status

ROOT = Path(__file__).resolve().parent.parent


def _table_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_migration_drops_status_from_an_old_shaped_database(tmp_path):
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    # schema.sql no longer creates `status` at all - add it back by hand to
    # simulate a database that predates this change.
    conn.execute("ALTER TABLE shows ADD COLUMN status TEXT CHECK (status IN ('Cancelled') OR status IS NULL)")
    assert "status" in _table_columns(conn, "shows")

    _migrate_drop_shows_status(conn)
    assert "status" not in _table_columns(conn, "shows")

    # Idempotent: a database that's already been migrated (including a
    # brand-new one, where schema.sql never created the column) is a no-op.
    _migrate_drop_shows_status(conn)
    assert "status" not in _table_columns(conn, "shows")
