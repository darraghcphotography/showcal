"""T1 (small-items queue): the homepage's "announced" count used to be built
by .replace()-ing the upcoming-shows query's exact SELECT clause text with
COUNT(*) - matching the source file's own indentation/newlines. Any reformat
of that clause would make the replace a silent no-op, so the full row-shaped
query ran instead and fetchone()[0] quietly returned shows.id as the count.
Now the count wraps the query in COUNT(*) FROM (...) instead of pattern
-matching its text, so it can't go stale that way."""
from datetime import date, timedelta

from conftest import seed_society


def _add_upcoming_show(db, society_id, show, days_ahead):
    opening = (date.today() + timedelta(days=days_ahead)).isoformat()
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, opening_date) "
        "VALUES (?, '26/27', 'Eastern', ?, 'import', 'approved', ?)",
        (society_id, show, opening),
    )


def test_announced_count_matches_real_row_count_beyond_the_page_limit(client, db):
    society_id = seed_society(db)
    # UPCOMING_LIMIT is 12 - seed more than that so the page's own LIMIT
    # would mask a count query that silently returned the wrong number.
    for i in range(15):
        _add_upcoming_show(db, society_id, f"Show {i}", days_ahead=i + 1)
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "15 productions announced" in body
