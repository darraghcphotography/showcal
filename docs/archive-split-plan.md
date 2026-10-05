# Splitting ShowCal into `archive.aims.ie` and a live site

**Status: plan, not started.** Written 2026-10-05 for whichever agent executes it. Read
`CLAUDE.md`, `docs/glossary.md` and `ROADMAP.md` first; the rules there still apply.

## 1. The decision this plan carries out

Darragh's call (2026-10-05): the history belongs at **`archive.aims.ie`** - the awards record
since 1912, the ShowTimes and aims.ie reviews, past productions, adjudicators, the repertoire,
the statistics. It is built for historians and for anyone looking something up, and it reads
as part of AIMS. Everything that is *about now* - what's on, tickets, posters, the season
calendar, committee logins and self-service, submissions, the watchlist, the costumes and
props exchange - stays on a separate **live site**, which may later merge into the
organisation's own website.

Two sites, one codebase, one database. Not a fork.

## 2. Why one codebase and one database

The data does not split cleanly. A society has a history (archive) and a next show (live). A
`shows` row is a past production the day after it closes. Venues, productions and titles are
read by both. Forking the database would create a sync problem that never ends; two faces on
one database costs one environment variable and a route allowlist.

So the shape is:

- **One image, two containers** (`aims-web` as today for the live site, a new `aims-archive`),
  both mounting the same `/data` volume, both running the same code. The backup service and
  the off-site job do not change: there is still exactly one `aims.db`.
- **`SITE_ROLE`** environment variable: `archive`, `live`, or `all`. **`all` is the default
  and means today's behaviour**, so nothing visible changes until a container is given a role.
  Tests run with `all` unless a test sets a role.
- **`OTHER_SITE_URL`**: the absolute URL of the other site, used for cross-links and for
  redirecting a route that belongs to the other role.
- Each container has its own `SITE_URL`, `URL_PREFIX` and `NOTIFY_EMAIL` as today. The archive
  sits at the root of its hostname (no `URL_PREFIX`); the live site keeps `/showcal` until its
  own domain is decided (Phase 0).

SQLite with two writer processes on one host is fine here: WAL is already on, `busy_timeout`
is 5 s, and writes are rare moderator actions. The one thing to verify in Phase 4 is that
both containers starting at once (both rebuild `productions`/`venues` on startup) serialise
cleanly rather than one failing on a lock - start them a minute apart on first deploy and read
both logs.

## 3. Route inventory

Every public endpoint is assigned to exactly one of: **Archive**, **Live**, **Both** (served
by either, with role-specific sections), or **Shared** (plumbing). The test in Phase 1 fails
if an endpoint exists that is not in this table, so a new route can never be forgotten.

### Public

