"""Three fixes from live-site review:
- A suggestion marked Done shows up on the Roadmap's "Recently shipped"
  list (dated by when it was triaged), not in the main suggestions list.
- Startup purges any page_views rows for a path that's since been added to
  analytics.EXCLUDED_PATHS/EXCLUDED_PREFIXES (e.g. /manifest.webmanifest
  used to be tracked before it was excluded).
- /admin/duplicate-titles can merge two arbitrary titles directly, not just
  ones the auto-suggestion threshold happened to flag.
"""
from pathlib import Path

from app import analytics
from conftest import seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_done_suggestion_appears_in_recently_shipped_not_main_list(client, db):
    db.execute(
        "INSERT INTO feature_suggestions (message, category, triage_status) "
        "VALUES ('Historical posters browse page', 'Idea/Feature', 'Done')"
    )
    db.commit()

    body = client.get("/suggestions").get_data(as_text=True)
    assert "Historical posters browse page" in body
    # Not rendered as a suggestion card (with its category tag) - just as
    # a plain "Recently shipped" line.
    assert '<span class="tag">Idea/Feature</span>' not in body


def test_marking_a_suggestion_done_stamps_triaged_at(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    db.execute("INSERT INTO feature_suggestions (message, category) VALUES ('X', 'Bug report')")
    db.commit()
    suggestion_id = db.execute("SELECT id FROM feature_suggestions").fetchone()["id"]
    login_as(client, admin_id)

    client.post(
        f"/admin/suggestions/{suggestion_id}/update",
        data={"category": "Bug report", "triage_status": "Done"},
        follow_redirects=False,
    )
    row = db.execute("SELECT triaged_at FROM feature_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    assert row["triaged_at"] is not None


def test_purge_excluded_pageviews_removes_stale_entries(app, db):
    db.execute("INSERT INTO page_views (path, views) VALUES ('/manifest.webmanifest', 259)")
    db.execute("INSERT INTO page_views (path, views) VALUES ('/', 628)")
    db.commit()

    with app.app_context():
        analytics.purge_excluded_pageviews(db)

    remaining = {r["path"] for r in db.execute("SELECT path FROM page_views").fetchall()}
    assert remaining == {"/"}


def test_create_app_purges_stale_pageviews_at_startup(tmp_path):
    """End-to-end: create_app() itself wires the purge in, not just the
    analytics function in isolation - see app/__init__.py."""
    import sqlite3
    from app import create_app

    db_path = tmp_path / "startup-purge.db"
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO page_views (path, views) VALUES ('/manifest.webmanifest', 259)")
    conn.execute("INSERT INTO page_views (path, views) VALUES ('/', 628)")
    conn.commit()
    conn.close()

    create_app({
        "TESTING": True, "DATABASE": str(db_path), "SECRET_KEY": "x",
        "WTF_CSRF_ENABLED": False, "UPLOAD_DIR": str(tmp_path / "uploads"),
    })

    conn = sqlite3.connect(db_path)
    remaining = {r[0] for r in conn.execute("SELECT path FROM page_views").fetchall()}
    conn.close()
    assert remaining == {"/"}


def test_manual_merge_works_for_a_pair_below_the_auto_suggest_threshold(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, result) VALUES (2015, 'Nativity! The Musical', 'Some Society', 'Nominee')"
    )
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, result) VALUES (2018, 'Nativity', 'Some Society', 'Nominee')"
    )
    db.commit()
    login_as(client, admin_id)

    resp = client.post(
        "/admin/duplicate-titles/merge",
        data={"canonical": "Nativity", "other": "Nativity! The Musical"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    remaining_titles = {
        r[0] for r in db.execute("SELECT DISTINCT show FROM historical_results").fetchall()
    }
    assert remaining_titles == {"Nativity"}


def test_duplicate_titles_page_offers_manual_merge_form(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)
    body = client.get("/admin/duplicate-titles").get_data(as_text=True)
    assert 'action="/admin/duplicate-titles/merge"' in body
    assert "Merge two titles directly" in body


def test_duplicate_titles_page_shows_true_total_beyond_display_limit(client, db):
    """Real production issue: the dashboard's duplicate-title count used to
    look permanently stuck at 60 (find_candidates truncated internally) even
    as pairs got resolved - the page now says how many exist beyond what's
    shown, instead of silently capping with no indication."""
    admin_id = seed_user(db, username="mod", role="moderator")
    for i in range(70):
        db.execute(
            "INSERT INTO historical_results (year, show, society_name, result) VALUES (2000, ?, 'Some Society', 'Nominee')",
            (f"Show {i}",),
        )
        db.execute(
            "INSERT INTO historical_results (year, show, society_name, result) VALUES (2000, ?, 'Some Society', 'Nominee')",
            (f"Show {i} Extra",),
        )
    db.commit()
    login_as(client, admin_id)

    body = client.get("/admin/duplicate-titles").get_data(as_text=True)
    assert "Showing the top 60 of" in body


def test_merge_does_not_crash_when_society_already_has_both_titles_same_season(client, db):
    """Real production bug: shows has a UNIQUE index on (society_id, season,
    show) - if one society already logged both the canonical and duplicate
    title for the same season (exactly the case this tool is meant to fix),
    the old blind UPDATE collided with that constraint and 500'd, taking the
    whole bulk-save down with it."""
    from conftest import seed_society

    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '24/25', 'Eastern', 'Nativity', 'approved', 'import')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '24/25', 'Eastern', 'Nativity! The Musical', 'approved', 'import')",
        (society_id,),
    )
    db.commit()
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    resp = client.post(
        "/admin/duplicate-titles/merge",
        data={"canonical": "Nativity", "other": "Nativity! The Musical"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.execute(
        "SELECT show FROM shows WHERE society_id = ? AND season = '24/25'", (society_id,)
    ).fetchall()
    assert [r["show"] for r in rows] == ["Nativity"]


def test_merge_still_renames_when_no_collision(client, db):
    from conftest import seed_society

    society_a = seed_society(db, id=1, name="Society A")
    society_b = seed_society(db, id=2, name="Society B")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '24/25', 'Eastern', 'Nativity! The Musical', 'approved', 'import')",
        (society_a,),
    )
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '24/25', 'Eastern', 'Nativity! The Musical', 'approved', 'import')",
        (society_b,),
    )
    db.commit()
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    client.post(
        "/admin/duplicate-titles/merge",
        data={"canonical": "Nativity", "other": "Nativity! The Musical"},
        follow_redirects=False,
    )

    shows = {r["show"] for r in db.execute("SELECT show FROM shows").fetchall()}
    assert shows == {"Nativity"}
    assert db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 2


