# Deployment

## Running it locally (Windows)

```powershell
py -m pip install -r requirements.txt

# one-time: create your own login (you'll be prompted for a password)
py seed_admin.py yourname --role admin

# create an invite code for members to use (or do this later from /admin/invite-codes)
py -c "import sqlite3; c=sqlite3.connect('aims.db'); c.execute(\"INSERT INTO invite_codes (code, label) VALUES ('AIMS-2026','general member code')\"); c.commit()"

$env:SECRET_KEY = "anything-for-local-dev"
$env:FLASK_APP = "app"
py -m flask run
```

Visit http://127.0.0.1:5000. `flask run` is the Flask **development** server -
fine for trying things out, not for the NAS deployment below.

Re-running `import_csv.py` any time you update the spreadsheet export is
always safe - it upserts import-sourced rows and never touches submissions
or moderator edits (see the design notes at the top of `schema.sql`).

## Deploying on the QNAP NAS via Portainer

`docker-compose.yml` works exactly the same way as a Portainer **Stack** as
it would via the `docker compose` CLI.

1. Get the project onto the NAS - easiest is `git clone` into a shared folder
   over SSH (this repo, once pushed), or upload the folder via File Station.
   Portainer's stack editor can also take a repo URL directly (Stacks -> Add
   stack -> Repository).
2. Generate a real secret key: `py -c "import secrets; print(secrets.token_hex(32))"`.
3. In Portainer: **Stacks -> Add stack**. Name it `aims-web`. Either point it
   at the cloned folder's `docker-compose.yml` (Stacks -> Add stack ->
   "Upload" or "Repository"), or paste its contents into the web editor.
4. Under **Environment variables** in the stack editor, add:
   - `SECRET_KEY` - the value you generated in step 2.
   - `URL_PREFIX` - `/showcal` (see the path-routing note below - only needed
     because you're serving this under a sub-path of darraghc.ie rather than
     its own subdomain).
5. Deploy the stack. Portainer builds the image and starts `aims-web`,
   reachable at `127.0.0.1:8000` on the NAS itself - not on your LAN or the
   internet - with `aims.db` and uploaded posters persisted under the
   absolute host path in `docker-compose.yml`'s `volumes:` line (currently
   `/share/CACHEDEV1_DATA/Data/config/aims-web`), so redeploying or
   rebuilding the image never touches your data.

   **This must be an absolute path, never a relative one like `./data`.**
   Portainer resolves a stack's relative volume paths against its own
   internal view of the filesystem, then passes that literal path string
   to the Docker daemon running on the bare NAS - which has no idea it was
   "supposed to" mean Portainer's own data folder, and will silently create
   an unrelated empty directory of the same name on the NAS's small system
   partition instead. That directory survives ordinary container restarts
   and redeploys (so this can go unnoticed for months), but does *not*
   survive an actual NAS reboot, unlike a real storage-pool path - which is
   exactly how this app's entire history got silently wiped once, after a
   RAM upgrade required a full shutdown. Use a real absolute path, matching
   how every other container on this NAS is already set up.
6. Create your admin login from Portainer's **Console** for the `aims-web`
   container (or via SSH):
   ```
   python seed_admin.py yourname --role admin --db /data/aims.db
   ```

### Redeploying after a code update

Push to GitHub, then in Portainer use the stack's **Pull and redeploy**
button - confirmed working for this stack (container name `aims-web`). If
it ever fails for a `Dockerfile`-only change, the fallback is removing the
stack and adding it again with the same repository/branch/env settings.

**Running a one-off script against the real database** (`import_csv.py`,
`import_awards.py`, `seed_admin.py`, `fix_show_titles.py`) always needs an
explicit `--db /data/aims.db` (and `--csv /data/...` where relevant):
```bash
docker exec aims-web python <script>.py --db /data/aims.db
```
Every script's default `--db` points at a throwaway path inside the image's
`/app` working directory, not the volume-mounted real database - forgetting
the flag doesn't error, it silently creates/uses an empty database inside
the container and reports success against *that*, so nothing on the live
site actually changes. `docker compose exec` needs to run from the directory
holding `docker-compose.yml`; plain `docker exec aims-web ...` works from
anywhere over SSH once you know the container name.

