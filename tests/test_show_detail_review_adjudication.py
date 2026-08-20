"""Show page field visibility: the raw adjudication date is never shown
publicly (only the reminder link, when applicable - see
test_show_calendar_links.py), and "Review: None" is hidden for a show that
hasn't happened yet, since an unpopulated review isn't useful information -
see show_detail.html."""
from conftest import seed_society


def _insert_show(db, society_id, opening_date, review_status="None", adjudication_date=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "review_status, adjudication_date, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', 'Oliver!', ?, ?, ?, ?, 'approved')",
        (society_id, opening_date, opening_date, review_status, adjudication_date),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE society_id = ?", (society_id,)).fetchone()["id"]


def test_review_none_hidden_for_upcoming_show(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2026-11-10", review_status="None")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    # Scoped to the page content, not the whole document - the site nav now
    # always has a "Reviews" link (added for the /reviews index), which
    # contains "Review" as a substring regardless of this show's own status.
    content = body.split('<main class="container">')[1]
    assert "Review" not in content


def test_review_shown_for_upcoming_show_with_real_status(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2026-11-10", review_status="Scheduled")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Review" in body
    assert "Scheduled" in body


def test_review_none_still_shown_for_past_show(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2020-01-06", review_status="None")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Review" in body


def test_raw_adjudication_date_never_shown(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, "2026-11-10", adjudication_date="2026-11-08")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "08-11-2026" not in body
    assert "8 November" not in body
