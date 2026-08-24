"""Covers the four presentation fixes from the 2026-08-19 UX audit:
one shared date format, past-aware "Not on record" wording, the Review
column collapsing when nothing in a table has one, and pagination on the
two long list pages that didn't have it."""
from app.season import season_has_ended, season_start_year

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


# --- season_start_year: the 1999/2000 rollover ------------------------------

def test_season_start_year_is_century_aware():
    # Plain string comparison puts '76/77' after '09/10'; the real years must not.
    assert season_start_year("76/77") == 1976
    assert season_start_year("09/10") == 2009
    assert season_start_year("25/26") == 2025
    assert season_start_year("76/77") < season_start_year("09/10")


def test_season_has_ended_against_current(db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01")
    assert season_has_ended(db, "22/23") is True
    assert season_has_ended(db, "25/26") is False
    assert season_has_ended(db, "26/27") is False
    # A 1970s season is past, even though it sorts after '09/10' as a string.
    assert season_has_ended(db, "76/77") is True


def test_season_has_ended_tolerates_junk(db):
    seed_society(db)
    seed_show(db, opening_date="2025-09-01")
    assert season_has_ended(db, None) is False
    assert season_has_ended(db, "") is False
    assert season_has_ended(db, "not-a-season") is False


# --- shared date format -----------------------------------------------------

def test_season_page_uses_the_compact_date_range(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2026-09-02", closing_date="2026-09-05")
    html = client.get("/season?season=25/26").get_data(as_text=True)
    assert "2–5 Sep 2026" in html
    # ...and not the old dd-mm-yyyy rendering the homepage never used.
    assert "02-09-2026" not in html


# --- "Not on record" vs "TBA" ----------------------------------------------

def test_past_season_says_not_on_record_for_a_missing_date(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01")  # sets current season
    seed_show(db, season="22/23", show="Old Show", opening_date=None)
    html = client.get("/season?season=22/23").get_data(as_text=True)
    assert "Not on record" in html
    assert ">TBA<" not in html


def test_current_season_still_says_tba(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01")
    seed_show(db, season="25/26", show="Undated Show", opening_date=None)
    html = client.get("/season?season=25/26").get_data(as_text=True)
    assert "TBA" in html
    assert "Not on record" not in html


def test_show_detail_says_not_on_record_for_a_past_season(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2025-09-01")
    old = seed_show(db, season="22/23", show="Old Show", opening_date=None, source="historical")
    html = client.get(f"/shows/{old}").get_data(as_text=True)
    assert "Not on record" in html


# --- Review column collapses -----------------------------------------------

def test_review_column_hidden_when_no_row_has_a_review(client, db):
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2026-09-02", review_status="None")
    html = client.get("/season?season=25/26").get_data(as_text=True)
    assert "<th>Review</th>" not in html
    assert "<th>Dates</th>" in html


def test_review_column_shown_when_a_row_has_one(client, db):
    seed_society(db)
    seed_show(
        db, season="25/26", opening_date="2026-09-02",
        review_status="Published", review_url="https://example.com/review",
    )
    html = client.get("/season?season=25/26").get_data(as_text=True)
    assert "<th>Review</th>" in html
    assert "Read review" in html


def test_review_column_shown_for_not_adjudicated(client, db):
    """'Not adjudicated' is real information (that show will never have a
    review), unlike 'Not yet' - so it must keep the column alive."""
    seed_society(db)
    seed_show(db, season="25/26", opening_date="2026-09-02", review_status="Not adjudicated")
    html = client.get("/season?season=25/26").get_data(as_text=True)
    assert "<th>Review</th>" in html


# --- pagination -------------------------------------------------------------

def test_titles_shows_every_title_on_one_page(client, db):
    """/titles dropped per-page pagination for the Shows A-Z redesign - the
    whole alphabet renders on one page behind a letter scrubber instead, so
    there's no "page 2" for a title to be missing from any more."""
    seed_society(db)
    for i in range(60):
        seed_show(db, show=f"Show {i:03d}", opening_date="2025-09-01")
    html = client.get("/titles").get_data(as_text=True)
    assert "60 distinct titles" in html
    assert "Show 000" in html
    assert "Show 059" in html


def test_societies_paginates(client, db):
    for i in range(60):
        seed_society(db, id=i + 1, name=f"Society {i:03d}")
    html = client.get("/societies?per_page=50").get_data(as_text=True)
    assert "60 societies found" in html
    assert "Society 000" in html
    assert "Society 059" not in html
    assert "Society 059" in client.get("/societies?per_page=50&page=2").get_data(as_text=True)


def test_out_of_range_page_clamps_instead_of_erroring(client, db):
    """A stale bookmark or a hand-edited URL should land on a real page, not
    a 404 or an empty table."""
    seed_society(db)
    for i in range(10):
        seed_show(db, show=f"Show {i}", opening_date="2025-09-01")
    for url in ("/titles?page=999", "/titles?page=-3", "/titles?per_page=7", "/societies?page=999"):
        assert client.get(url).status_code == 200
    assert "Show 0" in client.get("/titles?page=999").get_data(as_text=True)


def test_season_page_surfaces_unannounced_slots_for_the_current_season(client, db):
    """A society can reserve a slot before announcing a title - shows.show
    is NULL until they do. The season page used to filter those rows out
    entirely (WHERE shows.show IS NOT NULL), so they never had anywhere to
    appear at all."""
    seed_society(db, id=1, name="Announced Society")
    seed_society(db, id=2, name="Kilcock Musical & Dramatic Society", region="Eastern")
    seed_show(db, society_id=1, season="25/26", show="Test Show", opening_date="2025-09-01")  # sets current season
    seed_show(db, society_id=2, season="25/26", show=None, opening_date=None, region="Eastern")

    html = client.get("/season?season=25/26").get_data(as_text=True)
    assert "Unannounced" in html
    assert "Kilcock Musical &amp; Dramatic Society" in html


def test_unannounced_section_absent_for_a_past_season(client, db):
    """An unfilled slot in a past season is just a gap in the record, not
    'unannounced' - the section is scoped to the current season only."""
    seed_society(db, id=1, name="Announced Society")
    seed_society(db, id=2, name="Old Society")
    seed_show(db, society_id=1, season="25/26", show="Test Show", opening_date="2025-09-01")
    seed_show(db, society_id=2, season="22/23", show=None, opening_date=None)

    html = client.get("/season?season=22/23").get_data(as_text=True)
    assert "Unannounced" not in html


def test_non_aims_societies_sort_last_with_a_heading(client, db):
    """Non-AIMS societies used to sort alphabetically among real members -
    an 'Achill Musical & Dramatic Society' (Non-AIMS) landed above most of
    the real AIMS roster purely on its name. They should sort after every
    AIMS member instead, under their own heading."""
    seed_society(db, id=1, name="Zebra Musical Society", region="Eastern", section="Gilbert")
    seed_society(db, id=2, name="Achill Musical & Dramatic Society", region="Western", section="Non-AIMS")

    html = client.get("/societies?per_page=50").get_data(as_text=True)
    zebra_pos = html.index("Zebra Musical Society")
    achill_pos = html.index("Achill Musical")
    heading_pos = html.index("Non-AIMS societies")
    assert zebra_pos < heading_pos < achill_pos


def test_no_non_aims_heading_when_none_present(client, db):
    seed_society(db, id=1, name="Zebra Musical Society", section="Gilbert")
    html = client.get("/societies?per_page=50").get_data(as_text=True)
    assert "Non-AIMS societies" not in html


def test_pagination_keeps_the_active_filters(client, db):
    for i in range(60):
        seed_society(db, id=i + 1, name=f"Society {i:03d}", region="Western")
    seed_society(db, id=999, name="Eastern One", region="Eastern")
    html = client.get("/societies?per_page=50&region=Western").get_data(as_text=True)
    assert "60 societies found" in html      # the Eastern one is filtered out
    assert "region=Western" in html          # ...and paging links carry it through
