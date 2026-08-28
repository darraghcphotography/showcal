"""V3 (small-items queue): three narrow accessibility gaps found in an
otherwise-good site. Pagination's <nav> had no aria-label (two unlabelled nav
landmarks on any paginated page, alongside the header's own <nav>), flash
messages after a submit weren't announced to a screen reader, and the theme
toggle had no aria-pressed to say which state it's in."""
from conftest import seed_society


def test_pagination_nav_has_an_aria_label(client, db):
    seed_society(db)
    for i in range(60):
        db.execute(
            "INSERT INTO societies (name, region, section) VALUES (?, 'Eastern', 'Gilbert')",
            (f"Society {i}",),
        )
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    assert '<nav class="pagination" aria-label="Pagination">' in body


def test_flash_messages_are_announced(client, db):
    resp = client.post(
        "/submit/photo",
        data={"kind": "review", "notes": ""},
        content_type="multipart/form-data",
    )
    body = resp.get_data(as_text=True)
    assert '<ul class="flashes" role="status">' in body


def test_theme_toggle_has_aria_pressed(client):
    body = client.get("/").get_data(as_text=True)
    assert 'id="theme-toggle"' in body
    assert 'aria-pressed="false"' in body
