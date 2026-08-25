"""match_show_for_edit (app/blueprints/admin/historical_reviews.py) used to be
an exact-string match only, so a review title differing from the shows table
only by case/punctuation/whitespace (e.g. 'RENT' vs 'Rent') wrongly fell
through to no_show_match. Fixed 2026-08-25 to also try a normalization-
insensitive match (similarity.normalize_title) scoped to that same
society+season - not fuzzy matching (CLAUDE.md forbids that; Frozen and
Frozen Jr. must stay distinct shows)."""
from conftest import seed_society

from app.blueprints.admin.historical_reviews import match_show_for_edit


def _add_show(db, society_id, season, show, moderation_status="approved"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?)",
        (society_id, season, show, moderation_status),
    )
    db.commit()
    return db.execute(
        "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ?",
        (society_id, season, show),
    ).fetchone()["id"]


def test_exact_match_still_works(client, db):
    society_id = seed_society(db)
    show_id = _add_show(db, society_id, "22/23", "Oliver!")

    assert match_show_for_edit(db, society_id, "22/23", "Oliver!") == show_id


def test_matches_a_case_variant(client, db):
    society_id = seed_society(db)
    show_id = _add_show(db, society_id, "22/23", "RENT")

    assert match_show_for_edit(db, society_id, "22/23", "Rent") == show_id


def test_matches_a_punctuation_and_whitespace_variant(client, db):
    society_id = seed_society(db)
    show_id = _add_show(db, society_id, "22/23", "Oliver!")

    assert match_show_for_edit(db, society_id, "22/23", "  oliver  ") == show_id


def test_does_not_fuzzy_match_a_genuinely_different_title(client, db):
    """The whole point of normalize_title over a similarity threshold:
    Frozen and Frozen Jr. must never be treated as the same show."""
    society_id = seed_society(db)
    _add_show(db, society_id, "22/23", "Frozen Jr.")

    assert match_show_for_edit(db, society_id, "22/23", "Frozen") is None


def test_does_not_match_a_different_society(client, db):
    society_a = seed_society(db, id=1, name="Alpha Musical Society")
    society_b = seed_society(db, id=2, name="Beta Musical Society")
    _add_show(db, society_a, "22/23", "RENT")

    assert match_show_for_edit(db, society_b, "22/23", "Rent") is None


def test_does_not_match_a_different_season(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "22/23", "RENT")

    assert match_show_for_edit(db, society_id, "23/24", "Rent") is None


def test_does_not_match_an_unapproved_show(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "22/23", "RENT", moderation_status="pending")

    assert match_show_for_edit(db, society_id, "22/23", "Rent") is None


def test_returns_none_with_no_society(client, db):
    assert match_show_for_edit(db, None, "22/23", "Rent") is None


def test_returns_none_with_no_candidate_shows(client, db):
    society_id = seed_society(db)
    assert match_show_for_edit(db, society_id, "22/23", "Rent") is None
