"""The collapsed-societies queue: detecting, proposing, moving, undoing.

What is being protected: award records decades old, held nowhere else, can be
moved between societies from a web page. So these care most about the boring
parts - that nothing moves without a decision, that what moves is exactly the
season and section asked for, and that it comes back.

Background, and why the unit is a season-and-section rather than a row:
`docs/collapsed-societies.md` and `app/collapsed_societies.py`.
"""
import pytest
from conftest import seed_user

from app import collapsed_societies


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def society(db, name, section="Gilbert"):
    return db.execute(
        "INSERT INTO societies (name, region, section) VALUES (?, 'Midlands', ?) RETURNING id",
        (name, section),
    ).fetchone()[0]


def award(db, society_id, year, tier, show="A Show", nominee="A Person",
          category="Best Actor", society_name="Athlone Musical Society"):
    return db.execute(
        """
        INSERT INTO historical_results
               (year, tier, category_name, result, show, society_name,
                society_id, nominee_name)
        VALUES (?, ?, ?, 'Nominee', ?, ?, ?, ?) RETURNING id
        """,
        (year, tier, category, show, society_name, society_id, nominee),
    ).fetchone()[0]


def suggest(db, society_id, year, tier, name, suggested_id=None, confidence=1,
            row_count=1):
    db.execute(
        """
        INSERT INTO collapsed_society_suggestions
               (society_id, year, tier, suggested_name, suggested_id, confidence,
                row_count, evidence_url, evidence_capture)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'http://aims.ie/awards/', '20040623091916')
        """,
        (society_id, year, tier, name, suggested_id, confidence, row_count),
    )


@pytest.fixture
def collapsed(client, db):
    """One society with both sections in 2004 - the real Athlone shape - and a
    moderator already logged in."""
    athlone = society(db, "Athlone Musical Society")
    other = society(db, "Clane Musical Society", "Sullivan")
    award(db, athlone, 2004, "Gilbert", "The Hired Man", "Gilbert Person")
    award(db, athlone, 2004, "Sullivan", "My Fair Lady", "Brian Brady")
    award(db, athlone, 2004, "Sullivan", "My Fair Lady", "Pat Naughton",
          category="Best Male Singer")
    db.commit()
    login_as(client, seed_user(db, username="mod", role="moderator"))
    return {"athlone": athlone, "other": other}


def rows_under(db, society_id, year, tier):
    return db.execute(
        "SELECT COUNT(*) FROM historical_results WHERE society_id = ? AND year = ? AND tier = ?",
        (society_id, year, tier),
    ).fetchone()[0]


def decision_count(db):
    return db.execute("SELECT COUNT(*) FROM collapsed_society_decisions").fetchone()[0]


# --------------------------------------------------------------------------
# Detecting
# --------------------------------------------------------------------------

def test_a_society_in_both_sections_in_one_season_is_flagged(db, collapsed):
    flagged = collapsed_societies.conflicted_societies(db)
    assert [r["name"] for r in flagged] == ["Athlone Musical Society"]
    assert flagged[0]["award_rows"] == 3


def test_one_section_a_season_is_not_flagged(db):
    sid = society(db, "Ordinary Musical Society")
    award(db, sid, 2004, "Gilbert")
    award(db, sid, 2005, "Sullivan")
    db.commit()
    assert collapsed_societies.conflicted_societies(db) == []


def test_a_row_with_no_section_is_not_a_side_of_anything(db):
    # Pre-2001 rows carry no tier. They cannot be reassigned on this evidence,
    # so they must not create a conflict either.
    sid = society(db, "Old Musical Society")
    award(db, sid, 1998, None)
    award(db, sid, 1998, "Gilbert")
    db.commit()
    assert collapsed_societies.conflicted_societies(db) == []


def test_a_flagged_societys_unconflicted_seasons_are_listed_too(db, collapsed):
    # This is where 2008 hid: only one of the two societies was nominated that
    # year, so nothing flagged it, and the rows were misfiled all the same.
    award(db, collapsed["athlone"], 2008, "Sullivan", "Pirates of Penzance")
    db.commit()

    groups = collapsed_societies.groups_for(collapsed["athlone"], db)
    lonely = next(g for g in groups if g["year"] == 2008)
    assert lonely["in_conflict"] == 0
    assert lonely["row_count"] == 1


