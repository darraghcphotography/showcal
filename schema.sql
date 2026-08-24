-- AIMS show history database schema (SQLite)
--
-- Design notes:
--  * societies.id is the stable id from societies.csv (not autoincrement) so it can be
--    referenced directly as shows.society_id.
--  * shows.region/section are a SNAPSHOT of the society's region/section at the time of
--    that production (a society's tier can change season to season - shows keeps history
--    accurate even after a society moves Sullivan <-> Gilbert).
--  * shows.source distinguishes rows that came from the CSV export ('import') from rows
--    created via the member-submission workflow ('submission'), and from a minimal
--    "skeleton" row (source='historical') created only to give an approved historical_review
--    a real page to live on when no real show record exists yet. The import script only
--    ever updates 'import' rows, so re-running it after a spreadsheet update can never
--    overwrite or delete member-submitted / moderator-edited / historical-skeleton data.
--    A 'historical' row is deliberately excluded from every stats/leaderboard query -
--    historical_results stays the one source of truth for counting pre-24/25 productions,
--    so a skeleton show can never double-count against it.
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
    logo_filename   TEXT,      -- filename under the uploads dir, not a user path (see shows.poster_filename)

    -- Society-editable "get involved" profile, settable by the society's own
    -- login or by a moderator - shown on the society's public page.
    about           TEXT,
    website_url     TEXT,
    facebook_url    TEXT,
    instagram_url   TEXT,
    tiktok_url      TEXT,
    other_url       TEXT,      -- whatever doesn't fit the named platforms - WhatsApp group, Linktree, etc.
    other_label     TEXT,      -- short label for other_url, e.g. "WhatsApp group"

    -- Moderator-only: the society has asked not to be publicly associated
    -- with AIMS. Distinct from section='Inactive' (which just means "not
    -- currently competing" and is silent on public visibility) - hidden
    -- 404s the society's own public page and drops them from /societies,
    -- but does NOT touch historical stats/awards/Season Archive, which
    -- stay as an accurate historical record. A society's own self-service
    -- login (app/blueprints/society.py) is unaffected either way.
    hidden          INTEGER NOT NULL DEFAULT 0
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
    review_author          TEXT,                 -- byline for review_url; moderator-entered, never inferred
    ticket_url             TEXT,                 -- optional link to buy tickets, member-submitted
    poster_filename         TEXT,                 -- filename under the uploads dir, not a user path

    -- moderation / provenance (not present in the CSV export)
    moderation_status      TEXT NOT NULL DEFAULT 'approved' CHECK (moderation_status IN (
                                'pending', 'approved', 'rejected'
                            )),
    source                 TEXT NOT NULL DEFAULT 'import' CHECK (source IN ('import', 'submission', 'historical')),
    submitted_by           TEXT,                 -- member identifier/email/name who submitted it
    invite_code_id         INTEGER REFERENCES invite_codes(id),
    moderated_by           TEXT,
    moderated_at           TEXT,

    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now')),

    -- The production this staging belongs to (see the productions table
    -- further down). Filled in by build_productions.py, not by any form or
    -- import - a NULL here means the row hasn't been through a rebuild yet,
    -- or has no usable title (a "society slotted, title TBA" placeholder).
    production_id          INTEGER REFERENCES productions(id),

    -- The real building `venue` names (see the venues table). Resolved from
    -- the free-text `venue` above via venue_aliases; NULL when no venue was
    -- recorded for this production at all.
    venue_id               INTEGER REFERENCES venues(id)
);

