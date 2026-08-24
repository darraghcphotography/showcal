"""Three fields added 2026-08-24 for the Antigravity homework round:
societies.founded_year, show_info's composer/lyricist/book_author/
licensing_house, and venues' box_office_phone/box_office_url. Same trust
model as everything else here - moderator-entered, shown publicly once set."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_founded_year_saves_and_displays(client, db):
    society_id = seed_society(db, name="Test Society")
    admin_id = seed_user(db)
    login_as(client, admin_id)

    resp = client.post(
        f"/admin/societies/{society_id}/edit",
        data={
            "name": "Test Society", "region": "Eastern", "section": "Gilbert",
            "founded_year": "1957",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    row = db.execute("SELECT founded_year FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["founded_year"] == 1957

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "Founded 1957" in body


def test_founded_year_must_be_numeric(client, db):
    society_id = seed_society(db, name="Test Society")
    admin_id = seed_user(db)
    login_as(client, admin_id)

    client.post(
        f"/admin/societies/{society_id}/edit",
        data={"name": "Test Society", "region": "Eastern", "section": "Gilbert", "founded_year": "nope"},
    )

    row = db.execute("SELECT founded_year FROM societies WHERE id = ?", (society_id,)).fetchone()
    assert row["founded_year"] is None


def test_show_credits_save_and_display(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    society_id = seed_society(db, name="Test Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '25/26', 'Eastern', 'Oklahoma!', 'approved', 'import')",
        (society_id,),
    )
    db.commit()

    resp = client.post(
        "/admin/titles/Oklahoma!/info",
        data={
            "synopsis": "A cowman and a farm girl.",
            "composer": "Richard Rodgers", "lyricist": "Oscar Hammerstein II",
            "book_author": "Oscar Hammerstein II", "licensing_house": "Concord Theatricals",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    row = db.execute("SELECT * FROM show_info WHERE show = 'Oklahoma!'").fetchone()
    assert row["composer"] == "Richard Rodgers"
    assert row["lyricist"] == "Oscar Hammerstein II"
    assert row["licensing_house"] == "Concord Theatricals"

    body = client.get("/titles/Oklahoma!").get_data(as_text=True)
    assert "Richard Rodgers" in body
    assert "Concord Theatricals" in body


def test_venue_box_office_saves_and_displays(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    society_id = seed_society(db, name="Test Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, venue, moderation_status, source) "
        "VALUES (?, '25/26', 'Eastern', 'Test Show', 'Test Theatre', 'approved', 'import')",
        (society_id,),
    )
    db.commit()
    # Triggers venues_build's before_request rebuild, which is what actually
    # creates the venue row/alias from shows.venue text - venues aren't
    # hand-inserted (see schema.sql: DERIVED, NOT AUTHORED).
    client.get("/")
    venue = db.execute("SELECT id, slug FROM venues WHERE name = 'Test Theatre'").fetchone()
    assert venue is not None

    resp = client.post(
        f"/admin/venue-directory/{venue['id']}/edit",
        data={
            "name": "Test Theatre",
            "box_office_phone": "01 234 5678",
            "box_office_url": "https://example.com/tickets",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    row = db.execute("SELECT box_office_phone, box_office_url FROM venues WHERE id = ?", (venue["id"],)).fetchone()
    assert row["box_office_phone"] == "01 234 5678"
    assert row["box_office_url"] == "https://example.com/tickets"

    body = client.get(f"/venues/{venue['slug']}").get_data(as_text=True)
    assert "01 234 5678" in body
    assert "Book tickets" in body
