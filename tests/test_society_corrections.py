"""/admin/society-corrections: a one-time review queue for
society_gate_suggestions.json (the extractor-society-gate branch's proposed
historical_reviews.society_raw corrections - see ROADMAP.md's "Near-identical-
society audit"). The suggestions file is generated offline against the PDF
archive, not recomputed here - this page only cross-references it against the
real database and lets a moderator approve or reject each one. Nothing is
applied automatically, and an already-approved (public) review is never
silently rewritten."""
import json

from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _write_suggestions(app, tmp_path, suggestions):
    path = tmp_path / "society_gate_suggestions.json"
    path.write_text(json.dumps(suggestions), encoding="utf-8")
    app.config["SOCIETY_CORRECTIONS_PATH"] = str(path)


def _seed_review(db, society_raw, show_raw="Evita", adjudicator="Jane Doe",
                  source_issue="Issue 1, January 2020", moderation_status="pending"):
    adj_id = db.execute("INSERT INTO adjudicators (name) VALUES (?)", (adjudicator,)).lastrowid
    review_id = db.execute(
        "INSERT INTO historical_reviews (season, tier, show_raw, society_raw, adjudicator_id, review_text, "
        "source_issue, moderation_status) VALUES ('19/20', 'Gilbert', ?, ?, ?, 'Some review text.', ?, ?)",
        (show_raw, society_raw, adj_id, source_issue, moderation_status),
    ).lastrowid
    return review_id


SUGGESTION = {
    "source_issue": "Issue 1, January 2020",
    "season": "19/20", "tier": "Gilbert",
    "show_raw": "Evita", "adjudicator": "Jane Doe",
    "old_society_raw": "Kill Musical Society", "new_society_raw": "Kilcock Musical Society",
    "review_excerpt": "A fine production...", "ambiguous_key": False,
}


def test_page_lists_a_suggestion_matching_a_live_review(client, db, app, tmp_path):
    seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)
    _seed_review(db, "Kill Musical Society")
    db.commit()
    _write_suggestions(app, tmp_path, [SUGGESTION])

    body = client.get("/admin/society-corrections").get_data(as_text=True)
    assert "Kill Musical Society" in body
    assert "Kilcock Musical Society" in body
    assert "1 total suggestions" in body


def test_stale_suggestion_not_shown_when_value_already_differs(client, db, app, tmp_path):
    """The live row's society_raw no longer matches old_society_raw - already
    resolved some other way, nothing actionable."""
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)
    seed_society(db)
    _seed_review(db, "Something Else Entirely")
    db.commit()
    _write_suggestions(app, tmp_path, [SUGGESTION])

    body = client.get("/admin/society-corrections").get_data(as_text=True)
    assert "No corrections left to review." in body


def test_approve_updates_society_raw_and_resolves_society_id(client, db, app, tmp_path):
    society_id = seed_society(db, name="Kilcock Musical Society")
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)
    review_id = _seed_review(db, "Kill Musical Society")
    db.commit()
    _write_suggestions(app, tmp_path, [SUGGESTION])

    client.get("/admin/society-corrections")  # loads suggestions, not required but mirrors real usage
    resp = client.post("/admin/society-corrections/apply", data={
        "review_id_0": review_id, "new_value_0": "Kilcock Musical Society",
        "source_issue_0": SUGGESTION["source_issue"], "show_raw_0": "Evita", "adjudicator_0": "Jane Doe",
        "decision_0": "approve",
    })
    assert resp.status_code == 302

    row = db.execute(
        "SELECT society_raw, society_id FROM historical_reviews WHERE id = ?", (review_id,)
    ).fetchone()
    assert row["society_raw"] == "Kilcock Musical Society"
    assert row["society_id"] == society_id


def test_approve_also_applies_to_an_already_approved_review(client, db, app, tmp_path):
    """society_raw/society_id are internal citation fields only - never
    rendered publicly, and an approved review's public society comes from
    show_id -> shows.society_id instead (untouched here). Safe to correct
    regardless of moderation_status, unlike review_text - there's no
    moderator-authored content here to clobber. The page still needs to say
    so honestly (see the template's "already public" note) rather than
    silently pretending it moves the review to a different show."""
    society_id = seed_society(db, name="Kilcock Musical Society")
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)
    review_id = _seed_review(db, "Kill Musical Society", moderation_status="approved")
    db.commit()
    _write_suggestions(app, tmp_path, [SUGGESTION])

    body = client.get("/admin/society-corrections").get_data(as_text=True)
    assert "Already approved and public" in body

    resp = client.post("/admin/society-corrections/apply", data={
        "review_id_0": review_id, "new_value_0": "Kilcock Musical Society",
        "source_issue_0": SUGGESTION["source_issue"], "show_raw_0": "Evita", "adjudicator_0": "Jane Doe",
        "decision_0": "approve",
    }, follow_redirects=True)
    assert b"Corrected 1" in resp.data

    row = db.execute(
        "SELECT society_raw, society_id, moderation_status FROM historical_reviews WHERE id = ?", (review_id,)
    ).fetchone()
    assert row["society_raw"] == "Kilcock Musical Society"
    assert row["society_id"] == society_id
    assert row["moderation_status"] == "approved"  # the review's own status is unaffected


def test_dismiss_is_remembered_and_suggestion_stops_reappearing(client, db, app, tmp_path):
    seed_society(db)
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)
    review_id = _seed_review(db, "Kill Musical Society")
    db.commit()
    _write_suggestions(app, tmp_path, [SUGGESTION])

    client.post("/admin/society-corrections/apply", data={
        "review_id_0": review_id, "new_value_0": "Kilcock Musical Society",
        "source_issue_0": SUGGESTION["source_issue"], "show_raw_0": "Evita", "adjudicator_0": "Jane Doe",
        "decision_0": "dismiss",
    })

    assert db.execute("SELECT COUNT(*) FROM dismissed_society_corrections").fetchone()[0] == 1
    body = client.get("/admin/society-corrections").get_data(as_text=True)
    assert "No corrections left to review." in body

    # Unchanged - a dismiss never touches the review row itself.
    row = db.execute("SELECT society_raw FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
    assert row["society_raw"] == "Kill Musical Society"
