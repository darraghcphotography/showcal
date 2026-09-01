"""Stats page: pre-23/24 seasons collapse behind a <details> disclosure
instead of cluttering the main "Productions by season" table (see info.py's
stats() and stats.html). Season Archive page: a "hide cancelled shows"
filter and a soonest/latest sort toggle."""
import re
from datetime import date, timedelta

from conftest import seed_society

from app.season import season_for_date


def test_stats_splits_seasons_at_coverage_boundary(client, db):
    society_id = seed_society(db)
    # One recent (in-coverage) show, one production from well before 23/24 -
    # productions that old live in historical_results, not shows, so that's
    # what the unified "Productions by season" table actually reads from.
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Chicago', '2024-11-01', '2024-11-05', 'approved')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, source) "
        "VALUES (2011, 'Gilbert', 'Best Overall Show', 'Nominee', 'Oliver!', 'Test Society', 'manual')"
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert "Show 1 earlier season" in body

    before_details = body.split("<details>")[0]
    inside_details = body.split("<details>")[1].split("</details>")[0]
    assert "24/25" in before_details
    assert "10/11" not in before_details
    assert "10/11" in inside_details


def test_stats_defines_distinct_titles(client):
    body = client.get("/stats").get_data(as_text=True)
    assert "distinct titles" in body.lower()
    assert "counts once" in body


def _add_award(db, category_name, result, tier, society_name=None, nominee_name=None, year=2025):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, society_name, nominee_name, source) "
        "VALUES (?, ?, ?, ?, ?, ?, 'manual')",
        (year, tier, category_name, result, society_name, nominee_name),
    )


def test_award_leaderboard_explicit_category_shows_best_overall_show_by_society(client, db):
    _add_award(db, "Best Overall Show", "Winner", "Gilbert", society_name="Wexford Light Opera Society")
    db.commit()

    body = client.get("/stats?award_category=Best+Overall+Show").get_data(as_text=True)
    assert "Award Explorer" in body
    assert "Wexford Light Opera Society" in body
    assert "By society" in body


def test_award_leaderboard_no_category_param_picks_a_random_valid_category(client, db, monkeypatch):
    _add_award(db, "Best Overall Show", "Winner", "Gilbert", society_name="Wexford Light Opera Society")
    _add_award(db, "Best Director", "Winner", "Gilbert", nominee_name="Jane Doe")
    db.commit()

    from app.blueprints import info as info_module

    monkeypatch.setattr(info_module.random, "choice", lambda seq: {"key": "Best Director"})
    body = client.get("/stats").get_data(as_text=True)
    assert "Award Explorer" in body
    assert "Jane Doe" in body
    assert "By person" in body
    assert 'value="Best Director" selected' in body


def test_award_leaderboard_person_category_groups_by_nominee(client, db):
    _add_award(db, "Best Director", "Winner", "Gilbert", nominee_name="Jane Doe")
    _add_award(db, "Best Director", "Winner", "Sullivan", nominee_name="John Smith")
    db.commit()

    body = client.get("/stats?award_category=Best+Director").get_data(as_text=True)
    assert "By person" in body
    assert "Jane Doe" in body
    assert "John Smith" in body


def test_award_leaderboard_tier_filter_narrows_results(client, db):
    _add_award(db, "Best Director", "Winner", "Gilbert", nominee_name="Jane Doe")
    _add_award(db, "Best Director", "Winner", "Sullivan", nominee_name="John Smith")
    db.commit()

    body = client.get("/stats?award_category=Best+Director&award_tier=Gilbert").get_data(as_text=True)
    assert "Jane Doe" in body
    assert "John Smith" not in body


def test_award_leaderboard_keeps_choreography_and_choreographer_separate(client, db):
    """These were merged into one Explorer entry for a while on the
    assumption they were the same award renamed - wrong, corrected 19 Aug
    2026 by checking year-by-year: both ran in parallel as clearly distinct
    categories every year from 2019 to 2025, which a rename can't do."""
    _add_award(db, "Best Choreography", "Winner", "Gilbert", nominee_name="Choreography Winner")
    _add_award(db, "Best Choreographer", "Winner", "Gilbert", nominee_name="Choreographer Winner")
    db.commit()

    choreography = client.get("/stats?award_category=Best+Choreography").get_data(as_text=True)
    assert "Choreography Winner" in choreography
    assert "Choreographer Winner" not in choreography

    choreographer = client.get("/stats?award_category=Best+Choreographer").get_data(as_text=True)
    assert "Choreographer Winner" in choreographer
    assert "Choreography Winner" not in choreographer


