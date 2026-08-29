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

Run the test suite (`tests/`, pytest against a fresh temp SQLite db per test - never touches `aims.db`):
```powershell
py -m pip install -r requirements-dev.txt
py -m pytest
```

Docker / Portainer:
```bash
docker compose up -d --build
docker compose exec aims-web python import_csv.py --db /data/aims.db --societies /data/societies.csv --shows /data/shows.csv
docker compose exec aims-web python seed_admin.py yourname --role admin --db /data/aims.db
docker compose exec aims-web python import_awards.py --db /data/aims.db
docker compose exec aims-web python export_awards.py --db /data/aims.db --csv "/data/AIMS_Awards - Results.csv"
docker compose exec aims-web python load_historical_reviews.py --db /data/aims.db
```
`export_awards.py` is `import_awards.py`'s inverse (same pattern as `export_csv.py`/`import_csv.py`)
- run it after a correction made via `/admin/awards`, then pull the file back out (File Station/scp)
to update the git-tracked copy, same as the CSV export workflow.
**Where the scripts live (reorganised 2026-08-29).** The repo root used to hold 40 `.py` files
while `scripts/` sat empty. The root now keeps only the things you actually run against a live
database, which are exactly the commands documented above and below - `import_csv.py`,
`export_csv.py`, `import_awards.py`, `export_awards.py`, `seed_admin.py`, `backup_db.py`,
`verify_backup.py`, `build_productions.py`, `add_changelog.py`, `load_historical_reviews.py`,
`extract_historical_reviews.py`, plus `wsgi.py`. Everything else moved:

- `scripts/backfills/` - one-off society/data backfills already run once (Carnew, Naas,
  Tullamore/Castlerea, the Gilbert 26/27 dates, the Oyster Lane rollback...).
- `scripts/enrichment/` - the delegated-research import/apply half (logos, venues, show info,
  founding years, venue types).
- `scripts/maintenance/` - dedupe and integrity one-offs (duplicate titles, ordinal titlecasing).
- `scripts/archive/` - what was already there.

Two things that were NOT scripts moved differently: `society_names.py` is imported by the running
app (`admin/historical_reviews.py`, `admin/historical_society_links.py`) so it is now
`app/society_names.py`, and `wsgi.py` stays at the root because the Dockerfile's `CMD` names it.
A moved script computes the repo root as `Path(__file__).resolve().parents[2]`, not
`Path(__file__).parent`. `tests/conftest.py` puts the three script directories on `sys.path`, so a
test can still `from classify_venue_types import classify` by module name.

