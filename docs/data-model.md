# Data model

See `schema.sql` for the full definitions, CHECK constraints, and inline
comments - this is a guided tour, not a replacement for reading it.

- **societies** - one row per member society (imported from `societies.csv`).
  `id` is the stable id from that CSV export, not an autoincrement column -
  a society added directly via `/admin/societies` gets an id of 10000 or
  higher instead, so a future CSV re-import can never collide with it.
- **shows** - one row per production. Each row snapshots the society's
  `region`/`section` *at the time of that show*, since a society's section can
  change season to season - so a show stays correctly labelled even after its
  society later moves Sullivan &harr; Gilbert.
- Every show has a **`moderation_status`** (`pending` / `approved` /
  `rejected`) - only `approved` rows are ever shown on public pages. Rows
  imported from the CSV are auto-approved (they're already-published
  history); new member submissions default to `pending`.
- **`source`** (`import` vs `submission`) means re-running `import_csv.py`
  after you update the spreadsheet can never overwrite or delete anything
  created through the app - the importer only ever touches `source='import'`
  rows, and even then never regresses a `review_status`/`review_url` a
  moderator has already set beyond what the spreadsheet currently has.
- **users** - moderator/admin logins (created via `seed_admin.py`, not through
  the web UI - there's no public registration).
- **invite_codes** - shareable codes that unlock the submission form for
  members. Revoke by deactivating, not deleting, so old submissions keep
  their provenance. `society_id` is NULL for a regular one-off submission
  code, or set to turn it into a society login instead (see the
  [moderator guide](moderator-guide.md#society-logins)).
- **show_links** - a moderator-confirmed Wikipedia (or other) link per show
  title, shown on Shows A-Z. Falls back to an auto-generated search link
  until confirmed - nothing is ever auto-resolved and stored as if verified.
- **show_info** - a moderator-curated synopsis and amateur rights/licensing
  status per show title, shown on that title's own page. Same trust model as
  `show_links`: nothing fetched automatically, since there's no reliable
  public API for amateur theatre licensing - a moderator looks the title up
  on the actual rights holder's site and enters it once.
- **dismissed_duplicate_pairs** - remembers a "these are NOT the same show"
  decision from the duplicate-title finder (e.g. `Frozen` / `Frozen Jr.`) so
  it doesn't keep resurfacing.
- **poster_filename** on `shows` - an optional uploaded poster image. The file
  itself lives on disk under `AIMS_UPLOAD_DIR` (default `./uploads` locally,
  `/data/uploads` in Docker), named with a random id - never the filename the
  browser sent, which avoids path-traversal tricks and filename collisions.
  Only image types (JPG/PNG/WEBP/GIF) are accepted, capped at 8&nbsp;MB.
- Societies with `section = 'Inactive'` are hidden from the public browse page
  by default. Logged-in moderators get a "Show inactive societies" checkbox
  to reveal them - the underlying query only honours that flag for a
  logged-in session, so it can't be forced via the URL by anyone else.
- **societies.hidden** is a different concept from `Inactive` - a society that's
  asked not to be publicly associated with AIMS at all (moderator-only toggle on
  `/admin/societies/<id>/edit`). It 404s that society's own public page and drops
  them from the browse page (same logged-in-only reveal as Inactive), but does
  **not** touch historical stats, the Awards page, or the Season Archive - those
  stay an accurate historical record. Their own self-service login is unaffected.
- **page_views** - one row per URL path, with a running count and last-viewed
  timestamp. Populated by an `after_request` hook (`app/analytics.py`) on
  every successful public GET request; admin, upload, and feed routes are
  excluded. No cookies or per-visitor identity involved - it's a page counter,
  not visitor analytics.

## Duplicate-title detection

Title deduplication (`app/similarity.py`) only ever runs a normalized exact
match - lowercase, punctuation stripped, whitespace collapsed. It deliberately
does *not* do fuzzy/Levenshtein matching: that would also flag genuinely
different shows with similar names (there are several real ones in this
dataset - `Frozen` vs `Frozen Jr.`, `Calendar Girls` vs `Calendar Girls 2.0`),
and a false positive is a worse experience for a member filling in a form
than an occasional missed near-duplicate that a moderator can still catch
later. See `fix_show_titles.py` for the one-time corrections applied after
an initial audit of the imported data turned up real duplicates and a couple
of data entry errors (concatenated titles, stray status text) - it's
documented there rather than as an invisible database edit.

## Historical awards data (1977-present)

`historical_results` holds AIMS's full adjudication archive - one row per
award *nomination*, not per production (a single show can have several rows:
Best Director, Best Actor, etc). It originally covered only pre-2024 rows,
bootstrapped once by `import_awards.py` from `AIMS_Awards - Results.csv` (a
one-time export from AIMS's old internal awards database, which no longer
exists - that script is kept only as historical record of how the initial
data got in, not something expected to run again). The archive now covers
every year through the present, since award-level detail (who won which
category) was never tracked anywhere in `shows` in the first place - there's
nothing to double-count there.

The one place double-counting *is* a real risk: any query that treats a
`historical_results` row as equivalent to a `shows` row - i.e. counting or
listing *productions*, like "times performed" or "most performed shows" -
would double-count a 23/24+ show that's in both tables. Every such query
filters `historical_results` to `year < SHOWS_COVERAGE_START_YEAR` (a shared
constant in `app/constants.py`, currently 2024 = season 23/24, the first
season `shows` covers) to avoid this - see `app/blueprints/info.py`'s
`stats()` and `app/blueprints/public.py`'s `titles_list()`/`title_detail()`.
Pages that show award-*category* detail rather than a staging count - the
Awards page, a society's award history - aren't subject to this at all and
deliberately use the full, unfiltered archive.

`society_name` is plain text (not just a FK) since many historical societies
are defunct or renamed and don't match a row in `societies` - `society_id` is
filled in only when an exact name match was found (roughly 131 of 210
distinct historical names). `source` (`import` vs `manual`) distinguishes
CSV-bootstrapped rows from anything added/edited via `/admin/awards` -
`import_awards.py`'s wipe-and-reload only ever touches `source='import'`
rows, so a manually-entered or manually-corrected record can never be
silently discarded by a future re-run. `reason` holds the adjudicator's own
free-text note, present on about 1 in 15 records (mostly discretionary
categories like the Adjudicator's Special Award).

## Productions (the shared definition of "a staging")

`productions` is one row per real staging - one show, by one society, in one
season - and it's what "how many productions are on record" and "is this
production reviewed" should be answered from. Before it existed there was no
shared definition anywhere: each page re-derived its own by unioning `shows`
with `historical_results` and anti-joining the skeleton rows, and they
disagreed with each other. That cost 371 productions on `/stats` once, then a
further 823.

**It's derived, not authored - and that's a settled decision, not a stage.**
`app/productions_build.py` is the only thing
that writes to it; the three source tables above stay the place data is
entered and edited, and each carries a nullable `production_id` pointing back.
The rebuild upserts on the natural key, so a production keeps its id across
rebuilds. It runs on every app start, and lazily on a page that reads the
table when a cheap fingerprint shows the sources have moved - so a moderator
approving a show doesn't have to wait for a redeploy. A route that changes a
title *in place* without bumping `shows.updated_at` (an award record edited via
`/admin/awards`, a duplicate-title merge) calls `productions_build.mark_stale()`
itself, because the fingerprint can't see those. `build_productions.py` at the
repo root is the command-line half.

**The natural key is `(society_key, season_start_year, title_key)`**, derived in
`app/productions.py`:

- `society_key` is `id:<societies.id>` when the society matched a real row, and
  `name:<normalized name>` when it didn't. 71 society names in the awards
  archive are defunct or renamed and have never matched; they staged real
  productions and still have to count.
- `season_start_year` is the real four-digit year the season opened, **never a
  'yy/yy' string**. The archive runs from 1912, so `'11/12'` names both the 1912
  award year and the 2011/12 season. `historical_results_year()` (which decodes
  a season string as `2000+yy+1`) is therefore only safe on a `shows.season`
  value, and `season_start_year()`'s pivot at 50 only decodes seasons the shows
  table actually holds. Anything spanning the whole archive uses
  `award_year_to_season_start()` / `season_label()` and carries a four-digit
  year. Both older helpers now say so in their docstrings.
- `title_key` is `normalize_title()` - the same lowercase/strip-punctuation rule
  used everywhere else, deliberately not fuzzy.

Every rebuild ends with a verification pass that re-derives its totals from the
database rather than from the dict it just built, and raises rather than
committing on any disagreement - including the one failure that would matter
most, two `shows` rows landing under a single production.

Letting a moderator edit a production directly was scoped as a possible later
stage and was **decided against on 2026-08-23**, once all four surfaces were
cut over. The reasoning, so a future session doesn't re-litigate it: every way
a production can be wrong today traces to a source row being wrong (a title
spelled two ways, a society name that never matched, an award year mis-entered),
and each of those already has an editing surface - `/admin/awards`, the
duplicate-title merge, Edit Show - that fixes the production *and* the page the
data actually lives on. Editing the production instead would fix the index and
leave the source wrong, which is the exact disagreement between surfaces this
table was built to end. It would also cost the property that makes the rebuild
safe to run at any time: it's a pure function of its sources, so it can verify
itself by re-deriving every total from the database and refusing to commit on
disagreement. Authored rows would need an override layer the rebuild respects,
a merge/alias table the link-rewriting pass consults, and a verification pass
that can tell "a human said so" from "the data changed underneath you".

**Revisit that decision if**, and only if, one of these becomes true:

- a correction is needed that *cannot* be expressed as an edit to `shows`,
  `historical_results` or `historical_reviews` (none has come up);
- the rebuild's verification pass starts failing on real data, or two genuinely
  distinct stagings are found merged under one key;
- the ~71 unmatched historical society names are worked down (ROADMAP already
  carries that item, and it's the cheaper fix for the natural key's weakest
  point) and productions *still* split wrongly;
- a moderator needs a production that no source row implies. Today that's what
  `admin.bulk_historical_productions` is for - it writes a bare
  `historical_results` row and the production follows.

**Every public surface is cut over** as of 2026-08-23: `/stats`, the admin
dashboard counts, the Shows A-Z (plus `/search`'s Shows section and
`/sitemap.xml`), `/titles/<title>`, `/societies/<id>` and `/shows/<id>`. The one
shared filter they all apply is `ON_RECORD_PRODUCTION` in `app/productions.py` -
the table is built from every `shows` row regardless of `moderation_status`, so
a pending or rejected submission has a production row and each public query has
to exclude it the same way.

Some queries deliberately still read the old tables, and should stay that way:
anything showing award-*category* detail rather than a staging count. An award
record is a fact about a category, and there is nothing in `shows` to
double-count it against - so `/awards`, `/stats/trends`, `/stats`'s award
leaderboard and `wins_by_region`, a society's trophy case and its five award
badges, `search()`'s award-nominee section, and `app/similarity.py`'s
`find_award_record_match()` (a write-path check that runs *before* there is a
production to key on) all read `historical_results` unfiltered. The review lists
(`reviews_index()`, the adjudicator pages) count reviews, not stagings, and are
left alone for the same reason.

## Column migrations

SQLite's `CREATE TABLE IF NOT EXISTS` only creates a table the *first* time -
it can never add a column to a table that already exists. Every column added
after the initial release is listed in `app/db.py`'s `COLUMN_MIGRATIONS`, and
applied automatically (and idempotently) on every app startup. If you add a
new column to `schema.sql` later, add a matching entry there too, or existing
databases will 500 the first time that column is touched.
