"""The public show/society pages read the productions table (stage 3 of the
productions migration - see docs/productions-stage-3-4-plan.md).

What these pin down is what the old hand-rolled unions got wrong:

  - historical_results is one row per award *category*, not per production, so
    counting those rows as stagings overstated the whole A-Z by ~1.67x.
  - The old queries filtered the archive at SHOWS_COVERAGE_START_YEAR, so a
    title known only from a 2024+ award record had no page at all.
  - The society archive timeline had no year filter, so a 2024+ award record
    listed the same production twice.
  - show_detail matched award records by decoding 'yy/yy' as 2000+yy+1, which
    cannot express a season before 00/01.

The moderation test is the important one: productions_build.collect() reads
shows with no moderation_status filter, so a pending submission *has* a
production row. Zero such productions exist in real data today, which means a
missing ON_RECORD_PRODUCTION filter would sit latent until the next member
submission and then leak it onto a public page - no real data and no accident
would catch it. It has to be seeded deliberately.
"""
from conftest import seed_society


def _add_award(db, year, show, society_id=1, society_name="Test Society",
               category_name="Best Overall Show", result="Nominee", tier="Gilbert"):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, society_id, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')",
        (year, tier, category_name, result, show, society_name, society_id),
    )


def _add_show(db, season, show, society_id=1, moderation_status="approved",
              source="import", region="Eastern", opening_date=None, closing_date=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, "
        "opening_date, closing_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (society_id, season, region, show, source, moderation_status, opening_date, closing_date),
    )


def _squish(body):
    """Collapse whitespace so an assertion can span the template's own line
    breaks (the production count and the words after it are on two lines)."""
    return " ".join(body.split())


def _az_count(body, title):
    """The "Times performed" cell for `title` on /titles."""
    import re
    match = re.search(
        r">%s</a>.*?</td>\s*<td>(\d+)</td>" % re.escape(title), body, re.S
    )
    return int(match.group(1)) if match else None


# --------------------------------------------------------------- the A-Z count

def test_one_production_nominated_in_five_categories_counts_once(client, db):
    """The headline defect. Five historical_results rows are five nominations
    for one staging, and the A-Z used to call that five productions."""
    seed_society(db)
    for category in ("Best Overall Show", "Best Director", "Best Choreography",
                     "Best Musical Director", "Best Sets"):
        _add_award(db, 2019, "Chess", category_name=category)
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert _az_count(body, "Chess") == 1


def test_a_show_and_its_own_award_record_count_once(client, db):
    seed_society(db)
    _add_show(db, "23/24", "Chicago")
    _add_award(db, 2024, "Chicago")
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert _az_count(body, "Chicago") == 1


def test_separate_stagings_of_one_title_each_count(client, db):
    seed_society(db, id=1, name="First Society")
    seed_society(db, id=2, name="Second Society")
    _add_award(db, 2019, "Chess", society_id=1, society_name="First Society")
    _add_award(db, 2019, "Chess", society_id=2, society_name="Second Society")
    _add_award(db, 2021, "Chess", society_id=1, society_name="First Society")
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert _az_count(body, "Chess") == 3


def test_a_title_known_only_from_a_2024_award_record_appears(client, db):
    """The old union filtered the archive at year < 2024, so a title that
    reached the site only through a recent award record was invisible on the
    A-Z, absent from the sitemap, and 404ed on its own page. 16 real titles."""
    seed_society(db)
    _add_award(db, 2025, "Michael Collins")
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert "Michael Collins" in body
    assert _az_count(body, "Michael Collins") == 1


def test_a_historical_skeleton_show_with_no_award_record_counts(client, db):
    """A source='historical' shows row with nothing in the awards archive was
    counted by neither branch of the old union - excluded from the shows side
    by source != 'historical', absent from the other. Same shape as the 371
    productions /stats was missing."""
    seed_society(db)
    _add_show(db, "15/16", "White Christmas", source="historical")
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert _az_count(body, "White Christmas") == 1


def test_last_performed_is_the_season_start_year(client, db):
    """One convention for both eras. An award year is the season's *ending*
    year, so the archive's own value used to read a year later than the same
    season did when it came from a shows row."""
    seed_society(db)
    _add_award(db, 2019, "Chess")
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert "<td>2018</td>" in body


def test_titles_search_box_still_filters(client, db):
    seed_society(db)
    _add_award(db, 2019, "Chess")
    _add_award(db, 2019, "Oliver!")
    db.commit()

    body = client.get("/titles?q=Chess").get_data(as_text=True)
    assert "Chess" in body
    assert "Oliver!" not in body


