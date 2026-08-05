"""add_changelog.py - a CLI shortcut for publishing a changelog entry
without needing to log in and paste text into /admin/changelog."""
import sqlite3
from pathlib import Path

import add_changelog

ROOT = Path(__file__).resolve().parent.parent


def _fresh_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "changelog.db")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    return conn


def test_publish_joins_lines_into_one_entry(tmp_path):
    conn = _fresh_db(tmp_path)
    entry = add_changelog.publish(conn, ["Headline", "Detail one", "Detail two"])
    assert entry == "Headline\nDetail one\nDetail two"

    row = conn.execute("SELECT entry FROM changelog_entries").fetchone()
    assert row[0] == entry
    conn.close()


def test_publish_skips_blank_lines(tmp_path):
    conn = _fresh_db(tmp_path)
    entry = add_changelog.publish(conn, ["Headline", "  ", "", "Detail"])
    assert entry == "Headline\nDetail"
    conn.close()


def test_publish_rejects_all_blank(tmp_path):
    conn = _fresh_db(tmp_path)
    try:
        add_changelog.publish(conn, ["  ", ""])
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert conn.execute("SELECT COUNT(*) FROM changelog_entries").fetchone()[0] == 0
    conn.close()