-- Natural key for upsert-on-reimport. show can be NULL (placeholder "slotted for
-- this season, title TBA" rows) and plain SQLite UNIQUE treats every NULL as
-- distinct, which would make those rows duplicate on every re-run - so the key
-- is built on COALESCE(show, '') instead of show directly.
--
-- COLLATE NOCASE (added 20 Aug 2026): a case-only title difference used to be
-- a distinct key, so a review-created skeleton show could silently duplicate
-- an existing member-submitted one whenever the extracted title's casing
-- didn't match exactly ("Made in Dagenham" vs "Made In Dagenham") - 4 real
-- instances found and merged in production before this was added. Confirmed
-- import_csv.py's ON CONFLICT(society_id, season, COALESCE(show, '')) still
-- resolves correctly against this index without needing its own COLLATE
-- NOCASE annotation - SQLite matches the conflict target structurally and
-- applies the index's collation regardless.
CREATE UNIQUE INDEX IF NOT EXISTS ux_shows_natural_key
    ON shows(society_id, season, COALESCE(show, '') COLLATE NOCASE);

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
-- show submission: nothing here appears publicly until a moderator has
-- triaged it - see triage_status below), just a honeypot against basic bots.
-- `status` is legacy (a simple new/reviewed toggle) - superseded by
-- triage_status below, left in place unused rather than migrated, since
-- SQLite can't cheaply alter a CHECK constraint on a table with live data.
CREATE TABLE IF NOT EXISTS feature_suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message         TEXT NOT NULL,
    submitted_name  TEXT,
    status          TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'reviewed')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),

    -- Chosen by the submitter at submission time (constants.SUGGESTION_CATEGORIES).
    category        TEXT NOT NULL DEFAULT 'Idea/Feature'
                        CHECK (category IN ('Idea/Feature', 'Bug report', 'Data error')),
    -- Moderator-set triage state (constants.SUGGESTION_STATUSES) - anything
    -- other than 'New' is visible on the public /suggestions Roadmap page,
    -- so a duplicate idea can be spotted before it's resubmitted.
    triage_status   TEXT NOT NULL DEFAULT 'New'
                        CHECK (triage_status IN ('New', 'Planned', 'In Progress', 'Done', 'Not planned')),
    -- Optional, so a moderator can follow up personally once something
    -- ships - never shown publicly, never used for automated email.
    contact         TEXT,
    -- Set whenever a moderator saves a category/status change - lets a
    -- 'Done' suggestion sort into the Roadmap page's "Recently shipped"
    -- list by when it actually shipped, not by its original submission date.
    triaged_at      TEXT,
    -- Moderator's own free-text note on how a suggestion was interpreted/
    -- addressed - shown publicly on the Roadmap page, but only next to a
    -- 'Done' card (see suggestions_board.html), so the original submitter
    -- can see how it was actually handled without this cluttering every
    -- other lane.
    admin_note      TEXT
);

-- One admin-authored line per shipped update, shown on the public
-- /suggestions Roadmap page under "Recently shipped". Deliberately just a
-- single freeform text field - no title/category - for a quick one-liner,
-- not a full blog post. No edit-in-place; delete and re-add instead.
CREATE TABLE IF NOT EXISTS changelog_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entry           TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The public /faq page's content, moderator-authored. 'draft' rows are only
-- ever visible in /admin/faq - a moderator can write and revise a question
-- before it's ready, same idea as a draft blog post, rather than every edit
-- going live immediately. sort_order is a plain integer a moderator moves up
-- and down by hand (see admin/faq.py) - there's no natural ordering (not
-- alphabetical, not by date) for a page meant to read top-to-bottom.
CREATE TABLE IF NOT EXISTS faq_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_faq_entries_status ON faq_entries(status);

-- Remembers every entry from the git-tracked CHANGELOG.md that's ever been
-- auto-published into changelog_entries above, so app/changelog_sync.py can
-- tell "never synced yet" (publish it) apart from "synced once, then
-- deliberately deleted via /admin/changelog" (leave it deleted) - otherwise
-- every app restart would resurrect a manually-removed entry, since the
-- entry text is still sitting right there in the file.
CREATE TABLE IF NOT EXISTS changelog_synced_entries (
    entry           TEXT PRIMARY KEY,
    synced_at       TEXT NOT NULL DEFAULT (datetime('now'))
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
    source              TEXT NOT NULL DEFAULT 'import' CHECK (source IN ('import', 'manual')),
                                              -- 'import' rows are wiped/reloaded by import_awards.py on every
                                              -- run; 'manual' rows (added via /admin/awards) never are

    -- The production this award record is about - many rows per production
    -- (one show with 5 category results is 5 rows). Filled in by
    -- build_productions.py; NULL for a row with no usable show title, which
    -- names no production at all.
    production_id       INTEGER REFERENCES productions(id)
);

