"""Continuation of the 2026-08-19 "Not on record" vs "TBA" fix
(test_list_pagination_and_dates.py) to two pages that were missed the first
time round, caught by the 2026-08-23 UX audit: a society's own "Show
history" table mixes every season it's ever staged, past and current, in
one table - a blank date on a 2013 row isn't "to be announced", the date
was simply never recorded. Same for a venue's "Stage history" table and a
blank show title there. See public.py's society_detail()/venue_detail()."""
from conftest import seed_society


def seed_show(db, **kw):
    fields = {
        "society_id": 1, "season": "25/26", "show": "Test Show", "region": "Eastern",
        "section": "Gilbert", "moderation_status": "approved", "source": "import",
    }
    fields.update(kw)
    cols = ", ".join(fields)
    db.execute(
        f"INSERT INTO shows ({cols}) VALUES ({', '.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    db.commit()
    return db.execute("SELECT id FROM shows ORDER BY id DESC LIMIT 1").fetchone()["id"]


def test_society_history_says_not_recorded_for_a_past_season_with_no_date(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01")  # sets current season
    seed_show(db, season="22/23", show="Old Show", opening_date=None)

    html = client.get("/societies/1").get_data(as_text=True)
    assert "No date on record" in html
    assert ">TBA<" not in html


def test_society_history_still_says_tba_for_the_current_season(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01")
    seed_show(db, season="25/26", show="Undated Show", opening_date=None)

    html = client.get("/societies/1").get_data(as_text=True)
    assert "TBA" in html


def test_society_future_announced_show_still_says_tba(client, db):
    """The "Future announced shows" block is genuinely always upcoming -
    unlike the main history table, this one was never wrong and stays TBA."""
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01")  # sets current season
    seed_show(db, season="26/27", show="Next Year's Show", opening_date=None)

    html = client.get("/societies/1").get_data(as_text=True)
    assert "Next Year&#39;s Show" in html or "Next Year's Show" in html
    assert "TBA" in html


def test_society_a_future_dated_show_in_the_current_season_gets_the_callout(client, db):
    """Fixed 2026-08-25: the "Future announced show" highlight used to be
    season-based (season > current season), so a show dated later in the
    *current* season - the common case, since a season spans autumn to
    summer - never got pulled into the callout and just blended into the
    plain history table below. Now date-based instead."""
    seed_society(db)
    seed_show(db, season="25/26", show="Already Happened", opening_date="2025-09-01")  # sets current season
    seed_show(db, season="25/26", show="Later This Season", opening_date="2099-11-01")

    html = client.get("/societies/1").get_data(as_text=True)
    assert "Coming this season" in html
    assert "Later This Season" in html
    # Confirm it actually landed in the callout, not just somewhere on the page.
    callout = html.split("Coming this season")[1].split("Show history")[0]
    assert "Later This Season" in callout
    assert "Already Happened" not in callout


def test_society_a_past_dated_show_in_a_nominally_future_season_stays_in_history(client, db):
    """The reverse edge case: a data oddity (a dated show whose season label
    is technically ahead of current but whose real date has already passed)
    should follow the real date, not the season label."""
    seed_society(db)
    seed_show(db, season="25/26", show="Sets Current", opening_date="2025-09-01")
    seed_show(db, season="26/27", show="Already Ran", opening_date="2025-10-01")

    html = client.get("/societies/1").get_data(as_text=True)
    for heading in ("Coming this season", "Next production"):
        if heading in html:
            callout = html.split(heading)[1].split("Show history")[0]
            assert "Already Ran" not in callout


def test_venue_stage_history_says_not_recorded_for_a_blank_past_title(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01", venue="Test Theatre")  # sets current season
    seed_show(db, season="22/23", show=None, opening_date="2023-01-01", venue="Test Theatre")
    client.get("/venues")  # trigger venues_build.ensure_current()

    html = client.get("/venues/test-theatre").get_data(as_text=True)
    assert "Not recorded" in html
    assert ">TBA<" not in html
