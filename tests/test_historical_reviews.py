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


def seed_award(db, society_id, year, show):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_id, source) "
        "VALUES (?, 'Sullivan', 'Best Overall Show', 'Winner', ?, ?, 'manual')",
        (year, show, society_id),
    )
    db.commit()


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
    return db.execute(
        "SELECT id FROM historical_reviews WHERE show_raw = ? AND society_raw = ? AND source_issue = ?",
        (show_raw, society_raw, source_issue),
    ).fetchone()["id"]


def test_queue_requires_login(client):
    resp = client.get("/admin/historical-reviews")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_queue_lists_pending_reviews(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    seed_historical_review(db, society_id=society_id, show_raw="Oliver!", flag="no_show_match")

    resp = client.get("/admin/historical-reviews")
    assert resp.status_code == 200
    assert b"Oliver!" in resp.data
    assert b"no matching show on record" in resp.data


def test_queue_groups_a_review_with_no_society_matched(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)
    seed_historical_review(db, society_id=None, show_raw="Carousel", flag="needs_check")

    resp = client.get("/admin/historical-reviews")
    assert resp.status_code == 200
    assert b"Needs a society matched" in resp.data
    assert b"Carousel" in resp.data


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


def test_bulk_approve_publishes_only_matched_no_show_match_reviews(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    matched_1 = seed_historical_review(db, society_id=society_id, show_raw="Show One", flag="no_show_match")
    matched_2 = seed_historical_review(db, society_id=society_id, show_raw="Show Two", flag="no_show_match")
    needs_check = seed_historical_review(db, society_id=None, show_raw="Show Three", flag="needs_check")

    resp = client.post("/admin/historical-reviews/bulk-approve")
    assert resp.status_code == 302

    for review_id in (matched_1, matched_2):
        review = db.execute("SELECT * FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
        assert review["moderation_status"] == "approved"
        assert review["show_id"] is not None
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 2

    still_pending = db.execute("SELECT moderation_status FROM historical_reviews WHERE id = ?", (needs_check,)).fetchone()
    assert still_pending["moderation_status"] == "pending"


def test_bulk_approve_leaves_natural_key_conflicts_pending_for_a_moderator_to_pick(client, db):
    """Two reviews of the same (society, season, show) - a real production
    extracted twice from two different source issues, confirmed in the full
    archive (e.g. a show reviewed in both a February and a March issue) -
    would collide on ux_shows_natural_key if both tried to create their own
    skeleton show. categorize_pending_reviews catches this up front (see
    the 'conflict' category) and keeps *both* out of bulk-approve, rather
    than non-deterministically approving whichever one the batch happens to
    process first and leaving the other to fail - a moderator needs to
    actually look at both and decide which is the better transcription."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    first = seed_historical_review(db, society_id=society_id, show_raw="Titanic", flag="no_show_match")
    conflicting = seed_historical_review(
        db, society_id=society_id, show_raw="Titanic", flag="no_show_match",
        source_issue="Issue 66, March 2011",
    )
    clean = seed_historical_review(db, society_id=society_id, show_raw="Show Two", flag="no_show_match")

    resp = client.post("/admin/historical-reviews/bulk-approve")
    assert resp.status_code == 302

    clean_review = db.execute("SELECT moderation_status FROM historical_reviews WHERE id = ?", (clean,)).fetchone()
    assert clean_review["moderation_status"] == "approved"

    for review_id in (first, conflicting):
        review = db.execute("SELECT moderation_status FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
        assert review["moderation_status"] == "pending"
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 1  # only "Show Two"'s skeleton


def test_queue_flags_a_likely_historical_results_match(client, db):
    """No existing shows row (expected before 23/24), but the awards
    archive already has this same production under a slightly different
    title ('Titanic' vs 'Titanic The Musical', the real case that surfaced
    this - both the same 2011 production, just worded differently between
    the ShowTimes review heading and the AIMS awards CSV). Should land in
    history_match, not bulk-approvable as-is."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Marian Choral Society, Tuam")
    seed_award(db, society_id, 2011, "Titanic The Musical")
    login_as(client, admin_id)
    seed_historical_review(
        db, society_id=society_id, season="10/11", show_raw="Titanic", flag="no_show_match",
    )

    resp = client.get("/admin/historical-reviews")
    assert resp.status_code == 200
    assert b"Likely has award history" in resp.data
    assert b"Titanic The Musical" in resp.data

    bulk_resp = client.post("/admin/historical-reviews/bulk-approve")
    assert bulk_resp.status_code == 302
    review = db.execute("SELECT moderation_status FROM historical_reviews WHERE show_raw = 'Titanic'").fetchone()
    assert review["moderation_status"] == "pending"  # not blindly approved with the wrong title


def test_apply_title_match_corrects_show_raw_and_becomes_ready(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Marian Choral Society, Tuam")
    seed_award(db, society_id, 2011, "Titanic The Musical")
    login_as(client, admin_id)
    review_id = seed_historical_review(
        db, society_id=society_id, season="10/11", show_raw="Titanic", flag="no_show_match",
    )

    resp = client.post(
        f"/admin/historical-reviews/{review_id}/apply-title-match", data={"title": "Titanic The Musical"},
    )
    assert resp.status_code == 302

    review = db.execute("SELECT show_raw, flag FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert review["show_raw"] == "Titanic The Musical"
    assert review["flag"] == "no_show_match"  # still no *shows* row, but now the right title

    # now the corrected title matches the awards archive exactly, so it's
    # no longer a history_match needing a title check - safe to bulk-approve
    bulk_resp = client.post("/admin/historical-reviews/bulk-approve")
    assert bulk_resp.status_code == 302
    approved = db.execute("SELECT moderation_status, show_id FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert approved["moderation_status"] == "approved"
    show = db.execute("SELECT show FROM shows WHERE id = ?", (approved["show_id"],)).fetchone()
    assert show["show"] == "Titanic The Musical"


def test_bulk_approve_includes_reviews_already_matched_to_an_existing_show(client, db):
    """A review already linked to a real shows row (flag=None) is the most
    confident case there is - categorize_pending_reviews puts it in 'ready'
    alongside the no-existing-show ones, so bulk-approve covers it too
    instead of leaving it stuck needing an individual click."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, source) "
        "VALUES (?, '22/23', 'Eastern', 'Sullivan', 'Already There', 'import')",
        (society_id,),
    )
    db.commit()
    existing_show_id = db.execute("SELECT id FROM shows").fetchone()["id"]
    login_as(client, admin_id)
    already_matched = seed_historical_review(
        db, society_id=society_id, show_id=existing_show_id, show_raw="Already There", flag=None,
    )

    client.post("/admin/historical-reviews/bulk-approve")

    review = db.execute("SELECT moderation_status, show_id FROM historical_reviews WHERE id = ?", (already_matched,)).fetchone()
    assert review["moderation_status"] == "approved"
    assert review["show_id"] == existing_show_id
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 1  # no extra skeleton created


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


def test_skeleton_show_page_displays_matching_award_history(client, db):
    """A skeleton show has no foreign key to historical_results (that table
    predates this whole review/shows system) - public.show_detail matches
    them at display time instead, by (society, year, exact-normalized
    title). Confirms a review approved with the *correct*, awards-archive-
    aligned title (season -> year via historical_results_year: '10/11' ->
    2011) actually surfaces that history on its own page - the whole point
    of the history_match/apply-title-match flow in admin.py."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Marian Choral Society, Tuam")
    login_as(client, admin_id)
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_id, source) "
        "VALUES (2011, 'Sullivan', 'Best Overall Show', 'Winner', 'Titanic The Musical', ?, 'manual')",
        (society_id,),
    )
    db.commit()
    review_id = seed_historical_review(
        db, society_id=society_id, season="10/11", tier="Sullivan",
        show_raw="Titanic The Musical", flag="no_show_match",
    )
    client.post(f"/admin/historical-reviews/{review_id}/approve")
    show_id = db.execute("SELECT show_id FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()["show_id"]

    resp = client.get(f"/shows/{show_id}")
    body = resp.get_data(as_text=True)
    assert "Awards &amp; nominations" in body
    assert "Best Overall Show" in body
    assert "Winner" in body


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


def seed_skeleton_show(db, society_id, season, show, tier="Sullivan"):
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, source, moderation_status) "
        "VALUES (?, ?, 'Eastern', ?, ?, 'historical', 'approved')",
        (society_id, season, tier, show),
    )
    db.commit()
    return db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]


