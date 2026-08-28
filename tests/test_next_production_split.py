"""F2 (small-items queue, plan item 6): future_shows used to lump every
upcoming production for a society into one flat block headed "Future
announced shows". Split so the soonest upcoming production gets its own mini
card - "Coming this season" if it falls in the current season, "Next
production" otherwise - and everything else after it collapses to a single
"Also announced" line."""
from datetime import date, timedelta

from conftest import seed_society


def _add_show(db, society_id, show, season, opening_date=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, opening_date) "
        "VALUES (?, ?, 'Eastern', ?, 'import', 'approved', ?)",
        (society_id, season, show, opening_date),
    )


def test_soonest_show_in_the_current_season_is_headed_coming_this_season(client, db):
    society_id = seed_society(db)
    opening = (date.today() + timedelta(days=10)).isoformat()
    _add_show(db, society_id, "Chicago", "26/27", opening_date=opening)
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Coming this season" in body
    assert "Next production" not in body
    assert "Chicago" in body


def test_soonest_show_in_a_later_season_is_headed_next_production(client, db):
    society_id = seed_society(db)
    # No dated show at all, so current_season() falls back to today's guess
    # rather than being pulled forward by this TBA placeholder.
    _add_show(db, society_id, "Annie", "27/28", opening_date=None)
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Next production" in body
    assert "Coming this season" not in body
    assert "Annie" in body


def test_further_future_shows_collapse_to_one_also_announced_line(client, db):
    society_id = seed_society(db)
    soon = (date.today() + timedelta(days=5)).isoformat()
    later = (date.today() + timedelta(days=200)).isoformat()
    _add_show(db, society_id, "Chicago", "26/27", opening_date=soon)
    _add_show(db, society_id, "Grease", "26/27", opening_date=later)
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Also announced" in body
    assert "Chicago" in body
    assert "Grease" in body
    # Only one mini-card heading, not one per future show.
    assert body.count("next-production") == 1
