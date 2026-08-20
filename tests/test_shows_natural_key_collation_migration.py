"""ux_shows_natural_key originally had no COLLATE NOCASE on the title part,
so a case-only difference ("Made in Dagenham" vs "Made In Dagenham") wasn't
caught as the same production. app/db.py drops and recreates the index to
add it - these tests exercise that directly against a raw sqlite3 connection
standing in for an old-shape database, not through the Flask app (which
always creates fresh databases in the new shape already)."""
import sqlite3

from app.db import _migrate_shows_natural_key_collation


def make_old_shape_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE shows (id INTEGER PRIMARY KEY, society_id INTEGER, season TEXT, show TEXT)")
    db.execute(
        "CREATE UNIQUE INDEX ux_shows_natural_key ON shows(society_id, season, COALESCE(show, ''))"
    )
    db.execute("INSERT INTO shows (society_id, season, show) VALUES (1, '23/24', 'Oliver!')")
    db.commit()
    return db


def test_migration_adds_nocase_to_index():
    db = make_old_shape_db()
    _migrate_shows_natural_key_collation(db)
    sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'ux_shows_natural_key'"
    ).fetchone()[0]
    assert "NOCASE" in sql


def test_migration_catches_case_only_duplicate_after_running():
    db = make_old_shape_db()
    _migrate_shows_natural_key_collation(db)
    try:
        db.execute("INSERT INTO shows (society_id, season, show) VALUES (1, '23/24', 'OLIVER!')")
        db.commit()
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised, "a case-only variant must now violate the natural key"


def test_migration_preserves_existing_rows():
    db = make_old_shape_db()
    _migrate_shows_natural_key_collation(db)
    row = db.execute("SELECT society_id, season, show FROM shows").fetchone()
    assert row["society_id"] == 1
    assert row["season"] == "23/24"
    assert row["show"] == "Oliver!"


def test_migration_is_a_noop_once_already_migrated():
    db = make_old_shape_db()
    _migrate_shows_natural_key_collation(db)
    _migrate_shows_natural_key_collation(db)  # must not raise
    row = db.execute("SELECT show FROM shows").fetchone()
    assert row["show"] == "Oliver!"


def test_migration_does_nothing_if_index_does_not_exist_yet():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE shows (id INTEGER PRIMARY KEY, society_id INTEGER, season TEXT, show TEXT)")
    _migrate_shows_natural_key_collation(db)  # must not raise
    exists = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = 'ux_shows_natural_key'"
    ).fetchone()[0]
    assert exists == 0