def test_most_performed_sort_orders_by_real_production_count(client, db):
    """The sort used to rank by nomination volume, so a much-nominated title
    outranked a more-staged one."""
    seed_society(db, id=1, name="First Society")
    seed_society(db, id=2, name="Second Society")
    for category in ("Best Overall Show", "Best Director", "Best Sets"):
        _add_award(db, 2019, "Chess", category_name=category)
    _add_award(db, 2019, "Oliver!", society_id=1, society_name="First Society")
    _add_award(db, 2019, "Oliver!", society_id=2, society_name="Second Society")
    db.commit()

    body = client.get("/titles?sort=most").get_data(as_text=True)
    assert body.index(">Oliver!<") < body.index(">Chess<")


# ------------------------------------------------------------ the moderation gate

def test_a_pending_submission_is_not_counted_on_the_az(client, db):
    """productions_build.collect() has no moderation_status filter, so this
    submission does have a production row - ON_RECORD_PRODUCTION is the only
    thing keeping it off a public page."""
    seed_society(db)
    _add_show(db, "26/27", "Secret Submission", moderation_status="pending", source="submission")
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert "Secret Submission" not in body


def test_the_pending_submission_really_does_have_a_production_row(client, db):
    """Guards the guard: if collect() ever started filtering on moderation
    status, the test above would pass for the wrong reason."""
    seed_society(db)
    _add_show(db, "26/27", "Secret Submission", moderation_status="pending", source="submission")
    db.commit()
    client.get("/titles")

    assert db.execute(
        "SELECT COUNT(*) FROM productions p JOIN shows s ON s.production_id = p.id "
        "WHERE s.show = 'Secret Submission'"
    ).fetchone()[0] == 1


def test_a_rejected_submission_is_not_counted_on_the_az(client, db):
    seed_society(db)
    _add_show(db, "26/27", "Rejected Submission", moderation_status="rejected", source="submission")
    db.commit()

    body = client.get("/titles").get_data(as_text=True)
    assert "Rejected Submission" not in body


def test_a_pending_submission_is_not_in_the_sitemap(client, db):
    seed_society(db)
    _add_show(db, "26/27", "Secret Submission", moderation_status="pending", source="submission")
    _add_award(db, 2019, "Chess")
    db.commit()

    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "Secret" not in body
    assert "Chess" in body


def test_a_pending_submission_is_not_in_search_results(client, db):
    seed_society(db)
    _add_show(db, "26/27", "Secret Submission", moderation_status="pending", source="submission")
    db.commit()

    body = client.get("/search?q=Secret").get_data(as_text=True)
    assert "Secret Submission" not in body


# ----------------------------------------------------------------- search + sitemap

def test_search_reports_the_same_count_as_the_az(client, db):
    """Both read the same productions query, so the two pages can no longer
    contradict each other about the same title."""
    seed_society(db)
    for category in ("Best Overall Show", "Best Director", "Best Sets"):
        _add_award(db, 2019, "Chess", category_name=category)
    db.commit()

    az = _az_count(client.get("/titles").get_data(as_text=True), "Chess")
    body = client.get("/search?q=Chess").get_data(as_text=True)
    assert az == 1
    assert "<td>1</td>" in body


def test_the_sitemap_lists_a_title_only_the_recent_archive_knows(client, db):
    """The sitemap mirrored titles_list()'s definition exactly, so every title
    page the A-Z couldn't see was missing from the sitemap too."""
    seed_society(db)
    _add_award(db, 2025, "Michael Collins")
    db.commit()

    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "Michael%20Collins" in body or "Michael Collins" in body


# ------------------------------------------------------------ /titles/<title>

def test_a_title_only_a_2024_award_record_knows_has_a_page(client, db):
    """It used to 404: title_detail() needed either a shows row or a pre-23/24
    award record, so a title first staged in 24/25 that reached the site only
    through the awards archive had no page and no sitemap entry."""
    seed_society(db)
    _add_award(db, 2025, "Michael Collins")
    db.commit()

    resp = client.get("/titles/Michael Collins")
    assert resp.status_code == 200
    body = _squish(resp.get_data(as_text=True))
    assert "1 production on record" in body
    assert "<td>2025</td>" in body


def test_a_skeleton_show_with_an_award_record_is_listed_once(client, db):
    """The archive table is now "productions with no show page of their own",
    so a staging that has both a shows row and award records appears in the
    detail table only - not in both."""
    seed_society(db)
    _add_show(db, "18/19", "Cabaret", source="historical")
    _add_award(db, 2019, "Cabaret")
    db.commit()

    body = _squish(client.get("/titles/Cabaret").get_data(as_text=True))
    assert "1 production on record" in body
    assert "Also on record (awards archive)" not in body