def test_admin_can_delete_a_suggestion(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    db.execute("INSERT INTO feature_suggestions (message, category) VALUES ('Accidental duplicate', 'Data error')")
    db.commit()
    suggestion_id = db.execute("SELECT id FROM feature_suggestions").fetchone()["id"]
    login_as(client, admin_id)

    resp = client.post(f"/admin/suggestions/{suggestion_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert db.execute("SELECT 1 FROM feature_suggestions WHERE id = ?", (suggestion_id,)).fetchone() is None


def test_delete_suggestion_requires_login(client, db):
    db.execute("INSERT INTO feature_suggestions (message, category) VALUES ('X', 'Bug report')")
    db.commit()
    suggestion_id = db.execute("SELECT id FROM feature_suggestions").fetchone()["id"]

    resp = client.post(f"/admin/suggestions/{suggestion_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]
    assert db.execute("SELECT 1 FROM feature_suggestions WHERE id = ?", (suggestion_id,)).fetchone() is not None


def test_admin_suggestions_page_archives_done_behind_disclosure(client, db):
    admin_id = seed_user(db, username="mod", role="moderator")
    db.execute("INSERT INTO feature_suggestions (message, category, triage_status) VALUES ('Still open', 'Idea/Feature', 'Planned')")
    db.execute("INSERT INTO feature_suggestions (message, category, triage_status) VALUES ('Finished thing', 'Idea/Feature', 'Done')")
    db.commit()
    login_as(client, admin_id)

    body = client.get("/admin/suggestions").get_data(as_text=True)
    before_details = body.split("<details>")[0]
    inside_details = body.split("<details>")[1]
    assert "Still open" in before_details
    assert "Finished thing" not in before_details
    assert "Finished thing" in inside_details


def test_roadmap_shows_full_datetime_for_shipped_entries(client, db):
    # created_at is stored UTC (SQLite's datetime('now')) and irish_datetime
    # converts to Irish local time for display - 2026-08-05 is BST (UTC+1),
    # so 14:30 UTC becomes 15:30 on screen. See tests/test_filters.py for
    # the conversion itself.
    db.execute(
        "INSERT INTO changelog_entries (entry, created_at) VALUES ('Shipped a thing', '2026-08-05 14:30:00')"
    )
    db.commit()
    body = client.get("/suggestions").get_data(as_text=True)
    assert "05 Aug 2026, 15:30" in body


def test_merge_moves_a_showtimes_review_off_the_row_it_deletes(client, db):
    """Real production 500: merging two titles where one society has both in
    the same season deletes the redundant shows row - but once the ShowTimes
    import existed, a historical_reviews row could reference that show
    (historical_reviews.show_id), so the DELETE hit a FOREIGN KEY constraint
    and took the whole bulk merge down. The review has to move onto the
    surviving row, not be orphaned or block the merge."""
    from conftest import seed_society

    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (id, society_id, season, region, show, moderation_status, source) "
        "VALUES (900, ?, '24/25', 'Eastern', 'Nativity', 'approved', 'import')",
        (society_id,),
    )
    db.execute(
        "INSERT INTO shows (id, society_id, season, region, show, moderation_status, source) "
        "VALUES (901, ?, '24/25', 'Eastern', 'Nativity! The Musical', 'approved', 'historical')",
        (society_id,),
    )
    db.execute(
        """
        INSERT INTO historical_reviews
            (id, season, tier, show_raw, society_raw, review_text, source_issue,
             show_id, society_id, moderation_status)
        VALUES (700, '24/25', 'Sullivan', 'Nativity! The Musical', 'Test Society',
                'A fine production.', 'Issue 1, January 2025', 901, ?, 'approved')
        """,
        (society_id,),
    )
    db.commit()
    admin_id = seed_user(db, username="mod", role="moderator")
    login_as(client, admin_id)

    resp = client.post(
        "/admin/duplicate-titles/merge",
        data={"canonical": "Nativity", "other": "Nativity! The Musical"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    review = db.execute("SELECT show_id FROM historical_reviews WHERE id = 700").fetchone()
    assert review["show_id"] == 900  # moved onto the surviving row, not orphaned
    assert db.execute("SELECT COUNT(*) AS n FROM shows WHERE id = 901").fetchone()["n"] == 0
