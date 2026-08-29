"""Person identity resolution, internal only (app/people.py, /admin/people).

The same human is in this database several times over - as an award nominee,
as a show credit a society typed in, with and without a fada or an honorific -
and /admin/backfill-credits keeps adding more free text, so it grows untouched.

Two things these tests are really protecting:

* **Precision over recall.** A false "same person" quietly merges two real
  people's award records. Anything that could be two people must not be
  offered at full confidence, and father/son suffixes must never collapse.
* **The archive is never rewritten.** A merge writes to people/person_aliases
  only; historical_results and the shows credit columns keep their original
  text, which is what makes a merge undoable.
"""
from conftest import seed_society, seed_user

from app.people import fold, find_candidates, name_parts, normalized


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_nominee(db, name, year=2019, show="Oliver!"):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, "
        "society_name, society_id, nominee_name, source) "
        "VALUES (?, 'Gilbert', 'Best Actor', 'Winner', ?, 'Test Society', 1, ?, 'manual')",
        (year, show, name),
    )
    db.commit()


def seed_credit(db, name, column="director", season="25/26"):
    db.execute(
        f"INSERT INTO shows (society_id, season, region, section, show, {column}, "
        "moderation_status, source) "
        "VALUES (1, ?, 'Eastern', 'Gilbert', 'Test Show', ?, 'approved', 'import')",
        (season, name),
    )
    db.commit()


# --- the matcher itself -----------------------------------------------------

def test_folding_handles_the_four_differences_that_actually_occur():
    assert fold("Áine Gilmore") == fold("Aine Gilmore")
    assert fold("O'Brien") == fold("O’Brien")      # straight vs curly apostrophe
    assert fold("Mairead McKenna") == fold("Mairead Mckenna")
    assert fold("Ronan  P.  Byrne") == fold("Ronan P Byrne")


def test_an_honorific_is_not_part_of_the_name():
    assert normalized("Fr Noel Cannon") == normalized("Noel Cannon")
    assert normalized("Fr. John O'Brien") == normalized("John O’Brien")


def test_entries_naming_several_people_are_left_alone():
    """"Aaron Stone, Alan Maleady and Art McGuaran" is three people in one
    field - a data-quality problem, not an identity one. Giving it a canonical
    record would invent a person who does not exist."""
    for entry in [
        "Aaron Stone, Alan Maleady and Art McGuaran",
        "Paddy Boland & Johnny Kelly",
        "Claire Tighe / Jen Dawson",
    ]:
        assert name_parts(entry) is None, entry


def test_junk_and_mononyms_are_left_alone():
    for entry in ["", "-", "   ", "Madonna", None]:
        assert name_parts(entry) is None, entry


def test_the_same_name_written_differently_is_found():
    pairs = find_candidates(["Aine Foley", "Áine Foley"])
    assert len(pairs) == 1
    assert pairs[0][2] == 1.0
    assert pairs[0][3] == "same name, written differently"


def test_an_initial_matches_a_full_first_name():
    pairs = find_candidates(["A Gilmore", "Aine Gilmore"])
    assert len(pairs) == 1
    assert "initial" in pairs[0][3]


def test_an_initial_with_the_wrong_letter_is_not_a_match():
    assert find_candidates(["B Gilmore", "Aine Gilmore"]) == []


def test_different_surnames_are_never_compared():
    """The lesson from society-name matching: a whole-string ratio on names
    that share shape is misleading. Blocking on surname is what prevents it."""
    assert find_candidates(["Alan McClarty", "Alan McCarthy"]) == []


def test_a_suffix_keeps_a_father_and_son_apart():
    """The bug this test exists for: stripping "Senior" as noise paired "Sean
    Costello" with "Sean Costello Senior" at full confidence. A suffix is the
    one part of a name whose whole job is telling two people apart."""
    assert find_candidates(["Sean Costello", "Sean Costello Senior"]) == []


def test_short_first_names_are_not_scored_against_each_other():
    """Jo/Joe/Jon collide by coincidence and are three different people."""
    assert find_candidates(["Jo Ryan", "Joe Ryan"]) == []


def test_a_dismissed_pair_never_comes_back():
    names = ["Aine Foley", "Áine Foley"]
    assert find_candidates(names, dismissed=[("Aine Foley", "Áine Foley")]) == []
    # Order of the stored pair must not matter.
    assert find_candidates(names, dismissed=[("Áine Foley", "Aine Foley")]) == []


def test_the_matcher_stays_fast_on_a_realistic_number_of_names():
    """2,267 real names is 2.5M pairs swept naively - the shape that took the
    site down on 19 August. Blocking on surname must keep this trivial."""
    import time

    names = [f"Person{i} Surname{i % 400}" for i in range(2500)]
    started = time.time()
    find_candidates(names)
    assert time.time() - started < 2.0


# --- the admin queue --------------------------------------------------------

