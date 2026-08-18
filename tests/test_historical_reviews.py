"""/admin/historical-reviews - the Step 4 moderation queue for reviews
extracted from the AIMS ShowTimes PDF archive (see extract_historical_reviews.py
and ROADMAP.md's "Step 4" sections). Covers the queue listing, approve (both
the clean-match and skeleton-show-creation paths), skip/reject, and edit-
fields recomputing the match flag - plus that an approved review actually
renders on the resulting show's own public page."""
import re

from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_adjudicator(db, name="Peter Kennedy"):
    db.execute("INSERT INTO adjudicators (name) VALUES (?)", (name,))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def seed_historical_review(
    db, season="22/23", tier="Sullivan", show_raw="The Addams Family", society_raw="Tullyvin Musical Society",
    adjudicator_id=None, review_text="A fine production.", source_issue="Issue 160, December 2022",
    show_id=None, society_id=None, flag="no_show_match",
):
    db.execute(
        """
        INSERT INTO historical_reviews
            (season, tier, show_raw, society_raw, adjudicator_id, review_text, source_issue,
             show_id, society_id, flag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (season, tier, show_raw, society_raw, adjudicator_id, review_text, source_issue, show_id, society_id, flag),
    )
    db.commit()
    return db.execute("SELECT id FROM historical_reviews WHERE show_raw = ? AND society_raw = ?",
                       (show_raw, society_raw)).fetchone()["id"]


def test_queue_requires_login(client):
    resp = client.get("/admin/historical-reviews")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_queue_lists_pending_reviews(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    seed_historical_review(db, show_raw="Oliver!")

    resp = client.get("/admin/historical-reviews")
    assert resp.status_code == 200
    assert b"Oliver!" in resp.data
    assert b"no matching show on record" in resp.data


def test_approve_with_no_existing_show_creates_skeleton(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    adjudicator_id = seed_adjudicator(db)
    login_as(client, admin_id)
    review_id = seed_historical_review(
        db, society_id=society_id, adjudicator_id=adjudicator_id, flag="no_show_match",
    )

    resp = client.post(f"/admin/historical-reviews/{review_id}/approve")
    assert resp.status_code == 302

    review = db.execute("SELECT * FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert review["moderation_status"] == "approved"
    assert review["show_id"] is not None

    show = db.execute("SELECT * FROM shows WHERE id = ?", (review["show_id"],)).fetchone()
    assert show["source"] == "historical"
    assert show["moderation_status"] == "approved"
    assert show["show"] == "The Addams Family"
    assert show["society_id"] == society_id
    assert show["season"] == "22/23"
    assert show["section"] == "Sullivan"


def test_approve_links_to_an_already_matched_show(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, source) "
        "VALUES (?, '22/23', 'Eastern', 'Sullivan', 'The Addams Family', 'import')",
        (society_id,),
    )
    db.commit()
    existing_show_id = db.execute("SELECT id FROM shows").fetchone()["id"]
    login_as(client, admin_id)
    review_id = seed_historical_review(db, society_id=society_id, show_id=existing_show_id, flag=None)

    resp = client.post(f"/admin/historical-reviews/{review_id}/approve")
    assert resp.status_code == 302

    review = db.execute("SELECT * FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert review["show_id"] == existing_show_id
    # No second show should have been created for an already-matched review.
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 1


def test_approve_without_a_matched_society_is_refused(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    review_id = seed_historical_review(db, society_id=None, flag="needs_check")

    resp = client.post(f"/admin/historical-reviews/{review_id}/approve")
    assert resp.status_code == 302

    review = db.execute("SELECT * FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert review["moderation_status"] == "pending"
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 0


def test_skip_rejects_without_touching_shows(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    review_id = seed_historical_review(db, society_id=None, flag="needs_check")

    resp = client.post(f"/admin/historical-reviews/{review_id}/reject")
    assert resp.status_code == 302

    review = db.execute("SELECT * FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert review["moderation_status"] == "rejected"
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 0


def test_skeleton_show_does_not_double_count_against_the_awards_archive(client, db):
    """A skeleton show has no opening_date, so it's naturally excluded from
    most stats() leaderboards (they filter on 'has this happened by today').
    /titles is the case that actually needs the explicit
    shows.source != 'historical' exclusion (see public.titles_list()) -
    nothing there depends on dates, so without the fix this same production
    would be counted twice: once via the skeleton shows row, once via its
    real historical_results award record."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    review_id = seed_historical_review(
        db, society_id=society_id, show_raw="Double Count Test", season="22/23", flag="no_show_match",
    )
    client.post(f"/admin/historical-reviews/{review_id}/approve")
    db.execute(
        "INSERT INTO historical_results (year, show, society_id, society_name) VALUES (2023, ?, ?, ?)",
        ("Double Count Test", society_id, "Tullyvin Musical Society"),
    )
    db.commit()

    resp = client.get("/titles?q=Double+Count+Test")
    body = resp.get_data(as_text=True)
    row_match = re.search(r"<tr>\s*<td>.*?Double Count Test.*?</td>\s*<td>(\d+)</td>", body, re.S)
    assert row_match is not None
    assert row_match.group(1) == "1"


def test_edit_fields_matches_a_society_and_recomputes_flag(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    review_id = seed_historical_review(db, society_id=None, flag="needs_check")

    resp = client.post(
        f"/admin/historical-reviews/{review_id}/edit",
        data={
            "season": "22/23", "tier": "Sullivan", "show_raw": "The Addams Family",
            "society_raw": "Tullyvin Musical Society", "society_id": str(society_id),
            "review_text": "A fine production.", "source_issue": "Issue 160, December 2022",
        },
    )
    assert resp.status_code == 302

    review = db.execute("SELECT * FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert review["society_id"] == society_id
    assert review["flag"] == "no_show_match"  # society now matched, but still no shows row
    assert review["moderation_status"] == "pending"  # edit alone never approves


def test_approved_review_renders_on_the_shows_own_page(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    adjudicator_id = seed_adjudicator(db, name="Peter Kennedy")
    login_as(client, admin_id)
    review_id = seed_historical_review(
        db, society_id=society_id, adjudicator_id=adjudicator_id,
        review_text="A genuinely excellent production of the Addams Family.",
        flag="no_show_match",
    )
    client.post(f"/admin/historical-reviews/{review_id}/approve")
    show_id = db.execute("SELECT show_id FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()["show_id"]

    resp = client.get(f"/shows/{show_id}")
    assert resp.status_code == 200
    assert b"A genuinely excellent production of the Addams Family." in resp.data
    assert b"Reviewed by" in resp.data
    assert b"Peter Kennedy" in resp.data
    assert b"Issue 160, December 2022" in resp.data
