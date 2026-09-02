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
from werkzeug.datastructures import MultiDict

from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _bare_society(db, society_id, name):
    """A society with every checklist field empty - six gaps."""
    return seed_society(db, id=society_id, name=name)


ALL_FIELDS = ("about", "venue", "social", "web", "logo", "founded")


def _save(client, db, society_ids, statuses=None, ticked=(), editable=None):
    """POST the grid the way the page posts it.

    Mirrors the real form deliberately, including the two hidden markers that
    make a partial save safe: `rows` names which societies were on screen, and
    `editable` names which gap cells were rendered. A test that skipped them
    would pass while the page silently wiped every society it wasn't showing.

    Statuses default to what is already stored, because every <select> on the
    page is pre-filled with the current value - omitting one would mean "clear
    it", which is not what a caller changing one row means.
    """
    statuses = statuses or {}
    data = []
    for sid in society_ids:
        data.append(("rows", str(sid)))
        if sid in statuses:
            current = statuses[sid]
        else:
            current = db.execute(
                "SELECT lifecycle_status FROM societies WHERE id = ?", (sid,)
            ).fetchone()[0]
        data.append((f"status-{sid}", current or ""))

    # By default every field is offered as editable, which is what a bare
    # society renders. Pass `editable` explicitly to model a partial grid.
    for sid in society_ids:
        for field in (ALL_FIELDS if editable is None else [f for s, f in editable if s == sid]):
            data.append(("editable", f"{sid}:{field}"))

    for sid, field in ticked:
        data.append((f"checked-{sid}-{field}", "1"))

    return client.post("/admin/society-checklist/save", data=MultiDict(data))


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

    resp = _save(client, db, [1], ticked=[(1, "web")])
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

    _save(client, db, [1], ticked=[(1, "web")])
    # Saving again with the box unticked is the undo - same as the page.
    _save(client, db, [1])

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "6 gaps in total" in body
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 0


