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
