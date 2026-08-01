# Unofficial AIMS Show Tracker

A small Flask + SQLite web app for browsing AIMS member societies' show
history, with a moderated member-submission workflow so the site can replace
the hand-maintained spreadsheet over time. A project by Darragh C.

## Documentation

- **[User guide](docs/user-guide.md)** - browsing the site, and how members
  submit a show.
- **[Moderator guide](docs/moderator-guide.md)** - logging in, the moderation
  queue, editing shows, publishing reviews, invite codes.
- **[Deployment](docs/deployment.md)** - running it locally, and deploying to
  a QNAP NAS via Portainer + Cloudflare Tunnel.
- **[Data model](docs/data-model.md)** - the database schema, and why it's
  shaped the way it is.

## How it's built, and why

- **Flask + server-rendered Jinja templates.** No React/build step/npm - pages
  are plain HTML rendered on the server. Easiest thing to run on a NAS and to
  come back to in a year without re-learning a frontend toolchain.
- **SQLite**, one file (`aims.db`). No database server to run or back up
  separately - back up the site by copying one file.
- **Raw SQL via `sqlite3`**, no ORM. The schema (`schema.sql`) is the single
  source of truth; queries in the blueprints are plain, readable SQL.
- **Flask-WTF** is the one non-trivial dependency, used only for CSRF
  protection on forms (login, submission, moderation actions). Password
  hashing uses `werkzeug.security`, which ships with Flask - no separate
  auth library.
- **waitress** as the production server (in Docker). Pure Python, no
  native extensions, works the same on the NAS as it does anywhere else.

## Project layout

```
schema.sql          canonical DB schema (tables, constraints, indexes)
import_csv.py        one-time/re-runnable import from societies.csv + shows.csv
seed_admin.py         create/update a moderator or admin login
app/
  __init__.py         Flask app factory
  db.py               SQLite connection + schema/migration helpers
  auth.py             login + invite-code gating decorators
  constants.py         regions/tiers, kept in sync with schema.sql's CHECKs
  season.py            "what season are we in" helper, shared by submit + season page
  filters.py            Jinja filter: ISO dates -> dd-mm-yyyy for display
  uploads.py            poster image validation/save (never trusts the browser's filename)
  similarity.py          normalized-title matching for the submission duplicate warning
  analytics.py            simple per-page view counter, no cookies/tracking
  blueprints/
    public.py           browse societies, society/show detail, cross-society title view, poster serving
    submit.py            invite-code unlock + member submission form (with duplicate-title warning)
    admin.py             moderator login, queue, edit/publish, invite codes, traffic
    info.py               /season and /stats pages
    feeds.py               CSV export, robots.txt, sitemap.xml
  templates/          Jinja templates (one per page)
  static/style.css     all the CSS, plain, no framework
wsgi.py              entry point for waitress; also applies the optional URL_PREFIX middleware
fix_show_titles.py    documented, re-runnable data-quality corrections (see docs/data-model.md)
Dockerfile, docker-compose.yml   for QNAP Container Station / Portainer
docs/                user guide, moderator guide, deployment, data model
```

## Pages

Public: browse/search societies, upcoming shows, a society's full history, a
show's detail page, **Current season** at a glance (with a season picker for
past seasons), **Statistics** (with per-season drill-down and a cross-society
view of every production of a given title), a full CSV data export, and the
member submission form. Moderator (behind `/admin/login`): the moderation
queue, full show editing, invite code management, and a simple traffic page.
Full details in the [user guide](docs/user-guide.md) and
[moderator guide](docs/moderator-guide.md).

## Quick start

```powershell
py -m pip install -r requirements.txt
py seed_admin.py yourname --role admin
$env:SECRET_KEY = "anything-for-local-dev"
$env:FLASK_APP = "app"
py -m flask run
```

Visit http://127.0.0.1:5000. Full setup (including an invite code so you can
try the submission form) and NAS deployment steps are in
[docs/deployment.md](docs/deployment.md).
