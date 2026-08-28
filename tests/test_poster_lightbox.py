"""F4 (small-items queue, plan item 9): a poster lightbox using CSS and
<dialog> only - no new JS dependency, since the Leaflet CDN allowance stays
scoped to /venues/map and isn't meant to widen."""
from conftest import seed_society


def _add_show_with_poster(db, society_id, poster_filename="abc123.webp"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source, poster_filename) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'approved', 'import', ?)",
        (society_id, poster_filename),
    )


def test_poster_renders_a_lightbox_dialog(client, db):
    society_id = seed_society(db)
    _add_show_with_poster(db, society_id)
    db.commit()
    show_id = db.execute("SELECT id FROM shows").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert '<dialog class="poster-lightbox" id="poster-lightbox">' in body
    assert 'id="poster-lightbox-trigger"' in body


def test_no_poster_means_no_lightbox_markup(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'approved', 'import')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "poster-lightbox" not in body
