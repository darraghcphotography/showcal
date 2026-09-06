"""Append-only log of what a society login changed, and what it used to say.

Societies maintain their own history through `/society/` and their edits go
live immediately - no moderation queue. That is the right trade for people
keeping their own record straight, but it left the site unable to answer the
question an archive exists to answer: **what did this used to say?** A
committee also shares one login code, so a change could not be attributed, and
nothing surfaced that a change had happened at all.

This module is the whole mechanism. Routes call `snapshot()` before a write and
`record()` after, and the diff between the two becomes one row per changed
field (see `society_edit_log` in schema.sql).

Three deliberate limits, stated here because a log that quietly misses things is
worse than no log:

- **It records the society's login, not a person.** A committee shares one code.
  `/admin/society-edits` says so rather than implying an identity we do not have.
- **It never blocks the write.** A failure to log must not stop a society fixing
  their own data, so `record()` swallows its own errors. A missing row is a gap
  in the log; a 500 here would be a gap in the archive.
- **It logs what a society login does.** Moderator edits through `/admin` go
  through different routes and are not covered.
"""
import sqlite3

# Housekeeping columns. `updated_at` changes on literally every edit and says
# nothing about what was edited; the id and the owning society cannot change.
IGNORED_FIELDS = frozenset({"id", "created_at", "updated_at", "society_id"})

# Nothing here holds a secret today, but a log is exactly the wrong place to
# find out otherwise: values live in it long after the row they came from is
# gone, and it is read by a different set of eyes. Anything listed here is
# recorded as having changed, without its before/after values.
REDACTED_FIELDS = frozenset({"contact_email", "contact_phone", "contact_name"})

REDACTED = "(not recorded)"

# The column that best names a row, per table. A creation is logged as this one
# field rather than every column it was born with: those values are recoverable
# from the row itself minus the updates that followed, so logging fourteen rows
# for one added show buries the real edits underneath it. A *deletion* still
# records every field, because there the row is gone and the log is all there is.
LABEL_FIELDS = {
    "shows": "show",
    "wardrobe_items": "title",
    "societies": "name",
}


def snapshot(db, table, row_id):
    """The current state of a row, as a plain dict, or None if it is not there.

    Take one before a write and pass it to `record()` afterwards. Returns a dict
    rather than a `sqlite3.Row` because the row object is a live view onto a
    cursor - keeping one across the write that changes it is how you end up
    logging the new value as the old one."""
    try:
        row = db.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)  # noqa: S608 - callers pass literals
        ).fetchone()
    except sqlite3.Error:
        return None
    return dict(row) if row is not None else None


def _as_text(value):
    if value is None:
        return None
    return str(value)


def _changed_fields(before, after):
    """Field names whose value actually differs, ignoring housekeeping columns.

    Compared as text, because a form posts "1" where the column holds 1 and that
    is not a change anybody wants to read about."""
    fields = set(before or {}) | set(after or {})
    changed = []
    for field in sorted(fields - IGNORED_FIELDS):
        old = _as_text((before or {}).get(field))
        new = _as_text((after or {}).get(field))
        if old != new:
            changed.append((field, old, new))
    return changed


def record(db, society_id, code, table, row_id, before, after, action=None):
    """Write one row per changed field. Commits nothing - the caller's own
    commit carries these, so a rolled-back edit cannot leave a log entry behind
    claiming it happened.

    `code` is the `invite_codes` row from the session, or None. `action` is
    inferred from which of before/after is present unless given.
    """
    try:
        if action is None:
            if before is None:
                action = "create"
            elif after is None:
                action = "delete"
            else:
                action = "update"

        changes = _changed_fields(before, after)
        if not changes:
            return 0

        code_id = code["id"] if code is not None else None
        rows = []
        for field, old, new in changes:
            if field in REDACTED_FIELDS:
                old = REDACTED if old is not None else None
                new = REDACTED if new is not None else None
            rows.append((society_id, code_id, table, row_id, action, field, old, new))

        db.executemany(
            """
            INSERT INTO society_edit_log
                (society_id, invite_code_id, table_name, row_id, action, field,
                 old_value, new_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)
    except sqlite3.Error:
        # Never let logging stop a society fixing their own data. A gap in the
        # log is recoverable; refusing the edit is not.
        return 0


def record_create(db, society_id, code, table, row_id):
    """Log a newly-created row as a single entry naming what was created.

    See LABEL_FIELDS for why this is one row rather than one per column."""
    after = snapshot(db, table, row_id)
    if after is None:
        return 0
    label = LABEL_FIELDS.get(table)
    if label is None or label not in after:
        # An unknown table is better logged noisily than not at all.
        return record(db, society_id, code, table, row_id, None, after, action="create")
    return record(db, society_id, code, table, row_id,
                  {label: None}, {label: after[label]}, action="create")
