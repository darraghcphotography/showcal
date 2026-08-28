"""C3 (small-items queue): society.py's bulk-add route re-implemented
_read_form()/_validate() by hand for its "_{i}"-suffixed fields (one row per
society, up to BULK_ROWS at once) rather than reusing the single-show
versions of those helpers. Both now take an optional suffix, so bulk_add()
calls the same two functions the single-show form does."""
from conftest import seed_invite_code, seed_society


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def test_bulk_add_inserts_a_valid_row(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-BULK01", society_id=society_id)
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/bulk",
        data={"season_0": "24/25", "show_0": "Oliver!", "confirm_0": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.execute("SELECT * FROM shows WHERE society_id = ?", (society_id,)).fetchone()
    assert row["show"] == "Oliver!"
    assert row["season"] == "24/25"


def test_bulk_add_rejects_a_row_with_a_bad_season(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-BULK02", society_id=society_id)
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/bulk",
        data={"season_0": "not-a-season", "show_0": "Oliver!", "confirm_0": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 200  # re-renders with the row's own error
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 0


def test_bulk_add_leaves_a_fully_blank_row_alone(client, db):
    """A row with nothing filled in isn't an error - it's just unused."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-BULK03", society_id=society_id)
    unlock_society(client, code_id)

    resp = client.post(
        "/society/shows/bulk",
        data={"season_0": "24/25", "show_0": "Oliver!", "confirm_0": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Only row 0 was filled in - rows 1..9 stayed blank and inserted nothing.
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 1
