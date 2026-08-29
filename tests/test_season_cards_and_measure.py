"""Two fixes from the 2026-08-29 site audit, both correcting things the
homepage/container redesign earlier that day had introduced.

1. /season and the homepage list the same upcoming productions. The homepage
   became poster-led cards; /season stayed a bare table, so following "see the
   full season" took you from a wall of artwork to a spreadsheet of the
   identical shows. The card is now a shared partial (_upcoming_card.html) so
   the two cannot drift apart again. Past productions stay a table - that is a
   historical record to scan, not a set of shows to go and see.

2. Widening the container from 900px to 1240px helped dense pages (the awards
   archive's seven columns, the society history) and stranded sparse ones:
   /adjudicators is three narrow columns that ended around 460px of a 1240px
   row, and /about became prose at roughly 140 characters a line. Those opt
   into .container.narrow.
"""
from datetime import date, timedelta

from conftest import seed_society


def _add_show(db, society_id, show, days_ahead, season="26/27", **cols):
    opening = (date.today() + timedelta(days=days_ahead)).isoformat()
    fields = {
        "society_id": society_id, "season": season, "region": "Eastern", "show": show,
        "source": "import", "moderation_status": "approved", "opening_date": opening,
        "closing_date": opening,
    }
    fields.update(cols)
    keys = ", ".join(fields)
    marks = ", ".join("?" * len(fields))
    db.execute(f"INSERT INTO shows ({keys}) VALUES ({marks})", tuple(fields.values()))


# ------------------------------------------------------------ season cards

def test_upcoming_productions_render_as_poster_cards(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "Come From Away", days_ahead=30, poster_filename="cfa.webp")
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "whatson-list" in body
    assert "cfa.webp" in body


def test_the_homepage_and_season_use_the_same_card(client, db):
    """They render the same shows. The point of the shared partial is that
    they cannot diverge again."""
    society_id = seed_society(db)
    _add_show(db, society_id, "Come From Away", days_ahead=30, poster_filename="cfa.webp")
    db.commit()

    home = client.get("/").get_data(as_text=True)
    season = client.get("/season?season=26/27").get_data(as_text=True)
    for marker in ("whatson-item", "whatson-poster", "whatson-title"):
        assert marker in home, marker
        assert marker in season, marker


def test_past_productions_stay_a_table(client, db):
    """Deliberately not cards - a finished run is a record to scan."""
    society_id = seed_society(db)
    _add_show(db, society_id, "Already Ran", days_ahead=-30)
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "Past productions" in body
    assert "<th>Region</th>" in body


def test_an_undated_upcoming_show_still_says_tba(client, db):
    """The homepage's own query only ever passes dated shows, so the card
    assumed a date existed. /season carries announced slots with no dates."""
    society_id = seed_society(db)
    _add_show(db, society_id, "Dateless Slot", days_ahead=30)
    db.execute("UPDATE shows SET opening_date = NULL, closing_date = NULL WHERE show = 'Dateless Slot'")
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "Dateless Slot" in body
    assert "TBA" in body


def test_a_review_on_an_upcoming_show_survives_the_card(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "Mid Run", days_ahead=1,
              review_status="Published", review_url="https://example.com/r")
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "Read review" in body


def test_a_plain_upcoming_show_says_nothing_about_a_review(client, db):
    """"Not yet" is not information - the old table hid the whole column in
    this case, and the card shows no line at all."""
    society_id = seed_society(db)
    _add_show(db, society_id, "Just Announced", days_ahead=30, review_status="None")
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "Read review" not in body
    assert "Not adjudicated" not in body


# ------------------------------------------------------- reading measure

def test_prose_and_sparse_pages_use_the_narrow_container(client, db):
    for path in ("/about", "/faq", "/adjudicators"):
        body = client.get(path).get_data(as_text=True)
        assert 'class="container narrow"' in body, path


def test_dense_pages_keep_the_full_width(client, db):
    """The wide container is for the pages that earned it."""
    for path in ("/titles", "/awards", "/season"):
        body = client.get(path).get_data(as_text=True)
        assert 'class="container narrow"' not in body, path
        assert 'class="container"' in body, path
