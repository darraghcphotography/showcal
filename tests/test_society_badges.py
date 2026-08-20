"""Society milestone badges on the public society page (app/blueprints/
public.py's _society_badges) - each earned independently from real
historical_results/shows data, only ever rendered when actually earned."""
from conftest import seed_society


def _add_result(db, society_id, year, category_name=None, result=None, show=None, tier=None):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_id, source) "
        "VALUES (?, ?, ?, ?, ?, ?, 'manual')",
        (year, tier, category_name, result, show, society_id),
    )


def test_no_badges_when_nothing_earned(client, db):
    society_id = seed_society(db)
    db.commit()

    resp = client.get(f"/societies/{society_id}")
    body = resp.get_data(as_text=True)
    assert "badge-row" not in body


def test_century_club_badge(client, db):
    society_id = seed_society(db)
    for i in range(100):  # 100 distinct productions, all pre-2024
        _add_result(db, society_id, 2000, show=f"Show {i}")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Century Club" in body


def test_century_club_badge_absent_below_threshold(client, db):
    society_id = seed_society(db)
    for i in range(50):  # 50 distinct productions - short of 100
        _add_result(db, society_id, 2000, show=f"Show {i}")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Century Club" not in body


def test_triple_crown_badge(client, db):
    society_id = seed_society(db)
    _add_result(db, society_id, 1999, "Best Director", "Winner", show="Chess")
    _add_result(db, society_id, 1999, "Best Musical Director", "Winner", show="Chess")
    _add_result(db, society_id, 1999, "Best Choreography", "Winner", show="Chess")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Triple Crown" in body
    assert "3 wins for one production (1999)" in body


def test_triple_crown_badge_absent_when_wins_are_different_shows(client, db):
    society_id = seed_society(db)
    _add_result(db, society_id, 1999, "Best Director", "Winner", show="Chess")
    _add_result(db, society_id, 1999, "Best Musical Director", "Winner", show="Oliver!")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Triple Crown" not in body


def test_clean_sweep_badge(client, db):
    society_id = seed_society(db)
    for i in range(8):
        _add_result(db, society_id, 2022, f"Category {i}", "Nominee", show="Some Show")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "The Clean Sweep" in body
    assert "8 nominations in 2022" in body


def test_golden_jubilee_badge(client, db):
    society_id = seed_society(db)
    for year in range(1960, 2017):  # 57 consecutive years (1960..2016 inclusive)
        _add_result(db, society_id, year, show=f"Show {year}")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Golden Jubilee Society" in body
    assert "57 consecutive years active" in body


def test_golden_jubilee_badge_absent_with_a_gap(client, db):
    society_id = seed_society(db)
    for year in range(1960, 2000):  # 40 years, then a gap, then more - no unbroken 50-year run
        _add_result(db, society_id, year, show=f"Show {year}")
    for year in range(2015, 2026):
        _add_result(db, society_id, year, show=f"Show {year}")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Golden Jubilee Society" not in body


def test_dual_tier_champions_badge(client, db):
    society_id = seed_society(db)
    _add_result(db, society_id, 2010, "Best Overall Show", "Winner", show="Chess", tier="Gilbert")
    _add_result(db, society_id, 2018, "Best Overall Show", "Winner", show="Rent", tier="Sullivan")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Dual Tier Champions" in body


def test_dual_tier_champions_badge_absent_with_one_tier_only(client, db):
    society_id = seed_society(db)
    _add_result(db, society_id, 2010, "Best Overall Show", "Winner", show="Chess", tier="Gilbert")
    _add_result(db, society_id, 2018, "Best Overall Show", "Winner", show="Rent", tier="Gilbert")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Dual Tier Champions" not in body


def test_all_rounder_badge(client, db):
    society_id = seed_society(db)
    categories = ["Best Overall Show", "Best Director", "Best Musical Director", "Best Choreography", "Best Sets"]
    for i, cat in enumerate(categories):
        _add_result(db, society_id, 2010 + i, cat, "Winner", show=f"Show {i}")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "The All-Rounder" in body
    assert "Won in 5 different categories" in body


def test_debut_delight_badge(client, db):
    society_id = seed_society(db)
    _add_result(db, society_id, 2025, "Best Programme", "Winner", show="West Side Story")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Debut Delight" in body
    assert "Won in their first-ever year, 2025" in body


def test_debut_delight_badge_absent_when_debut_year_was_unplaced(client, db):
    society_id = seed_society(db)
    _add_result(db, society_id, 2025, "Best Programme", "Nominee", show="West Side Story")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Debut Delight" not in body


def test_gilbert_grandmaster_is_not_built(client, db):
    """Parked on Darragh's call - not on the icon-clash grounds it was
    originally proposed with, and not activated even with a clear real win
    count that would have qualified it under the old proposal."""
    society_id = seed_society(db)
    for year in range(2010, 2014):
        _add_result(db, society_id, year, "Best Overall Show", "Winner", show=f"Show {year}", tier="Gilbert")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Gilbert Grandmaster" not in body
