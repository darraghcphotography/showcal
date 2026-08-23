"""Circuit intelligence (app/circuit_intelligence.py) - the "Source C" panel
on /titles/<title>: award tally, signature category, regional spread, and a
revival-candidate flag, all read straight off the productions/award archive.
See public.py's title_detail() for the route.
"""
from datetime import date

from conftest import seed_society

from app.circuit_intelligence import _is_revival_candidate


def _add_award(db, year, show, society_name="Test Society", society_id=None,
                category_name="Best Overall Show", result="Nominee"):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, society_id, source) "
        "VALUES (?, 'Gilbert', ?, ?, ?, ?, ?, 'manual')",
        (year, category_name, result, show, society_name, society_id),
    )


def test_no_circuit_panel_when_a_title_has_no_award_history(client, db):
    """A brand-new announced show has a shows row but no adjudication yet -
    nothing a circuit-intelligence panel could say."""
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (1, '26/27', 'Eastern', 'Brand New Show', 'approved')"
    )
    db.commit()

    body = client.get("/titles/Brand New Show").get_data(as_text=True)
    assert "<h2>Circuit intelligence</h2>" not in body


def test_award_tally_counts_wins_and_nominations(client, db):
    seed_society(db)
    _add_award(db, 2015, "Test Show", society_id=1, result="Winner")
    _add_award(db, 2016, "Test Show", society_id=1, result="Nominee")
    _add_award(db, 2017, "Test Show", society_id=1, result="Nominee")
    _add_award(db, 2018, "Test Show", society_id=1, result="Third Place")
    db.commit()

    body = client.get("/titles/Test Show").get_data(as_text=True)
    assert "<h2>Circuit intelligence</h2>" in body
    assert '<span class="stat-value">1</span><span class="stat-label">Award wins</span>' in body
    assert '<span class="stat-value">4</span><span class="stat-label">Nominations</span>' in body


def test_best_overall_show_wins_listed_with_year_and_society(client, db):
    seed_society(db)
    _add_award(db, 2010, "Test Show", society_id=1, category_name="Best Overall Show", result="Winner")
    _add_award(db, 2020, "Test Show", society_id=1, category_name="Best Overall Show", result="Winner")
    db.commit()

    body = client.get("/titles/Test Show").get_data(as_text=True)
    assert "Best Overall Show 2010" in body
    assert "Best Overall Show 2020" in body
    assert "Test Society" in body


def test_signature_category_is_the_top_won_category(client, db):
    seed_society(db)
    for year in (2010, 2011, 2012):
        _add_award(db, year, "Test Show", society_id=1, category_name="Best Male Singer", result="Winner")
    _add_award(db, 2013, "Test Show", society_id=1, category_name="Best Director", result="Winner")
    db.commit()

    body = client.get("/titles/Test Show").get_data(as_text=True)
    assert "Best Male Singer (3&times;)" in body
    assert "Best Director" not in body.split("Signature categor")[1].split("</p>")[0]


def test_signature_category_below_the_win_floor_is_not_shown(client, db):
    """A single win isn't a defining category - see SIGNATURE_MIN_WINS."""
    seed_society(db)
    _add_award(db, 2010, "Test Show", society_id=1, category_name="Best Director", result="Winner")
    db.commit()

    body = client.get("/titles/Test Show").get_data(as_text=True)
    assert "Signature categor" not in body


def test_signature_category_tie_shows_both(client, db):
    seed_society(db)
    for year in (2010, 2011):
        _add_award(db, year, "Test Show", society_id=1, category_name="Best Director", result="Winner")
    for year in (2012, 2013):
        _add_award(db, year, "Test Show", society_id=1, category_name="Best Musical Director", result="Winner")
    db.commit()

    body = client.get("/titles/Test Show").get_data(as_text=True)
    line = body.split("Signature categor")[1].split("</p>")[0]
    assert "Best Director" in line
    assert "Best Musical Director" in line
    assert "categories:" in body  # plural, since it's a real tie


def test_signature_category_folds_a_renamed_category_together(client, db):
    """Best Chorus -> Best Choral Singing (2025/26) - a title's wins under
    both names must combine into one signature-category count."""
    seed_society(db)
    _add_award(db, 2020, "Test Show", society_id=1, category_name="Best Chorus", result="Winner")
    _add_award(db, 2026, "Test Show", society_id=1, category_name="Best Choral Singing", result="Winner")
    db.commit()

    body = client.get("/titles/Test Show").get_data(as_text=True)
    assert "Best Choral Singing (2&times;)" in body


def test_regional_distribution_shows_all_six_regions(client, db):
    seed_society(db, id=1, name="Eastern Society", region="Eastern")
    seed_society(db, id=2, name="Western Society", region="Western")
    _add_award(db, 2020, "Test Show", society_id=1, society_name="Eastern Society")
    _add_award(db, 2021, "Test Show", society_id=1, society_name="Eastern Society")
    _add_award(db, 2022, "Test Show", society_id=2, society_name="Western Society")
    db.commit()

    body = client.get("/titles/Test Show").get_data(as_text=True)
    assert '<span class="chip-n">2</span><span class="chip-label">Eastern</span>' in body
    assert '<span class="chip-n">1</span><span class="chip-label">Western</span>' in body
    for region in ("Northern", "South-West", "South-East", "Midlands"):
        assert '<span class="chip-n">0</span><span class="chip-label">{}</span>'.format(region) in body


def test_revival_candidate_matrix_below_production_floor():
    assert _is_revival_candidate(production_count=7, gap_years=15) is False


def test_revival_candidate_matrix_gap_too_recent():
    assert _is_revival_candidate(production_count=8, gap_years=9) is False


def test_revival_candidate_matrix_inside_the_window():
    assert _is_revival_candidate(production_count=8, gap_years=10) is True
    assert _is_revival_candidate(production_count=20, gap_years=20) is True
    assert _is_revival_candidate(production_count=8, gap_years=30) is True


def test_revival_candidate_matrix_gap_too_old():
    assert _is_revival_candidate(production_count=8, gap_years=31) is False


def test_revival_aside_shown_for_a_real_revival_candidate(client, db, monkeypatch):
    from app.blueprints import public as public_module

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 8, 23)

    monkeypatch.setattr(public_module, "date", FixedDate)

    seed_society(db)
    # 8 productions, the most recent opening in the 2011 season (award year
    # 2012) - a 2026 - 2011 = 15 year gap, inside the revival window.
    for year in range(2005, 2013):
        _add_award(db, year, "Old Favourite", society_id=1)
    db.commit()

    body = client.get("/titles/Old Favourite").get_data(as_text=True)
    assert "Last staged in 2011 (15 years ago), after" in body
    assert "8 AIMS productions - a candidate for a society to bring back." in body


def test_no_revival_aside_for_a_recently_staged_title(client, db):
    seed_society(db)
    for year in range(2019, 2027):
        _add_award(db, year, "Still Going Strong", society_id=1)
    db.commit()

    body = client.get("/titles/Still Going Strong").get_data(as_text=True)
    assert "candidate for a society to bring back" not in body


def test_ensure_current_makes_the_panel_reflect_freshly_seeded_awards(client, db):
    """The route must call productions_build.ensure_current(db) itself -
    forgetting it doesn't error, it silently reads a stale/empty productions
    table (see ROADMAP.md's ensure_current() tech-debt note)."""
    seed_society(db)
    _add_award(db, 2020, "Freshly Seeded Show", society_id=1, result="Winner")
    db.commit()

    body = client.get("/titles/Freshly Seeded Show").get_data(as_text=True)
    assert '<span class="stat-value">1</span><span class="stat-label">Award wins</span>' in body