# --------------------------------------------------------------------------
# The dashboard counter
# --------------------------------------------------------------------------

def test_the_counter_ignores_a_conflict_with_no_evidence(db, collapsed):
    # A number no amount of moderating could clear is worse than no number.
    assert collapsed_societies.undecided_count(db) == 0


def test_the_counter_counts_a_season_the_archive_speaks_for(db, collapsed):
    suggest(db, collapsed["athlone"], 2004, "Sullivan", "Athenry Musical Society")
    db.commit()
    assert collapsed_societies.undecided_count(db) == 1


def test_the_counter_can_reach_zero(client, db, collapsed):
    suggest(db, collapsed["athlone"], 2004, "Sullivan", "Clane Musical Society",
            collapsed["other"])
    db.commit()

    client.post("/admin/collapsed-societies/keep", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan"})

    assert collapsed_societies.undecided_count(db) == 0


# --------------------------------------------------------------------------
# Moving, and coming back
# --------------------------------------------------------------------------

def test_moving_a_season_moves_exactly_that_section(client, db, collapsed):
    response = client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to_id": collapsed["other"]}, follow_redirects=True)
    assert response.status_code == 200

    assert rows_under(db, collapsed["other"], 2004, "Sullivan") == 2
    assert rows_under(db, collapsed["athlone"], 2004, "Sullivan") == 0
    # The Gilbert side is untouched: it is this society's own record.
    assert rows_under(db, collapsed["athlone"], 2004, "Gilbert") == 1


def test_the_printed_name_moves_with_the_rows(client, db, collapsed):
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to_id": collapsed["other"]})

    names = {r[0] for r in db.execute(
        "SELECT society_name FROM historical_results WHERE society_id = ?",
        (collapsed["other"],))}
    assert names == {"Clane Musical Society"}


def test_a_move_is_undoable(client, db, collapsed):
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to_id": collapsed["other"]})
    client.post("/admin/collapsed-societies/undo", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan"})

    assert rows_under(db, collapsed["athlone"], 2004, "Sullivan") == 2
    assert rows_under(db, collapsed["other"], 2004, "Sullivan") == 0
    assert decision_count(db) == 0


def test_undo_restores_the_name_the_rows_carried(client, db, collapsed):
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to_id": collapsed["other"]})
    client.post("/admin/collapsed-societies/undo", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan"})

    names = {r[0] for r in db.execute(
        "SELECT society_name FROM historical_results WHERE society_id = ? AND tier = 'Sullivan'",
        (collapsed["athlone"],))}
    assert names == {"Athlone Musical Society"}


def test_keeping_a_season_moves_nothing(client, db, collapsed):
    client.post("/admin/collapsed-societies/keep", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan"})

    assert rows_under(db, collapsed["athlone"], 2004, "Sullivan") == 2
    decision = db.execute("SELECT * FROM collapsed_society_decisions").fetchone()
    assert decision["no_change"] == 1
    assert decision["moved_to_id"] is None


def test_a_move_to_the_same_society_is_refused(client, db, collapsed):
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to_id": collapsed["athlone"]})

    assert rows_under(db, collapsed["athlone"], 2004, "Sullivan") == 2
    assert decision_count(db) == 0


def test_a_move_to_a_society_we_do_not_hold_is_refused(client, db, collapsed):
    # Athenry is the real case: the archive is right and we have no row for it.
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to": "Athenry Musical Society"})

    assert rows_under(db, collapsed["athlone"], 2004, "Sullivan") == 2
    assert decision_count(db) == 0


def test_a_section_that_is_not_a_section_is_rejected(client, collapsed):
    response = client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Anything",
        "moved_to_id": collapsed["other"]})
    assert response.status_code == 400


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------

def test_the_queue_needs_a_login(client):
    response = client.get("/admin/collapsed-societies")
    assert response.status_code in (302, 401, 403)


def test_the_queue_shows_the_evidence_and_links_to_the_capture(client, db, collapsed):
    suggest(db, collapsed["athlone"], 2004, "Sullivan", "Athenry Musical Society")
    db.commit()

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "Athenry Musical Society" in body
    assert "web.archive.org/web/20040623091916" in body
    # Not applicable, and the page says so rather than offering a dead button.
    assert "not on our list" in body


def test_a_resolved_suggestion_offers_the_move(client, db, collapsed):
    suggest(db, collapsed["athlone"], 2004, "Sullivan", "Clane Musical Society",
            collapsed["other"])
    db.commit()

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "Move to Clane Musical Society" in body


def test_a_decided_season_offers_undo_rather_than_another_move(client, collapsed):
    client.post("/admin/collapsed-societies/keep", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan"})

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "correctly filed" in body
    assert "Undo" in body


# --------------------------------------------------------------------------
# Keeping the page to the decisions somebody can make
# --------------------------------------------------------------------------

def test_a_quiet_season_is_hidden_by_default_but_said_to_exist(client, db, collapsed):
    award(db, collapsed["athlone"], 2024, "Gilbert", "Urinetown", "Modern Person")
    db.commit()

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "Urinetown" not in body
    assert "1 other season" in body


def test_show_every_season_brings_the_quiet_ones_back(client, db, collapsed):
    # 2008 was exactly this shape, and it was really misfiled - so the quiet
    # seasons have to stay reachable and actionable, not just countable.
    award(db, collapsed["athlone"], 2008, "Sullivan", "Pirates of Penzance", "Someone")
    db.commit()

    body = client.get("/admin/collapsed-societies?all=1").get_data(as_text=True)
    assert "Pirates of Penzance" in body
    assert "Correctly filed" in body


def test_a_decided_quiet_season_stays_visible(client, db, collapsed):
    # Otherwise a decision would vanish the moment it was made, with no way
    # back to undo it.
    award(db, collapsed["athlone"], 2008, "Sullivan", "Pirates of Penzance", "Someone")
    db.commit()
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2008, "tier": "Sullivan",
        "moved_to_id": collapsed["other"]})

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "Pirates of Penzance" in body
    assert "Undo" in body


# --------------------------------------------------------------------------
# One hit is not the same evidence as seven
# --------------------------------------------------------------------------

def test_a_name_recurring_across_seasons_is_called_out(client, db, collapsed):
    award(db, collapsed["athlone"], 2005, "Sullivan", "South Pacific", "Someone Else")
    db.commit()
    suggest(db, collapsed["athlone"], 2004, "Sullivan", "Clane Musical Society",
            collapsed["other"])
    suggest(db, collapsed["athlone"], 2005, "Sullivan", "Clane Musical Society",
            collapsed["other"])
    db.commit()

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "The archive keeps naming:" in body
    assert "Clane Musical Society (2 seasons)" in body
    assert "one season only" not in body


def test_a_single_hit_is_flagged_as_such(client, db, collapsed):
    suggest(db, collapsed["athlone"], 2004, "Sullivan", "Clane Musical Society",
            collapsed["other"])
    db.commit()

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "one season only" in body
    # Flagged, not hidden - the queue reports, it does not decide.
    assert "Move to Clane Musical Society" in body


# --------------------------------------------------------------------------
# A correction must not hide itself
# --------------------------------------------------------------------------

def test_a_fully_separated_society_stays_on_the_page(client, db, collapsed):
    # Moving the Sullivan side is what makes the conflict go away, so the
    # society drops out of the detector - and with it would go its decisions,
    # its evidence and its Undo. Found on a rehearsal against a copy of the
    # live database, with the real Athenry data, before it reached production.
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to_id": collapsed["other"]})

    assert collapsed_societies.conflicted_societies(db) == []

    body = client.get("/admin/collapsed-societies").get_data(as_text=True)
    assert "Athlone Musical Society" in body
    assert ">Undo<" in body


def test_the_undo_still_works_once_the_conflict_is_gone(client, db, collapsed):
    client.post("/admin/collapsed-societies/move", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan",
        "moved_to_id": collapsed["other"]})
    client.post("/admin/collapsed-societies/undo", data={
        "society_id": collapsed["athlone"], "year": 2004, "tier": "Sullivan"})

    assert rows_under(db, collapsed["athlone"], 2004, "Sullivan") == 2
    assert decision_count(db) == 0
