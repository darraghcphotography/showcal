"""Poster-coverage workflow (2026-08-29).

Follows directly from the homepage redesign the same day: productions became
poster-led cards, so a show with no poster went from a barely-visible 54px
thumbnail to a large blank card beside real artwork. At the time only 12 of
67 upcoming productions had one.

The societies hold the posters, not the moderator, so this is two halves:
an admin chasing list, and a prompt on the society's own dashboard (they can
already upload - nothing ever told them it mattered).

The scoping is the important part, and it's the lesson MISSING_DATES_WHERE
already records: count only what someone can actually action. A poster is
promotional material for a run that hasn't happened, so past shows are
excluded - unscoped, this counter would read ~5,000 and never move.

Scoped a second time on 2026-09-02, for the same reason at the other end.
Darragh: a society does not commission its poster until the show is close, so a
run eight months out has no poster to ask for. The live numbers agreed - every
production opening within a month already had its artwork, while the one-to-
three-month band had almost none. The dashboard counter and the chasing list now
stop at POSTER_CHASE_DAYS; anything further ahead is listed for reference, not
as work. Without that the counter reads 54 when the actual job is 17, and a
queue that can never reach zero stops being read.
"""
from datetime import date, timedelta

from conftest import seed_invite_code, seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def _add_show(db, society_id, show, days_ahead=None, poster=None, season="26/27", source="import"):
    opening = (date.today() + timedelta(days=days_ahead)).isoformat() if days_ahead is not None else None
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, "
        "opening_date, poster_filename) VALUES (?, ?, 'Eastern', ?, ?, 'approved', ?, ?)",
        (society_id, season, show, source, opening, poster),
    )
    return db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]


# ----------------------------------------------------------------- admin side

def test_missing_posters_page_lists_only_upcoming_shows(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "Needs A Poster", days_ahead=30)
    _add_show(db, society_id, "Already Ran", days_ahead=-400, season="24/25")
    db.commit()

    admin_id = seed_user(db)
    login_as(client, admin_id)
    body = client.get("/admin/missing-posters").get_data(as_text=True)
    assert "Needs A Poster" in body
    assert "Already Ran" not in body


def test_a_show_that_has_a_poster_is_not_listed(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "Has A Poster", days_ahead=30, poster="abc.webp")
    db.commit()

    admin_id = seed_user(db)
    login_as(client, admin_id)
    body = client.get("/admin/missing-posters").get_data(as_text=True)
    assert "Has A Poster" not in body
    assert "Nothing worth chasing right now" in body


def test_a_show_too_far_out_is_not_presented_as_work(client, db):
    """The 2026-09-02 scoping. A run eight months away has no poster to ask for,
    so it must not sit in the chasing table beside next month's - it goes in the
    reference list underneath."""
    society_id = seed_society(db)
    _add_show(db, society_id, "Opens Soon", days_ahead=30)
    _add_show(db, society_id, "Opens Next Summer", days_ahead=280, season="27/28")
    db.commit()

    login_as(client, seed_user(db))
    body = client.get("/admin/missing-posters").get_data(as_text=True)

    chase_table = body[:body.index("not yet worth a message")]
    assert "Opens Soon" in chase_table
    assert "Opens Next Summer" not in chase_table
    # Still visible, just not as a job.
    assert "Opens Next Summer" in body


def test_the_dashboard_counter_only_counts_what_can_be_chased(client, db):
    """A counter that includes a show 18 months out can never reach zero, and a
    queue that never clears stops being read - the same rule as the dismissal
    tables."""
    society_id = seed_society(db)
    _add_show(db, society_id, "Opens Soon", days_ahead=30)
    for i, days in enumerate((200, 300, 400)):
        _add_show(db, society_id, f"Far Off {i}", days_ahead=days, season="27/28")
    db.commit()

    login_as(client, seed_user(db))
    body = client.get("/admin/").get_data(as_text=True)

    # Read the number out of the poster row itself. A bare ">4<" search matches
    # the unrelated "Fix dates" counter on the same table, which is how the
    # first version of this test failed for the wrong reason.
    row_end = body.index("Chase posters")
    row = body[body.rindex("<tr>", 0, row_end):row_end]
    assert ">1<" in row, f"expected 1 chaseable poster in the dashboard row, got: {row}"
    assert ">4<" not in row


def test_the_page_surfaces_the_society_login_code(client, db):
    """The code is the actual lever - it's what lets the society upload the
    poster themselves, which is the only way this list ever clears."""
    society_id = seed_society(db)
    seed_invite_code(db, code="AIMS-POST01", society_id=society_id)
    _add_show(db, society_id, "Needs A Poster", days_ahead=30)
    db.commit()

    admin_id = seed_user(db)
    login_as(client, admin_id)
    body = client.get("/admin/missing-posters").get_data(as_text=True)
    assert "AIMS-POST01" in body


def test_shows_are_ordered_soonest_first(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "Opens Later", days_ahead=300)
    _add_show(db, society_id, "Opens Soon", days_ahead=10)
    db.commit()

    admin_id = seed_user(db)
    login_as(client, admin_id)
    body = client.get("/admin/missing-posters").get_data(as_text=True)
    assert body.index("Opens Soon") < body.index("Opens Later")


