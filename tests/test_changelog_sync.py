"""app/changelog_sync.py - publishing CHANGELOG.md entries into
changelog_entries automatically on startup, without ever resurrecting one
that was deliberately deleted via /admin/changelog."""
import sqlite3
from pathlib import Path

from app import changelog_sync

ROOT = Path(__file__).resolve().parent.parent


def _fresh_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "changelog_sync.db")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    return conn


def test_parse_entries_splits_on_separator_and_drops_blank_lines():
    text = "Headline one\nDetail\n\n---\n\nHeadline two\n"
    assert changelog_sync.parse_entries(text) == ["Headline one\nDetail", "Headline two"]


def test_parse_entries_handles_single_entry_no_separator():
    assert changelog_sync.parse_entries("Just one line\n") == ["Just one line"]


def test_sync_publishes_new_entries(tmp_path):
    conn = _fresh_db(tmp_path)
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("Headline one\n---\nHeadline two\n", encoding="utf-8")

    published = changelog_sync.sync(conn, changelog_file)
    assert published == 2

    entries = [r[0] for r in conn.execute("SELECT entry FROM changelog_entries ORDER BY id").fetchall()]
    assert entries == ["Headline one", "Headline two"]
    conn.close()


def test_sync_is_idempotent(tmp_path):
    conn = _fresh_db(tmp_path)
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("Headline one\n", encoding="utf-8")

    changelog_sync.sync(conn, changelog_file)
    published_again = changelog_sync.sync(conn, changelog_file)

    assert published_again == 0
    assert conn.execute("SELECT COUNT(*) FROM changelog_entries").fetchone()[0] == 1
    conn.close()


def test_sync_never_resurrects_a_deleted_entry(tmp_path):
    conn = _fresh_db(tmp_path)
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("Headline one\n", encoding="utf-8")

    changelog_sync.sync(conn, changelog_file)
    # Simulate deleting it via /admin/changelog (see admin.delete_changelog_entry).
    conn.execute("DELETE FROM changelog_entries WHERE entry = 'Headline one'")
    conn.commit()

    published = changelog_sync.sync(conn, changelog_file)
    assert published == 0
    assert conn.execute("SELECT COUNT(*) FROM changelog_entries").fetchone()[0] == 0
    conn.close()


def test_sync_adds_new_entries_appended_to_an_already_synced_file(tmp_path):
    conn = _fresh_db(tmp_path)
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("Headline one\n", encoding="utf-8")
    changelog_sync.sync(conn, changelog_file)

    changelog_file.write_text("Headline one\n---\nHeadline two\n", encoding="utf-8")
    published = changelog_sync.sync(conn, changelog_file)

    assert published == 1
    entries = {r[0] for r in conn.execute("SELECT entry FROM changelog_entries").fetchall()}
    assert entries == {"Headline one", "Headline two"}
    conn.close()


def test_sync_missing_file_is_a_noop(tmp_path):
    conn = _fresh_db(tmp_path)
    assert changelog_sync.sync(conn, tmp_path / "does_not_exist.md") == 0
    conn.close()
