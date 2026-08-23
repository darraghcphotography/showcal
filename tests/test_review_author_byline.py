"""shows.review_author - a moderator-entered byline for a link-out review
(shows.review_url), shown as "reviewed by X" on the show page. Distinct from
the existing *inferred* credit (reviewed_by in public.py's show_detail(),
matched via adjudicator_assignments only when exactly one adjudicator
covered that season/tier) - this one is explicit, never guessed, and takes
precedence when set. Scoped 2026-08-05, resolved 2026-08-20 (backfillable
via the normal edit form, not forward-only; per-person not per-publication),
built 2026-08-23. See admin/shows.py's edit_show(), admin/reviews.py's
save_review_link(), and show_detail.html."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_adjudicator(db, name="Jane Smith"):
    db.execute("INSERT INTO adjudicators (name) VALUES (?)", (name,))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def assign(db, season, section, adjudicator_id):
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES (?, ?, ?)",
        (season, section, adjudicator_id),
    )
    db.commit()


def add_show(db, society_id, show="Oliver!", season="24/25", section="Gilbert",
             review_status="Published", review_url="https://www.aims.ie/post/x", review_author=None,
             moderation_status="approved"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url, "
        "review_author, moderation_status) VALUES (?, ?, 'Eastern', ?, ?, ?, ?, ?, ?)",
        (society_id, season, section, show, review_status, review_url, review_author, moderation_status),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE show = ? AND season = ?", (show, season)).fetchone()["id"]


# --- admin: editing an existing show -----------------------------------

def test_edit_show_saves_review_author(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    society_id = seed_society(db)
    show_id = add_show(db, society_id, review_author=None)

    client.post(
        f"/admin/shows/{show_id}/edit",
        data={
            "season": "24/25", "region": "Eastern", "review_status": "Published",
            "review_url": "https://www.aims.ie/post/x", "review_author": "Peter Kennedy",
        },
    )

    row = db.execute("SELECT review_author FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["review_author"] == "Peter Kennedy"


def test_edit_show_form_shows_existing_review_author(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    society_id = seed_society(db)
    show_id = add_show(db, society_id, review_author="Peter Kennedy")

    body = client.get(f"/admin/shows/{show_id}/edit").get_data(as_text=True)
    assert 'value="Peter Kennedy"' in body


def test_edit_show_can_backfill_an_author_onto_an_already_published_review(client, db):
    """The whole point of resolving "backfill, not forward-only": a show
    that already has its review_url saved must still be editable to add
    the author afterwards, not just at the moment the link is first added."""
    admin_id = seed_user(db)
    login_as(client, admin_id)
    society_id = seed_society(db)
    show_id = add_show(db, society_id, review_url="https://www.aims.ie/post/already-there", review_author=None)

    client.post(
        f"/admin/shows/{show_id}/edit",
        data={
            "season": "24/25", "region": "Eastern", "review_status": "Published",
            "review_url": "https://www.aims.ie/post/already-there", "review_author": "Added Later",
        },
    )

    row = db.execute("SELECT review_url, review_author FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["review_url"] == "https://www.aims.ie/post/already-there"
    assert row["review_author"] == "Added Later"


# --- admin: the reviews-queue quick paste-and-save ----------------------

def test_reviews_queue_save_accepts_an_author(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    society_id = seed_society(db)
    show_id = add_show(db, society_id, review_status="None", review_url=None)

    client.post(
        f"/admin/reviews-queue/{show_id}/save",
        data={"review_url": "https://www.aims.ie/post/new-review", "review_author": "Solo Judge"},
        follow_redirects=True,
    )

    row = db.execute("SELECT review_url, review_author FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["review_url"] == "https://www.aims.ie/post/new-review"
    assert row["review_author"] == "Solo Judge"


def test_reviews_queue_save_works_without_an_author(client, db):
    """The author field is optional - saving a link with it blank must not break."""
    admin_id = seed_user(db)
    login_as(client, admin_id)
    society_id = seed_society(db)
    show_id = add_show(db, society_id, review_status="None", review_url=None)

    client.post(
        f"/admin/reviews-queue/{show_id}/save",
        data={"review_url": "https://www.aims.ie/post/no-author"},
        follow_redirects=True,
    )

    row = db.execute("SELECT review_url, review_author FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert row["review_url"] == "https://www.aims.ie/post/no-author"
    assert row["review_author"] is None


# --- public show page ----------------------------------------------------

def test_show_page_shows_explicit_review_author(client, db):
    society_id = seed_society(db)
    show_id = add_show(db, society_id, review_author="Peter Kennedy")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by Peter Kennedy" in body


def test_explicit_review_author_takes_precedence_over_inferred_credit(client, db):
    society_id = seed_society(db)
    adj_id = seed_adjudicator(db, "Inferred Judge")
    assign(db, "24/25", "Gilbert", adj_id)
    show_id = add_show(db, society_id, review_author="Explicit Author")

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by Explicit Author" in body
    assert "Inferred Judge" not in body


def test_falls_back_to_inferred_credit_when_no_explicit_author(client, db):
    society_id = seed_society(db)
    adj_id = seed_adjudicator(db, "Solo Judge")
    assign(db, "24/25", "Gilbert", adj_id)
    show_id = add_show(db, society_id, review_author=None)

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by" in body
    assert "Solo Judge" in body
    assert f'href="/adjudicators/{adj_id}"' in body


def test_no_byline_at_all_when_neither_is_available(client, db):
    society_id = seed_society(db)
    show_id = add_show(db, society_id, review_author=None)

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by" not in body
