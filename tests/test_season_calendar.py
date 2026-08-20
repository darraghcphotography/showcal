"""Season calendar: /season's Gilbert/Sullivan agenda view and the homepage
congestion teaser (app/season.py's season_weeks(), info.py's season_summary(),
public.py's _congestion_teaser()). A week is "congested" when 3+ non-cancelled
shows are actually running at some point in it - including one still mid-run
from the week before - not just when 3+ open in it."""
from conftest import seed_society

from app.season import season_weeks


def _show(**overrides):
    row = {
        "id": 1, "show": "Show", "society_id": 1, "society_name": "Soc",
        "section": "Gilbert", "region": "Eastern", "status": None,
        "opening_date": "2026-04-06", "closing_date": "2026-04-11",
    }
    row.update(overrides)
    return row


def test_season_weeks_congestion_uses_overlap_not_just_opening_week():
    """A show still running from the week before counts toward the next
    week's congestion too, not just shows that open in it."""
    rows = [
        _show(id=1, show="A", opening_date="2026-04-06", closing_date="2026-04-13"),  # spans two ISO weeks
        _show(id=2, show="B", section="Sullivan", opening_date="2026-04-14", closing_date="2026-04-18"),
        _show(id=3, show="C", opening_date="2026-04-15", closing_date="2026-04-19"),
    ]
    weeks = season_weeks(rows)
    week2 = next(w for w in weeks if w["start"].isoformat() == "2026-04-13")
    # B and C open in week 2; A is still running (13-13 Apr) into it - all 3 overlap
    assert week2["congested"] is True
    assert week2["overlap_count"] == 3
    assert week2["open_count"] == 2
    assert week2["carryover"] == 1


def test_season_weeks_cancelled_shows_excluded_from_counts_not_from_lists():
    rows = [
        _show(id=1, show="A"),
        _show(id=2, show="B", section="Sullivan"),
        _show(id=3, show="C", status="Cancelled"),
    ]
    weeks = season_weeks(rows)
    assert len(weeks) == 1
    week = weeks[0]
    assert week["congested"] is False  # only 2 non-cancelled shows overlap
    assert week["overlap_count"] == 2
    assert len(week["gilbert"]) == 2  # A and the cancelled C both listed
    assert len(week["sullivan"]) == 1


def test_season_weeks_ignores_rows_without_opening_date():
    rows = [_show(id=1), _show(id=2, opening_date=None, closing_date=None)]
    weeks = season_weeks(rows)
    assert sum(len(w["gilbert"]) + len(w["sullivan"]) + len(w["other"]) for w in weeks) == 1


def _insert_show(db, society_id, show, opening, closing, section="Gilbert", status=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, opening_date, closing_date, "
        "status, moderation_status) VALUES (?, '26/27', 'Eastern', ?, ?, ?, ?, ?, 'approved')",
        (society_id, section, show, opening, closing, status),
    )


def test_season_page_renders_split_columns_and_congestion_flag(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Gil One", "2026-04-06", "2026-04-10")
    _insert_show(db, society_id, "Gil Two", "2026-04-07", "2026-04-10")
    _insert_show(db, society_id, "Sul One", "2026-04-08", "2026-04-11", section="Sullivan")
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "Season calendar" in body
    assert "Gilbert (2)" in body
    assert "Sullivan (1)" in body
    assert "Congested" in body


def test_season_page_section_filter_recomputes_congestion(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Gil One", "2026-04-06", "2026-04-10")
    _insert_show(db, society_id, "Gil Two", "2026-04-07", "2026-04-10")
    _insert_show(db, society_id, "Sul One", "2026-04-08", "2026-04-11", section="Sullivan")
    _insert_show(db, society_id, "Sul Two", "2026-04-08", "2026-04-11", section="Sullivan")
    db.commit()

    # Unfiltered: 4 shows overlapping one week - congested.
    combined = client.get("/season?season=26/27").get_data(as_text=True)
    assert "week-row congested" in combined

    # Filtered to Gilbert only: 2 shows - no longer congested.
    gilbert_only = client.get("/season?season=26/27&tier=Gilbert").get_data(as_text=True)
    assert "week-row congested" not in gilbert_only
    assert "Sullivan (0)" in gilbert_only


def test_season_page_cancelled_show_shown_but_not_congested(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Gil One", "2026-04-06", "2026-04-10")
    _insert_show(db, society_id, "Gil Two", "2026-04-07", "2026-04-10")
    _insert_show(db, society_id, "Gil Three", "2026-04-08", "2026-04-11", status="Cancelled")
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "Gil Three" in body
    assert "cancelled-tag" in body
    assert "week-row congested" not in body


def test_homepage_congestion_teaser_uses_current_season_when_congested(client, db):
    society_id = seed_society(db)
    _insert_show(db, society_id, "Gil One", "2026-04-06", "2026-04-10")
    _insert_show(db, society_id, "Gil Two", "2026-04-07", "2026-04-10")
    _insert_show(db, society_id, "Sul One", "2026-04-08", "2026-04-11", section="Sullivan")
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "Congested weeks coming up" in body
    assert "Not much confirmed yet" not in body


def test_homepage_congestion_teaser_falls_back_to_prior_season(client, db):
    society_id = seed_society(db)
    # Prior season, genuinely congested.
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '25/26', 'Eastern', 'Gilbert', 'Old One', '2025-04-06', '2025-04-10', 'approved')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '25/26', 'Eastern', 'Gilbert', 'Old Two', '2025-04-07', '2025-04-10', 'approved')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '25/26', 'Eastern', 'Sullivan', 'Old Three', '2025-04-08', '2025-04-11', 'approved')",
        (society_id,),
    )
    # Current season - real, but nowhere near congested.
    _insert_show(db, society_id, "New One", "2026-09-01", "2026-09-05")
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "Not much confirmed yet for 26/27" in body
    assert "25/26 had" in body


def test_homepage_no_teaser_when_no_dated_shows(client, db):
    body = client.get("/").get_data(as_text=True)
    assert "Congested weeks" not in body
