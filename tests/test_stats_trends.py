"""/stats/trends (Decades) - era leaderboards read off the awards archive
(historical_results), not the shows catalogue, which only covers 05/06
onward and would be too thin for a real decades story. See info.py's
stats_trends()."""
from datetime import date

import pytest

from conftest import seed_society


def _add_result(db, year, show=None, society_name=None, category_name="Best Overall Show", result="Nominee", tier=None):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, source) "
        "VALUES (?, ?, ?, ?, ?, ?, 'manual')",
        (year, tier, category_name, result, show, society_name),
    )


def test_no_archive_data_shows_empty_state(client):
    body = client.get("/stats/trends").get_data(as_text=True)
    assert "No awards-archive data on record yet." in body


def test_decade_scrubber_lists_every_decade_with_a_record_count(client, db):
    _add_result(db, 1985, show="Show A", society_name="Society A")
    _add_result(db, 1986, show="Show B", society_name="Society A")
    _add_result(db, 2021, show="Show C", society_name="Society B")
    db.commit()

    body = client.get("/stats/trends").get_data(as_text=True)
    assert "1980s" in body
    assert "2 records" in body
    assert "2020s" in body
    assert "1 record<" in body


def test_default_decade_is_current_decade_when_it_has_data(client, db, monkeypatch):
    from app.blueprints import info as info_module

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 8, 20)

    monkeypatch.setattr(info_module, "date", FixedDate)

    _add_result(db, 1985, show="Old Show", society_name="Old Society")
    _add_result(db, 2024, show="New Show", society_name="New Society")
    db.commit()

    body = client.get("/stats/trends").get_data(as_text=True)
    assert 'decade-pill active' in body
    active_block = body.split('decade-pill active')[1].split("</a>")[0]
    assert "2020s" in active_block


def test_default_decade_falls_back_to_latest_when_current_decade_has_no_data(client, db, monkeypatch):
    from app.blueprints import info as info_module

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 8, 20)

    monkeypatch.setattr(info_module, "date", FixedDate)

    _add_result(db, 1985, show="Old Show", society_name="Old Society")
    db.commit()

    body = client.get("/stats/trends").get_data(as_text=True)
    active_block = body.split('decade-pill active')[1].split("</a>")[0]
    assert "1980s" in active_block


def test_invalid_decade_param_falls_back_to_default(client, db):
    _add_result(db, 1985, show="Show A", society_name="Society A")
    db.commit()

    resp = client.get("/stats/trends?decade=notanumber")
    assert resp.status_code == 200
    resp2 = client.get("/stats/trends?decade=1500")
    assert resp2.status_code == 200


def test_most_staged_shows_dedupes_multi_category_nominations(client, db):
    """A single production can be nominated in several categories the same
    year (Best Overall Show, Best Director, Best Actor, ...) - each is a
    separate historical_results row, but it's one staging, not several."""
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A", category_name="Best Overall Show")
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A", category_name="Best Director")
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A", category_name="Best Actor")
    db.commit()

    body = client.get("/stats/trends?decade=1980").get_data(as_text=True)
    shows_section = body.split("Most-staged shows")[1].split("Most-nominated societies")[0]
    assert '<span class="rank-n">1</span>' in shows_section
    assert '<span class="rank-n">3</span>' not in shows_section


def test_most_staged_shows_counts_separate_productions(client, db):
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A")
    _add_result(db, 1986, show="Oklahoma!", society_name="Society B")
    db.commit()

    body = client.get("/stats/trends?decade=1980").get_data(as_text=True)
    assert '<span class="rank-n">2</span>' in body


def test_most_nominated_societies_counts_every_nomination_not_deduped(client, db):
    """Unlike most-staged shows above, this leaderboard is a raw nomination
    count on purpose - a society entered in 3 categories the same year
    genuinely got 3 nominations."""
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A", category_name="Best Overall Show")
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A", category_name="Best Director")
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A", category_name="Best Actor")
    db.commit()

    body = client.get("/stats/trends?decade=1980").get_data(as_text=True)
    assert "Society A" in body
    societies_section = body.split("Most-nominated societies")[1]
    assert '<span class="rank-n">3</span>' in societies_section


def test_best_overall_show_winners_listed_for_the_decade(client, db):
    _add_result(db, 1985, show="Oklahoma!", society_name="Society A", category_name="Best Overall Show", result="Winner", tier="Gilbert")
    _add_result(db, 1985, show="South Pacific", society_name="Society B", category_name="Best Overall Show", result="Nominee", tier="Gilbert")
    db.commit()

    body = client.get("/stats/trends?decade=1980").get_data(as_text=True)
    winners_section = body.split("Best Overall Show winners")[1]
    assert "Oklahoma!" in winners_section
    assert "South Pacific" not in winners_section


def test_stats_page_links_to_decades(client):
    body = client.get("/stats").get_data(as_text=True)
    assert 'href="/stats/trends"' in body


def test_the_decade_society_leaderboard_uses_the_societys_current_name(client, db):
    """Grouping is by society_id, which is right - the same society appears in
    the archive under more than one name. But the label came from
    historical_results.society_name, picked arbitrarily from the group, so the
    page could print a variant name rather than what the society is called
    today. Three real societies carry two names ("Pioneer Musical Society" vs
    "Pioneer Musical & Dramatic Society"), found 2026-09-02."""
    seed_society(db, id=1, name="Pioneer Musical Society")
    for year, archive_name in ((2011, "Pioneer Musical & Dramatic Society"),
                               (2013, "Pioneer Musical Society")):
        db.execute(
            "INSERT INTO historical_results (year, tier, category_name, result, show, "
            "society_id, society_name, source) VALUES (?, 'Gilbert', 'Best Overall Show', "
            "'Winner', 'Oliver!', 1, ?, 'manual')",
            (year, archive_name),
        )
    db.commit()

    body = client.get("/stats/trends?decade=2010").get_data(as_text=True)
    # Scoped to the leaderboard card. The "Best Overall Show winners" list lower
    # down deliberately still prints the name as the archive recorded it that
    # year - that one is a year-by-year record, not an aggregate over a decade,
    # and a society that renamed should read as it did at the time.
    board = body[body.index("Most-nominated societies"):body.index("Best Overall Show winners")]
    assert "Pioneer Musical Society" in board
    assert "Pioneer Musical &amp; Dramatic Society" not in board


def test_a_defunct_society_still_falls_back_to_its_archive_name(client, db):
    """The join must not blank out societies that never matched a current row -
    the archive name is all there is for them."""
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, "
        "society_name, source) VALUES (1985, 'Gilbert', 'Best Overall Show', 'Winner', "
        "'The Mikado', 'Long Gone Operatic Society', 'manual')"
    )
    db.commit()

    body = client.get("/stats/trends?decade=1980").get_data(as_text=True)
    assert "Long Gone Operatic Society" in body
