"""/admin/fix-dates: the opening-date input carries a data-sync-close
attribute so an empty closing date jumps to the same month once opening is
picked, instead of needing its own click-through from today's month
(base.html's delegated 'change' listener does the actual syncing client-side -
untestable here without a browser, this just confirms the markup it needs is
present and wired to the right paired field id)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_fix_dates_opening_input_wired_to_its_own_closing_field(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    cur = db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', 'Evita', 'approved')",
        (society_id,),
    )
    show_id = cur.lastrowid
    db.commit()

    body = client.get("/admin/shows/dates").get_data(as_text=True)
    assert f'data-sync-close="closing-{show_id}"' in body
    assert f'id="closing-{show_id}"' in body