### Backups

Two layers, both required - one alone isn't enough:

1. **Nightly local backup**, via the `aims-backup` service in
   `docker-compose.yml` - a small sidecar container running the same image,
   looping `backup_db.py` roughly once every 24 hours. This runs entirely
   inside Docker rather than via QNAP's own Task Scheduler because, on this
   NAS/firmware, Task Scheduler isn't present in Control Panel or App
   Center, HBS3's backup jobs have no pre/post-script hook, and a host
   crontab needs real root - the built-in `admin` superuser is disabled,
   and the SSH account available isn't in the administrators group, so
   `/etc/config/crontab` and `crond` itself aren't writable/restartable
   from it. If your NAS *does* have a working Task Scheduler, that's a
   perfectly good alternative to the sidecar - just point it at the same
   command:
   ```bash
   docker exec aims-web python backup_db.py --db /data/aims.db --backup-dir /data/backups
   ```
   Either way, this uses SQLite's own online backup API (safe against a
   mid-write torn copy), writes timestamped files under `/data/backups`,
   and keeps the last 14 by default. This only actually survives a reboot
   because `/data` is now a real absolute host path (see the volume note
   above) - it would not have under the old relative-path mount.
2. **An off-NAS copy**, via Hybrid Backup Sync (HBS3): a one-way **Backup
   Job** (not "Sync") from `/share/CACHEDEV1_DATA/Data/config/aims-web` (the
   whole folder, not just `backups/`, so `uploads/` - poster images - is
   covered too) to a cloud destination, scheduled to run shortly after the
   nightly local backup above. This is the layer that actually protects
   against the storage pool or a drive failing outright, which a same-pool
   backup never can. Run it manually once and confirm it completes before
   trusting the schedule.

### Recovering from a broken `/data` mount

If the site suddenly shows zero societies/shows after a NAS reboot or
redeploy, the app's own startup log will already have flagged it - see the
warning `app/__init__.py` logs when `AIMS_DB_PATH` is set but no database
file exists yet at that path. Don't assume the data is gone; check first:

1. **Confirm the mount is actually wrong**:
   ```bash
   docker inspect aims-web --format '{{json .Mounts}}'
   ```
   The `Source` should be the absolute path from `docker-compose.yml`
   (`/share/CACHEDEV1_DATA/Data/config/aims-web`). If it's anything else,
   that's the bug - fix the compose file's `volumes:` line first (must be an
   absolute path, never a relative one - see the note above), redeploy, and
   re-check this before doing anything else.
2. **Check for a recent local backup** in `/data/backups` on whichever path
   was actually mounted before the fix - restore from there if one exists
   and is newer than the CSVs.
3. **If no backup exists**, most of the data can be rebuilt from source
   files rather than lost outright - `societies.csv`, `shows.csv`, and
   `AIMS_Awards - Results.csv` are tracked in git, so even if they're not
   sitting on the (now-fixed) data volume, a checked-out copy of this repo
   exists somewhere on the NAS (Portainer clones the repository to build
   from it - `find /share -iname shows.csv 2>/dev/null` will find it).
   Copy `societies.csv` and `shows.csv` into the real data folder, then
   re-run, in this order:
   ```bash
   docker exec aims-web python import_csv.py --db /data/aims.db --societies /data/societies.csv --shows /data/shows.csv
   docker exec aims-web python import_awards.py --db /data/aims.db
   docker exec aims-web python fix_show_titles.py --db /data/aims.db --csv /data/shows.csv
   docker exec aims-web python enrich_show_info.py --db /data/aims.db
   docker exec aims-web python suggest_historical_regions.py --db /data/aims.db
   docker exec -it aims-web python seed_admin.py yourname --role admin --db /data/aims.db
   ```
   (`seed_admin.py` needs the `-it` flags - it prompts for a password
   interactively, which fails with a bare `EOFError` under plain `docker exec`.)
