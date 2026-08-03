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
    notes           TEXT,
    default_venue   TEXT,      -- prefilled as a show's venue when left blank at submission time
    logo_filename   TEXT       -- filename under the uploads dir, not a user path (see shows.poster_filename)
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
-- A code with society_id NULL is a generic member-submission gate (unlocks
-- the one-off /submit form, lands as 'pending'). A code with society_id SET
-- is a society login code instead: unlocking it opens that society's own
-- dashboard, where edits/additions to their own history go live immediately
-- (no moderation queue) - see app/blueprints/society.py.
CREATE TABLE IF NOT EXISTS invite_codes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    label           TEXT,                 -- e.g. 'General 2026 code', 'Eastern region reps'
    society_id      INTEGER REFERENCES societies(id),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    expires_at      TEXT,                 -- ISO date, nullable = never expires
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT
);

-- Simple self-hosted pageview count, no cookies/sessions/third parties - just
-- "has anyone actually looked at this page". path is the raw request path
-- (query strings not included, so filtered variants of / all count as one).
CREATE TABLE IF NOT EXISTS page_views (
    path            TEXT PRIMARY KEY,
    views           INTEGER NOT NULL DEFAULT 0,
    last_viewed     TEXT
);

-- Freeform "here's an idea" box - no invite code needed (lower risk than a
-- show submission: it never appears publicly, just a list only moderators
-- see), just a honeypot against basic bots.
CREATE TABLE IF NOT EXISTS feature_suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message         TEXT NOT NULL,
    submitted_name  TEXT,
    status          TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'reviewed')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per award nomination/result from AIMS's historical awards archive
-- (1977 onward), imported by import_awards.py. Only years strictly BEFORE
-- shows.csv's own coverage (season 23/24 = award Year 2024) are imported, so
-- this never double-counts a production already in the shows table.
-- society_name is a plain string, not just a FK, because many historical
-- societies are defunct/renamed and don't match a current societies row -
-- society_id is filled in only when an exact name match was found.
CREATE TABLE IF NOT EXISTS historical_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    year                INTEGER NOT NULL,
    tier                TEXT,                 -- 'Gilbert' / 'Sullivan', when known
    category_name       TEXT,                 -- e.g. 'Best Overall Show', 'Best Director'
    result              TEXT,                 -- 'Winner' / 'Nominee' / 'Third Place' etc.
    show                TEXT,
    society_name        TEXT,
    society_id          INTEGER REFERENCES societies(id),
    nominee_name        TEXT,                 -- person, for individual-award categories
    role                TEXT,
    reason              TEXT,                 -- adjudicator's free-text note, mostly on discretionary awards
    source              TEXT NOT NULL DEFAULT 'import' CHECK (source IN ('import', 'manual'))
                                              -- 'import' rows are wiped/reloaded by import_awards.py on every
                                              -- run; 'manual' rows (added via /admin/awards) never are
);

CREATE INDEX IF NOT EXISTS idx_historical_results_show ON historical_results(show);
CREATE INDEX IF NOT EXISTS idx_historical_results_society_id ON historical_results(society_id);

-- Remembers "these two titles are NOT the same show" decisions from the
-- duplicate-title finder (/admin/duplicate-titles), so a legitimately
-- similar pair (e.g. 'Frozen' / 'Frozen Jr.') doesn't keep getting flagged
-- every time the page loads. Always stored with title_a < title_b so a pair
-- only needs checking one way round.
CREATE TABLE IF NOT EXISTS dismissed_duplicate_pairs (
    title_a         TEXT NOT NULL,
    title_b         TEXT NOT NULL,
    PRIMARY KEY (title_a, title_b)
);

