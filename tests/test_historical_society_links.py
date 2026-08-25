"""Linking historical award records to a current society.

The headline test here is durability across a re-import: import_awards.py wipes
and reloads every source='import' row, and all ~540 unmatched rows are
source='import'. A society_id written only onto those rows is destroyed
silently on the next awards import, which is why the decision lives in
historical_society_links keyed on the printed name."""
import csv

from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _award(db, society_name, year=1990, show="Some Show", source="import"):
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, society_id, source) "
        "VALUES (?, ?, ?, NULL, ?)",
        (year, show, society_name, source),
    )
    db.commit()


# --- durability -------------------------------------------------------------

def test_a_confirmed_link_survives_an_awards_reimport(tmp_path, app, db):
    """The bug this whole feature exists for. Without the overlay in
    import_awards.py, the DELETE would throw this link away with no warning."""
    import import_awards

    society_id = seed_society(db, name="Real Society")
    db.execute(
        "INSERT INTO historical_society_links (society_name, society_id, no_match) VALUES (?, ?, 0)",
        ("Olde Printed Name", society_id),
    )
    db.commit()

    csv_path = tmp_path / "awards.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Year", "Section", "CategoryName", "Result", "Showname", "ResolvedSocietyName", "NomineeName", "Role"])
        w.writerow(["1990", "Gilbert", "Best Actor", "Winner", "Some Show", "Olde Printed Name", "", ""])

    import_awards.main([
        "--db", app.config["DATABASE"], "--csv", str(csv_path),
    ])

    row = db.execute(
        "SELECT society_id FROM historical_results WHERE society_name = 'Olde Printed Name'"
    ).fetchone()
    assert row is not None, "the row should have been re-imported"
    assert row["society_id"] == society_id, "the confirmed link should have been re-applied"


def test_a_link_pointing_at_a_deleted_society_is_skipped_not_written(tmp_path, app, db):
    """The foreign key stops a dangling link being created through the app - but
    import_awards.py connects without `PRAGMA foreign_keys = ON` (unlike
    app/db.py), so it can still meet one in a database that was restored or
    edited outside the app. Set up here the same way that script would see it."""
    import import_awards

    db.execute("PRAGMA foreign_keys = OFF")
    db.execute(
        "INSERT INTO historical_society_links (society_name, society_id, no_match) VALUES (?, ?, 0)",
        ("Ghost Name", 9999),  # no such society
    )
    db.commit()
    db.execute("PRAGMA foreign_keys = ON")

    csv_path = tmp_path / "awards.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Year", "Section", "CategoryName", "Result", "Showname", "ResolvedSocietyName", "NomineeName", "Role"])
        w.writerow(["1990", "Gilbert", "Best Actor", "Winner", "Some Show", "Ghost Name", "", ""])

    import_awards.main(["--db", app.config["DATABASE"], "--csv", str(csv_path)])

    row = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Ghost Name'").fetchone()
    assert row["society_id"] is None


# --- the queue --------------------------------------------------------------

def test_queue_lists_one_row_per_name_not_per_record(client, db):
    admin_id = seed_user(db)
    for year in (1990, 1991, 1992):
        _award(db, "Defunct Operatic Society", year=year)
    login_as(client, admin_id)

    body = client.get("/admin/historical-society-links").get_data(as_text=True)
    assert body.count("Defunct Operatic Society") >= 1
    assert ">3<" in body  # the record count for the single grouped row


def test_queue_requires_login(client):
    assert client.get("/admin/historical-society-links").status_code == 302


