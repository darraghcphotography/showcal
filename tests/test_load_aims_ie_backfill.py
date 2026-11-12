"""load_aims_ie_backfill.py: loads the aims.ie export conservatively - a
review lands pending (or approved with --approve), a link is only changed
while the live value is what the file expected, a credit only fills a blank,
and anything matched to a show that has since changed is skipped."""
import json

import load_aims_ie_backfill as loader
from conftest import seed_society


def seed(db):
    seed_society(db, name="Test Society")
    db.execute(
        "INSERT INTO shows (society_id, season, show, region, section, moderation_status, source, director) "
        "VALUES (1, '24/25', 'Evita', 'Eastern', 'Gilbert', 'approved', 'import', 'Already Here')"
    )
    db.execute("INSERT INTO adjudicators (name) VALUES ('Jane Smith')")
    db.commit()
    return db.execute("SELECT id FROM shows").fetchone()["id"]


def write_json(tmp_path, show_id, **overrides):
    match = {"show_id": show_id, "expect_society": "Test Society", "expect_season": "24/25"}
    data = {
        "reviews": [dict(
            match, wix_title="Review: Evita - Test", tier="Gilbert", show_raw="Evita", adjudicator="Jane Smith",
            review_text="One.\n\nTwo.", source_issue="6 March 2025", source_file="https://www.aims.ie/post/evita",
        )],
        "review_links": [dict(match, field="review_url", current=None, new="https://www.aims.ie/post/evita", set_title=None)],
        "credits": [
            dict(match, field="director", value="Someone Else"),
            dict(match, field="choreographer", value="New Choreo"),
        ],
    }
    data.update(overrides)
    path = tmp_path / "backfill.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def run(app, path, *extra):
    return loader.main(["--db", app.config["DATABASE"], "--json", path, *extra])


def test_loads_review_pending_with_show_and_adjudicator(app, db, tmp_path):
    show_id = seed(db)
    run(app, write_json(tmp_path, show_id))
    row = db.execute("SELECT * FROM historical_reviews").fetchone()
    assert row["source"] == "aims_ie"
    assert row["moderation_status"] == "pending"
    assert row["show_id"] == show_id
    assert row["adjudicator_id"] == 1
    assert row["source_file"] == "https://www.aims.ie/post/evita"


def test_approve_flag_publishes(app, db, tmp_path):
    show_id = seed(db)
    run(app, write_json(tmp_path, show_id), "--approve")
    assert db.execute("SELECT moderation_status FROM historical_reviews").fetchone()[0] == "approved"


def test_credits_fill_blanks_only_and_link_is_set(app, db, tmp_path):
    show_id = seed(db)
    run(app, write_json(tmp_path, show_id))
    show = db.execute("SELECT * FROM shows WHERE id = ?", (show_id,)).fetchone()
    assert show["director"] == "Already Here"
    assert show["choreographer"] == "New Choreo"
    assert show["review_url"] == "https://www.aims.ie/post/evita"
    assert show["review_status"] == "Published"


def test_rerun_changes_nothing(app, db, tmp_path):
    show_id = seed(db)
    path = write_json(tmp_path, show_id)
    run(app, path)
    report = run(app, path)
    assert report["reviews_inserted"] == 0
    assert report["reviews_already_loaded"] == 1
    assert report["links_changed"] == 0
    assert sum(report["credits_filled"].values()) == 0
    assert db.execute("SELECT COUNT(*) FROM historical_reviews").fetchone()[0] == 1


def test_link_left_alone_if_changed_since_export(app, db, tmp_path):
    show_id = seed(db)
    db.execute("UPDATE shows SET review_url = 'https://example.org/other' WHERE id = ?", (show_id,))
    db.commit()
    report = run(app, write_json(tmp_path, show_id))
    assert report["links_changed"] == 0
    assert db.execute("SELECT review_url FROM shows").fetchone()[0] == "https://example.org/other"


def test_everything_skipped_if_show_no_longer_matches(app, db, tmp_path):
    show_id = seed(db)
    db.execute("UPDATE shows SET season = '25/26' WHERE id = ?", (show_id,))
    db.commit()
    report = run(app, write_json(tmp_path, show_id))
    assert report["reviews_inserted"] == 0
    assert report["links_changed"] == 0
    assert sum(report["credits_filled"].values()) == 0


def test_dry_run_writes_nothing(app, db, tmp_path):
    show_id = seed(db)
    report = run(app, write_json(tmp_path, show_id), "--dry-run")
    assert report["reviews_inserted"] == 1
    assert db.execute("SELECT COUNT(*) FROM historical_reviews").fetchone()[0] == 0
    assert db.execute("SELECT choreographer FROM shows").fetchone()[0] is None