-- Moderator-confirmed link (Wikipedia or elsewhere) for a show title, shown
-- on the /titles browse page. Titles without a row here fall back to an
-- auto-generated Wikipedia search link at render time - nothing is ever
-- auto-resolved to a specific article and stored as if confirmed.
CREATE TABLE IF NOT EXISTS show_links (
    show            TEXT PRIMARY KEY,
    url             TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Moderator-curated editorial content for a show title - synopsis and amateur
-- rights/licensing info, meant to help a society browsing Shows A-Z decide on
-- their next production. Nothing here is auto-fetched (no reliable public API
-- for amateur theatre licensing exists); a moderator looks the title up on
-- the actual rights holder's site (MTI, Concord Theatricals, etc.) and enters
-- it once, same trust model as show_links above.
CREATE TABLE IF NOT EXISTS show_info (
    show            TEXT PRIMARY KEY,
    synopsis        TEXT,
    rights_url      TEXT,
    rights_status   TEXT CHECK (rights_status IN (
                        'Available', 'Contact publisher', 'Restricted'
                    ) OR rights_status IS NULL),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A best-guess region for a historical society that never resolved to a row
-- in societies (defunct/renamed/never re-registered) - historical_results
-- itself has no region column, since a show's region snapshot only exists on
-- the shows table. suggested_region is a one-time guess (from the name
-- itself or a web search); confirmed_region is set once a moderator has
-- actually reviewed it via /admin/historical-societies - only confirmed_region
-- feeds into region-filtered stats, never the raw suggestion.
CREATE TABLE IF NOT EXISTS historical_society_regions (
    society_name        TEXT PRIMARY KEY,
    suggested_region     TEXT CHECK (suggested_region IN (
                            'Eastern', 'Western', 'Northern',
                            'South-West', 'South-East', 'Midlands'
                        ) OR suggested_region IS NULL),
    confirmed_region     TEXT CHECK (confirmed_region IN (
                            'Eastern', 'Western', 'Northern',
                            'South-West', 'South-East', 'Midlands'
                        ) OR confirmed_region IS NULL),
    note                 TEXT,   -- why this region was guessed, e.g. "name references Waterford"
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Full-text search indexes (SQLite FTS5, built in - no extra dependency).
-- External-content tables: the FTS index stores only the tokenized text, the
-- real data stays in societies/historical_results, kept in sync via the
-- triggers below so every INSERT/UPDATE/DELETE - whether from the app or a
-- script like import_awards.py - keeps the index correct automatically.
-- app/db.py backfills these once after creation (a fresh virtual table
-- starts empty; the triggers only cover changes from that point on).
CREATE VIRTUAL TABLE IF NOT EXISTS societies_fts USING fts5(
    name, content='societies', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS societies_fts_ai AFTER INSERT ON societies BEGIN
    INSERT INTO societies_fts(rowid, name) VALUES (new.id, new.name);
END;
CREATE TRIGGER IF NOT EXISTS societies_fts_ad AFTER DELETE ON societies BEGIN
    INSERT INTO societies_fts(societies_fts, rowid, name) VALUES ('delete', old.id, old.name);
END;
CREATE TRIGGER IF NOT EXISTS societies_fts_au AFTER UPDATE ON societies BEGIN
    INSERT INTO societies_fts(societies_fts, rowid, name) VALUES ('delete', old.id, old.name);
    INSERT INTO societies_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS historical_results_fts USING fts5(
    society_name, show, nominee_name, reason, content='historical_results', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS historical_results_fts_ai AFTER INSERT ON historical_results BEGIN
    INSERT INTO historical_results_fts(rowid, society_name, show, nominee_name, reason)
    VALUES (new.id, new.society_name, new.show, new.nominee_name, new.reason);
END;
CREATE TRIGGER IF NOT EXISTS historical_results_fts_ad AFTER DELETE ON historical_results BEGIN
    INSERT INTO historical_results_fts(historical_results_fts, rowid, society_name, show, nominee_name, reason)
    VALUES ('delete', old.id, old.society_name, old.show, old.nominee_name, old.reason);
END;
CREATE TRIGGER IF NOT EXISTS historical_results_fts_au AFTER UPDATE ON historical_results BEGIN
    INSERT INTO historical_results_fts(historical_results_fts, rowid, society_name, show, nominee_name, reason)
    VALUES ('delete', old.id, old.society_name, old.show, old.nominee_name, old.reason);
    INSERT INTO historical_results_fts(rowid, society_name, show, nominee_name, reason)
    VALUES (new.id, new.society_name, new.show, new.nominee_name, new.reason);
END;