def test_title_check_flags_a_real_wording_gap_but_not_a_case_difference(client, db):
    """Retroactive audit for skeleton shows approved before this check
    existed (find_mismatched_skeleton_shows). A pure case/punctuation
    difference is already tolerated by show_detail's own award-history
    lookup (normalize_title), so shouldn't need a manual fix; a real
    wording gap ('And His' vs 'and the') isn't tolerated by that and
    should show up here."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    seed_award(db, society_id, 2011, "Joseph and the Amazing Technicolor Dreamcoat")
    seed_award(db, society_id, 2015, "Rock of Ages")
    case_only = seed_skeleton_show(db, society_id, "14/15", "Rock Of Ages")
    real_gap = seed_skeleton_show(db, society_id, "10/11", "Joseph And His Amazing Technicolor Dreamcoat")

    resp = client.get("/admin/historical-shows/title-check")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Joseph And His Amazing Technicolor Dreamcoat" in body
    assert "Rock Of Ages" not in body  # case-only difference, not flagged

    show = db.execute("SELECT show FROM shows WHERE id = ?", (case_only,)).fetchone()
    assert show["show"] == "Rock Of Ages"  # untouched either way


def test_apply_show_title_match_corrects_a_skeleton_shows_title(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    seed_award(db, society_id, 2011, "Joseph and the Amazing Technicolor Dreamcoat")
    show_id = seed_skeleton_show(db, society_id, "10/11", "Joseph And His Amazing Technicolor Dreamcoat")

    resp = client.post(
        f"/admin/historical-shows/{show_id}/apply-title-match",
        data={"title": "Joseph and the Amazing Technicolor Dreamcoat"},
    )
    assert resp.status_code == 302

    show = db.execute("SELECT show FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert show["show"] == "Joseph and the Amazing Technicolor Dreamcoat"

    detail_resp = client.get(f"/shows/{show_id}")
    assert b"Awards &amp; nominations" in detail_resp.data


def test_apply_show_title_match_merges_into_an_already_existing_show(client, db):
    """The corrected title can collide with a real shows row that already
    exists independently of the review pipeline - confirmed in production
    (Thurles Musical Society, 17/18: a member submission 'Ragtime The
    Musical' already existed; a review's own skeleton was a separate row
    titled just 'Ragtime' for the same actual production). A plain rename
    500'd on ux_shows_natural_key - should instead re-point the review onto
    the real show and remove the now-redundant skeleton."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    adjudicator_id = seed_adjudicator(db)
    login_as(client, admin_id)
    real_show_id = seed_skeleton_show(db, society_id, "17/18", "Ragtime The Musical")
    db.execute("UPDATE shows SET source = 'submission' WHERE id = ?", (real_show_id,))
    db.commit()
    skeleton_id = seed_skeleton_show(db, society_id, "17/18", "Ragtime")
    review_id = seed_historical_review(
        db, society_id=society_id, adjudicator_id=adjudicator_id, show_id=skeleton_id,
        season="17/18", show_raw="Ragtime", flag=None, source_issue="Issue 126, December 2017",
    )
    db.execute("UPDATE historical_reviews SET moderation_status = 'approved' WHERE id = ?", (review_id,))
    db.commit()

    resp = client.post(
        f"/admin/historical-shows/{skeleton_id}/apply-title-match", data={"title": "Ragtime The Musical"},
    )
    assert resp.status_code == 302

    assert db.execute("SELECT id FROM shows WHERE id = ?", (skeleton_id,)).fetchone() is None  # skeleton removed
    review = db.execute("SELECT show_id FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert review["show_id"] == real_show_id  # re-pointed onto the real show

    detail_resp = client.get(f"/shows/{real_show_id}")
    assert b"A fine production." in detail_resp.data  # the review now renders on the real show's page


def test_apply_show_title_match_refuses_a_non_skeleton_show(client, db):
    """A real imported show's title is authoritative on its own - this
    action only ever touches source='historical' rows."""
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Tullyvin Musical Society")
    login_as(client, admin_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, source) "
        "VALUES (?, '23/24', 'Eastern', 'Sullivan', 'Real Show', 'import')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Real Show'").fetchone()["id"]

    resp = client.post(f"/admin/historical-shows/{show_id}/apply-title-match", data={"title": "Something Else"})
    assert resp.status_code == 404

    show = db.execute("SELECT show FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert show["show"] == "Real Show"