def test_an_unknown_field_is_rejected(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    resp = client.post("/admin/society-checklist/save", data=MultiDict([
        ("rows", "1"), ("status-1", ""), ("editable", "1:bank_details"),
    ]))
    assert resp.status_code == 400
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 0


def test_a_row_that_was_not_on_the_page_is_rejected(client, db):
    """`editable` naming a society outside `rows` is either a stale form or
    someone poking at it - either way it must not write."""
    _bare_society(db, 1, "On Screen")
    _bare_society(db, 2, "Not On Screen")
    db.commit()
    login_as(client, seed_user(db))

    resp = client.post("/admin/society-checklist/save", data=MultiDict([
        ("rows", "1"), ("status-1", ""), ("editable", "2:web"), ("checked-2-web", "1"),
    ]))
    assert resp.status_code == 400
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 0


def test_lifecycle_status_is_saved_and_validated(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    _save(client, db, [1], statuses={1: "Dormant"})
    assert db.execute("SELECT lifecycle_status FROM societies WHERE id = 1").fetchone()[0] == "Dormant"

    resp = _save(client, db, [1], statuses={1: "Exploded"})
    assert resp.status_code == 400
    assert db.execute("SELECT lifecycle_status FROM societies WHERE id = 1").fetchone()[0] == "Dormant"


def test_lifecycle_status_can_be_cleared_back_to_unset(client, db):
    _bare_society(db, 1, "Gapful Society")
    db.commit()
    login_as(client, seed_user(db))

    _save(client, db, [1], statuses={1: "Dormant"})
    _save(client, db, [1], statuses={1: ""})
    assert db.execute("SELECT lifecycle_status FROM societies WHERE id = 1").fetchone()[0] is None


def test_a_closed_society_is_not_counted_as_outstanding(client, db):
    """A wound-up society is a settled answer, not a job."""
    _bare_society(db, 1, "Closed Society")
    db.commit()
    login_as(client, seed_user(db))

    _save(client, db, [1], statuses={1: "Closed"})

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
    _save(client, db, [1, 2], statuses={1: "Closed"})

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

    # One save, every field at once - which is the point of the batch form.
    _save(client, db, [1], ticked=[(1, f) for f in ALL_FIELDS])

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

    _save(client, db, [1], statuses={1: "Active"})

    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "1 society with something outstanding" in body


# --- batch save, 2026-09-02 -------------------------------------------------
#
# Every cell used to be its own form: a status select that submitted on change,
# and a button per gap dot. Working down a column meant a full page load per
# click, and the grid re-sorts as gaps close, so the row you were about to click
# had moved by the time the page came back. Darragh: make several changes and
# save at the end.


def test_several_changes_across_several_societies_save_in_one_go(client, db):
    _bare_society(db, 1, "First Society")
    _bare_society(db, 2, "Second Society")
    db.commit()
    login_as(client, seed_user(db))

    _save(client, db, [1, 2],
          statuses={1: "Dormant", 2: "Closed"},
          ticked=[(1, "web"), (1, "logo"), (2, "founded")])

    rows = dict(db.execute("SELECT id, lifecycle_status FROM societies").fetchall())
    assert rows[1] == "Dormant"
    assert rows[2] == "Closed"
    checked = {
        (r["society_id"], r["field"])
        for r in db.execute("SELECT society_id, field FROM society_field_checked")
    }
    assert checked == {(1, "web"), (1, "logo"), (2, "founded")}


def test_saving_a_filtered_page_leaves_every_other_society_alone(client, db):
    """The correctness question this whole design turns on. An unticked
    checkbox is indistinguishable from one that was never rendered, so without
    the `rows`/`editable` markers, saving while filtered to one region would
    read as "nothing is ticked anywhere" and wipe the lot."""
    seed_society(db, id=1, name="Eastern Society", region="Eastern")
    seed_society(db, id=2, name="Western Society", region="Western")
    db.commit()
    login_as(client, seed_user(db))

    # Western is marked up first, then a save that only ever saw Eastern.
    _save(client, db, [2], ticked=[(2, "web"), (2, "logo")], statuses={2: "Active"})
    _save(client, db, [1], ticked=[(1, "about")])

    checked = {
        (r["society_id"], r["field"])
        for r in db.execute("SELECT society_id, field FROM society_field_checked")
    }
    assert (2, "web") in checked and (2, "logo") in checked, "off-screen ticks were wiped"
    assert (1, "about") in checked
    assert db.execute(
        "SELECT lifecycle_status FROM societies WHERE id = 2"
    ).fetchone()[0] == "Active", "an off-screen status was cleared"


def test_a_field_already_on_record_cannot_be_disturbed(client, db):
    """A present field renders as a plain dot with no checkbox, so it never
    appears in `editable` and its state is untouchable from this page."""
    _bare_society(db, 1, "Society")
    _fill_everything(db, 1)
    db.commit()
    login_as(client, seed_user(db))

    resp = _save(client, db, [1], editable=[])
    assert resp.status_code == 302
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 0
    body = client.get("/admin/society-checklist").get_data(as_text=True)
    assert "0 gaps in total" in body


def test_saving_with_nothing_changed_says_so_rather_than_claiming_a_save(client, db):
    """Submitting an untouched grid should not report a successful save - it
    would train you to ignore the confirmation."""
    _bare_society(db, 1, "Society")
    db.commit()
    login_as(client, seed_user(db))

    resp = _save(client, db, [1])
    assert resp.status_code == 302
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 0

    body = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "No changes to save." in body


def test_an_empty_save_is_refused_rather_than_treated_as_clear_everything(client, db):
    """No `rows` at all means the form never rendered - not that every society
    should be reset."""
    _bare_society(db, 1, "Society")
    db.commit()
    login_as(client, seed_user(db))
    _save(client, db, [1], ticked=[(1, "web")])

    client.post("/admin/society-checklist/save", data=MultiDict([("csrf_token", "")]))
    assert db.execute("SELECT COUNT(*) FROM society_field_checked").fetchone()[0] == 1


def test_saving_requires_login(client, db):
    _bare_society(db, 1, "Society")
    db.commit()
    resp = client.post("/admin/society-checklist/save", data=MultiDict([("rows", "1")]))
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


# --- filters ----------------------------------------------------------------


def test_the_missing_field_filter_shows_only_that_gap(client, db):
    """The way this job is actually done: an hour of founding years, not one
    society at a time."""
    _bare_society(db, 1, "Needs Everything")
    _bare_society(db, 2, "Has A Founding Year")
    db.execute("UPDATE societies SET founded_year = 1950 WHERE id = 2")
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist?missing=founded").get_data(as_text=True)
    assert "Needs Everything" in body
    assert "Has A Founding Year" not in body


def test_a_field_marked_checked_drops_out_of_the_missing_filter(client, db):
    """"Checked, nothing to get" is an answer, so it is not still missing."""
    _bare_society(db, 1, "Looked, Nothing There")
    db.commit()
    login_as(client, seed_user(db))
    _save(client, db, [1], ticked=[(1, "logo")])

    body = client.get("/admin/society-checklist?missing=logo").get_data(as_text=True)
    assert "Looked, Nothing There" not in body


def test_the_progress_filter_splits_outstanding_from_complete(client, db):
    _bare_society(db, 1, "Outstanding Society")
    _bare_society(db, 2, "Complete Society")
    _fill_everything(db, 2)
    db.commit()
    login_as(client, seed_user(db))

    outstanding = client.get("/admin/society-checklist?outstanding=1").get_data(as_text=True)
    assert "Outstanding Society" in outstanding
    assert "Complete Society" not in outstanding

    complete = client.get("/admin/society-checklist?outstanding=0").get_data(as_text=True)
    assert "Complete Society" in complete
    assert "Outstanding Society" not in complete


def test_the_upcoming_filter_finds_societies_with_a_show_on(client, db):
    _bare_society(db, 1, "Has A Show")
    _bare_society(db, 2, "No Shows")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, moderation_status) "
        "VALUES (1, '26/27', 'Eastern', 'Chess', date('now', '+30 days'), 'approved')"
    )
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist?upcoming=1").get_data(as_text=True)
    assert "Has A Show" in body
    assert "No Shows" not in body


def test_the_name_search_narrows_the_grid(client, db):
    _bare_society(db, 1, "Ballina Musical Society")
    _bare_society(db, 2, "Tralee Musical Society")
    db.commit()
    login_as(client, seed_user(db))

    body = client.get("/admin/society-checklist?q=ballina").get_data(as_text=True)
    assert "Ballina Musical Society" in body
    assert "Tralee Musical Society" not in body


def test_filters_combine(client, db):
    seed_society(db, id=1, name="Eastern Gapful", region="Eastern")
    seed_society(db, id=2, name="Western Gapful", region="Western")
    db.commit()
    login_as(client, seed_user(db))

    body = client.get(
        "/admin/society-checklist?region=Eastern&missing=logo&outstanding=1"
    ).get_data(as_text=True)
    assert "Eastern Gapful" in body
    assert "Western Gapful" not in body