CREATE INDEX IF NOT EXISTS idx_historical_results_show ON historical_results(show);
CREATE INDEX IF NOT EXISTS idx_historical_results_society_id ON historical_results(society_id);
-- NOTE: the index on production_id is created in app/db.py, not here - on a
-- database that predates the column, schema.sql runs before COLUMN_MIGRATIONS
-- adds it, so a CREATE INDEX here would fail with "no such column". Same for
-- shows.production_id and historical_reviews.production_id.

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

-- One-time review queue for society_gate_suggestions.json (the
-- extractor-society-gate branch's proposed historical_reviews.society_raw
-- corrections - see ROADMAP.md's "Near-identical-society audit"). Rejecting
-- a suggestion here is remembered the same way dismissed_duplicate_pairs
-- remembers "not a duplicate", so it stops reappearing on reload.
CREATE TABLE IF NOT EXISTS dismissed_society_corrections (
    source_issue    TEXT NOT NULL,
    show_raw        TEXT NOT NULL,
    adjudicator     TEXT NOT NULL,
    PRIMARY KEY (source_issue, show_raw, adjudicator)
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
    -- Original worldwide premiere, not an AIMS one - e.g. premiere_year 1964,
    -- premiere_place "Broadway (Imperial Theatre, New York)". Moderator-
    -- entered from a source like Wikipedia, same trust model as the rest of
    -- this table - never guessed.
    premiere_year   INTEGER,
    premiere_place  TEXT,
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
    -- Settled as having no region at all, rather than a region nobody has
    -- confirmed yet. AIMS itself is the clear case (a national body, not a
    -- society); the rest are defunct names with no location clue anywhere, so
    -- leaving them in the queue asks a question that has no answer.
    -- Deliberately separate from confirmed_region rather than a sentinel value
    -- in it: that column feeds the /stats region breakdown and
    -- productions.region, so "Unknown" in there would show up publicly as if
    -- it were a region.
    no_region            INTEGER NOT NULL DEFAULT 0,
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per person who has adjudicated for AIMS. Built up as
-- adjudicator_assignments below is filled in, so a name typed once (e.g.
-- "Jane Smith") stays consistent across every season they judged rather than
-- drifting spelling season to season - see also historical_results.reason,
-- the free-text adjudicator's note that predates this table.
CREATE TABLE IF NOT EXISTS adjudicators (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    notes           TEXT,       -- short bio, shown on their public page
    photo_filename  TEXT,       -- filename under the uploads dir, not a user path (see shows.poster_filename)
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Which adjudicator(s) covered each tier in a given season - normally
-- exactly one per tier per season, not per show, but AIMS has occasionally
-- swapped an adjudicator mid-season (see notes) - a season/tier can have
-- more than one row for that reason. An unfilled season/tier combination
-- simply has no row here. Lets a moderator match a show's published review
-- to its likely author (same adjudicator judges every show in their tier
-- that season, except across a recorded mid-season change) and find every
-- review a given adjudicator wrote, without a per-show author field.
-- notes is a plain free-text log for a mid-season change ("Aug-Dec 2013",
-- "took over from Richie Ryan") - same "simple text log, not a structured
-- history table" pattern as societies.section_history, deliberately not a
-- real date-range/versioning model.
CREATE TABLE IF NOT EXISTS adjudicator_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    season          TEXT NOT NULL,
    section         TEXT NOT NULL CHECK (section IN ('Gilbert', 'Sullivan')),
    adjudicator_id  INTEGER NOT NULL REFERENCES adjudicators(id),
    notes           TEXT,
    UNIQUE (season, section, adjudicator_id)
);

-- One row per review extracted from the AIMS ShowTimes PDF archive (Step 4 -
-- see ROADMAP.md's "Step 4 scoping" sections). Nothing here is public until a
-- moderator approves it via /admin/historical-reviews - same moderation_status
-- gate as shows.moderation_status, deliberately a separate status rather than
-- reusing that column since a review can be approved independently of - and
-- before - the show/society match underneath it is fully confirmed.
-- show_raw/society_raw keep exactly what the parser read off the page; show_id/
-- society_id are only filled in once a moderator has matched (or the approve
-- step has created) the real row - never auto-resolved and treated as
-- confirmed. tier can be NULL ('unknown') when the source issue's header
-- didn't state adjudicator names, same real gap the archive report surfaces.
CREATE TABLE IF NOT EXISTS historical_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    season          TEXT NOT NULL,        -- 'YY/YY', same convention as shows.season
    tier            TEXT CHECK (tier IN ('Gilbert', 'Sullivan') OR tier IS NULL),
    show_raw        TEXT NOT NULL,
    society_raw     TEXT NOT NULL,
    adjudicator_id  INTEGER REFERENCES adjudicators(id),
    review_text     TEXT NOT NULL,
    source_issue    TEXT,                 -- e.g. 'ShowTimes Issue 163, April 2023' - the public citation
    source_file     TEXT,                 -- e.g. 'Show Times April '23 Web.pdf' - moderator-facing only

    show_id         INTEGER REFERENCES shows(id),
    society_id      INTEGER REFERENCES societies(id),

    -- Moderator-facing hint from the extraction pass, not shown publicly:
    -- 'needs_check' = a show/society match exists but looked uncertain (e.g.
    -- text that may be calendar/listing content, not a real review);
    -- 'no_show_match' = no shows/historical_results row at all was found for
    -- this show+society+season - approving this one creates a skeleton show.
    flag            TEXT CHECK (flag IN ('needs_check', 'no_show_match') OR flag IS NULL),

    moderation_status TEXT NOT NULL DEFAULT 'pending' CHECK (moderation_status IN (
                            'pending', 'approved', 'rejected'
                        )),
    moderated_by    TEXT,
    moderated_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),

    -- 'showtimes' = extracted from the PDF archive (source_issue/source_file
    -- are a real magazine citation); 'manual' = typed in directly by a
    -- moderator via Edit Show, for a review that exists but was never in
    -- the archive - show_detail.html cites these differently (no "Originally
    -- published in AIMS ShowTimes..." line, since that would be false).
    source          TEXT NOT NULL DEFAULT 'showtimes' CHECK (source IN ('showtimes', 'manual')),

    -- The production this review is of. Reached via show_id (a review is
    -- always attached to a shows row before it can be approved), so an
    -- unmatched/pending review has NULL here - same state as show_id IS NULL.
    production_id   INTEGER REFERENCES productions(id)
);

-- (production_id's index lives in app/db.py - see the note by historical_results.)
CREATE INDEX IF NOT EXISTS idx_historical_reviews_show_id ON historical_reviews(show_id);
CREATE INDEX IF NOT EXISTS idx_historical_reviews_moderation_status ON historical_reviews(moderation_status);
CREATE INDEX IF NOT EXISTS idx_historical_reviews_season_tier ON historical_reviews(season, tier);

-- A public, no-login "here's an old photo" intake for material this archive
-- has no other way to collect: pre-2009 ShowTimes review clippings (older
-- than the digitized PDF archive extract_historical_reviews.py works from)
-- and old production/programme photos for shows with a thin record. Open to
-- anyone, deliberately - unlike historical_reviews or shows, nothing here is
-- required to match an existing society/show/production; society_guess/
-- show_guess/date_guess are free text a moderator reads and acts on by hand,
-- same trust model as everywhere else in this repo. Nothing here writes to
-- shows/historical_reviews/show_info automatically - a moderator does that
-- themselves once they've looked at the photo, then marks the row 'done'.
CREATE TABLE IF NOT EXISTS photo_submissions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    kind             TEXT NOT NULL CHECK (kind IN ('review', 'production_photo')),
    filename         TEXT NOT NULL,     -- under the uploads dir, same convention as shows.poster_filename
    society_guess    TEXT,
    show_guess       TEXT,
    date_guess       TEXT,              -- free text - "1987" or "sometime in the 90s" is a valid answer
    notes            TEXT,              -- submitter's own description (publication name, who's pictured, etc.)
    submitter_name   TEXT,
    submitter_email  TEXT,
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'rejected')),
    moderator_notes  TEXT,
    moderated_by     TEXT,
    moderated_at     TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_photo_submissions_status ON photo_submissions(status);

