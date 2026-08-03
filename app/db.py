import sqlite3

import click
from flask import current_app, g


def get_db():
    """Return a request-scoped SQLite connection, opening one if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
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
]


def _apply_column_migrations(db):
    for table, column, ddl in COLUMN_MIGRATIONS:
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            db.execute(ddl)


# FTS5 external-content tables need an explicit 'rebuild' to actually build
# the searchable index from their source table - the triggers in schema.sql
# only cover changes from this point on. Deliberately NOT guarded by a
# `COUNT(*) FROM fts_table == 0` check: for an external-content table, COUNT(*)
# reads through to the content table's own row count regardless of whether
# the index has ever been built, so that check never actually caught an
# unbuilt index in testing (it always read the real societies/historical_
# results row count). Rebuilding unconditionally is simple, always correct,
# and cheap at this data's scale (low thousands of rows, once per app start).
FTS_TABLES = ["societies_fts", "historical_results_fts"]


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
    _apply_column_migrations(db)
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
