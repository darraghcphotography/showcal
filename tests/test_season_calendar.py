"""Season calendar: /season's Gilbert/Sullivan agenda view and the homepage
congestion teaser (app/season.py's season_weeks(), info.py's season_summary(),
public.py's _congestion_teaser()).

A section (Gilbert or Sullivan) is flagged "congested" for a week where 4+ of
its own shows are actually *running* at some point in it - including one
still mid-run from the week before, not just shows opening in it - judged
separately per section, since an adjudicator only needs to reach everything
in their own (2 Gilbert + 2 Sullivan in the same week is 4 shows total but a
real clash for neither).

info.py's season_summary() also drops already-finished weeks for the current/
a future season (a past season being browsed as history keeps its full
calendar) - integration tests below use dates offset from today so they stay
valid regardless of when they're run.
"""
from datetime import date, timedelta

from conftest import seed_society

from app.season import season_weeks


def _show(**overrides):
    row = {
        "id": 1, "show": "Show", "society_id": 1, "society_name": "Soc",
        "section": "Gilbert", "region": "Eastern",
        "opening_date": "2026-04-06", "closing_date": "2026-04-11",
    }
    row.update(overrides)
    return row


def test_season_weeks_congestion_uses_overlap_not_just_opening_week():
    """A show still running from the week before counts toward the next
    week's congestion too, not just shows that open in it."""
    rows = [
        _show(id=1, show="A", opening_date="2026-04-06", closing_date="2026-04-13"),  # spans two ISO weeks
        _show(id=2, show="B", opening_date="2026-04-14", closing_date="2026-04-18"),
        _show(id=3, show="C", opening_date="2026-04-15", closing_date="2026-04-19"),
        _show(id=4, show="D", opening_date="2026-04-15", closing_date="2026-04-19"),
    ]
    weeks = season_weeks(rows)
    week2 = next(w for w in weeks if w["start"].isoformat() == "2026-04-13")
    # B, C, D open in week 2; A is still running (13-13 Apr) into it - all 4 overlap
    assert week2["gilbert_congested"] is True
    assert week2["gilbert_overlap"] == 4
    assert week2["gilbert_open"] == 3
    assert week2["congestion_notes"] == [{"label": "Gilbert", "overlap": 4, "carryover": 1}]


def test_season_weeks_two_plus_two_across_sections_is_not_congested():
    """The exact case flagged as a false positive: 2 Gilbert + 2 Sullivan in
    one week is 4 shows total, but neither section alone hits the threshold,
    and an adjudicator only needs to cover their own section."""
    rows = [
        _show(id=1, show="A", section="Gilbert"),
        _show(id=2, show="B", section="Gilbert"),
        _show(id=3, show="C", section="Sullivan"),
        _show(id=4, show="D", section="Sullivan"),
    ]
    weeks = season_weeks(rows)
    assert len(weeks) == 1
    week = weeks[0]
    assert week["gilbert_congested"] is False
    assert week["sullivan_congested"] is False
    assert week["congested"] is False
    assert week["congestion_notes"] == []


def test_season_weeks_ignores_rows_without_opening_date():
    rows = [_show(id=1), _show(id=2, opening_date=None, closing_date=None)]
    weeks = season_weeks(rows)
    assert sum(len(w["gilbert"]) + len(w["sullivan"]) + len(w["other"]) for w in weeks) == 1


def _monday_weeks_ahead(n):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday + timedelta(weeks=n)


def _week_run(weeks_ahead, day_offset=0, length=4):
    """An opening/closing ISO date pair guaranteed to land `weeks_ahead` ISO
    weeks from now (well clear of today, so the "hide already-finished
    weeks" filter never eats it), offset a few days apart so several shows
    in the same test land in the same ISO week without being on identical
    dates."""
    start = _monday_weeks_ahead(weeks_ahead) + timedelta(days=day_offset)
    end = start + timedelta(days=length)
    return start.isoformat(), end.isoformat()


def _insert_show(db, society_id, show, opening, closing, section="Gilbert", region="Eastern"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, opening_date, closing_date, "
        "moderation_status) VALUES (?, '26/27', ?, ?, ?, ?, ?, 'approved')",
        (society_id, region, section, show, opening, closing),
    )


