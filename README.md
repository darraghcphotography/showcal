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
import_awards.py      one-time/re-runnable import of AIMS's awards archive (see docs/data-model.md)
seed_admin.py         create/update a moderator or admin login
fix_show_titles.py    documented, re-runnable data-quality corrections (see docs/data-model.md)
app/
  __init__.py         Flask app factory
  db.py               SQLite connection + schema/migration helpers
  auth.py             login + invite-code + society-code gating decorators
  constants.py         regions/tiers/etc, kept in sync with schema.sql's CHECKs
  season.py            "what season are we in" + season-dropdown helpers
  filters.py            Jinja filter: ISO dates -> dd-mm-yyyy for display
  uploads.py            poster/logo image validation/save (never trusts the browser's filename)
  similarity.py          normalized-title matching for the submission duplicate warning
  dedupe.py              fuzzy near-duplicate title finder for the admin merge tool
  analytics.py            simple per-page view counter, no cookies/tracking
  blueprints/
    public.py           browse societies, society/show/title detail, poster serving
    submit.py            invite-code unlock + member submission form (with duplicate-title warning)
    society.py            society self-service login: add/edit/bulk-add their own shows, logo upload
    admin.py             moderator login, dashboard, queue, edit/publish, societies, awards CRUD,
                          invite codes, fix-dates, duplicate titles, traffic, show info
    info.py               /season, /stats, and /awards pages
    feeds.py               CSV export, robots.txt, sitemap.xml
  templates/          Jinja templates (one per page)
  static/style.css     all the CSS, plain, no framework
wsgi.py              entry point for waitress; also applies the optional URL_PREFIX middleware
Dockerfile, docker-compose.yml   for QNAP Container Station / Portainer
docs/                user guide, moderator guide, deployment, data model
```

## Pages

Public: browse/search societies with a poster gallery and upcoming-shows
region filter, a society's full history (shows plus their awards archive
record), a show's detail page, **Shows A-Z** (search/sort, times-performed
count, an optional synopsis/amateur-rights info panel), **Current season**
at a glance (region/tier filters, upcoming and already-finished split),
**Statistics** (region drill-down, per-season breakdown, most
selected/performed, signature show per society, win-rate leaderboards, and
more - see the [user guide](docs/user-guide.md)), an **Awards** page
(browse/filter AIMS's full 1977-present adjudication archive), a full CSV
data export, a feature-suggestion box, and the member submission form.

Society login (behind `/society/login`, code issued by a moderator): a
dashboard to add/edit that society's own show history live (no moderation
queue), bulk-add past seasons, and upload a society logo.

Moderator (behind `/admin/login`): a dashboard summarising what needs
attention (pending submissions, missing review links/dates, possible
duplicate titles, unmatched award records), the moderation queue, full
show/society/award editing (including adding a new society or show
directly, and bulk-entering a whole award category's results at once), a
bulk date-fix workspace, invite/society-login code management, suggestion
review, and a simple traffic page. Full details in the
[user guide](docs/user-guide.md) and
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