def test_a_pre_2024_skeleton_show_is_listed_with_full_detail_not_as_archive(client, db):
    """The split is "is there a show page to link to", not an era."""
    seed_society(db)
    _add_show(db, "12/13", "Cabaret", source="historical")
    db.commit()

    body = client.get("/titles/Cabaret").get_data(as_text=True)
    assert "Productions with full detail" in body
    assert "Also on record (awards archive)" not in body


def test_the_opening_count_matches_the_rows_below_it(client, db):
    """The A-Z said 148 for Jesus Christ Superstar while its own detail page
    listed 57 rows. Both now come from the same definition."""
    seed_society(db, id=1, name="First Society")
    seed_society(db, id=2, name="Second Society")
    for category in ("Best Overall Show", "Best Director", "Best Sets"):
        _add_award(db, 2019, "Chess", society_id=1, society_name="First Society", category_name=category)
    _add_award(db, 2021, "Chess", society_id=2, society_name="Second Society")
    db.commit()

    az = _az_count(client.get("/titles").get_data(as_text=True), "Chess")
    body = _squish(client.get("/titles/Chess").get_data(as_text=True))
    assert az == 2
    assert "2 productions on record" in body


def test_the_archive_years_are_unchanged_by_the_cutover(client, db):
    """season_start_year + 1 reproduces historical_results.year exactly - the
    rebuild's verification asserts that relationship - so the only visible
    difference on this page is which rows appear, never a year shifting."""
    seed_society(db)
    _add_award(db, 1994, "Chess")
    db.commit()

    body = client.get("/titles/Chess").get_data(as_text=True)
    assert "<td>1994</td>" in body
    assert "AIMS debut: 1994" in body


def test_two_spellings_of_one_title_land_on_one_page(client, db):
    """title_key, not raw text - the archive really does carry "Ghost the
    Musical" and "Ghost: The Musical" for the same show."""
    seed_society(db, id=1, name="First Society")
    seed_society(db, id=2, name="Second Society")
    _add_award(db, 2015, "Ghost the Musical", society_id=1, society_name="First Society")
    _add_award(db, 2017, "Ghost: The Musical", society_id=2, society_name="Second Society")
    db.commit()

    for url in ("/titles/Ghost the Musical", "/titles/Ghost: The Musical"):
        body = _squish(client.get(url).get_data(as_text=True))
        assert "2 productions on record" in body


def test_a_pending_submission_does_not_appear_on_a_title_page(client, db):
    seed_society(db)
    _add_award(db, 2019, "Chess")
    _add_show(db, "26/27", "Chess", moderation_status="pending", source="submission")
    db.commit()

    body = _squish(client.get("/titles/Chess").get_data(as_text=True))
    assert "1 production on record" in body


def test_a_pending_submission_does_not_inflate_the_circuit_panel(client, db):
    """production_ids_for_title() feeds the regional chips and the revival
    panel's production_count, which sit directly under the count above."""
    seed_society(db)
    _add_award(db, 2019, "Chess", category_name="Best Overall Show", result="Winner")
    _add_show(db, "26/27", "Chess", moderation_status="pending", source="submission", region="Western")
    db.commit()

    client.get("/titles/Chess")
    from app.circuit_intelligence import production_ids_for_title
    assert len(production_ids_for_title(db, "Chess")) == 1


def test_the_detail_table_is_ordered_by_a_real_year_not_a_season_string(client, db):
    """ORDER BY shows.season DESC is a text sort: '76/77' sorts after '09/10'."""
    seed_society(db)
    _add_show(db, "09/10", "Chess", source="historical")
    _add_show(db, "23/24", "Chess", source="historical")
    db.commit()

    body = client.get("/titles/Chess").get_data(as_text=True)
    assert body.index("23/24") < body.index("09/10")


def test_a_title_with_nothing_on_record_still_404s(client, db):
    seed_society(db)
    db.commit()

    assert client.get("/titles/Nothing At All").status_code == 404


# ---------------------------------------------------------- /societies/<id>

def test_a_2024_award_record_is_not_listed_twice_on_a_society_page(client, db):
    """The archive query had no year filter at all, despite a heading reading
    "pre-23/24 archive" - so any 2024+ award record appeared both in the show
    history table and again in the timeline below it. 195 duplicated lines."""
    seed_society(db)
    _add_show(db, "24/25", "Chicago")
    _add_award(db, 2025, "Chicago")
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    # Twice per rendering site-wide by design (desktop table + mobile cards),
    # so four occurrences would be the duplicate this removes.
    assert body.count(">Chicago</a>") == 2


def test_a_production_with_a_show_page_keeps_its_award_badges(client, db):
    """It used to get them from the archive table it was wrongly listed in.
    Deduping without an awards column on the show history table would have
    silently dropped them - hence the column."""
    seed_society(db)
    _add_show(db, "24/25", "Chicago")
    _add_award(db, 2025, "Chicago", category_name="Best Director", result="Winner")
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "Best Director" in body
    assert "Also on record (awards archive)" not in body