`build_productions.py` rebuilds the derived `productions` table (see `schema.sql`) from
`shows`/`historical_results`/`historical_reviews`. **Normally you never need to run it** - the app
rebuilds on every startup and lazily whenever the source tables have moved. Run it by hand only to see
what a rebuild would do before letting it near production (`--dry-run` verifies and rolls back), or after
a bulk import script has rewritten rows outside the app.
`load_historical_reviews.py` is `extract_historical_reviews.py`'s other half - extraction needs
PyMuPDF and the ShowTimes PDF archive (`E:\showtimes archive`), neither of which exist in the
container, so extraction always runs locally (`py extract_historical_reviews.py`) into a git-tracked
JSON file (`historical_reviews_pilot.json`); only loading that JSON into a database runs in the
container, same default filename either side so no `--json` override is normally needed.
Changelog entries (shown on the public `/suggestions` Roadmap page) publish themselves - write a
new entry into `CHANGELOG.md` (one line per bullet, blocks separated by `---`) and it's live the
moment that commit gets redeployed, no command needed (`app/changelog_sync.py`, runs once on every
startup - a deleted entry never comes back, see `schema.sql`'s `changelog_synced_entries`). For a
one-off entry outside the normal commit/redeploy flow: `docker compose exec aims-web python
add_changelog.py --db /data/aims.db "Headline" "Detail one"`.
**Always pass `--db /data/aims.db` explicitly in the container** - every management script's default `--db`
points at a bare `aims.db` relative to the image's `/app` working directory, not the volume-mounted real
database. Forgetting the flag doesn't error - it silently creates/uses a fresh, empty throwaway database
inside the container's writable layer and reports success against *that*, so nothing actually changes on
the live site. (`docker compose exec` also needs to be run from the directory holding `docker-compose.yml`;
if it says "no configuration file provided", `docker exec <container-name>` works from anywhere once you
have the container name from `docker ps`.)

**Claude has direct SSH access to the NAS** (set up 2026-08-19, so Darragh doesn't have to relay
every command manually): `ssh -i ~/.ssh/claudeshowcal_ed25519 claudeshowcal@dc-qnap-2` - a dedicated
key-only account, no password stored or typed anywhere. Two things that aren't obvious from a plain
shell there:
- **`docker` isn't on `claudeshowcal`'s `$PATH`** - use the full path,
  `/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker`, for every `docker exec`/`docker ps`/etc.
- **There's no `git` on the NAS host at all**, and the `showcal` project folder there
  (`/share/CACHEDEV1_DATA/homes/darraghc/showcal/`) is a plain file copy, not a git clone - "pull and
  redeploy" happens through Portainer's own git-backed stack mechanism, not anything on the host
  filesystem. Don't try to `git pull` there or treat that folder as the deploy source.
- **Portainer's own API (port 9000) is unreachable even from the NAS itself** - connections time out
  rather than refuse, consistent with QNAP's own firewall app blocking it rather than the service
  being down. Triggering "pull and redeploy" still needs to go through the Portainer UI (or Darragh's
  phone/Chrome Remote Desktop) for now - this was investigated once and not solved, not untried.
- **GitOps updates enabled 2026-08-25 (Polling, 5m interval)** - a push to `main` now reaches
  production **on its own within ~5 minutes**, with no manual "pull and redeploy" click and no human
  review step in between. This is a real change to how much autonomy a push has: previously Darragh's
  own redeploy click was the last checkpoint before anything shipped went live; now there isn't one.
  Weigh that when deciding whether to push something uncertain versus flagging it first. Also: any
  config change made by hand in the Portainer UI (env vars, etc.) gets silently overwritten on the
  next poll - anything that needs to persist has to live in `docker-compose.yml` in git instead.
- **The deployed stack is readable, so verify against it rather than assuming.** This is Portainer
  **Stack 8**, and its GitOps checkout of the whole repo sits at
  `/share/CACHEDEV2_DATA/Data/config/portainer/compose/8/`. That folder is what actually got
  deployed, so `md5sum` on a file there against the local copy answers "is production running my
  code?" definitively, in one command. Use it after any push that matters. `stack.env` beside it
  holds the real environment (`SECRET_KEY`, `URL_PREFIX`, `SMTP_USER`, `SMTP_PASSWORD`) - that, not
  a `.env` anywhere on the host, is where those values live.
- **The config volume moved to `CACHEDEV2_DATA` on 2026-08-28** - Darragh installed two Integral M.2
  NVMe drives as a RAID 1 mirror (Storage Pool 2, `SSD_DATA`) and moved all container config onto
  them, for speed and to stop the database queueing behind everything else on the spinning array.
  The database now runs on SSD; the old volume is a 7.9TB array that sits at 96% full. A
  pre-migration snapshot is kept at `C:\Users\Darragh\aims_backup_preshutdown.db`.
  Only the *data* path moved: Container Station
  itself (`/share/CACHEDEV1_DATA/.qpkg/...`) and the `homes/darraghc/showcal/` folder above are both
  still on volume 1, so don't "fix" those to match.
  **⚠ A stale copy of the whole `aims-web` folder is still sitting at the old
  `/share/CACHEDEV1_DATA/Data/config/aims-web/` path, and it looks completely plausible** - a real
  `aims.db` of the same size, with its own `backups/` directory, frozen at 2026-08-28 13:02. Reading
  it instead of the live one is a silent, entirely convincing failure: it gives you real data that is
  merely out of date, with nothing to signal that anything is wrong. This already happened once, on
  the day of the move, and cost most of a session's analysis. Check the mtime before trusting any
  copy you pull down.
- The `aims.db` file itself lives at `/share/CACHEDEV2_DATA/Data/config/aims-web/aims.db` on the NAS
  host - safe to `scp` down read-only for analysis (a live production audit doesn't need to run
  inside the container), but never edit that copy and push it back; use the container's own management
  scripts (with `--db /data/aims.db`, as above) for any real write.

## Rules for Claude working in this repo

1. **Diffs, not rewrites.** Use `Edit` with a minimal, targeted `old_string`/`new_string`. Never
   regenerate a whole file for a small change - only use `Write` for genuinely new files.
2. **Code first.** Skip conversational preamble ("I'll now...", "Let's..."). Make the edit, then
   give a short summary of what changed and why.
3. **Read `/docs` before asking.** `docs/user-guide.md`, `docs/moderator-guide.md`,
   `docs/deployment.md`, and `docs/data-model.md` already answer most "how does X work" or
   "why is Y built this way" questions - check there first.
4. **Check `ROADMAP.md` at the start of a session.** It tracks the current phase of work, a flat
   list of genuinely open items, and working agreements from prior retrospectives - update it when
   the phase changes rather than just saying the plan out loud in chat, since chat history doesn't
   survive `/clear`. Kept deliberately lean (pruned 2026-08-20, was ~3,000 lines) since it's read
   every session - full session-by-session history lives in `ROADMAP_ARCHIVE.md` instead; only
   check that file if you need past reasoning/detail behind something, not for everyday pickup.
   When a session fully resolves an open item, move its entry out of `ROADMAP.md` rather than
   letting resolved items accumulate there again.

## Things worth knowing before editing

- Adding a column to an existing table needs an entry in `app/db.py`'s `COLUMN_MIGRATIONS` list -
  `CREATE TABLE IF NOT EXISTS` in `schema.sql` never adds a column to a table that already exists.
- `shows.source` distinguishes `import` (from CSV) vs `submission` (member-submitted) rows -
  `import_csv.py` only ever updates `source='import'` rows, and never regresses
  `review_status`/`review_url`/`venue`/`director`/`musical_director`/`choreographer` to blank -
  a real spreadsheet value still wins, but a blank one won't erase a value set directly in the app.
- Title matching (submission duplicate warning, stats grouping) is an exact match on a normalized
  string (`app/similarity.py`), deliberately not fuzzy - several real shows have close names
  (`Frozen` vs `Frozen Jr.`) that fuzzy matching would wrongly conflate.
- Clean up any test admin logins / test data from `aims.db` after manual testing rather than
  leaving them in.
