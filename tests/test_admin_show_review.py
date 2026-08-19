"""Manual review entry on Edit Show (19 Aug 2026 feedback review, item 2):
a moderator can paste in a review directly for a show that has one but was
never in the ShowTimes archive or an aims.ie link, writing into the same
historical_reviews table the ShowTimes import uses so it renders through
the identical show-page component - just tagged source='manual' so the
public citation doesn't falsely claim it was in a ShowTimes issue."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_show(db, **kw):
    fields = {
        "society_id": 1, "season": "25/26", "show": "Test Show", "region": "Eastern",
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


def seed_adjudicator(db, name="Jane Smith"):
    db.execute("INSERT INTO adjudicators (name) VALUES (?)", (name,))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def test_add_review_form_present_on_edit_show(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    body = client.get(f"/admin/shows/{show_id}/edit").get_data(as_text=True)
    assert 'name="review_text"' in body
    assert "Add review" in body


def test_add_review_creates_an_approved_manual_review(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    adjudicator_id = seed_adjudicator(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    resp = client.post(f"/admin/shows/{show_id}/add-review", data={
        "csrf_token": "x", "adjudicator_id": adjudicator_id,
        "source_issue": "AIMS ShowTimes, Issue 168", "review_text": "A genuinely fine production.",
    })
    assert resp.status_code == 302

    row = db.execute("SELECT * FROM historical_reviews WHERE show_id = ?", (show_id,)).fetchone()
    assert row["moderation_status"] == "approved"
    assert row["source"] == "manual"
    assert row["review_text"] == "A genuinely fine production."
    assert row["adjudicator_id"] == adjudicator_id


def test_added_review_renders_on_the_public_show_page_without_showtimes_citation(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    client.post(f"/admin/shows/{show_id}/add-review", data={
        "csrf_token": "x", "review_text": "A genuinely fine production.",
    })

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "A genuinely fine production." in body
    assert "Originally published in AIMS" not in body


def test_add_review_refused_without_a_title(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db, show=None)
    login_as(client, admin_id)

    client.post(f"/admin/shows/{show_id}/add-review", data={
        "csrf_token": "x", "review_text": "A review with no show to attach to.",
    })
    assert db.execute("SELECT COUNT(*) FROM historical_reviews WHERE show_id = ?", (show_id,)).fetchone()[0] == 0


def test_add_review_refused_when_one_already_exists(client, db):
    """Guards against recreating the exact bug this session found and fixed
    elsewhere - a show silently carrying two approved reviews with no
    deterministic pick of which renders."""
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    client.post(f"/admin/shows/{show_id}/add-review", data={
        "csrf_token": "x", "review_text": "First review.",
    })
    client.post(f"/admin/shows/{show_id}/add-review", data={
        "csrf_token": "x", "review_text": "Second review.",
    })

    rows = db.execute(
        "SELECT review_text FROM historical_reviews WHERE show_id = ? AND moderation_status = 'approved'",
        (show_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["review_text"] == "First review."


def test_remove_review_deletes_a_manual_one_only(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    client.post(f"/admin/shows/{show_id}/add-review", data={
        "csrf_token": "x", "review_text": "A manually added review.",
    })
    client.post(f"/admin/shows/{show_id}/remove-review", data={"csrf_token": "x"})

    assert db.execute(
        "SELECT COUNT(*) FROM historical_reviews WHERE show_id = ? AND moderation_status = 'approved'",
        (show_id,),
    ).fetchone()[0] == 0


def test_remove_review_does_not_touch_a_showtimes_review(client, db):
    """The Remove button only ever appears for a manually-added review, but
    the route itself is also scoped to source='manual' as a second line of
    defence - a real ShowTimes archive review has its own moderation
    history and isn't something this button should be able to touch."""
    admin_id = seed_user(db)
    society_id = seed_society(db)
    show_id = seed_show(db)
    db.execute(
        "INSERT INTO historical_reviews "
        "(season, tier, show_raw, society_raw, review_text, show_id, society_id, "
        " moderation_status, source) "
        "VALUES ('25/26', 'Gilbert', 'Test Show', 'Test Society', 'Extracted review text.', "
        "        ?, ?, 'approved', 'showtimes')",
        (show_id, society_id),
    )
    db.commit()
    login_as(client, admin_id)

    client.post(f"/admin/shows/{show_id}/remove-review", data={"csrf_token": "x"})

    assert db.execute(
        "SELECT COUNT(*) FROM historical_reviews WHERE show_id = ? AND moderation_status = 'approved'",
        (show_id,),
    ).fetchone()[0] == 1
