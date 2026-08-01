# CLAUDE.md

Guidance for Claude Code in this repo (AIMS Show Tracker).

## Stack

- **Flask**, server-rendered Jinja templates. No frontend framework, no build step.
- **SQLite** (`aims.db`), raw `sqlite3` queries - no ORM. `schema.sql` is the single source of truth for the schema.
- **Flask-WTF** for CSRF only. `werkzeug.security` for password hashing. No other auth library.
- **waitress** as the production WSGI server (Docker). Flask's own dev server for local work.

## Dev & run commands

Local dev:
```powershell
py -m pip install -r requirements.txt
py seed_admin.py yourname --role admin        # create/reset a moderator login (prompts for password)
$env:SECRET_KEY = "anything-for-local-dev"
$env:FLASK_APP = "app"
py -m flask run                                # dev server at :5000
```
`wsgi.py` only defines the `app` object (no `__main__` block) - it's a WSGI entry point for
waitress/Docker, not something you run directly with `py wsgi.py`.

Import/refresh data (safe to re-run - upserts, never touches member submissions or moderator edits):
```powershell
py import_csv.py
```

Docker / Portainer:
```bash
docker compose up -d --build
docker compose exec aims-web python import_csv.py --db /data/aims.db --societies /data/societies.csv --shows /data/shows.csv
docker compose exec aims-web python seed_admin.py yourname --role admin --db /data/aims.db
```

## Rules for Claude working in this repo

1. **Diffs, not rewrites.** Use `Edit` with a minimal, targeted `old_string`/`new_string`. Never
   regenerate a whole file for a small change - only use `Write` for genuinely new files.
2. **Code first.** Skip conversational preamble ("I'll now...", "Let's..."). Make the edit, then
   give a short summary of what changed and why.
3. **Read `/docs` before asking.** `docs/user-guide.md`, `docs/moderator-guide.md`,
   `docs/deployment.md`, and `docs/data-model.md` already answer most "how does X work" or
   "why is Y built this way" questions - check there first.

## Things worth knowing before editing

- Adding a column to an existing table needs an entry in `app/db.py`'s `COLUMN_MIGRATIONS` list -
  `CREATE TABLE IF NOT EXISTS` in `schema.sql` never adds a column to a table that already exists.
- `shows.source` distinguishes `import` (from CSV) vs `submission` (member-submitted) rows -
  `import_csv.py` only ever updates `source='import'` rows, and never regresses a
  `review_status`/`review_url` a moderator has already set.
- Title matching (submission duplicate warning, stats grouping) is an exact match on a normalized
  string (`app/similarity.py`), deliberately not fuzzy - several real shows have close names
  (`Frozen` vs `Frozen Jr.`) that fuzzy matching would wrongly conflate.
- Clean up any test admin logins / test data from `aims.db` after manual testing rather than
  leaving them in.
