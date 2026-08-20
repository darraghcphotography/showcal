"""/admin/shows/dates ("Fix dates"):

- The opening-date input carries a data-sync-close attribute so an empty
  closing date jumps to the same month once opening is picked, instead of
  needing its own click-through from today's month (base.html's delegated
  'change' listener does the actual syncing client-side - untestable here
  without a browser, this just confirms the markup it needs is present and
  wired to the right paired field id).
- The whole visible batch now shares one real <form> with indexed field
  names (show_id_0, opening_date_0, ... show_id_1, ...) instead of one
  hidden <form> per row. The old per-row-form version had a real bug: typing
  new dates into several rows and clicking any one row's Save only saved
  that row - the page reload silently discarded every other row's unsaved
  edit. One shared form means any submit always carries every row's current
  values, and the backend applies them atomically (a bad date anywhere
  blocks the whole save rather than silently skipping just that row)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _seed_show(db, society_id, show, season="26/27", opening=None, closing=None):
    cur = db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?, ?, 'approved')",
        (society_id, season, show, opening, closing),
    )
    return cur.lastrowid


def test_fix_dates_opening_input_wired_to_its_own_closing_field(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    show_id = _seed_show(db, society_id, "Evita")
    db.commit()

    body = client.get("/admin/shows/dates").get_data(as_text=True)
    assert f'data-sync-close="closing-{show_id}"' in body
    assert f'id="closing-{show_id}"' in body


def test_fix_dates_form_has_one_shared_form_with_indexed_rows(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    show_a = _seed_show(db, society_id, "Evita")
    show_b = _seed_show(db, society_id, "Grease")
    db.commit()

    body = client.get("/admin/shows/dates").get_data(as_text=True)
    assert 'id="row-' not in body  # the old one-hidden-form-per-row pattern is gone
    assert f'name="show_id_0" value="{show_a}"' in body
    assert f'name="show_id_1" value="{show_b}"' in body


def test_fix_dates_bulk_save_updates_every_row_in_one_submit(client, db):
    """The exact bug reported: entering dates on several rows and hitting
    Save must not drop the ones that weren't clicked."""
    society_id = seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    show_a = _seed_show(db, society_id, "Evita")
    show_b = _seed_show(db, society_id, "Grease")
    show_c = _seed_show(db, society_id, "Chicago")
    db.commit()

    resp = client.post("/admin/shows/dates", data={
        "show_id_0": show_a, "opening_date_0": "2026-09-01", "closing_date_0": "2026-09-05",
        "show_id_1": show_b, "opening_date_1": "2026-10-01", "closing_date_1": "2026-10-05",
        "show_id_2": show_c, "opening_date_2": "", "closing_date_2": "",
    })
    assert resp.status_code == 302

    rows = {
        r["id"]: (r["opening_date"], r["closing_date"])
        for r in db.execute("SELECT id, opening_date, closing_date FROM shows").fetchall()
    }
    assert rows[show_a] == ("2026-09-01", "2026-09-05")
    assert rows[show_b] == ("2026-10-01", "2026-10-05")
    assert rows[show_c] == (None, None)


def test_fix_dates_bulk_save_is_all_or_nothing_on_a_bad_date(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    show_a = _seed_show(db, society_id, "Evita")
    show_b = _seed_show(db, society_id, "Grease")
    db.commit()

    resp = client.post("/admin/shows/dates", data={
        "show_id_0": show_a, "opening_date_0": "2026-09-01", "closing_date_0": "2026-09-05",
        "show_id_1": show_b, "opening_date_1": "not-a-date", "closing_date_1": "",
    }, follow_redirects=True)
    assert b"must be a valid date" in resp.data

    rows = {
        r["id"]: r["opening_date"]
        for r in db.execute("SELECT id, opening_date FROM shows").fetchall()
    }
    assert rows[show_a] is None  # the valid row was NOT saved either - atomic


def test_fix_dates_bulk_save_skips_unchanged_rows(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    show_a = _seed_show(db, society_id, "Evita", opening="2026-09-01", closing="2026-09-05")
    db.commit()
    before = db.execute("SELECT updated_at FROM shows WHERE id = ?", (show_a,)).fetchone()["updated_at"]

    resp = client.post("/admin/shows/dates", data={
        "show_id_0": show_a, "opening_date_0": "2026-09-01", "closing_date_0": "2026-09-05",
    }, follow_redirects=True)
    assert b"No changes to save" in resp.data

    after = db.execute("SELECT updated_at FROM shows WHERE id = ?", (show_a,)).fetchone()["updated_at"]
    assert before == after
