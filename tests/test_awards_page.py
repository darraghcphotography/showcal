"""The /awards browse page: pagination (info.py's awards()) and hiding the
Nominee column for society-level categories (Best Technical/Programme/etc -
nominee_name on those rows is actually a society name, not a person, see
SOCIETY_AWARD_CATEGORY_NAMES in constants.py)."""


def _add_result(db, year, category_name, result="Winner", society_name=None, nominee_name=None, tier="Gilbert",
                 role=None, reason=None):
    db.execute(
        "INSERT INTO historical_results "
        "(year, tier, category_name, result, society_name, nominee_name, role, reason, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual')",
        (year, tier, category_name, result, society_name, nominee_name, role, reason),
    )


def test_awards_page_paginates(client, db):
    for i in range(120):
        _add_result(db, 2000 + i, "Best Overall Show", society_name=f"Society {i}")
    db.commit()

    resp = client.get("/awards?per_page=50")
    body = resp.get_data(as_text=True)
    assert "Page 1 of 3" in body
    assert "Next" in body
    assert "Previous" not in body

    resp2 = client.get("/awards?per_page=50&page=2")
    body2 = resp2.get_data(as_text=True)
    assert "Page 2 of 3" in body2
    assert "Previous" in body2
    assert "Next" in body2

    resp3 = client.get("/awards?per_page=100")
    body3 = resp3.get_data(as_text=True)
    assert "Page 1 of 2" in body3


def test_awards_page_out_of_range_page_clamps_to_last(client, db):
    for i in range(10):
        _add_result(db, 2000 + i, "Best Overall Show", society_name=f"Society {i}")
    db.commit()

    resp = client.get("/awards?per_page=50&page=99")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Only one page of results exists, so pagination controls don't render
    # at all (nothing to page through) rather than showing "Page 1 of 1".
    assert "pagination" not in body
    assert "Society 0" in body


def test_awards_page_defaults_to_all_results_not_just_winners(client, db):
    """Darragh's ask: someone might want to see how many times they've been
    nominated, not just wins - the default view (no ?result= at all) should
    include Nominee rows, not just Winner."""
    _add_result(db, 2020, "Best Overall Show", result="Winner", society_name="Winning Society")
    _add_result(db, 2020, "Best Overall Show", result="Nominee", society_name="Nominated Society")
    db.commit()

    body = client.get("/awards").get_data(as_text=True)
    assert "Winning Society" in body
    assert "Nominated Society" in body
    assert '<option value="" selected>All results</option>' in body
    assert "Clear" not in body  # no filter is actually active at the bare /awards default


def test_awards_page_hides_nominee_for_society_category(client, db):
    _add_result(db, 2020, "Best Technical (Lighting, Sets & Sound)", society_name="Carrick-on-Suir Musical Society", nominee_name="Carrick-on-Suir Musical Society")
    db.commit()

    body = client.get("/awards").get_data(as_text=True)
    # Renders in the Society column of both the table view and the card
    # view (both always render server-side, toggled by a media query) - if
    # Nominee were also shown, the name would appear 4 times, not 2, since
    # this test's nominee_name deliberately mirrors the real data quirk
    # (some society-level rows store the society's own name in nominee_name).
    assert body.count("Carrick-on-Suir Musical Society") == 2


def test_awards_page_shows_nominee_for_person_category(client, db):
    _add_result(db, 2020, "Best Director", society_name="Test Society", nominee_name="Jane Doe")
    db.commit()

    body = client.get("/awards").get_data(as_text=True)
    assert "Jane Doe" in body


def test_winner_rows_get_the_gold_tint_class(client, db):
    """Second Act backlog item 5 - a Winner row is visually distinct without
    reading the Result column cell by cell."""
    _add_result(db, 2020, "Best Overall Show", result="Winner", society_name="Winning Society")
    _add_result(db, 2020, "Best Overall Show", result="Nominee", society_name="Nominated Society")
    db.commit()

    body = client.get("/awards").get_data(as_text=True)
    assert '<tr class="row-winner">' in body
    assert '<span class="win-tag">🏆 Winner</span>' in body


def test_no_filter_chips_at_the_bare_default(client, db):
    body = client.get("/awards").get_data(as_text=True)
    assert "filter-chips" not in body


def test_active_filters_render_as_removable_chips(client, db):
    _add_result(db, 2020, "Best Overall Show", result="Winner", society_name="Test Society")
    db.commit()

    body = client.get("/awards?year=2020&result=Winner").get_data(as_text=True)
    assert '<div class="filter-chips">' in body
    assert "Year: 2020" in body
    assert "Result: Winner" in body
    assert '<a class="filter-chip filter-chip-clear" href="/awards">Clear all</a>' in body


def test_a_chip_removes_only_its_own_filter(client, db):
    _add_result(db, 2020, "Best Overall Show", result="Winner", society_name="Test Society")
    db.commit()

    body = client.get("/awards?year=2020&result=Winner").get_data(as_text=True)
    # The "Year: 2020" chip's href drops year but keeps result=Winner.
    year_chip_start = body.index("Year: 2020")
    chip_html = body[max(0, year_chip_start - 200):year_chip_start]
    href = chip_html.rsplit('href="', 1)[1].split('"')[0]
    assert "result=Winner" in href
    assert "year=2020" not in href


def test_awards_page_hides_literal_none_sentinel(client, db):
    """A handful of legacy rows store the literal string 'None' (or 'NULL')
    in reason/role/nominee_name instead of a real blank - a plain
    `or '—'`/`if x` check treats those as present, since they're non-empty
    strings, so the page used to render an italic "None" note and a
    "(None)" next to the nominee."""
    _add_result(db, 2020, "Best Director", society_name="Test Society", nominee_name="None", role="None", reason="None")
    _add_result(db, 2021, "Best Actor", society_name="Test Society", nominee_name="Jane Doe", role="NULL", reason="NULL")
    db.commit()

    body = client.get("/awards").get_data(as_text=True)
    assert "None" not in body
    assert "NULL" not in body
    assert "Jane Doe" in body
