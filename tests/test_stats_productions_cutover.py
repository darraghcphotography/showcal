"""/stats reads its production counts from the productions table (info.py's
stats()), the first surface cut over in the productions migration.

The behaviour worth pinning is what the old five-query merge got wrong: every
season before 00/01 reported zero, because the 'yy/yy' round-trip it leaned on
couldn't express an award year before 2001.
"""
import re

from conftest import seed_society


def _add_award(db, year, show, society_name="Test Society", society_id=None, result="Nominee"):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, society_id, source) "
        "VALUES (?, 'Gilbert', 'Best Overall Show', ?, ?, ?, ?, 'manual')",
        (year, result, show, society_name, society_id),
    )


def _row(body, label):
    """The (productions, reviewed) pair on the season row labelled `label`."""
    match = re.search(
        r"<td>%s</td>\s*<td>(\d+)</td>\s*<td>(\d+)</td>" % re.escape(label), body
    )
    return (int(match.group(1)), int(match.group(2))) if match else None


def test_a_pre_2001_award_year_is_counted_at_all(client, db):
    """The 823-production hole. An award year before 2001 used to land on a
    season key that no lookup could ever match, so its whole season read 0."""
    seed_society(db)
    _add_award(db, 1995, "Carousel", society_id=1)
    _add_award(db, 1995, "Oklahoma!", society_id=1)
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert _row(body, "94/95") == (2, 0)


def test_the_headline_total_includes_those_seasons(client, db):
    seed_society(db)
    _add_award(db, 1995, "Carousel", society_id=1)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (1, '24/25', 'Eastern', 'Chicago', '2024-11-01', '2024-11-05', 'approved')"
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    total = re.search(r'stat-value">(\d+)</span>\s*<span class="stat-label">Productions on record', body)
    assert int(total.group(1)) == 2


def test_1912_and_2012_are_counted_as_different_seasons(client, db):
    """Both display as '11/12'. The old code resolved them to the same key."""
    seed_society(db)
    _add_award(db, 1912, "The Mikado", society_id=1)
    _add_award(db, 2012, "Legally Blonde", society_id=1)
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    total = re.search(r'stat-value">(\d+)</span>\s*<span class="stat-label">Productions on record', body)
    assert int(total.group(1)) == 2


def test_a_show_and_its_award_record_are_not_counted_twice(client, db):
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (1, '23/24', 'Eastern', 'Chicago', '2023-11-01', '2023-11-05', 'approved')"
    )
    _add_award(db, 2024, "Chicago", society_id=1)
    _add_award(db, 2024, "Chicago", society_id=1, result="Winner")
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert _row(body, "23/24") == (1, 0)


def test_reviews_count_as_coverage_of_the_same_total(client, db):
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (1, '18/19', 'Eastern', 'Cabaret', 'historical', 'approved')"
    )
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, show_id, moderation_status) "
        "VALUES ('18/19', 'Cabaret', 'Test Society', 'A fine show.', 1, 'approved')"
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert _row(body, "18/19") == (1, 1)


def test_the_thin_pre_1976_archive_folds_into_one_labelled_row(client, db):
    seed_society(db)
    _add_award(db, 1954, "The Mikado", society_id=1)
    _add_award(db, 1960, "Carousel", society_id=1)
    _add_award(db, 1990, "Oliver!", society_id=1)
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert _row(body, "89/90") == (1, 0)
    assert _row(body, "1953&ndash;1960") == (2, 0)
    note = " ".join(body.split())
    assert "row is one line rather than 2" in note
    assert "1 society whose own production histories" in note


def test_no_deep_archive_row_when_nothing_is_that_old(client, db):
    seed_society(db)
    _add_award(db, 1990, "Oliver!", society_id=1)
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    assert "whose own production histories" not in body


def test_the_region_filter_still_narrows_every_era(client, db):
    seed_society(db, id=1, name="Eastern Society", region="Eastern")
    seed_society(db, id=2, name="Western Society", region="Western")
    _add_award(db, 1995, "Carousel", society_name="Eastern Society", society_id=1)
    _add_award(db, 1995, "Oklahoma!", society_name="Western Society", society_id=2)
    db.commit()

    body = client.get("/stats?region=Eastern").get_data(as_text=True)
    assert _row(body, "94/95") == (1, 0)


def test_an_unmatched_historical_society_still_counts(client, db):
    """No societies row, no region - it still staged the show. Counted in the
    all-regions view, left out of a region-filtered one (unchanged behaviour,
    it can't be placed)."""
    _add_award(db, 1995, "Carousel", society_name="Long Gone Operatic Society")
    db.commit()

    assert _row(client.get("/stats").get_data(as_text=True), "94/95") == (1, 0)
    assert _row(client.get("/stats?region=Eastern").get_data(as_text=True), "94/95") is None


def test_an_upcoming_show_is_not_counted_as_having_happened(client, db):
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (1, '27/28', 'Eastern', 'Wicked', '2099-01-01', '2099-01-05', 'approved')"
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    total = re.search(r'stat-value">(\d+)</span>\s*<span class="stat-label">Productions on record', body)
    assert int(total.group(1)) == 0


def test_a_cancelled_show_is_not_counted(client, db):
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, status, moderation_status) "
        "VALUES (1, '23/24', 'Eastern', 'Chicago', '2023-11-01', '2023-11-05', 'Cancelled', 'approved')"
    )
    db.commit()

    body = client.get("/stats").get_data(as_text=True)
    total = re.search(r'stat-value">(\d+)</span>\s*<span class="stat-label">Productions on record', body)
    assert int(total.group(1)) == 0


def test_the_page_picks_up_a_show_added_since_the_last_build(client, db):
    """The table is derived, so /stats refreshes it when the sources have
    moved - a moderator shouldn't have to wait for a redeploy to see a show
    counted."""
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (1, '23/24', 'Eastern', 'Chicago', '2023-11-01', '2023-11-05', 'approved')"
    )
    db.commit()
    assert _row(client.get("/stats").get_data(as_text=True), "23/24") == (1, 0)

    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (1, '23/24', 'Eastern', 'Cabaret', '2023-11-01', '2023-11-05', 'approved')"
    )
    db.commit()
    assert _row(client.get("/stats").get_data(as_text=True), "23/24") == (2, 0)


def test_only_recent_seasons_link_to_a_season_page(client, db):
    """/season has no content for a season the shows table doesn't cover -
    the earlier table used to render a View link on every row regardless."""
    seed_society(db)
    _add_award(db, 1995, "Carousel", society_id=1)
    db.commit()

    inside = client.get("/stats").get_data(as_text=True).split("<details>")[1].split("</details>")[0]
    assert "94/95" in inside
    assert "season=94%2F95" not in inside
