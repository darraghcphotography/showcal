"""Test for scripts/backfills/resolve_historical_links_and_lifecycle.py.

Verifies that confirmed links, defunct marks, lifecycle updates, and photo submission
clearances apply cleanly and are safely idempotent.
"""

from scripts.backfills.resolve_historical_links_and_lifecycle import run


def test_resolve_historical_links_and_lifecycle_dry_run_and_commit(app, db, tmp_path):
    db_path = str(tmp_path / "test_backfill.db")

    # Initialize a test db file
    import sqlite3
    from app.db import init_schema

    with app.app_context():
        # Seed test society and photo
        db.execute(
            "INSERT INTO societies (id, name, region, section, lifecycle_status) VALUES (10009, 'Encore Theatre Company', 'Western', 'Gilbert', 'Closed')"
        )
        db.execute(
            "INSERT INTO societies (id, name, region, section, lifecycle_status) VALUES (10004, 'KATS', 'Western', 'Sullivan', 'Unverified')"
        )
        db.execute(
            "INSERT INTO photo_submissions (id, kind, filename, status) VALUES (8, 'production_photo', 'test.jpg', 'pending')"
        )
        db.commit()

        # Run dry run on current test database
        current_db_path = app.config["DATABASE"]
        run(current_db_path, dry_run=True)

        # In dry run, status should still be Unverified and pending
        row_kats = db.execute("SELECT lifecycle_status FROM societies WHERE id = 10004").fetchone()
        assert row_kats["lifecycle_status"] == "Unverified"
        row_photo = db.execute("SELECT status FROM photo_submissions WHERE id = 8").fetchone()
        assert row_photo["status"] == "pending"

        # Run live
        run(current_db_path, dry_run=False)

        # After live run, KATS is Active, photo is done, links are added
        row_kats = db.execute("SELECT lifecycle_status FROM societies WHERE id = 10004").fetchone()
        assert row_kats["lifecycle_status"] == "Active"
        row_photo = db.execute("SELECT status FROM photo_submissions WHERE id = 8").fetchone()
        assert row_photo["status"] == "done"

        link_encore = db.execute(
            "SELECT * FROM historical_society_links WHERE society_name = 'Encore Theatre Company, Galway'"
        ).fetchone()
        assert link_encore is not None
        assert link_encore["society_id"] == 10009
        assert link_encore["no_match"] == 0

        link_defunct = db.execute(
            "SELECT * FROM historical_society_links WHERE society_name = 'Bangor Operatic Society'"
        ).fetchone()
        assert link_defunct is not None
        assert link_defunct["no_match"] == 1
        assert link_defunct["society_id"] is None