def test_linking_applies_to_every_row_with_that_name(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Real Society")
    for year in (1990, 1991):
        _award(db, "Olde Name", year=year)
    login_as(client, admin_id)

    resp = client.post("/admin/historical-society-links/link", data={
        "society_name": "Olde Name", "society_id": society_id,
    }, follow_redirects=False)
    assert resp.status_code == 302

    rows = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Olde Name'").fetchall()
    assert [r["society_id"] for r in rows] == [society_id, society_id]
    link = db.execute("SELECT * FROM historical_society_links WHERE society_name = 'Olde Name'").fetchone()
    assert link["society_id"] == society_id and link["no_match"] == 0


def test_linking_never_repoints_a_row_matched_by_hand(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Real Society")
    other_id = seed_society(db, id=2, name="Other Society")
    _award(db, "Olde Name")
    db.execute("UPDATE historical_results SET society_id = ? WHERE society_name = 'Olde Name'", (other_id,))
    db.commit()
    login_as(client, admin_id)

    client.post("/admin/historical-society-links/link",
                data={"society_name": "Olde Name", "society_id": society_id})

    row = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Olde Name'").fetchone()
    assert row["society_id"] == other_id


def test_no_match_clears_the_name_from_the_queue_without_touching_rows(client, db):
    admin_id = seed_user(db)
    _award(db, "Truly Defunct Society")
    login_as(client, admin_id)

    client.post("/admin/historical-society-links/no-match",
                data={"society_name": "Truly Defunct Society"})

    row = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Truly Defunct Society'").fetchone()
    assert row["society_id"] is None
    link = db.execute("SELECT * FROM historical_society_links WHERE society_name = 'Truly Defunct Society'").fetchone()
    assert link["no_match"] == 1

    body = client.get("/admin/historical-society-links").get_data(as_text=True)
    assert "Every printed name has been decided" in body


def test_no_match_is_bulk_submittable(client, db):
    admin_id = seed_user(db)
    _award(db, "Defunct One")
    _award(db, "Defunct Two")
    login_as(client, admin_id)

    client.post("/admin/historical-society-links/no-match",
                data={"society_name": ["Defunct One", "Defunct Two"]})

    assert db.execute("SELECT COUNT(*) FROM historical_society_links WHERE no_match = 1").fetchone()[0] == 2


def test_clear_fully_reverses_a_link(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Real Society")
    _award(db, "Olde Name")
    login_as(client, admin_id)
    client.post("/admin/historical-society-links/link",
                data={"society_name": "Olde Name", "society_id": society_id})

    client.post("/admin/historical-society-links/clear", data={"society_name": "Olde Name"})

    row = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Olde Name'").fetchone()
    assert row["society_id"] is None
    assert db.execute("SELECT 1 FROM historical_society_links WHERE society_name = 'Olde Name'").fetchone() is None


def test_clear_does_not_blank_a_row_pointed_elsewhere_since(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Real Society")
    other_id = seed_society(db, id=2, name="Other Society")
    _award(db, "Olde Name")
    login_as(client, admin_id)
    client.post("/admin/historical-society-links/link",
                data={"society_name": "Olde Name", "society_id": society_id})
    # A moderator then re-points that row somewhere else by hand.
    db.execute("UPDATE historical_results SET society_id = ? WHERE society_name = 'Olde Name'", (other_id,))
    db.commit()

    client.post("/admin/historical-society-links/clear", data={"society_name": "Olde Name"})

    row = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Olde Name'").fetchone()
    assert row["society_id"] == other_id


def test_linking_marks_productions_stale(client, db):
    """An in-place UPDATE moves neither COUNT(*) nor MAX(id), so the freshness
    fingerprint can't see it - mark_stale is the only thing that makes the
    rebuild happen."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Real Society")
    _award(db, "Olde Name")
    login_as(client, admin_id)
    db.execute("DELETE FROM productions_build_state")
    db.execute("INSERT INTO productions_build_state (id, fingerprint) VALUES (1, 'stale-marker')")
    db.commit()

    client.post("/admin/historical-society-links/link",
                data={"society_name": "Olde Name", "society_id": society_id})

    state = db.execute("SELECT fingerprint FROM productions_build_state WHERE id = 1").fetchone()
    assert state is None or state["fingerprint"] != "stale-marker"


# --- dashboard --------------------------------------------------------------

def test_dashboard_counter_counts_names_not_rows(client, db):
    admin_id = seed_user(db)
    for year in (1990, 1991, 1992):
        _award(db, "One Defunct Name", year=year)
    login_as(client, admin_id)

    from app.blueprints.admin.historical_society_links import undecided_name_count
    assert undecided_name_count(db) == 1

    body = client.get("/admin/").get_data(as_text=True)
    assert "Award-archive society names awaiting a link decision" in body


def test_the_permanent_row_count_is_left_alone(client, db):
    """The "Won't reach zero" framing is correct and must survive - that count
    is rows, and most of those societies really are gone for good."""
    admin_id = seed_user(db)
    for year in (1990, 1991, 1992):
        _award(db, "One Defunct Name", year=year)
    login_as(client, admin_id)

    body = client.get("/admin/").get_data(as_text=True)
    assert "Won't reach zero" in body
    assert "Award records with no society match" in body


def test_manual_pick_accepts_a_typed_society_name(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Real Society")
    _award(db, "Olde Name")
    login_as(client, admin_id)

    client.post("/admin/historical-society-links/link",
                data={"society_name": "Olde Name", "society": "Real Society"})

    row = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Olde Name'").fetchone()
    assert row["society_id"] == society_id


def test_manual_pick_rejects_a_name_that_is_not_a_society(client, db):
    admin_id = seed_user(db)
    seed_society(db, name="Real Society")
    _award(db, "Olde Name")
    login_as(client, admin_id)

    client.post("/admin/historical-society-links/link",
                data={"society_name": "Olde Name", "society": "Not A Society"})

    row = db.execute("SELECT society_id FROM historical_results WHERE society_name = 'Olde Name'").fetchone()
    assert row["society_id"] is None


def test_the_queue_does_not_render_a_full_society_select_per_row(client, db):
    """69 rows x a 194-option <select> made this page 1.5MB - the same class of
    problem as the per-row fuzzy matching that once 524'd the site. One shared
    <datalist> is the fix, so guard it."""
    admin_id = seed_user(db)
    for i in range(12):
        seed_society(db, id=i + 1, name=f"Society {i}")
    for i in range(12):
        _award(db, f"Defunct Name {i}", year=1990 + i)
    login_as(client, admin_id)

    body = client.get("/admin/historical-society-links").get_data(as_text=True)
    assert body.count("<datalist") == 1
    # The invariant that matters: the society list is rendered ONCE, so option
    # count tracks the number of societies, not societies x queue rows.
    assert body.count("<option") == 12
