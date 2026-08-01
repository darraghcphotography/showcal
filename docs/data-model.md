# Data model

See `schema.sql` for the full definitions, CHECK constraints, and inline
comments - this is a guided tour, not a replacement for reading it.

- **societies** - one row per member society (imported from `societies.csv`).
- **shows** - one row per production. Each row snapshots the society's
  `region`/`section` *at the time of that show*, since a society's tier can
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
  their provenance.
- **poster_filename** on `shows` - an optional uploaded poster image. The file
  itself lives on disk under `AIMS_UPLOAD_DIR` (default `./uploads` locally,
  `/data/uploads` in Docker), named with a random id - never the filename the
  browser sent, which avoids path-traversal tricks and filename collisions.
  Only image types (JPG/PNG/WEBP/GIF) are accepted, capped at 8&nbsp;MB.
- Societies with `section = 'Inactive'` are hidden from the public browse page
  by default. Logged-in moderators get a "Show inactive societies" checkbox
  to reveal them - the underlying query only honours that flag for a
  logged-in session, so it can't be forced via the URL by anyone else.

## Column migrations

SQLite's `CREATE TABLE IF NOT EXISTS` only creates a table the *first* time -
it can never add a column to a table that already exists. Every column added
after the initial release is listed in `app/db.py`'s `COLUMN_MIGRATIONS`, and
applied automatically (and idempotently) on every app startup. If you add a
new column to `schema.sql` later, add a matching entry there too, or existing
databases will 500 the first time that column is touched.
