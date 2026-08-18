"""adjudicator_assignments originally allowed only one adjudicator per
season+tier (PRIMARY KEY (season, section)) - a real mid-season change needs
a second row, which that constraint can't hold. Since SQLite can't ALTER a
PRIMARY KEY in place, app/db.py rebuilds the table instead - these tests
exercise that rebuild directly against a raw sqlite3 connection standing in
for an old-shape database, not through the Flask app (which always creates
fresh databases in the new shape already)."""
import sqlite3

from app.db import _migrate_adjudicator_assignments_table


def make_old_shape_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE adjudicators (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, notes TEXT)")
    db.execute(
        "CREATE TABLE adjudicator_assignments ("
        "season TEXT NOT NULL, section TEXT NOT NULL, adjudicator_id INTEGER NOT NULL, "
        "PRIMARY KEY (season, section))"
    )
    db.execute("INSERT INTO adjudicators (id, name) VALUES (1, 'Jane Smith')")
    db.execute("INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES ('23/24', 'Gilbert', 1)")
    db.commit()
    return db


def test_migration_adds_notes_column():
    db = make_old_shape_db()
    _migrate_adjudicator_assignments_table(db)
    cols = {row[1] for row in db.execute("PRAGMA table_info(adjudicator_assignments)")}
    assert "notes" in cols
    assert "id" in cols


def test_migration_preserves_existing_rows():
    db = make_old_shape_db()
    _migrate_adjudicator_assignments_table(db)
    row = db.execute("SELECT season, section, adjudicator_id, notes FROM adjudicator_assignments").fetchone()
    assert row["season"] == "23/24"
    assert row["section"] == "Gilbert"
    assert row["adjudicator_id"] == 1
    assert row["notes"] is None


def test_migration_allows_second_row_for_same_season_tier():
    db = make_old_shape_db()
    _migrate_adjudicator_assignments_table(db)
    db.execute("INSERT INTO adjudicators (id, name) VALUES (2, 'John Byrne')")
    # Would have violated the old PRIMARY KEY (season, section) - must succeed now.
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id, notes) "
        "VALUES ('23/24', 'Gilbert', 2, 'took over mid-season')"
    )
    db.commit()
    count = db.execute(
        "SELECT COUNT(*) FROM adjudicator_assignments WHERE season = '23/24' AND section = 'Gilbert'"
    ).fetchone()[0]
    assert count == 2


def test_migration_is_a_noop_once_already_migrated():
    db = make_old_shape_db()
    _migrate_adjudicator_assignments_table(db)
    _migrate_adjudicator_assignments_table(db)  # must not raise or wipe data
    row = db.execute("SELECT season FROM adjudicator_assignments").fetchone()
    assert row["season"] == "23/24"