def test_calendar_page_renders_split_columns_and_congestion_flag(client, db):
    society_id = seed_society(db)
    o1, c1 = _week_run(4, day_offset=0)
    o2, c2 = _week_run(4, day_offset=1)
    o3, c3 = _week_run(4, day_offset=2)
    o4, c4 = _week_run(4, day_offset=2)
    o5, c5 = _week_run(4, day_offset=3)
    _insert_show(db, society_id, "Gil One", o1, c1)
    _insert_show(db, society_id, "Gil Two", o2, c2)
    _insert_show(db, society_id, "Gil Three", o3, c3)
    _insert_show(db, society_id, "Gil Four", o4, c4)
    _insert_show(db, society_id, "Sul One", o5, c5, section="Sullivan")
    db.commit()

    body = client.get("/season/calendar?season=26/27").get_data(as_text=True)
    assert "season calendar" in body
    assert "Gilbert (4)" in body
    assert "Sullivan (1)" in body
    assert "week-row congested" in body
    assert "Busy for Gilbert" in body
    assert "Busy for Sullivan" not in body


def test_calendar_page_hides_the_other_column_when_filtered_to_one_section(client, db):
    society_id = seed_society(db)
    o1, c1 = _week_run(4, day_offset=0)
    o2, c2 = _week_run(4, day_offset=1)
    _insert_show(db, society_id, "Gil One", o1, c1)
    _insert_show(db, society_id, "Sul One", o2, c2, section="Sullivan")
    db.commit()

    unfiltered = client.get("/season/calendar?season=26/27").get_data(as_text=True)
    assert "Gilbert (1)" in unfiltered
    assert "Sullivan (1)" in unfiltered

    gilbert_only = client.get("/season/calendar?season=26/27&tier=Gilbert").get_data(as_text=True)
    assert "Gilbert (1)" in gilbert_only
    assert "Sullivan (0)" not in gilbert_only
    assert "Nothing opening this week" not in gilbert_only


def test_calendar_page_section_filter_recomputes_congestion(client, db):
    society_id = seed_society(db)
    o1, c1 = _week_run(5, day_offset=0)
    o2, c2 = _week_run(5, day_offset=1)
    o3, c3 = _week_run(5, day_offset=2)
    o4, c4 = _week_run(5, day_offset=3)
    _insert_show(db, society_id, "East One", o1, c1, region="Eastern")
    _insert_show(db, society_id, "East Two", o2, c2, region="Eastern")
    _insert_show(db, society_id, "West One", o3, c3, region="Western")
    _insert_show(db, society_id, "West Two", o4, c4, region="Western")
    db.commit()

    # Unfiltered: 4 Gilbert shows overlapping one week - congested.
    combined = client.get("/season/calendar?season=26/27").get_data(as_text=True)
    assert "week-row congested" in combined

    # Filtered to Eastern only: 2 shows - no longer congested.
    eastern_only = client.get("/season/calendar?season=26/27&region=Eastern").get_data(as_text=True)
    assert "week-row congested" not in eastern_only
    assert "Gilbert (2)" in eastern_only


def test_calendar_page_hides_already_finished_weeks_for_current_season(client, db):
    society_id = seed_society(db)
    past_opening = (date.today() - timedelta(days=60)).isoformat()
    past_closing = (date.today() - timedelta(days=55)).isoformat()
    future_opening, future_closing = _week_run(3)
    _insert_show(db, society_id, "Old Show", past_opening, past_closing)
    _insert_show(db, society_id, "New Show", future_opening, future_closing)
    db.commit()

    body = client.get("/season/calendar?season=26/27").get_data(as_text=True)
    assert "New Show" in body
    assert "Old Show" not in body


def test_season_page_no_longer_shows_the_calendar(client, db):
    """/season kept the productions list when the calendar moved to its own
    page (see ROADMAP, 2026-08-24) - guards against the split regressing."""
    society_id = seed_society(db)
    o1, c1 = _week_run(4, day_offset=0)
    _insert_show(db, society_id, "Gil One", o1, c1)
    db.commit()

    body = client.get("/season?season=26/27").get_data(as_text=True)
    assert "season-calendar" not in body
    assert "week-split" not in body
    assert 'href="/season/calendar' in body


def test_homepage_never_shows_congestion_teaser(client, db):
    """Darragh's call: the congestion teaser was cut from the homepage -
    /season is the only place the calendar lives now, however congested a
    season's weeks get."""
    society_id = seed_society(db)
    o1, c1 = _week_run(4, day_offset=0)
    o2, c2 = _week_run(4, day_offset=1)
    o3, c3 = _week_run(4, day_offset=2)
    o4, c4 = _week_run(4, day_offset=3)
    _insert_show(db, society_id, "Gil One", o1, c1)
    _insert_show(db, society_id, "Gil Two", o2, c2)
    _insert_show(db, society_id, "Gil Three", o3, c3)
    _insert_show(db, society_id, "Gil Four", o4, c4)
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "Congested" not in body
    assert "congested" not in body
