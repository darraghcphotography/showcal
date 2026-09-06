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
    # opening_date/closing_date are required now: the date leg of the proof is
    # checked against them, so a db_show without them cannot validate.
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company",
               "opening_date": "2026-09-29", "closing_date": "2026-10-03"}
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
    db_show = {"id": 102, "show": "The Wedding Singer",
               "society_name": "Harolds Cross Tallaght Musical Society",
               "opening_date": "2026-11-10", "closing_date": "2026-11-14"}
    valid, reason, url = validate_row(item, db_show)
    assert valid is True
    assert reason == "valid"


def test_validate_row_off_sale():
    item = {
        "show_id": 101,
        "ticket_url": None,
        "notes": "not_on_sale_yet",
    }
    # opening_date/closing_date are required now: the date leg of the proof is
    # checked against them, so a db_show without them cannot validate.
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company",
               "opening_date": "2026-09-29", "closing_date": "2026-10-03"}
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
    # opening_date/closing_date are required now: the date leg of the proof is
    # checked against them, so a db_show without them cannot validate.
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company",
               "opening_date": "2026-09-29", "closing_date": "2026-10-03"}
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
    # opening_date/closing_date are required now: the date leg of the proof is
    # checked against them, so a db_show without them cannot validate.
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company",
               "opening_date": "2026-09-29", "closing_date": "2026-10-03"}
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
    # opening_date/closing_date are required now: the date leg of the proof is
    # checked against them, so a db_show without them cannot validate.
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company",
               "opening_date": "2026-09-29", "closing_date": "2026-10-03"}
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
    # opening_date/closing_date are required now: the date leg of the proof is
    # checked against them, so a db_show without them cannot validate.
    db_show = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company",
               "opening_date": "2026-09-29", "closing_date": "2026-10-03"}
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


# --- The three legs of the proof, tightened 2026-09-07 -----------------------
#
# As first written, the "3-point page proof" was a 2-point proof: the dates were
# required to be non-empty and then never compared, so a page reading
# "14-18 November 1998" validated against a show running in 2026. The name
# matcher also accepted a single shared word, which passes two different
# societies in the same town against each other. Both are exactly the wrong-show
# failure the whole brief exists to prevent, so both are pinned here.

ADDAMS = {"id": 101, "show": "The Addams Family", "society_name": "Ulster Operatic Company",
          "opening_date": "2026-09-29", "closing_date": "2026-10-03"}


def proof(**overrides):
    item = {
        "show_id": 101,
        "ticket_url": "https://example.com/book",
        "ticket_url_kind": "venue",
        "title_shown_on_page": "The Addams Family",
        "society_shown_on_page": "Ulster Operatic Company",
        "dates_shown_on_page": "Tue 29 Sep - Sat 3 Oct 2026",
    }
    item.update(overrides)
    return item


def test_dates_are_actually_compared_not_just_present():
    """The original failure: any non-empty string satisfied the date leg."""
    valid, reason, _ = validate_row(proof(dates_shown_on_page="14-18 November 1998"), ADDAMS)
    assert valid is False
    assert "Date mismatch" in reason


def test_a_page_naming_the_wrong_month_is_rejected():
    valid, reason, _ = validate_row(proof(dates_shown_on_page="Tue 29 Nov - Sat 3 Dec 2026"), ADDAMS)
    assert valid is False
    assert "month mismatch" in reason


def test_a_page_naming_the_wrong_day_is_rejected():
    valid, reason, _ = validate_row(proof(dates_shown_on_page="Tue 12 Sep - Sat 16 Sep 2026"), ADDAMS)
    assert valid is False
    assert "day mismatch" in reason


def test_a_show_with_no_date_on_record_cannot_be_verified():
    """Not "pass by default" - there is nothing to check the page against."""
    dateless = dict(ADDAMS, opening_date=None)
    valid, reason, _ = validate_row(proof(), dateless)
    assert valid is False
    assert "no opening_date on record" in reason


def test_a_page_with_no_readable_date_is_rejected():
    valid, reason, _ = validate_row(proof(dates_shown_on_page="Tickets available now"), ADDAMS)
    assert valid is False
    assert "no recognisable date" in reason


def test_a_page_that_omits_the_year_is_still_accepted():
    """Common on venue listings, and not a mismatch - month and day still pin it."""
    valid, reason, _ = validate_row(proof(dates_shown_on_page="29 Sep - 3 Oct"), ADDAMS)
    assert valid is True, reason


def test_real_world_date_formats_all_validate():
    """Copied verbatim from the returned worklist - the researcher records the
    page's own wording, so the parser has to cope with whatever a venue used."""
    for opening, text in [
        ("2026-10-06", "Tue 6 - Sat 10 Oct 2026"),
        ("2026-10-06", "Nightly, 6th to 10th October - 8pm Saturday 10th - Matinee - 2pm"),
        ("2026-10-14", "14 October - 18 October"),
        ("2026-11-10", "10 - 14 Nov | 7:30pm"),
        ("2026-11-18", "18 November 2026 - 21 November 2026"),
        ("2027-05-04", "Tue 4 May - Sat 8 May 2027"),
    ]:
        show = dict(ADDAMS, opening_date=opening)
        valid, reason, _ = validate_row(
            proof(dates_shown_on_page=text, title_shown_on_page=show["show"]), show)
        assert valid is True, f"{text!r} vs {opening}: {reason}"


def test_a_clock_time_is_not_read_as_a_day():
    """"7:30pm" must not contribute a day 30, or a page for the 30th validates
    against a show on any date whose page mentions a half-past time."""
    show = dict(ADDAMS, opening_date="2026-09-30")
    valid, _, _ = validate_row(proof(dates_shown_on_page="Tue 29 Sep - Sat 3 Oct 2026 | 7:30pm"), show)
    assert valid is False


def test_two_societies_in_one_town_do_not_match_each_other():
    """One shared word used to be enough. Sligo has more than one society."""
    sligo = dict(ADDAMS, society_name="Sligo Pantomime Society")
    valid, reason, _ = validate_row(proof(society_shown_on_page="Sligo Musical Society"), sligo)
    assert valid is False
    assert "Society mismatch" in reason


def test_a_shared_word_does_not_match_two_different_titles():
    beauty = dict(ADDAMS, show="The Beauty Queen of Leenane")
    valid, reason, _ = validate_row(proof(title_shown_on_page="Beauty and the Beast"), beauty)
    assert valid is False
    assert "Title mismatch" in reason


def test_a_shorter_title_is_not_matched_as_a_prefix():
    """"the wiz" is a substring of "the wizard of oz" - whole words only."""
    wiz = dict(ADDAMS, show="The Wiz")
    valid, reason, _ = validate_row(proof(title_shown_on_page="The Wizard of Oz"), wiz)
    assert valid is False
    assert "Title mismatch" in reason


def test_a_town_suffix_on_our_own_name_still_matches():
    """The tightening must not reject the legitimate cases it looks like."""
    cecilian = dict(ADDAMS, society_name="Cecilian Musical Society, Limerick")
    valid, reason, _ = validate_row(proof(society_shown_on_page="Cecilian Musical Society"), cecilian)
    assert valid is True, reason


def test_an_accented_title_matches_its_unaccented_spelling():
    lesmis = dict(ADDAMS, show="Les Misérables")
    valid, reason, _ = validate_row(proof(title_shown_on_page="Les Miserables"), lesmis)
    assert valid is True, reason
