"""Show/society detail pages, desktop widths (Second Act backlog item 3):
poster/logo one side, the facts the other, instead of a 240px image sitting
alone in the 900px container with nothing beside it (see .detail-hero in
style.css, and show_detail.html / society_detail.html). A show or society
with no image uploaded still gets the two-column layout - the initials
placeholder (item 2's pattern, generalised via app/filters.py's `initials`)
fills the slot instead of collapsing to one column."""
from conftest import seed_society


def _insert_show(db, society_id, show="Oliver!", poster_filename=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "poster_filename, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', ?, '2026-11-10', '2026-11-14', ?, 'approved')",
        (society_id, show, poster_filename),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE society_id = ?", (society_id,)).fetchone()["id"]


def test_show_with_poster_renders_real_image_in_hero(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, show="Oliver!", poster_filename="oliver.jpg")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert '<div class="detail-hero">' in body
    assert 'class="poster" src=' in body
    assert "oliver.jpg" in body
    assert 'class="poster is-placeholder"' not in body


def test_show_without_poster_gets_initials_placeholder(client, db):
    society_id = seed_society(db)
    show_id = _insert_show(db, society_id, show="The Hired Man", poster_filename=None)

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert '<div class="poster is-placeholder" aria-hidden="true"><span>HM</span></div>' in body


def test_society_with_logo_renders_real_image_in_hero(client, db):
    society_id = seed_society(db, name="Test Soc")
    db.execute("UPDATE societies SET logo_filename = 'logo.png' WHERE id = ?", (society_id,))
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert '<div class="detail-hero society-hero">' in body
    assert 'class="poster" src=' in body
    assert "logo.png" in body
    assert 'class="poster is-placeholder"' not in body


def test_society_without_logo_gets_initials_placeholder(client, db):
    society_id = seed_society(db, name="The Hired Man Society")

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert '<div class="poster is-placeholder" aria-hidden="true"><span>HM</span></div>' in body
