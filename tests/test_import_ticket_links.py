"""Tests for scripts/backfills/import_ticket_links.py.

Verifies that the importer strictly enforces page proof evidence (title, society, dates)
against database records, rejects bad schemes/kinds, honors dry-run, and only writes
when explicitly told to apply.
"""
import json
import sqlite3

import pytest

from scripts.backfills.import_ticket_links import run_import, validate_row


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_aims.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE societies (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE shows (
            id INTEGER PRIMARY KEY,
            society_id INTEGER NOT NULL REFERENCES societies(id),
            show TEXT NOT NULL,
            opening_date TEXT,
            closing_date TEXT,
            ticket_url TEXT
        )
        """
    )
    conn.execute("INSERT INTO societies (id, name) VALUES (1, 'Ulster Operatic Company')")
    conn.execute("INSERT INTO societies (id, name) VALUES (2, 'Harolds Cross Tallaght Musical Society')")
    conn.execute(
        "INSERT INTO shows (id, society_id, show, opening_date, closing_date, ticket_url) "
        "VALUES (101, 1, 'The Addams Family', '2026-09-29', '2026-10-03', NULL)"
    )
    conn.execute(
        "INSERT INTO shows (id, society_id, show, opening_date, closing_date, ticket_url) "
        "VALUES (102, 2, 'The Wedding Singer', '2026-11-10', '2026-11-14', NULL)"
    )
    conn.commit()
    conn.close()
    return db_file


def test_validate_row_valid_ticket_link():
    item = {
        "show_id": 101,
        "ticket_url": "https://www.goh.co.uk/whats-on/the-addams-family",
        "ticket_url_kind": "venue",
        "title_shown_on_page": "The Addams Family",
        "society_shown_on_page": "Ulster Operatic Company",
        "dates_shown_on_page": "29 Sep - 3 Oct 2026",
    }
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is True
    assert reason == "valid"
    assert url == "https://www.goh.co.uk/whats-on/the-addams-family"


def test_validate_row_acronym_society_match():
    item = {
        "show_id": 102,
        "ticket_url": "https://www.civictheatre.ie/whats-on/the-wedding-singer-hxt/",
        "ticket_url_kind": "venue",
        "title_shown_on_page": "The Wedding Singer",
        "society_shown_on_page": "HXT Musical Society",
        "dates_shown_on_page": "10 - 14 Nov 2026",
    }
    db_show = {"id": 102, "show": "The Wedding Singer", "society_name": "Harolds Cross Tallaght Musical Society"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is True
    assert reason == "valid"


def test_validate_row_off_sale():
    item = {
        "show_id": 101,
        "ticket_url": None,
        "notes": "not_on_sale_yet",
    }
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is False
    assert reason == "off_sale"
    assert url is None


def test_validate_row_rejects_missing_page_proof():
    item = {
        "show_id": 101,
        "ticket_url": "https://example.com/tickets",
        "ticket_url_kind": "venue",
        "title_shown_on_page": "The Addams Family",
        "society_shown_on_page": "",  # missing!
        "dates_shown_on_page": "29 Sep - 3 Oct 2026",
    }
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is False
    assert "Missing society_shown_on_page proof" in reason


def test_validate_row_rejects_mismatched_title():
    item = {
        "show_id": 101,
        "ticket_url": "https://example.com/tickets",
        "ticket_url_kind": "venue",
        "title_shown_on_page": "Les Miserables",  # wrong title!
        "society_shown_on_page": "Ulster Operatic Company",
        "dates_shown_on_page": "29 Sep - 3 Oct 2026",
    }
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is False
    assert "Title mismatch" in reason


def test_validate_row_rejects_mismatched_society():
    item = {
        "show_id": 101,
        "ticket_url": "https://example.com/tickets",
        "ticket_url_kind": "venue",
        "title_shown_on_page": "The Addams Family",
        "society_shown_on_page": "Cork Operatic Society",  # wrong society!
        "dates_shown_on_page": "29 Sep - 3 Oct 2026",
    }
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is False
    assert "Society mismatch" in reason


def test_validate_row_rejects_invalid_url_and_kind():
    item = {
        "show_id": 101,
        "ticket_url": "javascript:alert(1)",
        "ticket_url_kind": "venue",
        "title_shown_on_page": "The Addams Family",
        "society_shown_on_page": "Ulster Operatic Company",
        "dates_shown_on_page": "29 Sep - 3 Oct 2026",
    }
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is False
    assert "Invalid URL scheme" in reason

    item["ticket_url"] = "https://example.com"
    item["ticket_url_kind"] = "unsupported_kind"
    valid, reason, url = validate_row(item, db_show)
    assert valid is False
    assert "Invalid ticket_url_kind" in reason


def test_run_import_dry_run_does_not_commit(test_db, tmp_path):
    worklist_file = tmp_path / "worklist.json"
    data = [
        {
            "show_id": 101,
            "ticket_url": "https://www.goh.co.uk/whats-on/the-addams-family",
            "ticket_url_kind": "venue",
            "title_shown_on_page": "The Addams Family",
            "society_shown_on_page": "Ulster Operatic Company",
            "dates_shown_on_page": "29 Sep - 3 Oct 2026",
        }
    ]
    worklist_file.write_text(json.dumps(data), encoding="utf-8")

    res = run_import(test_db, worklist_file, dry_run=True)
    assert res["valid"] == 1
    assert res["updated"] == 1

    conn = sqlite3.connect(test_db)
    row = conn.execute("SELECT ticket_url FROM shows WHERE id = 101").fetchone()
    conn.close()
    assert row[0] is None, "Dry run must not modify the database"


def test_run_import_apply_updates_database(test_db, tmp_path):
    worklist_file = tmp_path / "worklist.json"
    data = [
        {
            "show_id": 101,
            "ticket_url": "https://www.goh.co.uk/whats-on/the-addams-family",
            "ticket_url_kind": "venue",
            "title_shown_on_page": "The Addams Family",
            "society_shown_on_page": "Ulster Operatic Company",
            "dates_shown_on_page": "29 Sep - 3 Oct 2026",
        }
    ]
    worklist_file.write_text(json.dumps(data), encoding="utf-8")

    res = run_import(test_db, worklist_file, dry_run=False)
    assert res["valid"] == 1
    assert res["updated"] == 1

    conn = sqlite3.connect(test_db)
    row = conn.execute("SELECT ticket_url FROM shows WHERE id = 101").fetchone()
    conn.close()
    assert row[0] == "https://www.goh.co.uk/whats-on/the-addams-family"

    # Second run should report already_current
    res2 = run_import(test_db, worklist_file, dry_run=False)
    assert res2["updated"] == 0
    assert res2["already_current"] == 1