4. **What this can't bring back**: anything that only ever lived in the
   database and isn't sourced from a CSV or script - moderator-confirmed
   historical-society regions (re-run `suggest_historical_regions.py` for
   the *suggestions*, but confirmations need re-reviewing in the admin UI),
   uploaded poster images, pending member submissions, invite codes,
   analytics history, and any `/admin/awards` edit that isn't already baked
   into `import_awards.py`'s `SHOW_RENAMES`/`CATEGORY_FIXES` dicts.

### Exposing it at darraghc.ie/showcal via Cloudflare Tunnel

Since Blacknight is just the registrar and DNS already runs on Cloudflare,
you don't need anything new opened on your router - a Tunnel is an outbound
connection the NAS makes out to Cloudflare, so nothing ever listens on your
WAN side, and TLS is Cloudflare's problem rather than yours (no certbot cron
job to babysit). That's the same reasoning as any reverse-proxy-vs-tunnel
choice, and it applies whether you're mounting at a subdomain or a sub-path.

**The one thing specific to a sub-path** (`darraghc.ie/showcal` rather than
`showcal.darraghc.ie`): Cloudflare Tunnel forwards the *full* incoming path
to your origin - it doesn't strip `/showcal` off before handing the request
to the container. Left alone, every route in this app would 404, since Flask
only knows about `/`, `/societies/1`, etc, not `/showcal/societies/1`. That's
what `URL_PREFIX` (set in step 4 above) exists to fix: `wsgi.py` wraps the app
in a small middleware that strips the prefix and sets `SCRIPT_NAME`, so
Flask's routing and every internal link (`url_for`, the CSS file, all nav
links) automatically account for it. This was tested locally before it
shipped - hitting `/showcal/` serves the homepage and every link on the page
correctly points back under `/showcal/...`.

Setup (Cloudflare's dashboard wording has shifted over time - look for
"Published application routes" under a tunnel if "Public Hostname" isn't
what you see):
1. In the [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/),
   under **Networks -> Tunnels**, either reuse an existing tunnel on this NAS
   or create one, and install/run `cloudflared` on the NAS using the token
   from that tunnel.
2. Add a route on the tunnel: Domain `darraghc.ie`, Path `^/showcal` (the
   `^` anchors it to a path *prefix* - Cloudflare's path field is regex, so
   without it "showcal" would also match anywhere else that text appears in
   a URL), Service `HTTP` -> `aims-web:8000`.
3. **If `cloudflared` runs in a different Portainer stack** (common if you
   already use a tunnel for other services), it needs to be on the *same*
   Docker network as `aims-web` for the container-name lookup above to
   resolve - `docker-compose.yml`'s `networks:` section declares this as an
   external network named `media-net` (edit the `name:` there to match
   whatever your existing stack's network is actually called; check
   Portainer -> Networks). Pointing the route at the NAS's LAN IP instead
   (`http://<nas-ip>:8000`) looks like it should work as a shortcut, but
   containers often can't loop back through the host's own LAN IP to reach
   another container's published port ("hairpin NAT") - joining the network
   properly avoids that entirely.
4. Confirm `URL_PREFIX=/showcal` is set on the `aims-web` stack (step 4
   above) and redeploy if you added it after the first deploy.
5. Visit `https://darraghc.ie/showcal/` - you should see the homepage, and
   clicking around should never drop back to a bare unprefixed URL.

If darraghc.ie already serves something else at its root, this path rule
only intercepts `/showcal*` - everything else on the domain is unaffected.
If you'd rather avoid the path-prefix complexity entirely, a subdomain
(`showcal.darraghc.ie`) is simpler - just point that hostname at the service
with no Path set, and leave `URL_PREFIX` unset.

## Things intentionally left out (for now)

- No email notifications when something is submitted/approved - check the
  queue page yourself.
- No self-service member accounts/registration - invite codes plus your own
  admin login is the whole auth surface, on purpose (no public writes).
- No automated backups - `aims.db` (or `data/aims.db` under Docker) is the
  entire database; back it up however you already back up NAS shares. Back up
  the `uploads`/`data/uploads` folder the same way if posters matter to you -
  it's not part of the database file.
- No image resizing - posters are stored and served exactly as uploaded
  (capped at 8&nbsp;MB). A member uploading an unnecessarily huge photo will
  make that page slow to load; nothing currently downsizes it.
