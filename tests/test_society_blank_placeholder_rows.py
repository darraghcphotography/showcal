"""Reported 2026-08-29 (Thurles Musical Society's live page): a completely
blank "27/28 | TBA | - | - | TBA" row sat at the top of Show history. It is a
placeholder slot imported from AIMS's own schedule before the society picked
a show - every field but society_id/season/source is NULL. 142 such rows
exist in production (111 for 27/28, 30 for 26/27, 1 for 25/26), so this
clutters the top of many society pages, not just this one.

A public visitor has nothing to do with such a row (no show to click, no date
to read); a logged-in moderator does - for them it's a real to-do with an
Edit link. So it's hidden from the public only.

Also pins the "Not recorded" vs "TBA" wording, which used to compare season
strings directly in the template - the same 1999/2000-rollover bug as
test_society_season_string_sort_bug.py, so an old dateless show could wrongly
read "TBA" (implying upcoming) instead of "Not recorded" (a real gap).
"""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_blank_row(db, society_id, season):
    """A placeholder exactly as import_csv.py creates it: a season slot and
    nothing else."""
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, ?, 'Eastern', NULL, 'import', 'approved')",
        (society_id, season),
    )


def _add_real_show(db, society_id, season, show, opening_date=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, opening_date) "
        "VALUES (?, ?, 'Eastern', ?, 'import', 'approved', ?)",
        (society_id, season, show, opening_date),
    )


def test_blank_future_placeholder_is_hidden_from_the_public(client, db):
    society_id = seed_society(db)
    _add_real_show(db, society_id, "25/26", "The Hunchback of Notre Dame", opening_date="2026-03-24")
    _add_blank_row(db, society_id, "27/28")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "The Hunchback of Notre Dame" in body
    assert "27/28" not in body


def test_a_moderator_still_sees_the_blank_placeholder(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db)
    _add_real_show(db, society_id, "25/26", "The Hunchback of Notre Dame", opening_date="2026-03-24")
    _add_blank_row(db, society_id, "27/28")
    db.commit()

    login_as(client, admin_id)
    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "27/28" in body
    assert "TBA" in body


def test_a_blank_row_for_a_past_season_still_shows_publicly(client, db):
    """Not an empty future slot - a genuine hole in the historical record,
    which is worth showing and is worded differently."""
    society_id = seed_society(db)
    _add_real_show(db, society_id, "25/26", "The Hunchback of Notre Dame", opening_date="2026-03-24")
    _add_blank_row(db, society_id, "12/13")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "12/13" in body
    assert "No date on record" in body


def test_an_old_dateless_titled_show_reads_not_recorded_not_tba(client, db):
    """The wording bug: '79/80' > '25/26' as a plain string, so this used to
    read "TBA" - implying an upcoming show rather than a missing date on a
    show staged decades ago."""
    society_id = seed_society(db)
    _add_real_show(db, society_id, "25/26", "The Hunchback of Notre Dame", opening_date="2026-03-24")
    _add_real_show(db, society_id, "79/80", "My Fair Lady")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    history = body.split("Show history")[1]
    assert "My Fair Lady" in history
    assert "No date on record" in history