-- One row per real staging: one show, by one society, in one season. This is
-- the thing every "how many productions are on record" / "is this production
-- reviewed" question on the site is actually about, and until this table
-- existed there was no shared definition of it anywhere - each page re-derived
-- its own by unioning shows with historical_results and anti-joining the
-- skeleton rows, and they disagreed with each other (see ROADMAP: a 371-
-- production undercount on /stats, then an 823-production one, both caused by
-- exactly that).
--
-- DERIVED, NOT AUTHORED - and staying that way. Nothing writes here except
-- build_productions.py, which rebuilds the whole table from shows /
-- historical_results / historical_reviews and is safe to re-run - it upserts
-- on the natural key, so a production keeps its id across rebuilds. Those
-- three tables stay the place data is entered and edited; this one is the
-- index over them.
--
-- Making it authored (a moderator editing a production directly) was scoped as
-- a later step and was decided against on 2026-08-23, after all four public
-- surfaces were cut over. Every way a production can be wrong today traces to a
-- source row being wrong, and each of those already has an editing surface that
-- fixes the production *and* the page the data actually lives on; editing the
-- production instead would fix the index and leave the source wrong, which is
-- the exact disagreement this table exists to end. Authored rows would also
-- cost the property that makes the table trustworthy - it is a pure function of
-- its sources, which is why the rebuild can verify itself by re-deriving every
-- total from the database and refusing to commit on disagreement. Revisit only
-- if a correction is needed that cannot be expressed as an edit to shows /
-- historical_results / historical_reviews, if the verification pass starts
-- failing on real data, or if the unmatched historical society names are worked
-- down and productions still split wrongly. See docs/data-model.md.
--
-- season_start_year, not season, is identity. A 'yy/yy' string cannot
-- identify a season across this archive's real 1912-2028 span: '11/12' names
-- both the 1912 award year and the 2011/12 season, and the app's own
-- historical_results_year() helper ('yy/yy' -> 2000+yy+1) silently sent every
-- pre-2001 award year to a year that doesn't exist (1912 -> 2012, 2000 ->
-- 2100). Storing the real four-digit start year makes that class of bug
-- impossible rather than merely fixed. season is kept alongside purely as the
-- display string.
--
-- society_key is how a production is identified when its society isn't in the
-- societies table at all - 71 society names in the awards archive are
-- defunct/renamed and have never matched a current row, and they still stage
-- real productions that have to count. 'id:<societies.id>' when matched,
-- 'name:<normalized name>' when not, so the natural key works either way and
-- can never collide between the two forms.
CREATE TABLE IF NOT EXISTS productions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,

    -- identity (see ux_productions_natural_key below)
    season_start_year  INTEGER NOT NULL,
    society_key        TEXT NOT NULL,
    title_key          TEXT NOT NULL,       -- app.similarity.normalize_title(title)

    -- display values, resolved once here instead of re-derived per query
    season             TEXT NOT NULL,       -- 'yy/yy', derived from season_start_year
    society_id         INTEGER REFERENCES societies(id),   -- NULL = never matched
    society_name       TEXT NOT NULL,       -- always populated, even when society_id is NULL
    title              TEXT NOT NULL,

    -- Region resolves once per production rather than through the three-way
    -- COALESCE(shows.region, societies.region, historical_society_regions.
    -- confirmed_region) fallback every historical query hand-rolls today.
    -- NULL = a defunct society with no confirmed region guess, which is a real
    -- state, not an error.
    region             TEXT CHECK (region IN (
                            'Eastern', 'Western', 'Northern',
                            'South-West', 'South-East', 'Midlands'
                        ) OR region IS NULL),

    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row (id is pinned to 1), holding a cheap fingerprint of the source