def test_award_leaderboard_merges_renamed_categories(client, db):
    """Best Chorus -> Best Choral Singing and Adjudicator's Special Award ->
    Spirit of AIMS ARE clean renames (confirmed year-by-year: the category
    simply stops appearing under one name and starts under another, never
    both in the same year) - these should count continuously."""
    _add_award(db, "Best Chorus", "Winner", "Gilbert", society_name="Old Era Society", year=2000)
    _add_award(db, "Best Choral Singing", "Winner", "Gilbert", society_name="Old Era Society", year=2026)
    db.commit()

    body = client.get("/stats?award_category=Best+Choral+Singing").get_data(as_text=True)
    assert '<span class="rank-n">2</span>' in body
    assert "Renamed from" in body


def test_stats_headline_reframed(client):
    body = client.get("/stats").get_data(as_text=True)
    assert "Who's won the most?" not in body
    assert "Explore any award category" in body


def test_no_timeframe_toggle_and_explorer_is_always_all_time(client, db):
    """The 'Since 23/24 / All-time' toggle was removed 20 Aug 2026 - it was
    making per-person leaderboards degenerate (a handful of people tied at 1
    under 'recent', a real ranking all-time). Explorer and every remaining
    stat are all-time only now, no control needed to see old data."""
    _add_award(db, "Best Director", "Winner", "Gilbert", nominee_name="Old Adjudicator Pick", year=1980)
    db.commit()

    body = client.get("/stats?award_category=Best+Director").get_data(as_text=True)
    assert "Old Adjudicator Pick" in body
    assert "Timeframe" not in body


def test_award_leaderboard_invalid_category_falls_back_to_default(client, db):
    resp = client.get("/stats?award_category=Not+A+Real+Category&award_tier=Nonsense")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'value="Best Overall Show" selected' in body


def _productions_cell(body, season):
    match = re.search(rf"<td>{re.escape(season)}</td>\s*<td>(\d+)</td>", body)
    return int(match.group(1)) if match else None


def test_productions_count_includes_review_only_skeleton_shows(client, db):
    """A ShowTimes review with no matching award record still creates a
    real, countable production (a shows.source='historical' skeleton show)
    - previously invisible from every count on this page (371 such
    productions found in production data, 20 Aug 2026, the bug that drove
    the 20 Aug redesign). Fixed by folding unmatched skeleton shows into
    the unified season table."""
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '18/19', 'Eastern', 'Review Only Show', 'approved', 'historical')",
        (society_id,),
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert _productions_cell(body, "18/19") == 1


def test_productions_count_does_not_double_count_matched_skeleton_shows(client, db):
    """A skeleton show that DOES have a matching award record must count
    once, not twice - the NOT EXISTS check that keeps the two sources from
    double-counting the same real production."""
    society_id = seed_society(db, name="Matched Society")
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_id, society_name, source) "
        "VALUES (2019, 'Gilbert', 'Best Overall Show', 'Nominee', 'Matched Show', ?, 'Matched Society', 'manual')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '18/19', 'Eastern', 'Matched Show', 'approved', 'historical')",
        (society_id,),
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert _productions_cell(body, "18/19") == 1


def test_signature_show_and_leaderboards_removed(client):
    """Both cut 20 Aug 2026 - Signature Show confirmed low-value twice by
    Darragh; the standalone Leaderboards grid duplicated what Award
    Explorer already does interactively per category."""
    body = client.get("/stats").get_data(as_text=True)
    assert "Signature show" not in body
    assert "Most nominated, never won" not in body
    assert "Win-rate leaderboard" not in body


def test_season_page_lists_shows_soonest_first(client, db):
    """The sort-direction toggle was removed (see ROADMAP, 2026-08-20) -
    always soonest/earliest-first now, the fixed order the toggle already
    defaulted to.

    The dates are relative to today on purpose. This test used to hardcode two
    September 2026 dates; on 2026-09-02 the earlier of the two became the past,
    /season sorted it out of the upcoming list, and the test went red for a
    reason that had nothing to do with sort direction."""
    society_id = seed_society(db)

    early = date.today() + timedelta(days=10)
    late = early + timedelta(days=7)
    # Step past a season boundary rather than straddling it: /season shows one
    # season at a time, so a pair split across the mid-May cutoff would render
    # apart for a reason that isn't sort order either.
    while season_for_date(early.isoformat()) != season_for_date(late.isoformat()):
        early += timedelta(days=7)
        late = early + timedelta(days=7)
    season = season_for_date(early.isoformat())

    for show, opening in [("Late Bloomer", late), ("Early Bird", early)]:
        db.execute(
            "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
            "VALUES (?, ?, 'Eastern', ?, ?, ?, 'approved')",
            (society_id, season, show, opening.isoformat(), opening.isoformat()),
        )
    db.commit()

    table = client.get(f"/season?season={season}").get_data(as_text=True).split("Upcoming productions")[-1]
    assert table.index("Early Bird") < table.index("Late Bloomer")
