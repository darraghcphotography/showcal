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