def test_the_queue_suggests_a_nominee_and_a_credit_as_one_person(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    seed_nominee(db, "Áine Gilmore")
    seed_credit(db, "Aine Gilmore")
    login_as(client, admin_id)

    body = client.get("/admin/people").get_data(as_text=True)
    assert "Aine Gilmore" in body
    assert "same name, written differently" in body


def test_merging_records_both_spellings_and_leaves_the_archive_alone(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    seed_nominee(db, "Áine Gilmore")
    seed_credit(db, "Aine Gilmore")
    login_as(client, admin_id)

    resp = client.post("/admin/people/merge",
                       data={"canonical": "Áine Gilmore", "other": "Aine Gilmore"})
    assert resp.status_code == 302

    person = db.execute("SELECT * FROM people").fetchone()
    assert person["canonical_name"] == "Áine Gilmore"
    aliases = {r["alias"] for r in db.execute("SELECT alias FROM person_aliases")}
    assert aliases == {"Áine Gilmore", "Aine Gilmore"}

    # The whole point: the archive still says exactly what it said before.
    assert db.execute("SELECT nominee_name FROM historical_results").fetchone()[0] == "Áine Gilmore"
    assert db.execute("SELECT director FROM shows").fetchone()[0] == "Aine Gilmore"


def test_a_merged_pair_leaves_the_queue(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    seed_nominee(db, "Áine Gilmore")
    seed_credit(db, "Aine Gilmore")
    login_as(client, admin_id)

    client.post("/admin/people/merge",
                data={"canonical": "Áine Gilmore", "other": "Aine Gilmore"})
    body = client.get("/admin/people").get_data(as_text=True)
    assert "Nothing left to review" in body


def test_a_third_spelling_joins_the_existing_person(client, db):
    """Not a second half-merged record - the whole reason _link looks for an
    existing person before creating one."""
    admin_id = seed_user(db)
    seed_society(db)
    login_as(client, admin_id)

    client.post("/admin/people/merge", data={"canonical": "Aine Gilmore", "other": "Áine Gilmore"})
    client.post("/admin/people/merge", data={"canonical": "Aine Gilmore", "other": "A Gilmore"})

    assert db.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM person_aliases").fetchone()[0] == 3


def test_dismissing_a_pair_keeps_it_out_of_the_queue(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    seed_nominee(db, "Louis Moore")
    seed_credit(db, "Louise Moore")
    login_as(client, admin_id)

    assert "Louise Moore" in client.get("/admin/people").get_data(as_text=True)
    client.post("/admin/people/dismiss",
                data={"name_a": "Louise Moore", "name_b": "Louis Moore"})

    body = client.get("/admin/people").get_data(as_text=True)
    assert "Nothing left to review" in body
    stored = db.execute("SELECT name_a, name_b FROM dismissed_person_pairs").fetchone()
    assert (stored["name_a"], stored["name_b"]) == ("Louis Moore", "Louise Moore")


def test_a_merge_can_be_undone(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    seed_nominee(db, "Áine Gilmore")
    seed_credit(db, "Aine Gilmore")
    login_as(client, admin_id)

    client.post("/admin/people/merge",
                data={"canonical": "Áine Gilmore", "other": "Aine Gilmore"})
    person_id = db.execute("SELECT id FROM people").fetchone()[0]

    client.post(f"/admin/people/{person_id}/unlink", data={"alias": "Aine Gilmore"})
    assert db.execute("SELECT COUNT(*) FROM person_aliases").fetchone()[0] == 1
    # The pair is a live suggestion again, which is what "undone" has to mean.
    assert "same name, written differently" in client.get("/admin/people").get_data(as_text=True)


def test_removing_the_last_spelling_removes_the_person(client, db):
    """An identity with no spellings attached is not a record of anything."""
    admin_id = seed_user(db)
    seed_society(db)
    login_as(client, admin_id)
    client.post("/admin/people/merge", data={"canonical": "Aine Gilmore", "other": "Áine Gilmore"})
    person_id = db.execute("SELECT id FROM people").fetchone()[0]

    client.post(f"/admin/people/{person_id}/unlink", data={"alias": "Áine Gilmore"})
    client.post(f"/admin/people/{person_id}/unlink", data={"alias": "Aine Gilmore"})
    assert db.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 0


def test_the_queue_needs_a_login(client, db):
    assert client.get("/admin/people").status_code in (302, 401, 403)


def test_there_is_no_public_person_surface(client, db):
    """Darragh's privacy objection was to public person pages. This feature
    exists inside /admin only, and that must stay true."""
    seed_society(db)
    for path in ["/people", "/person/1", "/people/1"]:
        assert client.get(path).status_code == 404, path


def test_the_dashboard_counts_open_pairs_and_can_reach_zero(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    seed_nominee(db, "Áine Gilmore")
    seed_credit(db, "Aine Gilmore")
    login_as(client, admin_id)

    assert "Names that may be the same person" in client.get("/admin/").get_data(as_text=True)
    client.post("/admin/people/merge",
                data={"canonical": "Áine Gilmore", "other": "Aine Gilmore"})

    from app.blueprints.admin.people import open_candidates

    assert open_candidates(db) == []
