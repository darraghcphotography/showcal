"""The adjudication submission cut-off is a deadline for the society staging
the show, and noise to everyone else - and the show page is the one most likely
to be shared publicly (site audit, finding 07).

It isn't secret: it's just opening_date minus six weeks, arithmetic on a date
the page already shows. So this is an audience decision, not an access-control
one - but a visitor should still never meet it.
"""
from datetime import date, timedelta

from conftest import seed_invite_code, seed_society, seed_user

CUTOFF_LABEL = "Adjudication submission cut-off"


def unlock_society(client, db, society_id, code="AIMS-TEST01"):
    seed_invite_code(db, code=code, society_id=society_id)
    code_id = db.execute("SELECT id FROM invite_codes WHERE code = ?", (code,)).fetchone()["id"]
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def add_upcoming_show(db, society_id, show="Oliver!"):
    opening = date.today() + timedelta(days=90)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "review_status, moderation_status) VALUES (?, '26/27', 'Eastern', ?, ?, ?, 'None', 'approved')",
        (society_id, show, opening.isoformat(), (opening + timedelta(days=4)).isoformat()),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]


def test_public_visitor_never_sees_it(client, db):
    society_id = seed_society(db)
    show_id = add_upcoming_show(db, society_id)

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert CUTOFF_LABEL not in body


def test_the_society_sees_it_on_their_own_show(client, db):
    society_id = seed_society(db)
    show_id = add_upcoming_show(db, society_id)
    unlock_society(client, db, society_id)

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert CUTOFF_LABEL in body


def test_a_society_does_not_see_it_on_another_society_s_show(client, db):
    ours = seed_society(db)
    theirs = seed_society(db, id=2, name="Other Society")
    their_show = add_upcoming_show(db, theirs, show="Chess")
    unlock_society(client, db, ours)

    body = client.get(f"/shows/{their_show}").get_data(as_text=True)
    assert CUTOFF_LABEL not in body


def test_a_moderator_sees_it_on_any_show(client, db):
    society_id = seed_society(db)
    show_id = add_upcoming_show(db, society_id)
    user_id = seed_user(db)
    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert CUTOFF_LABEL in body
