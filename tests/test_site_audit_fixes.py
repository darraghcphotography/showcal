"""Fixes from the 2026-10-05 fresh-eyes audit of the live site.

Every page that quotes a headline figure now reads it from app/site_facts.py,
so two pages can't contradict each other (the More page said 194 societies
while /stats said 196 and /societies found 143; the awards archive "started"
in 1977, 1910 or 1912 depending on the page). And "Published" with no review
link can no longer reach a public page or be saved from the admin form.
"""
import sqlite3

from conftest import seed_society, seed_user

from app import site_facts
from fix_run_note_venues import apply as fix_venues
from reset_published_without_link import reset as reset_reviews


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _seed_societies(db):
    seed_society(db, id=1, name="Gilbert Soc", section="Gilbert")
    seed_society(db, id=2, name="Sullivan Soc", section="Sullivan")
    seed_society(db, id=3, name="Gone Soc", section="Inactive")
    seed_society(db, id=4, name="Hidden Soc", section="Non-AIMS")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = 4")
    db.commit()


def _add_show(db, show_id, opening, review_status="None", review_url=None, venue=None, society_id=1):
    db.execute(
        "INSERT INTO shows (id, society_id, season, region, show, opening_date, closing_date, "
        "review_status, review_url, venue, moderation_status) "
        "VALUES (?, ?, '26/27', 'Eastern', 'Oliver!', ?, ?, ?, ?, ?, 'approved')",
        (show_id, society_id, opening, opening, review_status, review_url, venue),
    )
    db.commit()


# --- one source for the headline figures ---------------------------------

def test_society_totals_keep_the_record_and_the_listing_apart(db):
    _seed_societies(db)
    assert site_facts.society_total(db) == 4
    assert site_facts.listed_society_count(db) == 2


def test_more_page_quotes_the_live_listed_count_not_a_typed_number(client, db):
    _seed_societies(db)
    body = client.get("/more").get_data(as_text=True)
    assert "All 2 societies, across the 6 regions" in body
    assert "194" not in body


def test_stats_tile_shows_the_record_and_how_many_are_listed(client, db):
    _seed_societies(db)
    body = client.get("/stats").get_data(as_text=True)
    assert "Societies on record" in body
    assert "2 listed today" in body


def test_awards_page_starts_the_archive_at_its_real_first_year(client, db):
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, source) "
        "VALUES (1912, 'Best Overall Show', 'Winner', 'The Mikado', 'manual')"
    )
    db.commit()
    body = client.get("/awards").get_data(as_text=True)
    assert "from the full AIMS awards archive, 1912" in body
    assert "1977" not in body


def test_decades_page_quotes_the_first_award_year_and_first_dated_season(client, db):
    seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, source) "
        "VALUES (1912, 'Best Overall Show', 'Winner', 'The Mikado', 'manual')"
    )
    _add_show(db, 10, "2006-03-22")
    body = client.get("/stats/trends").get_data(as_text=True)
    assert "only starts in 05/06" in body
    assert "goes back to 1912," in body


def test_first_venue_season_reads_across_the_century(db):
    seed_society(db)
    db.execute("INSERT INTO venues (id, name, slug, name_key) VALUES (1, 'Hall', 'hall', 'hall')")
    for show_id, season in ((20, "09/10"), (21, "99/00")):
        db.execute(
            "INSERT INTO shows (id, society_id, season, region, show, venue_id, moderation_status) "
            "VALUES (?, 1, ?, 'Eastern', 'Annie', 1, 'approved')",
            (show_id, season),
        )
    db.commit()
    assert site_facts.first_venue_season(db) == "99/00"


# --- "Published" with no review link ------------------------------------

def _main(body):
    return body.split("<main", 1)[1]


def test_upcoming_show_published_without_a_link_has_no_review_line(client, db):
    seed_society(db)
    _add_show(db, 30, "2099-04-16", review_status="Published")
    body = _main(client.get("/shows/30").get_data(as_text=True))
    assert "Published" not in body
    assert "<dt>Review</dt>" not in body


def test_past_show_published_without_a_link_reads_as_no_review(client, db):
    seed_society(db)
    _add_show(db, 31, "2020-04-16", review_status="Published")
    body = _main(client.get("/shows/31").get_data(as_text=True))
    assert "<dt>Review</dt>" in body
    assert "Published" not in body


def test_admin_form_refuses_published_without_a_link(client, db):
    login_as(client, seed_user(db, role="admin"))
    seed_society(db)
    _add_show(db, 32, "2099-04-16")
    client.post("/admin/shows/32/edit", data={
        "season": "26/27", "region": "Eastern", "show": "Oliver!", "review_status": "Published",
    })
    row = db.execute("SELECT review_status FROM shows WHERE id = 32").fetchone()
    assert row["review_status"] == "None"


def test_new_show_form_starts_on_none_not_published(client, db):
    login_as(client, seed_user(db, role="admin"))
    seed_society(db)
    body = client.get("/admin/societies/1/shows/new").get_data(as_text=True)
    assert '<option value="None" selected>' in body
    assert '<option value="Published" selected>' not in body


# --- the two backfill scripts --------------------------------------------

def _script_db(tmp_path):
    db = sqlite3.connect(tmp_path / "s.db")
    db.row_factory = sqlite3.Row
    db.executescript(
        "CREATE TABLE societies (id INTEGER PRIMARY KEY, name TEXT);"
        "CREATE TABLE shows (id INTEGER PRIMARY KEY, society_id INTEGER, show TEXT, season TEXT,"
        " opening_date TEXT, closing_date TEXT, review_status TEXT, review_url TEXT, venue TEXT,"
        " updated_at TEXT);"
        "INSERT INTO societies VALUES (1, 'Mallow Musical Society');"
    )
    return db


def test_reset_only_touches_listed_shows_still_published_without_a_link(tmp_path):
    db = _script_db(tmp_path)
    db.executescript(
        "INSERT INTO shows (id, society_id, show, review_status, review_url) VALUES"
        " (3094, 1, 'All Shook Up', 'Published', NULL),"
        " (3096, 1, 'Dear Evan Hansen', 'Published', 'https://aims.ie/r'),"
        " (5000, 1, 'Unlisted', 'Published', NULL);"
    )
    changed = reset_reviews(db)
    assert [r["id"] for r in changed] == [3094]
    status = dict(db.execute("SELECT id, review_status FROM shows").fetchall())
    assert status == {3094: "None", 3096: "Published", 5000: "Published"}
    assert reset_reviews(db) == []


def test_venue_fix_only_rewrites_a_venue_that_still_holds_the_note(tmp_path):
    db = _script_db(tmp_path)
    db.executescript(
        "CREATE TABLE venues (id INTEGER PRIMARY KEY, name TEXT);"
        "INSERT INTO shows (id, society_id, show, venue) VALUES"
        " (385, 1, 'Newsies', 'Cork run'),"
        " (398, 1, 'Sweet Charity', 'Already fixed by hand');"
    )
    changed = fix_venues(db)
    assert [c[0] for c in changed] == [385]
    venues = dict(db.execute("SELECT id, venue FROM shows").fetchall())
    assert venues == {385: "The Everyman, Cork", 398: "Already fixed by hand"}