-- tables as they were at the last successful rebuild. A page reading the
-- derived productions table checks this first and rebuilds if the sources
-- have moved, so a moderator approving a show doesn't have to wait for the
-- next deploy to see it counted. No row at all = rebuild on next read.
CREATE TABLE IF NOT EXISTS productions_build_state (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    fingerprint  TEXT NOT NULL,
    built_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_productions_natural_key
    ON productions(society_key, season_start_year, title_key);

-- One row per real building an AIMS society has staged a production in.
--
-- shows.venue is free text typed per production, and it drifts: "Town Hall
-- Theatre" is spelled 8 different ways across the archive, "National Opera
-- House" 4, and some entries are a bare town name ("Dublin") or not a venue at
-- all ("Cork run"). 177 distinct strings stand for roughly 110-130 buildings.
-- That's fine for recording what someone typed, and useless as something to
-- hang a capacity or a map pin on - hence a real record, with the raw string
-- kept exactly as entered and mapped to it through venue_aliases.
--
-- Everything below town is optional and drip-fed: a moderator fills a field in
-- when they have it, and the public page renders each one only when it's set,
-- rather than showing "not collected" placeholders. Nothing here is required
-- for the page to work - name, productions, resident societies and stage
-- history all come from the shows table as they always did.
CREATE TABLE IF NOT EXISTS venues (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,          -- canonical display name
    slug             TEXT NOT NULL UNIQUE,   -- /venues/<slug>
    name_key         TEXT NOT NULL UNIQUE,   -- normalized name; the identity

    town             TEXT,
    county           TEXT,
    -- Seeded from the productions staged here (a show carries its own region
    -- snapshot), then moderator-correctable. NULL where those disagree with no
    -- majority - a real "needs a human" state, not an error.
    region           TEXT CHECK (region IN (
                          'Eastern', 'Western', 'Northern',
                          'South-West', 'South-East', 'Midlands'
                      ) OR region IS NULL),

    capacity         INTEGER,
    auditorium_type  TEXT,
    latitude         REAL,
    longitude        REAL,
    website_url      TEXT,
    tech_spec_url    TEXT,
    notes            TEXT,                   -- moderator-facing, never shown publicly

    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Every distinct spelling that has ever appeared in shows.venue, pointing at
-- the venue it means. This is what makes merging safe and re-runnable: the
-- seeder creates one venue plus one alias per new spelling, a moderator merge
-- repoints the alias, and a later re-run finds the alias rather than
-- recreating the venue that was merged away. shows.venue itself is never
-- rewritten - what someone typed stays what they typed.
CREATE TABLE IF NOT EXISTS venue_aliases (
    name_key   TEXT PRIMARY KEY,             -- normalized shows.venue string
    raw        TEXT NOT NULL,                -- one real spelling, for the admin UI
    venue_id   INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_venue_aliases_venue_id ON venue_aliases(venue_id);
CREATE INDEX IF NOT EXISTS idx_venues_region ON venues(region);

-- Same one-row change detector as productions_build_state above.
CREATE TABLE IF NOT EXISTS venues_build_state (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    fingerprint  TEXT NOT NULL,
    built_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_productions_society_id ON productions(society_id);
CREATE INDEX IF NOT EXISTS idx_productions_season_start_year ON productions(season_start_year);
CREATE INDEX IF NOT EXISTS idx_productions_title_key ON productions(title_key);

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

-- Reviews from the ShowTimes archive. review_text is the whole review, so
-- this is the one index that searches prose rather than names - it's what
-- makes "who directed X", a cast member's name, or a venue findable at all,
-- since none of that exists as a column anywhere. Same external-content
-- pattern as the two above: the index holds only tokenized text, the row
-- itself stays in historical_reviews.
CREATE VIRTUAL TABLE IF NOT EXISTS historical_reviews_fts USING fts5(
    show_raw, society_raw, review_text, content='historical_reviews', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS historical_reviews_fts_ai AFTER INSERT ON historical_reviews BEGIN
    INSERT INTO historical_reviews_fts(rowid, show_raw, society_raw, review_text)
    VALUES (new.id, new.show_raw, new.society_raw, new.review_text);
END;
CREATE TRIGGER IF NOT EXISTS historical_reviews_fts_ad AFTER DELETE ON historical_reviews BEGIN
    INSERT INTO historical_reviews_fts(historical_reviews_fts, rowid, show_raw, society_raw, review_text)
    VALUES ('delete', old.id, old.show_raw, old.society_raw, old.review_text);
END;
CREATE TRIGGER IF NOT EXISTS historical_reviews_fts_au AFTER UPDATE ON historical_reviews BEGIN
    INSERT INTO historical_reviews_fts(historical_reviews_fts, rowid, show_raw, society_raw, review_text)
    VALUES ('delete', old.id, old.show_raw, old.society_raw, old.review_text);
    INSERT INTO historical_reviews_fts(rowid, show_raw, society_raw, review_text)
    VALUES (new.id, new.show_raw, new.society_raw, new.review_text);
END;