def test_a_production_with_no_show_page_is_still_listed(client, db):
    seed_society(db)
    _add_award(db, 1999, "Ham")
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "Also on record (awards archive)" in body
    assert "Ham" in body


def test_a_pending_submission_is_not_listed_on_a_society_page(client, db):
    """It has a production row, and nothing but ON_RECORD_PRODUCTION keeps it
    out of the archive timeline (the show history table filters on
    moderation_status itself)."""
    seed_society(db)
    _add_show(db, "26/27", "Secret Submission", moderation_status="pending", source="submission")
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "Secret Submission" not in body


def test_active_since_is_the_first_year_on_record_not_the_first_win(client, db):
    seed_society(db)
    _add_award(db, 2001, "Carousel", result="Nominee")
    _add_award(db, 2019, "Chess", result="Winner")
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "Active since 2001" in body


def test_active_since_can_express_a_year_before_2001(client, db):
    """The fallback it replaced was 2000 + int(season[:2]) - a hard-coded
    century pivot, the same shape of bug that cost this migration two rounds."""
    seed_society(db)
    _add_award(db, 1954, "The Mikado")
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "Active since 1954" in body


def test_the_century_club_count_is_one_production_per_staging(client, db):
    """The old count summed a DISTINCT (year, show) over the archive with a
    plain shows count, which double-counted a production present in both."""
    seed_society(db)
    for i in range(99):
        _add_award(db, 2000, "Show %d" % i)
    _add_show(db, "23/24", "Chicago")
    _add_award(db, 2024, "Chicago")
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "100 productions on record" in body
    assert "Century Club" in body


def test_the_jubilee_streak_spans_the_century_boundary(client, db):
    """The years set used to mix award years with historical_results_year()
    decoding a season as 2000 + yy + 1, which can't express a season before
    00/01 - so a streak running through 1999 was broken by the arithmetic
    rather than by the data."""
    seed_society(db)
    for year in range(1970, 2027):
        _add_award(db, year, "Show %d" % year)
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "Golden Jubilee Society" in body
    assert "57 consecutive years active" in body


def test_person_awards_still_have_their_own_table(client, db):
    """They have no show, so no production - they can't come through the
    productions path at all and need their own query."""
    seed_society(db)
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, nominee_name, society_id, source) "
        "VALUES (2019, 'Unsung Hero Award', 'Winner', 'Jane Doe', 1, 'manual')"
    )
    db.commit()

    body = client.get("/societies/1").get_data(as_text=True)
    assert "Person &amp; company awards" in body
    assert "Jane Doe" in body


# ------------------------------------------------------------- /shows/<id>

def test_award_history_resolves_for_a_season_before_2001(client, db):
    """The old match decoded shows.season with historical_results_year, which
    returns 2000 + yy + 1: '95/96' gave 2096, so this show's own award record
    could never be found. Latent while shows holds 09/10 onward, live the
    moment anyone bulk-creates an older row."""
    seed_society(db)
    _add_show(db, "95/96", "Chess", source="historical")
    _add_award(db, 1996, "Chess", category_name="Best Director", result="Winner")
    db.commit()

    body = client.get("/shows/1").get_data(as_text=True)
    assert "Best Director" in body


def test_award_history_still_resolves_for_a_modern_season(client, db):
    seed_society(db)
    _add_show(db, "23/24", "Chicago")
    _add_award(db, 2024, "Chicago", category_name="Best Choreography", result="Nominee")
    db.commit()

    body = client.get("/shows/1").get_data(as_text=True)
    assert "Best Choreography" in body


def test_a_bare_production_row_is_not_rendered_as_an_award(client, db):
    """admin.bulk_historical_productions writes a historical_results row with
    no category and no result - it says the production happened, not that it
    was nominated for anything."""
    seed_society(db)
    _add_show(db, "18/19", "Cabaret", source="historical")
    _add_award(db, 2019, "Cabaret", category_name=None, result=None)
    db.commit()

    body = client.get("/shows/1").get_data(as_text=True)
    assert "Awards &amp; nominations" not in body


def test_another_societys_award_record_is_not_borrowed(client, db):
    seed_society(db, id=1, name="First Society")
    seed_society(db, id=2, name="Second Society")
    _add_show(db, "18/19", "Cabaret", society_id=1, source="historical")
    _add_award(db, 2019, "Cabaret", society_id=2, society_name="Second Society",
               category_name="Best Director", result="Winner")
    db.commit()

    body = client.get("/shows/1").get_data(as_text=True)
    assert "Best Director" not in body