| Endpoint | Role | Notes |
|---|---|---|
| `public.index` | Live | What's on. The archive gets its own `index` (Phase 2). |
| `info.season_calendar` | Live | |
| `public.venues_map` | Live | "Near me" is live-only. |
| `public.watchlist` | Live | |
| `public.exchange_index`, `public.exchange_detail` | Live | |
| `public.suggest`, `public.suggest_thanks`, `public.suggestions_board` | Live | Feature suggestions and the roadmap page. The archive links to them. |
| `public.show_card` | Live | Social card PNG; it is for sharing upcoming shows. |
| `public.more` | Live | Mobile "More" tab. |
| `submit.unlock`, `submit.new`, `submit.thanks` | Live | |
| `society.*` (all 17) | Live | Committee tools, magic links, vault. |
| `feeds.calendar_ics`, `feeds.show_calendar_ics` | Live | |
| `feeds.manifest`, `feeds.service_worker` | Live | The archive is not a PWA. Serve a no-op `sw.js` on the archive that unregisters itself, so a visitor who had the live site installed is not stuck with a stale worker on the new host. |
| `info.awards` | Archive | |
| `public.reviews_index` | Archive | |
| `public.adjudicators_list`, `public.adjudicator_detail` | Archive | |
| `public.titles_list`, `public.title_detail` | Archive | |
| `info.stats`, `info.stats_trends` | Archive | |
| `info.season_summary` | Archive | Every season including the current one, as a record. The live site links "this season" here. |
| `submit.photo`, `submit.photo_thanks` | Archive | "Submit society history" - programmes, clippings, photos. |
| `feeds.export_shows_csv` | Archive | |
| `public.societies_list` | Both | Archive: a directory ordered for lookup, with productions-on-record and active-since. Live: the same list led by next production. The existing template already carries both; the role picks which block leads. |
| `public.society_detail` | Both | **The one page that genuinely belongs to both.** Archive view: history, awards, reviews, person awards, "also on record". Live view: next production, profile, socials, committee-login call to action, costumes and props. Each view ends with one link to the other: "Full history on the AIMS Archive" / "What's on now". |
| `public.show_detail` | Both, by date | A production whose `closing_date` (or `opening_date` if no closing) is before today is archive; otherwise live. The wrong host **redirects** (301) to the right one, so every existing link keeps working forever. |
| `public.venues_index`, `public.venue_detail` | Both | Archive: the directory and what has played there. Live: what is playing there next, map link, near-me. |
| `public.search` | Both | Scoped by role: the archive searches productions, awards, reviews, titles, societies; the live site searches upcoming shows and societies. |
| `public.about`, `public.faq` | Both | Role-specific copy. The FAQ table gains no column; filter published entries by a `site` value only if Darragh writes entries that differ (Phase 0 question). |
| `public.uploaded_file` | Shared | Posters and logos are read by both. |
| `feeds.robots_txt`, `feeds.sitemap_xml` | Shared, role-aware | Each host emits only its own routes (Phase 5). |

### Admin

Moderators log in on either host. The dashboard shows only the counters for that host's
queues. Any admin route that belongs to the other role redirects there, so a moderator who
bookmarked `/admin/historical-reviews` on the live site lands on the archive's.

| Group | Role | Routes |
|---|---|---|
| Archive data | Archive | `historical_reviews_*`, `historical_societies`, `historical_society_links_*`, `collapsed_societies_*`, `people_*`, `duplicate_titles_*`, `data_quality` + its two actions, `awards_*` (list, new, edit, delete, bulk), `adjudicators` + actions, `bulk_historical_productions`, `edit_show_info`/`clear_show_info`, `photo_submissions_*`, `backfill_credits` + apply, `historical_shows_title_check` + apply, `society_corrections` + apply, `venue_directory` + actions, `venues` + save |
| Live operations | Live | `queue` + approve/reject, `missing_posters`, `reviews_queue` + actions (review links for the current season), `invite_codes_*`, `access_requests_*`, `logo_candidates_*`, `set_show_link`/`clear_show_link`, `shows_list`, `edit_show`, `delete_show`, `add_show_review`/`remove_show_review`, `fix_dates`, `date_anomalies`, `bulk_credits`, `new_show`, `suggestions_*`, `changelog_*`, `faq_*`, `society_checklist` + save, `society_edits`, `traffic` |
| Societies | Both | `societies_list`, `new_society`, `edit_society`, `generate_society_code` - a moderator fixes a society's name from either side. |
| Account | Shared | `login`, `logout`, `reset_password`, `dashboard` |

### Tables

All 36 tables stay in the one database. For the record, who writes what:

- **Archive writes:** `historical_results`, `historical_reviews`, `historical_society_*`,
  `collapsed_society_*`, `people`, `person_aliases`, `dismissed_*`, `adjudicators`,
  `adjudicator_assignments`, `show_info`, `photo_submissions`, `venues`, `venue_aliases`,
  `show_links`, `society_field_checked`.
- **Live writes:** `shows` (submissions, committee edits), `invite_codes`,
  `society_access_requests`, `society_edit_log`, `feature_suggestions`, `changelog_entries`,
  `faq_entries`, `logo_candidates`, `wardrobe_*`.
- **Both write:** `societies`, `users`, `admin_password_resets`, `page_views`,
  `page_views_daily` (add a `site` column via `COLUMN_MIGRATIONS` so the two hosts' traffic is
  not summed under one path), and the derived `productions`/`venues` build-state tables.

## 4. Branding per role

