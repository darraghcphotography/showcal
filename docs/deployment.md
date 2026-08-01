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
   internet - with `aims.db` and uploaded posters persisted under
   `./data` next to the stack, so redeploying or rebuilding the image never
   touches your data.
6. Create your admin login from Portainer's **Console** for the `aims-web`
   container (or via SSH):
   ```
   python seed_admin.py yourname --role admin --db /data/aims.db
   ```

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

Setup:
1. In the [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/),
   under **Networks -> Tunnels**, either reuse an existing tunnel on this NAS
   or create one, and install/run `cloudflared` on the NAS (as a Portainer
   stack alongside this one, or as its own container) using the token from
   that tunnel.
2. Add a **Public Hostname** on the tunnel:
   - Domain: `darraghc.ie`
   - Path: `showcal*`
   - Service: `HTTP` -> `aims-web:8000` (the compose service name - if
     `cloudflared` is a separate stack, put both stacks on the same Docker
     network so it can resolve that name, or use the NAS's LAN IP instead).
3. Confirm `URL_PREFIX=/showcal` is set on the `aims-web` stack (step 4
   above) and redeploy if you added it after the first deploy.
4. Visit `https://darraghc.ie/showcal/` - you should see the homepage, and
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
