"""AIMS re-tiers societies between Gilbert and Sullivan season to season
(a points-based allocation on nomination history - see /about). shows.section
is deliberately a snapshot, not a live mirror of societies.section (schema.sql),
so a society moving tiers must never rewrite a show that's already run under
its old tier. But a not-yet-run show for the exact season the edit claims to
speak for (section_as_of) was just sitting stale with no route back to the
society's real value - caught 2026-08-23 when Darragh re-tiered a batch of
societies for 26/27 and one of the untouched shows (Bravo Theatre Group's
Dear Evan Hansen) was still tagged under the old section. See admin/societies.py's
edit_society()."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_show(db, **kw):
    fields = {
        "society_id": 1, "season": "26/27", "show": "Test Show", "region": "Eastern",
        "section": "Gilbert", "moderation_status": "approved", "source": "import",
    }
    fields.update(kw)
    cols = ", ".join(fields)
    db.execute(
        f"INSERT INTO shows ({cols}) VALUES ({', '.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    db.commit()
    return db.execute("SELECT id FROM shows ORDER BY id DESC LIMIT 1").fetchone()["id"]


def edit_section(client, society_id, section, section_as_of="26/27", region="Eastern", name="Test Society"):
    return client.post(
        f"/admin/societies/{society_id}/edit",
        data={"name": name, "region": region, "section": section, "section_as_of": section_as_of},
        follow_redirects=True,
    )


def test_editing_a_societys_section_cascades_to_its_unplayed_show_that_season(client, db):
    mod_id = seed_user(db, role="moderator")
    login_as(client, mod_id)
    society_id = seed_society(db, section="Gilbert")
    show_id = seed_show(db, society_id=society_id, season="26/27", section="Gilbert", opening_date=None)

    edit_section(client, society_id, "Sullivan")

    row = db.execute("SELECT section FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["section"] == "Sullivan"


def test_cascade_does_not_touch_a_different_season(client, db):
    mod_id = seed_user(db, role="moderator")
    login_as(client, mod_id)
    society_id = seed_society(db, section="Gilbert")
    show_id = seed_show(db, society_id=society_id, season="25/26", section="Gilbert", opening_date=None)

    edit_section(client, society_id, "Sullivan", section_as_of="26/27")

    row = db.execute("SELECT section FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["section"] == "Gilbert"


def test_cascade_does_not_rewrite_a_show_that_already_ran(client, db):
    """A show that already happened keeps the section it actually ran under -
    that's the whole point of the snapshot, not a bug to fix."""
    mod_id = seed_user(db, role="moderator")
    login_as(client, mod_id)
    society_id = seed_society(db, section="Gilbert")
    show_id = seed_show(db, society_id=society_id, season="26/27", section="Gilbert", opening_date="2020-01-01")

    edit_section(client, society_id, "Sullivan")

    row = db.execute("SELECT section FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["section"] == "Gilbert"


def test_cascade_does_nothing_without_section_as_of(client, db):
    mod_id = seed_user(db, role="moderator")
    login_as(client, mod_id)
    society_id = seed_society(db, section="Gilbert")
    show_id = seed_show(db, society_id=society_id, season="26/27", section="Gilbert", opening_date=None)

    edit_section(client, society_id, "Sullivan", section_as_of="")

    row = db.execute("SELECT section FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["section"] == "Gilbert"


def test_no_cascade_flash_when_section_is_unchanged(client, db):
    mod_id = seed_user(db, role="moderator")
    login_as(client, mod_id)
    society_id = seed_society(db, section="Gilbert")
    seed_show(db, society_id=society_id, season="26/27", section="Gilbert", opening_date=None)

    body = edit_section(client, society_id, "Gilbert").get_data(as_text=True)
    assert "Also updated" not in body
