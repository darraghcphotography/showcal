"""The two charts on /stats (see app/templates/_stat_charts.html).

The page carried thousands of productions and award records across 114 years
and not one chart until 2026-09-02 - every figure was a number in a table or a
count in a pill.

What matters most here is not that a chart renders. It is that the chart cannot
disagree with the numbers printed beside it: both are folded out of rows the
page already computed for its table and its chip strip, so there is one
definition of what counts, not two.
"""
from conftest import seed_society

from app.blueprints.info import _decade_series


def _rows(*pairs):
    return [{"start_year": year, "productions": n} for year, n in pairs]


def test_seasons_fold_into_their_decade():
    series = _decade_series(_rows((1994, 3), (1997, 5), (2001, 7)))
    assert [(r["decade"], r["productions"]) for r in series] == [(1990, 8), (2000, 7)]


def test_the_series_is_oldest_first_whatever_order_it_arrives_in():
    """season_rows comes back newest-first for the table below the chart; an
    axis has to read left to right in time."""
    series = _decade_series(_rows((2011, 4), (1981, 2), (2001, 3)))
    assert [r["decade"] for r in series] == [1980, 2000, 2010]


def test_only_the_newest_decade_is_flagged_in_progress():
    """A partial decade drawn like a complete one reads as a collapse. The flag
    is what lets the chart draw it as an outline and say so in the caption."""
    series = _decade_series(_rows((1994, 3), (2004, 9), (2021, 2)))
    assert [r["in_progress"] for r in series] == [False, False, True]


def test_a_four_digit_year_is_not_mistaken_for_a_two_digit_season():
    """productions.season_start_year holds a real year - the table spans
    1911-2027. season_start_year() the *function* would be wrong here: its
    50-pivot cannot tell 1911/12 from 2011/12. This pins the two apart."""
    series = _decade_series(_rows((1911, 6), (2011, 887)))
    assert [(r["label"], r["productions"]) for r in series] == [("1910s", 6), ("2010s", 887)]


def test_no_seasons_means_no_chart_rather_than_a_crash():
    assert _decade_series([]) == []


def _seed_one_production(db, year=2011, title="Evita"):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO productions (season_start_year, society_key, title_key, season, "
        "society_id, society_name, title) VALUES (?, ?, ?, ?, ?, 'Test Society', ?)",
        (year, f"id:{society_id}", title.lower(),
         f"{year % 100:02d}/{(year + 1) % 100:02d}", society_id, title),
    )
    pid = db.execute("SELECT id FROM productions ORDER BY id DESC LIMIT 1").fetchone()["id"]
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, "
        "society_id, production_id, source) VALUES (?, 'Gilbert', 'Best Overall Show', "
        "'Nominee', ?, ?, ?, 'manual')",
        (year + 1, title, society_id, pid),
    )
    db.commit()
    return society_id


def test_a_page_with_no_productions_draws_no_chart_rather_than_an_empty_axis(client, db):
    """A fresh or fully filtered-out page must not render a bare grid with
    nothing on it."""
    body = client.get("/stats").get_data(as_text=True)
    assert "Productions on record, by decade" not in body


def test_the_decade_chart_totals_match_the_number_printed_above_it(client, db):
    """The whole reason the series is folded out of season_rows rather than
    queried separately: two queries drift, one cannot."""
    society_id = seed_society(db)
    for year, title in ((1998, "Oliver!"), (1999, "Chess"), (2011, "Evita")):
        db.execute(
            "INSERT INTO productions (season_start_year, society_key, title_key, season, "
            "society_id, society_name, title) VALUES (?, ?, ?, ?, ?, 'Test Society', ?)",
            (year, f"id:{society_id}", title.lower(),
             f"{year % 100:02d}/{(year + 1) % 100:02d}", society_id, title),
        )
        pid = db.execute("SELECT id FROM productions ORDER BY id DESC LIMIT 1").fetchone()["id"]
        db.execute(
            "INSERT INTO historical_results (year, tier, category_name, result, show, "
            "society_id, production_id, source) VALUES (?, 'Gilbert', 'Best Overall Show', "
            "'Nominee', ?, ?, ?, 'manual')",
            (year + 1, title, society_id, pid),
        )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert "Productions on record, by decade" in body
    # 2 in the 1990s, 1 in the 2010s - and "3 in total" in the caption.
    assert "3 in total" in body


def test_both_charts_offer_the_numbers_without_needing_the_picture(client, db):
    """Colour and shape are not the only way to read these."""
    _seed_one_production(db)

    body = client.get("/stats").get_data(as_text=True)
    assert "View as a table" in body
    # A single-series chart needs no legend, and must not grow one.
    assert "chart-legend" not in body


def test_the_region_split_is_bars_not_chips(client, db):
    seed_society(db, id=1, name="Eastern Soc", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status) VALUES (1, '20/21', 'Eastern', 'Chicago', '2001-09-01', "
        "'2001-09-05', 'approved')"
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert "Shows by region" in body
    assert "region-fill" in body