- **Archive:** the AIMS brand kit, as mocked up on 2026-10-05
  (https://claude.ai/artifact/MEqEn1N6rUJYnfowXUeMRw): white and stone, charcoal text, deep
  red links, AIMS red for rules and marks only, gold for award wins only, light as the default.
  Name on the page: **"AIMS Archive"** (Darragh to confirm). The AIMS logo appears only once
  council has agreed - until then the archive uses the palette and the name, not the logo.
- **Live:** stays **ShowCal**, and takes the same quick fixes from that review (one name
  everywhere, no emoji icons, no install banner on desktop, no green buttons, section as a
  word not a dot). Whether it also adopts the kit is a Phase 0 question; nothing in the
  split depends on it.

Implementation: `base.html` already branches on `body.public-chrome`; add a `site_role`
template global and a `_brand.html` include per role rather than a second base template.
One stylesheet, with the role set as a class on `<html>` so the archive's tokens override.

## 5. Phases

Each phase ends with `py -m pytest` green and a commit. Phases 1-3 ship to the live site with
`SITE_ROLE` unset, so they are invisible until Phase 4 turns the roles on.

### Phase 0 - decisions (Darragh, not code)

1. The live site's eventual domain (stays `darraghc.ie/showcal` until decided).
2. Who adds the `archive.aims.ie` CNAME in the AIMS Cloudflare zone, and who owns the
   Cloudflare Tunnel's public-hostname entry.
3. Council agreement to the AIMS palette and name on the archive; the logo separately.
4. Whether the 2023/24-onwards aims.ie review links (the `reviews_queue` data) are listed on
   the archive's `/reviews` beside the ShowTimes reviews. Recommended: yes, as links.
5. Whether FAQ entries differ per site.

### Phase 1 - the role flag, with no visible change

- `SITE_ROLE` read in `create_app`, default `all`; exposed as `app.config["SITE_ROLE"]` and a
  `site_role` Jinja global.
- `app/site_roles.py`: the allowlist from §3 as a dict `endpoint -> {"archive","live","both",
  "shared"}`, plus `role_for_show(show_row, today)`.
- A `before_request` after `keep_derived_tables_current`: if the role is `all`, do nothing.
  Otherwise, if the endpoint is not allowed for this role, respond with a 301 to the same
  path on `OTHER_SITE_URL` for GET, and 404 for anything else. `show_detail` uses
  `role_for_show`.
- `cross_site_url(endpoint, **values)` Jinja global: `OTHER_SITE_URL + url_for(...)` with the
  other site's prefix stripped/added correctly (the live site has `/showcal`, the archive has
  none - build it from the `url_for` path, not from `request.url`).
- `tests/test_site_roles.py`:
  - every endpoint in `app.url_map` is classified, or the test fails naming it;
  - with `SITE_ROLE=archive`, `/` redirects to the live site and `/awards` renders;
  - with `SITE_ROLE=live`, `/awards` redirects and `/` renders;
  - a past show redirects from the live site and renders on the archive; an upcoming one the
    reverse;
  - `SITE_ROLE=all` renders both.
- Acceptance: all existing tests pass unchanged; the new test passes; production unchanged.

### Phase 2 - the archive face

- Archive home page (`archive.index`, a new blueprint or a branch in `public.index` keyed on
  role): what the archive is, search, the current season's productions on record, the latest
  reviews added, the award categories explorer that already exists on `/stats`, and a way in
  for historians (by society, by title, by decade, by adjudicator).
- Navigation and footer for the archive role: Awards, Reviews, Societies, Titles, Decades,
  Adjudicators, Venues, Submit history, About. No watchlist, no login pill except the
  moderator link in the footer, no install banner, no PWA.
- `society_detail` archive view (lead with history; a single "What's on now" link to the live
  site). `venue_detail` archive view likewise.
- `search` scoped to archive entities.
- The brand tokens from §4 under `html.role-archive`.
- Acceptance: a screenshot of the archive home, a society page and `/awards` at desktop and
  phone width, both themes, reviewed by Darragh before Phase 4.

### Phase 3 - the live face

- Navigation and footer trimmed to live concerns; one "AIMS Archive" entry that links across.
- `society_detail` live view (lead with next production and committee call to action; one
  "Full history on the AIMS Archive" link). `venue_detail` live view likewise.
