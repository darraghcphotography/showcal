"""build_ticket_worklist.py picks exactly the shows that need a ticket link.

The worklist is handed to an outside researcher, so a wrong query here is
expensive in a way a wrong query on a page is not: it sends someone off to
research shows that are over, or quietly omits the ones the site most needs.
"""
import json

from build_ticket_worklist import build
from conftest import seed_society


def seed_show(db, title, opening, closing, ticket_url=None, status="approved"):
    db.execute(
        """
        INSERT INTO shows (society_id, season, region, show, venue,
                           opening_date, closing_date, ticket_url, moderation_status)
        VALUES (1, '26/27', 'Eastern', ?, 'The Venue', ?, ?, ?, ?)
        """,
        (title, opening, closing, ticket_url, status),
    )
    db.commit()


def run(app, tmp_path):
    out = tmp_path / "worklist.json"
    build(app.config["DATABASE"], out)
    return json.loads(out.read_text(encoding="utf-8"))


def titles(rows):
    return {r["known_title"] for r in rows}


def test_only_upcoming_shows_without_a_ticket_link(app, db, tmp_path):
    seed_society(db, id=1)
    seed_show(db, "Wanted", "2099-01-01", "2099-01-05")
    seed_show(db, "Already has tickets", "2099-02-01", "2099-02-05",
              ticket_url="https://example.com/book")
    seed_show(db, "Long over", "2020-01-01", "2020-01-05")
    seed_show(db, "Still pending", "2099-03-01", "2099-03-05", status="pending")

    assert titles(run(app, tmp_path)) == {"Wanted"}


def test_a_show_running_right_now_is_still_wanted(app, db, tmp_path):
    """It opened yesterday and closes tomorrow - someone can still buy a ticket,
    so filtering on opening_date alone would wrongly drop it."""
    seed_society(db, id=1)
    seed_show(db, "Mid-run", "2000-01-01", "2099-01-01")

    assert titles(run(app, tmp_path)) == {"Mid-run"}


def test_a_blank_ticket_url_counts_as_missing(app, db, tmp_path):
    """Whitespace is what an emptied form field actually leaves behind."""
    seed_society(db, id=1)
    seed_show(db, "Blanked", "2099-01-01", "2099-01-05", ticket_url="   ")

    assert titles(run(app, tmp_path)) == {"Blanked"}


def test_rows_are_ordered_by_opening_date(app, db, tmp_path):
    """The brief tells the researcher to work top-down and stop when they run
    out of budget, which is only useful advice if the nearest shows are first."""
    seed_society(db, id=1)
    seed_show(db, "Later", "2099-06-01", "2099-06-05")
    seed_show(db, "Sooner", "2099-01-01", "2099-01-05")

    assert [r["known_title"] for r in run(app, tmp_path)] == ["Sooner", "Later"]


def test_the_horizon_can_be_narrowed(app, db, tmp_path):
    seed_society(db, id=1)
    seed_show(db, "Next week", "2099-01-01", "2099-01-05")
    db.execute("UPDATE shows SET opening_date = date('now', '+7 days'), "
               "closing_date = date('now', '+9 days') WHERE show = 'Next week'")
    seed_show(db, "Next year", "2099-01-01", "2099-01-05")
    db.commit()

    out = tmp_path / "w.json"
    build(app.config["DATABASE"], out, horizon_days=30)
    assert titles(json.loads(out.read_text(encoding="utf-8"))) == {"Next week"}


def test_every_field_the_researcher_fills_starts_blank(app, db, tmp_path):
    """A pre-filled field is one they might leave as-is and we might read as an
    answer."""
    seed_society(db, id=1)
    seed_show(db, "Wanted", "2099-01-01", "2099-01-05")

    row = run(app, tmp_path)[0]
    for field in ("ticket_url", "ticket_url_kind", "dates_shown_on_page",
                  "society_shown_on_page", "title_shown_on_page", "source_url", "notes"):
        assert row[field] is None, field
    # And the context we supply for matching is actually there.
    assert row["known_society"] == "Test Society"
    assert row["show_id"]
