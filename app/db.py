import sqlite3

import click
from flask import current_app, g


def get_db():
    """Return a request-scoped SQLite connection, opening one if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        # WAL lets readers (most requests) proceed without blocking on a
        # writer, instead of every connection fighting over one exclusive
        # lock - standard hardening for SQLite under concurrent requests
        # (pageviews, submissions, backups and changelog sync all writing
        # under Waitress's worker threads). busy_timeout makes a write that
        # does collide retry for up to 5s instead of failing immediately
        # with "database is locked".
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA busy_timeout = 5000")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Columns added to a table after its initial release. `CREATE TABLE IF NOT
# EXISTS` in schema.sql only creates a table the first time - it can never
# add a column to a table that already exists, so any new column needs an
# entry here too, or every database created before that column was added
# will 500 on first use. List as (table, column, DDL for the ADD COLUMN).
COLUMN_MIGRATIONS = [
    ("shows", "invite_code_id", "ALTER TABLE shows ADD COLUMN invite_code_id INTEGER REFERENCES invite_codes(id)"),
    ("shows", "ticket_url", "ALTER TABLE shows ADD COLUMN ticket_url TEXT"),
    ("shows", "poster_filename", "ALTER TABLE shows ADD COLUMN poster_filename TEXT"),
    ("societies", "default_venue", "ALTER TABLE societies ADD COLUMN default_venue TEXT"),
    ("societies", "logo_filename", "ALTER TABLE societies ADD COLUMN logo_filename TEXT"),
    ("invite_codes", "society_id", "ALTER TABLE invite_codes ADD COLUMN society_id INTEGER REFERENCES societies(id)"),
    ("historical_results", "reason", "ALTER TABLE historical_results ADD COLUMN reason TEXT"),
    (
        "historical_results", "source",
        "ALTER TABLE historical_results ADD COLUMN source TEXT NOT NULL DEFAULT 'import' "
        "CHECK (source IN ('import', 'manual'))",
    ),
    ("societies", "about", "ALTER TABLE societies ADD COLUMN about TEXT"),
    ("societies", "website_url", "ALTER TABLE societies ADD COLUMN website_url TEXT"),
    ("societies", "facebook_url", "ALTER TABLE societies ADD COLUMN facebook_url TEXT"),
    ("societies", "instagram_url", "ALTER TABLE societies ADD COLUMN instagram_url TEXT"),
    ("societies", "tiktok_url", "ALTER TABLE societies ADD COLUMN tiktok_url TEXT"),
    ("societies", "other_url", "ALTER TABLE societies ADD COLUMN other_url TEXT"),
    ("societies", "other_label", "ALTER TABLE societies ADD COLUMN other_label TEXT"),
    (
        "feature_suggestions", "category",
        "ALTER TABLE feature_suggestions ADD COLUMN category TEXT NOT NULL DEFAULT 'Idea/Feature' "
        "CHECK (category IN ('Idea/Feature', 'Bug report', 'Data error'))",
    ),
    (
        "feature_suggestions", "triage_status",
        "ALTER TABLE feature_suggestions ADD COLUMN triage_status TEXT NOT NULL DEFAULT 'New' "
        "CHECK (triage_status IN ('New', 'Planned', 'In Progress', 'Done', 'Not planned'))",
    ),
    ("feature_suggestions", "contact", "ALTER TABLE feature_suggestions ADD COLUMN contact TEXT"),
    ("feature_suggestions", "triaged_at", "ALTER TABLE feature_suggestions ADD COLUMN triaged_at TEXT"),
    ("societies", "hidden", "ALTER TABLE societies ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0"),
    ("show_info", "premiere_year", "ALTER TABLE show_info ADD COLUMN premiere_year INTEGER"),
    ("show_info", "premiere_place", "ALTER TABLE show_info ADD COLUMN premiere_place TEXT"),
    ("feature_suggestions", "admin_note", "ALTER TABLE feature_suggestions ADD COLUMN admin_note TEXT"),
    (
        "historical_reviews", "source",
        "ALTER TABLE historical_reviews ADD COLUMN source TEXT NOT NULL DEFAULT 'showtimes' "
        "CHECK (source IN ('showtimes', 'manual'))",
    ),
    ("adjudicators", "photo_filename", "ALTER TABLE adjudicators ADD COLUMN photo_filename TEXT"),
    # Links into the productions table (see schema.sql). Populated only by
    # build_productions.py - adding the column here is safe on an existing
    # database because every one of them is nullable and nothing reads them
    # until that script has run.
    ("shows", "production_id", "ALTER TABLE shows ADD COLUMN production_id INTEGER REFERENCES productions(id)"),
    (
        "historical_results", "production_id",
        "ALTER TABLE historical_results ADD COLUMN production_id INTEGER REFERENCES productions(id)",
    ),
    (
        "historical_reviews", "production_id",
        "ALTER TABLE historical_reviews ADD COLUMN production_id INTEGER REFERENCES productions(id)",
    ),
    # Links a production's free-text venue to the real building it names (see
    # the venues table in schema.sql). Populated by app/venues_build.py.
    ("shows", "venue_id", "ALTER TABLE shows ADD COLUMN venue_id INTEGER REFERENCES venues(id)"),
    ("shows", "review_author", "ALTER TABLE shows ADD COLUMN review_author TEXT"),
    # "This name has no region, and asking again won't change that" - AIMS
    # itself is a national body rather than a society, and a few defunct
    # touring names give no location clue anywhere. Deliberately NOT a sentinel
    # value in confirmed_region: that column feeds the /stats region breakdown
    # and productions.region, so an "Unknown" in it would surface publicly as a
    # region. This just takes the row out of the moderator queue.
    (
        "historical_society_regions", "no_region",
        "ALTER TABLE historical_society_regions ADD COLUMN no_region INTEGER NOT NULL DEFAULT 0",
    ),
]


def _apply_column_migrations(db):
    for table, column, ddl in COLUMN_MIGRATIONS:
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            db.execute(ddl)


# Indexes on columns that COLUMN_MIGRATIONS adds. These deliberately can't
# live in schema.sql: on a database created before the column existed,
# schema.sql runs first, so a CREATE INDEX there would hit "no such column"
# before the ALTER TABLE ever ran. Applied straight after the column
# migrations instead, when the column is guaranteed to exist either way.
MIGRATED_COLUMN_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_shows_production_id ON shows(production_id)",
    "CREATE INDEX IF NOT EXISTS idx_historical_results_production_id ON historical_results(production_id)",
    "CREATE INDEX IF NOT EXISTS idx_historical_reviews_production_id ON historical_reviews(production_id)",
    "CREATE INDEX IF NOT EXISTS idx_shows_venue_id ON shows(venue_id)",
]


def _create_migrated_column_indexes(db):
    for ddl in MIGRATED_COLUMN_INDEXES:
        db.execute(ddl)


def _migrate_adjudicator_assignments_table(db):
    """adjudicator_assignments originally allowed only one adjudicator per
    season+tier (PRIMARY KEY (season, section)) - a real mid-season change
    (see ROADMAP) needs a second row for the same season+tier, which that
    constraint physically can't hold. SQLite can't ALTER a PRIMARY KEY in
    place, so this rebuilds the table the standard SQLite way (new table,
    copy, drop, rename) - a plain ADD COLUMN (COLUMN_MIGRATIONS) isn't
    enough here since the key itself has to change, not just add a field.
    Keyed off whether `notes` already exists (added in the same rebuild), so
    this is a no-op on every startup once a database has been migrated -
    including a brand-new database, where schema.sql already creates the
    table in its final shape."""
    existing = {row[1] for row in db.execute("PRAGMA table_info(adjudicator_assignments)")}
    if "notes" in existing:
        return
    db.execute(
        """
        CREATE TABLE adjudicator_assignments_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            season          TEXT NOT NULL,
            section         TEXT NOT NULL CHECK (section IN ('Gilbert', 'Sullivan')),
            adjudicator_id  INTEGER NOT NULL REFERENCES adjudicators(id),
            notes           TEXT,
            UNIQUE (season, section, adjudicator_id)
        )
        """
    )
    db.execute(
        "INSERT INTO adjudicator_assignments_new (season, section, adjudicator_id) "
        "SELECT season, section, adjudicator_id FROM adjudicator_assignments"
    )
    db.execute("DROP TABLE adjudicator_assignments")
    db.execute("ALTER TABLE adjudicator_assignments_new RENAME TO adjudicator_assignments")


def _migrate_shows_source_check(db):
    """shows.source originally only allowed 'import'/'submission' - Step 4's
    skeleton shows (see schema.sql) need a third value, 'historical', and
    SQLite can't ALTER a CHECK constraint in place, so this rebuilds the
    table the standard SQLite way (new table, copy, drop, rename) - same
    pattern as _migrate_adjudicator_assignments_table above. Unlike that
    table, shows.id is a stable public identifier (linked from bookmarks,
    /shows/<id> URLs, the calendar feed) - every row is copied with its
    original id preserved explicitly, and AUTOINCREMENT's own sequence
    tracking picks up the max id automatically from that, so the next
    genuinely-new show still gets a fresh, never-reused id. Keyed off
    whether the live table's own CHECK constraint text already mentions
    'historical' (read straight from sqlite_master, not schema.sql - that
    file's text changes the moment this migration is written, long before
    any given database has actually been migrated), so this is a no-op on
    every startup once a database has been migrated - including a brand-new
    one, where schema.sql already creates the table in its final shape."""
    current_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'shows'"
    ).fetchone()[0]
    if "historical" in current_sql:
        return

    db.execute(
        """
        CREATE TABLE shows_new (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            society_id             INTEGER NOT NULL REFERENCES societies(id),
            season                 TEXT NOT NULL,
            region                 TEXT NOT NULL CHECK (region IN (
                                        'Eastern', 'Western', 'Northern',
                                        'South-West', 'South-East', 'Midlands'
                                    )),
            section                TEXT CHECK (section IN ('Gilbert', 'Sullivan', 'Non-AIMS') OR section IS NULL),
            show                   TEXT,
            opening_date           TEXT,
            closing_date           TEXT,
            adjudication_date      TEXT,
            adjudication_month_raw TEXT,
            venue                  TEXT,
            director               TEXT,
            musical_director       TEXT,
            choreographer          TEXT,
            review_status          TEXT NOT NULL DEFAULT 'None' CHECK (review_status IN (
                                        'Published', 'Scheduled', 'Not adjudicated', 'None'
                                    )),
            review_url             TEXT,
            ticket_url             TEXT,
            poster_filename        TEXT,
            moderation_status      TEXT NOT NULL DEFAULT 'approved' CHECK (moderation_status IN (
                                        'pending', 'approved', 'rejected'
                                    )),
            source                 TEXT NOT NULL DEFAULT 'import' CHECK (source IN ('import', 'submission', 'historical')),
            submitted_by           TEXT,
            invite_code_id         INTEGER REFERENCES invite_codes(id),
            moderated_by           TEXT,
            moderated_at           TEXT,
            created_at             TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        INSERT INTO shows_new (
            id, society_id, season, region, section, show, opening_date, closing_date,
            adjudication_date, adjudication_month_raw, venue, director, musical_director, choreographer,
            review_status, review_url, ticket_url, poster_filename, moderation_status, source,
            submitted_by, invite_code_id, moderated_by, moderated_at, created_at, updated_at
        )
        SELECT
            id, society_id, season, region, section, show, opening_date, closing_date,
            adjudication_date, adjudication_month_raw, venue, director, musical_director, choreographer,
            review_status, review_url, ticket_url, poster_filename, moderation_status, source,
            submitted_by, invite_code_id, moderated_by, moderated_at, created_at, updated_at
        FROM shows
        """
    )
    db.execute("DROP TABLE shows")
    db.execute("ALTER TABLE shows_new RENAME TO shows")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_shows_natural_key ON shows(society_id, season, COALESCE(show, ''))")
    db.execute("CREATE INDEX IF NOT EXISTS idx_shows_society_id ON shows(society_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_shows_season ON shows(season)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_shows_moderation_status ON shows(moderation_status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_shows_review_status ON shows(review_status)")


def _migrate_shows_natural_key_collation(db):
    """ux_shows_natural_key originally had no COLLATE NOCASE on the title
    part, so a case-only difference ("Made in Dagenham" vs "Made In
    Dagenham") wasn't caught as the same production - a review-created
    skeleton show could silently duplicate an existing member-submitted one
    whenever the extracted title's casing didn't match exactly (see
    ROADMAP, 20 Aug 2026 - 4 real instances found and merged in production
    before this was written). `CREATE INDEX IF NOT EXISTS` in schema.sql
    can't change an index that already exists under that name, so this
    drops and recreates it - keyed off whether the live index's own SQL
    already mentions NOCASE (read from sqlite_master, same reasoning as
    _migrate_shows_source_check above), so it's a no-op once a database has
    been migrated, including a brand-new one where schema.sql already
    creates it in the final shape."""
    current_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'ux_shows_natural_key'"
    ).fetchone()
    if current_sql is None or "NOCASE" in current_sql[0]:
        return
    db.execute("DROP INDEX ux_shows_natural_key")
    db.execute(
        "CREATE UNIQUE INDEX ux_shows_natural_key "
        "ON shows(society_id, season, COALESCE(show, '') COLLATE NOCASE)"
    )


def _migrate_drop_shows_status(db):
    """shows.status only ever held 'Cancelled' or NULL, and turned out to be
    unreliable - repeatedly misattributed to shows that actually went ahead
    (see ROADMAP, 24 Aug 2026) - with a real root cause: import_csv.py read a
    'status' column straight off the source spreadsheet and upserted it
    unconditionally on every import, unlike review_status's own blank-can't-
    overwrite-a-real-value protection, so a routine re-import could silently
    resurrect a wrong Cancelled flag. Removed entirely rather than just
    cleared, so it can't recur. A plain DROP COLUMN, not the new-table/copy/
    drop/rename dance _migrate_shows_source_check and
    _migrate_adjudicator_assignments_table above use - those exist because
    SQLite can't ALTER a CHECK constraint or a PRIMARY KEY in place, but a
    straight column removal has been supported natively since SQLite 3.35
    (this app's SQLite is well past that floor), and status isn't part of
    any index, trigger, or foreign key. Keyed off whether the column still
    exists, so this is a no-op on every startup once a database has been
    migrated, including a brand-new one where schema.sql no longer creates
    the column at all."""
    existing = {row[1] for row in db.execute("PRAGMA table_info(shows)")}
    if "status" not in existing:
        return
    db.execute("ALTER TABLE shows DROP COLUMN status")


# FTS5 external-content tables need an explicit 'rebuild' to actually build
# the searchable index from their source table - the triggers in schema.sql
# only cover changes from this point on. Deliberately NOT guarded by a
# `COUNT(*) FROM fts_table == 0` check: for an external-content table, COUNT(*)
# reads through to the content table's own row count regardless of whether
# the index has ever been built, so that check never actually caught an
# unbuilt index in testing (it always read the real societies/historical_
# results row count). Rebuilding unconditionally is simple, always correct,
# and cheap at this data's scale (low thousands of rows, once per app start).
FTS_TABLES = ["societies_fts", "historical_results_fts", "historical_reviews_fts"]


def _backfill_fts_indexes(db):
    for fts_table in FTS_TABLES:
        db.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES ('rebuild')")


def init_schema():
    """(Re-)apply schema.sql plus any pending column migrations. Safe to run
    against an existing database - it never drops or overwrites data."""
    db = get_db()
    schema_path = current_app.config["SCHEMA_PATH"]
    with open(schema_path, encoding="utf-8") as f:
        db.executescript(f.read())
    _migrate_adjudicator_assignments_table(db)
    _migrate_shows_source_check(db)
    _migrate_shows_natural_key_collation(db)
    _migrate_drop_shows_status(db)
    _apply_column_migrations(db)
    _create_migrated_column_indexes(db)
    db.commit()

    # Deliberately a separate transaction from the schema/column changes above -
    # rebuilding an FTS5 index while the virtual table's own creation is still
    # part of an uncommitted transaction produced a silently-broken index in
    # testing (row count looked right, but every MATCH query returned nothing).
    _backfill_fts_indexes(db)
    db.commit()


@click.command("init-db")
def init_db_command():
    """Flask CLI command: `flask --app app init-db`."""
    init_schema()
    click.echo("Schema applied.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
