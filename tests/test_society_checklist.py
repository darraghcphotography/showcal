"""Society coverage checklist + lifecycle status (2026-08-29).

Plan item 7, the largest thing on the board, built from
mockups/society_checklist_grid.html. One row per society, every column
derived from data already held - no new fields to maintain.

Two ideas carry it:

  - **Lifecycle status** is a moderator's judgement, separate from `section`.
    section says which AIMS adjudication tier a society competes in (or
    'Inactive'); it cannot say "wound up", "mid-hiatus" or "never in scope",
    and the checklist needs those to know who is worth chasing.
  - **"Checked, nothing to get"** is a real answer. Plenty of societies have
    no website and never will. Without a way to record that, the grid can
    only ever be filled and never finished - the same permanent-vs-fixable
    trap dismissed_duplicate_pairs and dismissed_venue_pairs exist to avoid.

The mockup carries no contact fields, so the privacy note ROADMAP attached
to this item (admin-only contact details must never leak publicly) does not
apply to what was actually built.
"""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _bare_society(db, society_id, name):
    """A society with every checklist field empty - six gaps."""
    return seed_society(db, id=society_id, name=name)


def _fill_everything(db, society_id):
    db.execute(
        """UPDATE societies SET about = 'A society.', default_venue = 'The Hall',
               facebook_url = 'https://fb.example', website_url = 'https://x.example',
               logo_filename = 'logo.webp', founded_year = 1950
           WHERE id = ?""",
        (society_id,),
    )


def test_a_bare_society_shows_every_field_as_a_gap(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "Gapful Society" in body
    assert "1 society with something outstanding" in body
    assert "6 gaps in total" in body


def test_a_fully_populated_society_has_no_gaps(client, db):
    _bare_society(db, 1, "Complete Society")
    _fill_everything(db, 1)
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "0 societies with something outstanding" in body
    assert "0 gaps in total" in body


def test_marking_a_field_checked_stops_it_counting(client, db):
    """The core idea: a society with no website genuinely has none, and that
    has to be recordable or this list never finishes."""
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    admin_id = seed_user(db)
    login_as(client, admin_id)

    resp = client.post("/admin/society-checklist/1/checked", data={"field": "web"})
    assert resp.status_code == 302

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "5 gaps in total" in body
    row = db.execute("SELECT * FROM society_field_checked WHERE society_id = 1").fetchone()
    assert row["field"] == "web"
    assert row["checked_by"] == "mod"


def test_a_checked_field_can_be_undone(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    client.post("/admin/society-checklist/1/checked", data={"field": "web"})
    client.post("/admin/society-checklist/1/checked", data={"field": "web", "undo": "1"})

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "6 gaps in total" in body
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 0


def test_an_unknown_field_is_rejected(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    resp = client.post("/admin/society-checklist/1/checked", data={"field": "bank_details"})
    assert resp.status_code == 400
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 0


def test_lifecycle_status_is_saved_and_validated(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    client.post("/admin/society-checklist/1/status", data={"lifecycle_status": "Dormant"})
    assert db.execute("SELECT lifecycle_status FROM societies WHERE id = 1").fetchone()[0] == "Dormant"

    resp = client.post("/admin/society-checklist/1/status", data={"lifecycle_status": "Exploded"})
    assert resp.status_code == 400
    assert db.execute("SELECT lifecycle_status FROM societies WHERE id = 1").fetchone()[0] == "Dormant"


def test_lifecycle_status_can_be_cleared_back_to_unset(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    client.post("/admin/society-checklist/1/status", data={"lifecycle_status": "Dormant"})
    client.post("/admin/society-checklist/1/status", data={"lifecycle_status": ""})
    assert db.execute("SELECT lifecycle_status FROM societies WHERE id = 1").fetchone()[0] is None


def test_a_closed_society_is_not_counted_as_outstanding(client, db):
    """A wound-up society is a settled answer, not a job."""
    _bare_society(db, 1, "Closed Society")
    db.commit()
    login_as(client, seed_user(db))

    client.post("/admin/society-checklist/1/status", data={"lifecycle_status": "Closed"})

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "0 societies with something outstanding" in body
    # Still listed - excluded from the count, not hidden.
    assert "Closed Society" in body


def test_societies_with_more_gaps_sort_first(client, db):
    _bare_society(db, 1, "Aaa Complete")
    _fill_everything(db, 1)
    _bare_society(db, 2, "Zzz Gapful")
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert body.index("Zzz Gapful") < body.index("Aaa Complete")


def test_closed_societies_sort_below_active_ones(client, db):
    _bare_society(db, 1, "Aaa Closed")
    _bare_society(db, 2, "Zzz Active")
    db.commit()
    login_as(client, seed_user(db))
    client.post("/admin/society-checklist/1/status", data={"lifecycle_status": "Closed"})

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert body.index("Zzz Active") < body.index("Aaa Closed")


def test_the_region_filter_narrows_the_grid(client, db):
    seed_society(db, id=1, name="Eastern Society", region="Eastern")
    seed_society(db, id=2, name="Western Society", region="Western")
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist?region=Western").get_data(as_text=True)
    assert "Western Society" in body
    assert "Eastern Society" not in body


def test_the_dashboard_counter_matches_and_can_reach_zero(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    dash = client.get("/admin/").get_data(as_text=True)
    assert "Societies with an unfilled profile gap" in dash
    row = dash.split("Societies with an unfilled profile gap")[1].split("</tr>")[0]
    assert "<td>1</td>" in row

    for field in ("about", "venue", "social", "web", "logo", "founded"):
        client.post("/admin/society-checklist/1/checked", data={"field": field})

    dash = client.get("/admin/").get_data(as_text=True)
    row = dash.split("Societies with an unfilled profile gap")[1].split("</tr>")[0]
    assert "<td>0</td>" in row


def test_the_checklist_requires_login(client, db):
    assert client.get("/admin/society-checklist").status_code == 302


def test_inactive_societies_sink_below_active_ones_by_default(client, db):
    """Found against real data: 194 societies, no lifecycle_status set on any
    of them, and the whole top of the grid was defunct panto companies with
    six gaps and no shows. They sorted first precisely because nobody will
    ever fill them in. section == 'Inactive' stands in until someone sets a
    lifecycle_status."""
    seed_society(db, id=1, name="Aaa Defunct Panto", section="Inactive")
    seed_society(db, id=2, name="Zzz Working Society", section="Gilbert")
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert body.index("Zzz Working Society") < body.index("Aaa Defunct Panto")
    # Both have six gaps, but only the active one is work.
    assert "1 society with something outstanding" in body


def test_an_explicit_status_overrides_the_inactive_fallback(client, db):
    """The fallback is only a default. Marking a revived society Active has
    to bring it back into the list."""
    seed_society(db, id=1, name="Revived Society", section="Inactive")
    db.commit()
    login_as(client, seed_user(db))

    assert "0 societies with something outstanding" in client.get(
        "/admin/society-checklist"
    ).get_data(as_text=True)

    client.post("/admin/society-checklist/1/status", data={"lifecycle_status": "Active"})

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "1 society with something outstanding" in body
