"""Reviews from the old aims.ie (Wix) blog, 23/24 onwards, live in
historical_reviews with source='aims_ie' so the show page can credit them
("Originally published on aims.ie", linked to the post) instead of
mislabelling them as ShowTimes reviews or as typed-in manual ones.

Adding the value needs a CHECK change, which SQLite can only do by
rebuilding the table - the migration tests run against a raw connection
holding the exact old shape the live database has (source and
production_id appended by ALTER TABLE), FTS index and triggers included."""
import sqlite3

from app.db import _migrate_historical_reviews_source_check
from conftest import seed_society

# The live table as it actually stands before this migration: the original
# CREATE plus two ALTER TABLE ADD COLUMNs, which is why source sits after
# created_at rather than where schema.sql puts it.
OLD_SHAPE = """
CREATE TABLE historical_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    season          TEXT NOT NULL,
    tier            TEXT CHECK (tier IN ('Gilbert', 'Sullivan') OR tier IS NULL),
    show_raw        TEXT NOT NULL,
    society_raw     TEXT NOT NULL,
    adjudicator_id  INTEGER REFERENCES adjudicators(id),
    review_text     TEXT NOT NULL,
    source_issue    TEXT,
    source_file     TEXT,
    show_id         INTEGER REFERENCES shows(id),
    society_id      INTEGER REFERENCES societies(id),
    flag            TEXT CHECK (flag IN ('needs_check', 'no_show_match') OR flag IS NULL),
    moderation_status TEXT NOT NULL DEFAULT 'pending' CHECK (moderation_status IN (
                            'pending', 'approved', 'rejected'
                        )),
    moderated_by    TEXT,
    moderated_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
, source TEXT NOT NULL DEFAULT 'showtimes' CHECK (source IN ('showtimes', 'manual')), production_id INTEGER REFERENCES productions(id));
CREATE INDEX idx_historical_reviews_show_id ON historical_reviews(show_id);
CREATE INDEX idx_historical_reviews_production_id ON historical_reviews(production_id);
CREATE VIRTUAL TABLE historical_reviews_fts USING fts5(
    show_raw, society_raw, review_text, content='historical_reviews', content_rowid='id'
);
CREATE TRIGGER historical_reviews_fts_ai AFTER INSERT ON historical_reviews BEGIN
    INSERT INTO historical_reviews_fts(rowid, show_raw, society_raw, review_text)
    VALUES (new.id, new.show_raw, new.society_raw, new.review_text);
END;
CREATE TRIGGER historical_reviews_fts_ad AFTER DELETE ON historical_reviews BEGIN
    INSERT INTO historical_reviews_fts(historical_reviews_fts, rowid, show_raw, society_raw, review_text)
    VALUES ('delete', old.id, old.show_raw, old.society_raw, old.review_text);
END;
"""


def make_old_shape_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(OLD_SHAPE)
    db.execute(
        "INSERT INTO historical_reviews (id, season, show_raw, society_raw, review_text, source, production_id) "
        "VALUES (7, '18/19', 'Oliver!', 'Test Society', 'A marvellous Fagin.', 'showtimes', 3)"
    )
    db.commit()
    return db


def table_sql(db):
    return db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'historical_reviews'"
    ).fetchone()[0]


def test_migration_allows_aims_ie_source():
    db = make_old_shape_db()
    _migrate_historical_reviews_source_check(db)
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, source) "
        "VALUES ('24/25', 'Evita', 'Test Society', 'Strong lead.', 'aims_ie')"
    )
    assert "aims_ie" in table_sql(db)


def test_migration_keeps_rows_ids_and_values():
    db = make_old_shape_db()
    _migrate_historical_reviews_source_check(db)
    row = db.execute("SELECT * FROM historical_reviews").fetchone()
    assert row["id"] == 7
    assert row["source"] == "showtimes"
    assert row["production_id"] == 3
    assert row["review_text"] == "A marvellous Fagin."


def test_migration_keeps_indexes_triggers_and_search():
    db = make_old_shape_db()
    _migrate_historical_reviews_source_check(db)
    names = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE tbl_name = 'historical_reviews' AND type IN ('index', 'trigger')"
    )}
    assert {"idx_historical_reviews_show_id", "idx_historical_reviews_production_id",
            "historical_reviews_fts_ai", "historical_reviews_fts_ad"} <= names

    # The pre-existing row is still findable (rowid unchanged), and the
    # recreated insert trigger indexes a new one.
    assert db.execute("SELECT rowid FROM historical_reviews_fts WHERE historical_reviews_fts MATCH 'fagin'").fetchall()[0][0] == 7
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, source) "
        "VALUES ('24/25', 'Evita', 'Test Society', 'A commanding Peron.', 'aims_ie')"
    )
    assert len(db.execute("SELECT rowid FROM historical_reviews_fts WHERE historical_reviews_fts MATCH 'peron'").fetchall()) == 1


def test_migration_is_a_no_op_once_applied():
    db = make_old_shape_db()
    _migrate_historical_reviews_source_check(db)
    before = table_sql(db)
    _migrate_historical_reviews_source_check(db)
    assert table_sql(db) == before


def test_fresh_database_already_allows_aims_ie(db):
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, source) "
        "VALUES ('24/25', 'Evita', 'Test Society', 'Strong lead.', 'aims_ie')"
    )


def seed_show_with_aims_ie_review(db):
    seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, show, region, section, moderation_status, source, "
        "review_status, review_url) VALUES (1, '24/25', 'Evita', 'Eastern', 'Gilbert', 'approved', 'import', "
        "'Published', 'https://www.aims.ie/post/evita-test')"
    )
    show_id = db.execute("SELECT id FROM shows").fetchone()["id"]
    db.execute("INSERT INTO adjudicators (name) VALUES ('Jane Smith')")
    db.execute(
        "INSERT INTO historical_reviews (season, tier, show_raw, society_raw, adjudicator_id, review_text, "
        "source_issue, source_file, show_id, society_id, moderation_status, source) "
        "VALUES ('24/25', 'Gilbert', 'Evita', 'Test Society', 1, 'First paragraph.\nSecond paragraph.', "
        "'6 March 2025', 'https://www.aims.ie/post/evita-test', ?, 1, 'approved', 'aims_ie')",
        (show_id,),
    )
    db.commit()
    return show_id


def test_show_page_credits_aims_ie_with_a_link(client, db):
    show_id = seed_show_with_aims_ie_review(db)
    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Second paragraph." in body
    assert "Originally published on" in body
    assert 'href="https://www.aims.ie/post/evita-test"' in body
    assert "6 March 2025" in body
    assert "ShowTimes review" not in body
    assert "Originally published in AIMS" not in body


def test_show_page_points_at_the_text_below_not_off_site(client, db):
    show_id = seed_show_with_aims_ie_review(db)
    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Read the review below" in body
    assert "Read the AIMS review" not in body