- The ShowCal quick fixes from the 2026-10-05 review (listed in §4).
- `search` scoped to live entities.
- Acceptance: same screenshot review.

### Phase 4 - deploy

1. `docker-compose.yml`: add service `aims-archive`, same `build: .`, same `/data` volume,
   `environment`: `SITE_ROLE=archive`, `SITE_URL=https://archive.aims.ie`,
   `OTHER_SITE_URL=https://darraghc.ie/showcal`, no `URL_PREFIX`, same `SECRET_KEY` (sessions
   are per host anyway; one key keeps `stack.env` simple), same SMTP values, on `media-net`,
   same healthcheck. Add `SITE_ROLE=live` and `OTHER_SITE_URL=https://archive.aims.ie` to
   `aims-web`.
2. **Push order matters because GitOps deploys `main` on its own within five minutes.** Push
   the compose change with `aims-web` still on `SITE_ROLE=all` first; verify `aims-archive` is
   up (`docker ps`, `curl -H 'Host: archive.aims.ie' http://aims-archive:8000/awards` from
   inside the tunnel container); only then push the commit that sets `aims-web` to `live`.
3. Cloudflare Tunnel: add public hostname `archive.aims.ie` -> `http://aims-archive:8000` in the
   existing tunnel (it lives in the `cloudflared` container on `media-net`; the hostname entry
   is added in the Cloudflare dashboard, not in this repo). DNS: the CNAME for
   `archive.aims.ie` in the AIMS zone, pointing at the tunnel (Phase 0 item 2).
4. Verify against the deployed checkout (`md5sum` against Portainer stack 8's folder, per
   `CLAUDE.md`), then `curl -I https://archive.aims.ie/awards` and
   `curl -I https://darraghc.ie/showcal/awards` (expect 301 to the archive).
5. Read both containers' startup logs once for the productions/venues rebuild - see §2.
6. `CLAUDE.md`: add the second container to the deployment section (`docker exec aims-archive`
   works for any script, since both see the same `/data/aims.db`).

### Phase 5 - content and search engines

- `sitemap.xml` per role; `robots.txt` unchanged.
- Open Graph tags use each host's `SITE_URL` (already the case via `absolute_url`).
- A redirect map is not needed beyond the role redirects in Phase 1, because every path keeps
  its meaning on the other host.
- `CHANGELOG.md` entry; the roadmap page is live-only, so the archive's footer links to it.
- Analytics: the `site` column from §3.

### Phase 6 - later, separate decisions

- A read-only JSON API on the live site for upcoming productions and societies, for the
  organisation site to consume. Not part of the split.
- Importing the 2023/24-onwards aims.ie review texts into `historical_reviews` (today they are
  links). Depends on Phase 0 item 4 and on an agreed source.

## 6. Things that will bite if ignored

- **The working tree is CRLF.** Search-and-replace with LF patterns silently matches nothing.
- **`URL_PREFIX` differs per container.** Never build a cross-site link from `request.url`;
  build it from `url_for` plus `OTHER_SITE_URL`.
- **Emails.** `notify.py` builds links from `SITE_URL`. Magic-link and access-request emails
  are sent by live routes, so they will carry the live host. Submission-notification emails
  likewise. Nothing on the archive sends mail except photo submissions - check that one.
- **The rate limiter is in-memory per process.** Two containers means two buckets. Fine.
- **The PWA.** The service worker's scope is the whole site; the archive must serve the
  unregistering `sw.js` (§3) or an installed ShowCal will cache archive pages under the wrong
  identity.
- **Hidden societies** (`societies.hidden`) 404 on both hosts for the public; keep that.
- **Do not fuzzy-match titles**, do not add a licence file, do not write to `aims.db` outside
  the container scripts. All three are standing rules in `CLAUDE.md`.
- **Tests:** 1,303 green as of 2026-10-05. Every phase adds to that number, never subtracts.

## 7. What the executing agent reports back

A `HANDBACK.md` entry per phase, as `CLAUDE.md` rule 6 describes: commits, what was verified
against production, what was written to the live database (expected: nothing except the
`site` column migration), what needs Darragh, and the screenshots for Phases 2 and 3 as
artifact links.
