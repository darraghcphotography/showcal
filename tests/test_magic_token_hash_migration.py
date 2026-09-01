"""society_access_requests originally stored the magic-link token in
plaintext, so any copy of the database - and backups sit beside it on the NAS
- handed over working society logins. app/db.py rebuilds the table around a
token_hash column instead. These tests exercise that rebuild directly against
a raw sqlite3 connection standing in for an old-shape database, not through
the Flask app (which always creates fresh databases in the new shape), same
approach as test_adjudicator_assignments_migration.py.

The thing that actually matters here, and the reason this file exists rather
than just a column-shape assertion: a link already sitting in a society's
inbox has to keep working across the migration."""
import sqlite3

from app.auth import hash_magic_token
from app.db import _migrate_magic_tokens_to_hashes


def make_old_shape_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE societies (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    db.execute("CREATE TABLE invite_codes (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
    db.execute(
        """
        CREATE TABLE society_access_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            society_id      INTEGER NOT NULL REFERENCES societies(id) ON DELETE CASCADE,
            requester_name  TEXT NOT NULL,
            requester_email TEXT NOT NULL,
            requester_role  TEXT NOT NULL,
            token           TEXT UNIQUE NOT NULL,
            invite_code_id  INTEGER REFERENCES invite_codes(id) ON DELETE SET NULL,
            status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'used')),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            approved_at     TEXT,
            expires_at      TEXT
        )
        """
    )
    db.execute("INSERT INTO societies (id, name) VALUES (1, 'Clane Musical Society')")
    db.execute("INSERT INTO invite_codes (id, code) VALUES (7, 'brisk-otter-4821')")
    db.execute(
        "INSERT INTO society_access_requests "
        "(id, society_id, requester_name, requester_email, requester_role, token, "
        " invite_code_id, status, created_at, approved_at, expires_at) "
        "VALUES (3, 1, 'John Doe', 'john@example.com', 'PRO', 'live-token-in-an-inbox', "
        "        7, 'approved', '2026-08-30 10:00:00', '2026-08-30 11:00:00', '2026-09-29')"
    )
    db.commit()
    return db


def test_migration_replaces_the_plaintext_column_with_a_hash():
    db = make_old_shape_db()
    _migrate_magic_tokens_to_hashes(db)
    cols = {row[1] for row in db.execute("PRAGMA table_info(society_access_requests)")}
    assert "token" not in cols
    assert {"token_hash", "used_at", "use_count"} <= cols


def test_a_link_already_in_an_inbox_still_resolves_after_migration():
    db = make_old_shape_db()
    _migrate_magic_tokens_to_hashes(db)
    row = db.execute(
        "SELECT * FROM society_access_requests WHERE token_hash = ?",
        (hash_magic_token("live-token-in-an-inbox"),),
    ).fetchone()
    assert row is not None
    assert row["requester_name"] == "John Doe"


def test_migration_preserves_every_other_field():
    db = make_old_shape_db()
    _migrate_magic_tokens_to_hashes(db)
    row = db.execute("SELECT * FROM society_access_requests").fetchone()
    assert row["id"] == 3  # ids are handed out in emailed admin URLs - must not shift
    assert row["society_id"] == 1
    assert row["requester_email"] == "john@example.com"
    assert row["requester_role"] == "PRO"
    assert row["invite_code_id"] == 7
    assert row["status"] == "approved"
    assert row["created_at"] == "2026-08-30 10:00:00"
    assert row["approved_at"] == "2026-08-30 11:00:00"
    assert row["expires_at"] == "2026-09-29"
    assert row["used_at"] is None
    assert row["use_count"] == 0


def test_the_plaintext_is_gone_from_the_file_not_just_the_column():
    """Dropping the column is the point - a rename alone would leave the old
    values readable to anyone who opened the file."""
    db = make_old_shape_db()
    _migrate_magic_tokens_to_hashes(db)
    db.commit()
    dumped = "\n".join(db.iterdump())
    assert "live-token-in-an-inbox" not in dumped
    assert "society_access_requests_old" not in dumped


def test_migration_is_a_noop_once_already_migrated():
    db = make_old_shape_db()
    _migrate_magic_tokens_to_hashes(db)
    _migrate_magic_tokens_to_hashes(db)  # must not raise or re-hash the hash
    row = db.execute("SELECT * FROM society_access_requests").fetchone()
    assert row["token_hash"] == hash_magic_token("live-token-in-an-inbox")
