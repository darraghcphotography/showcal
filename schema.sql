-- AIMS show history database schema (SQLite)
--
-- Design notes:
--  * societies.id is the stable id from societies.csv (not autoincrement) so it can be
--    referenced directly as shows.society_id.
--  * shows.region/section are a SNAPSHOT of the society's region/section at the time of
--    that production (a society's tier can change season to season - shows keeps history
--    accurate even after a society moves Sullivan <-> Gilbert).
--  * shows.source distinguishes rows that came from the CSV export ('import') from rows
--    created via the member-submission workflow ('submission'). The import script only
--    ever updates 'import' rows, so re-running it after a spreadsheet update can never
--    overwrite or delete member-submitted / moderator-edited data.
--  * shows.moderation_status is the public-visibility gate: only 'approved' rows should
--    ever be shown on public pages. CSV-imported rows are approved on first insert since
--    they're already-published historical record; new member submissions default to
--    'pending' at the application layer.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS societies (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    region          TEXT NOT NULL CHECK (region IN (
                        'Eastern', 'Western', 'Northern',
                        'South-West', 'South-East', 'Midlands'
                    )),
    section         TEXT NOT NULL CHECK (section IN (
                        'Gilbert', 'Sullivan', 'Non-AIMS', 'Inactive'
                    )),
    section_as_of   TEXT,      -- season string e.g. '26/27', nullable
    section_history TEXT,      -- free-text log e.g. '23/24: Sullivan · 24/25: Gilbert · ...'
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS shows (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id             INTEGER NOT NULL REFERENCES societies(id),

    -- snapshot fields, as they were for this specific production
    season                 TEXT NOT NULL,        -- 'YY/YY', e.g. '23/24' (sorts correctly as text)
    region                 TEXT NOT NULL CHECK (region IN (
                                'Eastern', 'Western', 'Northern',
                                'South-West', 'South-East', 'Midlands'
                            )),
    section                TEXT CHECK (section IN ('Gilbert', 'Sullivan', 'Non-AIMS') OR section IS NULL),

    show                   TEXT,                 -- NULL = society slotted for this season, title TBA
    opening_date           TEXT,                 -- ISO yyyy-mm-dd, nullable
    closing_date           TEXT,
    adjudication_date      TEXT,
    adjudication_month_raw TEXT,                 -- free text fallback e.g. 'not adjudicated', a month name

    venue                  TEXT,
    director               TEXT,
    musical_director       TEXT,
    choreographer          TEXT,

    review_status          TEXT NOT NULL DEFAULT 'None' CHECK (review_status IN (
                                'Published', 'Scheduled', 'Not adjudicated', 'None'
                            )),
    review_url             TEXT,
    ticket_url             TEXT,                 -- optional link to buy tickets, member-submitted
    poster_filename         TEXT,                 -- filename under the uploads dir, not a user path

    status                 TEXT CHECK (status IN ('Cancelled') OR status IS NULL),

    -- moderation / provenance (not present in the CSV export)
    moderation_status      TEXT NOT NULL DEFAULT 'approved' CHECK (moderation_status IN (
                                'pending', 'approved', 'rejected'
                            )),
    source                 TEXT NOT NULL DEFAULT 'import' CHECK (source IN ('import', 'submission')),
    submitted_by           TEXT,                 -- member identifier/email/name who submitted it
    invite_code_id         INTEGER REFERENCES invite_codes(id),
    moderated_by           TEXT,
    moderated_at           TEXT,

    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Natural key for upsert-on-reimport. show can be NULL (placeholder "slotted for
-- this season, title TBA" rows) and plain SQLite UNIQUE treats every NULL as
-- distinct, which would make those rows duplicate on every re-run - so the key
-- is built on COALESCE(show, '') instead of show directly.
CREATE UNIQUE INDEX IF NOT EXISTS ux_shows_natural_key
    ON shows(society_id, season, COALESCE(show, ''));

CREATE INDEX IF NOT EXISTS idx_shows_society_id        ON shows(society_id);
CREATE INDEX IF NOT EXISTS idx_shows_season             ON shows(season);
CREATE INDEX IF NOT EXISTS idx_shows_moderation_status   ON shows(moderation_status);
CREATE INDEX IF NOT EXISTS idx_shows_review_status       ON shows(review_status);

-- App-only tables below: nothing here is populated by import_csv.py, and
-- re-running that script never touches these.

-- Moderators/admins who can log in to approve submissions and attach reviews.
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'moderator' CHECK (role IN ('admin', 'moderator')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Shareable codes that gate the public submission form (no login required for
-- members, but no code = no form). Revoke by flipping is_active to 0 rather
-- than deleting, so past submissions keep their provenance link.
CREATE TABLE IF NOT EXISTS invite_codes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    label           TEXT,                 -- e.g. 'General 2026 code', 'Eastern region reps'
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    expires_at      TEXT,                 -- ISO date, nullable = never expires
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT
);