def test_the_dashboard_counter_matches_the_page(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "One", days_ahead=10)
    _add_show(db, society_id, "Two", days_ahead=20)
    _add_show(db, society_id, "Old One", days_ahead=-500, season="24/25")
    _add_show(db, society_id, "Covered", days_ahead=30, poster="abc.webp")
    db.commit()

    admin_id = seed_user(db)
    login_as(client, admin_id)
    dashboard = client.get("/admin/").get_data(as_text=True)
    assert "Upcoming shows with no poster" in dashboard
    # The counter cell, not just the digit somewhere on a busy page.
    assert "<td>2</td>" in dashboard


def test_missing_posters_requires_login(client, db):
    resp = client.get("/admin/missing-posters")
    assert resp.status_code == 302


# --------------------------------------------------------------- society side

def test_society_dashboard_prompts_for_a_missing_poster(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-POST02", society_id=society_id)
    _add_show(db, society_id, "Needs A Poster", days_ahead=30)
    db.commit()

    unlock_society(client, code_id)
    body = client.get("/society/").get_data(as_text=True)
    assert "No poster yet" in body
    assert "Add a poster" in body
    assert "Your upcoming show has no poster yet." in body


def test_society_dashboard_does_not_nag_about_past_shows(client, db):
    """A society is never going to produce artwork for a 1998 run, and a
    prompt that can't be satisfied is a prompt that gets ignored."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-POST03", society_id=society_id)
    _add_show(db, society_id, "Long Gone", days_ahead=-900, season="23/24")
    db.commit()

    unlock_society(client, code_id)
    body = client.get("/society/").get_data(as_text=True)
    assert "No poster yet" not in body
    assert "Long Gone" in body  # still listed, just not nagged about


def test_society_dashboard_is_quiet_when_every_poster_is_in(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-POST04", society_id=society_id)
    _add_show(db, society_id, "Sorted", days_ahead=30, poster="abc.webp")
    db.commit()

    unlock_society(client, code_id)
    body = client.get("/society/").get_data(as_text=True)
    assert "No poster yet" not in body


def test_a_dateless_future_placeholder_is_not_prompted(client, db):
    """No date means nothing is on sale yet - there's nothing to promote, so
    it isn't a gap the society can close."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-POST05", society_id=society_id)
    _add_show(db, society_id, "Slot With No Date", days_ahead=None, season="27/28")
    db.commit()

    unlock_society(client, code_id)
    body = client.get("/society/").get_data(as_text=True)
    assert "No poster yet" not in body


# ------------------------------------------------- generating a code in place

def test_generate_code_button_returns_to_the_chasing_list(client, db):
    """Working down 45 societies, being dumped on each one's public page and
    losing your place in the list would make this unusable."""
    society_id = seed_society(db)
    _add_show(db, society_id, "Needs A Poster", days_ahead=30)
    db.commit()

    admin_id = seed_user(db, role="admin")
    login_as(client, admin_id)
    resp = client.post(
        f"/admin/societies/{society_id}/generate-code",
        data={"next": "admin.missing_posters"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/missing-posters")


def test_the_generated_code_then_appears_on_the_list(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "Needs A Poster", days_ahead=30)
    db.commit()

    admin_id = seed_user(db, role="admin")
    login_as(client, admin_id)
    client.post(f"/admin/societies/{society_id}/generate-code", data={"next": "admin.missing_posters"})

    code = db.execute("SELECT code FROM invite_codes WHERE society_id = ?", (society_id,)).fetchone()["code"]
    body = client.get("/admin/missing-posters").get_data(as_text=True)
    assert code in body
    assert "Copy message" in body


def test_an_off_site_next_value_is_ignored(client, db):
    """back_to() resolves an endpoint *name* against an allowlist - a raw URL
    here would be an open redirect."""
    society_id = seed_society(db)
    db.commit()

    admin_id = seed_user(db, role="admin")
    login_as(client, admin_id)
    resp = client.post(
        f"/admin/societies/{society_id}/generate-code",
        data={"next": "https://evil.example/phishing"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "evil.example" not in resp.headers["Location"]
    assert resp.headers["Location"].endswith(f"/societies/{society_id}")


def test_the_copy_message_names_the_show_and_carries_the_code(client, db):
    """The message is the whole point of the button - a bare code with no
    context is something the moderator has to write around every time."""
    society_id = seed_society(db, name="Tullyvin Musical Society")
    seed_invite_code(db, code="AIMS-POST99", society_id=society_id)
    _add_show(db, society_id, "Shrek the Musical", days_ahead=30)
    db.commit()

    admin_id = seed_user(db)
    login_as(client, admin_id)
    body = client.get("/admin/missing-posters").get_data(as_text=True)
    assert "Tullyvin Musical Society" in body
    assert "Shrek the Musical" in body
    assert "AIMS-POST99" in body
    assert 'data-copy-target="invite-msg-' in body
