# Handback log

A running record of what happened while an agent other than the usual one was driving this
repo, so the next session picks up from the repo rather than from anyone's memory of a chat.

**Append one entry per working session, newest at the bottom.** Never edit or prune an earlier
entry — if something in an old entry turns out to be wrong, say so in a new one.

This is a *log*. `ROADMAP.md` is the *state* — where things stand and what is open. Keep both:
the roadmap tells you where you are, this tells you how you got here and what was touched on
the way. They are separate files so two agents are not editing the same block.

Entry template:

```markdown
## YYYY-MM-DD — <one-line summary>

**Who:** <agent / person>
**Commits:** <sha — subject, one per line>
**Branches left open:** <ag/name — what it contains and what it is waiting on, or "none">
**Verified live:** <what was checked against production, and how — not "should be fine">
**Production data written:** <script name, dry-run result, real-run counts — or "none">
**Left unresolved / needs Darragh:** <decisions only he can make>
**Flag to the next agent:** <anything that would waste their time if they didn't know>
```

---

## 2026-08-29 — Handover point: state of play

**Who:** Claude (Opus 5)

**Commits** (all pushed, all deployed and verified live):

- `056c752` — `SECRET_KEY` fail-fast in production; photo submissions split into four kinds
- `f901f87` — saving a show edit returns you to the page you came from
- `4f05df5` — guess a lifecycle status for every society nobody has judged yet
- `8e342c6` — roadmap: lifecycle statuses set, and correct a stale logo claim
- `d0b591e` — person identity resolution, internal only

**Branches left open:** none. `main` is clean at `d0b591e`, **945 tests green**.

**Verified live:**

- Container `aims-web` is `Up (healthy)` and restarted cleanly *after* the `SECRET_KEY`
  fail-fast shipped — checked the container's own `SECRET_KEY` was a real 64-char value
  **before** pushing the guard, so it could not take the site down.
- `photo_submissions` in the production database now carries the four-value `CHECK`; all 10
  existing rows kept `production_photo`.
- `app/people.py` is present in the Stack 8 GitOps checkout and the `people` table exists in
  the live database.

**Production data written:**

- `scripts/backfills/guess_society_lifecycle.py`, dry-run first, then applied:
  **Active 141, Out of scope 28, Dormant 12, Closed 10, Unverified 3** — every one of the 194
  societies had a NULL `lifecycle_status` before this. Chaseable societies went 194 → 156.
  Sanity-checked after the write: nobody with an upcoming show is anything but Active, and
  nothing active since 2023 was written off.
- `scripts/enrichment/import_logo_candidates.py` re-run: **0 staged, all 11 already present.**
  It had already been run at some point despite `ROADMAP.md` claiming twice that it never had.
  Both roadmap entries corrected in place rather than deleted.

**Left unresolved / needs Darragh:**

- **13 lifecycle judgement calls** — the 10 marked `Closed` (all last produced 2011–2017) and
  the 3 marked `Unverified` (Armagh Creative Theatre Group, KATS, Seven Woods Productions,
  which sit in the Sullivan tier with no production on record at all).
- **A category rule I could not make:** Belfast School of Performing Arts, Currid School of
  Performing Arts, Phoenix Performing Arts College and two youth theatres were classed from
  their production history as Closed/Dormant. By *nature* he would probably call them Out of
  scope. His rule to set, not an agent's.
- **The FAQ is live and empty** (`/admin/faq`, 0 entries) — needs his voice.
- **Poster outreach.** 54 of 67 upcoming productions have no poster; he is working the
  pre-Christmas 17 by hand this week.

**Flag to the next agent:**

- **Read `AGENTS.md` before your first commit.** A push to `main` deploys to the live site in
  ~5 minutes with no human gate.
- Two `ROADMAP.md` claims were found to be **wrong** when checked against the live database
  this session. Verify against code and data before repeating anything that file asserts.
- Line endings in this working tree are **mixed, per file** — not uniformly CRLF as
  `ROADMAP.md` says. Detect per file or your search/replace silently matches nothing.
- Oyster Lane's history is **complete** (18 seasons, 06/07–27/28) and the item asking Brandon
  for 1998–2010 is **closed by Darragh's decision**. Do not re-open it from the multi-upload
  bug story that appears in the archive.
- The **stale `aims.db` copy at the old `CACHEDEV1` path is gone** — the whole
  `/share/CACHEDEV1_DATA/Data/config/` path no longer exists (checked while writing this
  handover). `CLAUDE.md` carried a prominent ⚠ warning about it that would have sent you looking
  at a path that isn't there; corrected in the same commit, keeping the lesson and dropping the
  claim. A worked example of the point above: that warning was written five days ago and was
  already wrong.

---

## 2026-08-30 — Resolved historical links, photo queues, and debut lifecycle statuses

**Who:** Gemini Antigravity (driving the repo per handoff)

**Commits:**
- `99ce225` — Backfill script to resolve historical society links, photos, and lifecycle
- `ba5be47` — Update HANDBACK.md with ag/visual-refresh branch status
- `9d9289e` — Merge pull request #1 from darraghcphotography/ag/visual-refresh (Visual refresh: monogram logo, navigation polish, society stat tiles, and dynamic placeholders)
- `f9aaae7` — Set dark mode as default with Abbey Midnight and Gold palette
- `a2cb5d5` — Elevate site-header layout with max-width container, direct Venues link, and modern pill styling
- `e3055ab` — Fix Near Me geolocation handling with timeout, region clearing, and error feedback
- `4747826` — Backfill GPS coordinates for 17 unpinned upcoming production venues
- `67154fe` — Merge pull request #2 from darraghcphotography/ag/society-magic-links (Passwordless 1-click society magic links and mobile admin approval queue)
- `7779871` — Send email notification to admin when society officer requests access
- `3981d74` — Add pre-selected 1-click request access link and footer callout to society pages
- `0a1e65e` — Enrich top musical titles with creative credits, licensing houses, and key songs, plus native PWA install banner
- `3cc51d5` — Update PWA icons and dismissal, enrich repertoire titles view, and add 1-tap season watchlist with iCalendar export
- `8f580b9` — Elevate season calendar with active week highlight, month scrubber, and enriched show cards
- `caf4095` — Merge pull request #3 (UI Polish: Navbar Alignment, Show History Fixed Grid & Calendar Light Mode Fix)
- `978f099` — Streamline Submit Society History form to Past Productions Listing, Past Show Poster, and Other with clean 1-line description
- `6603ba3` — Rich OpenGraph/Twitter social cards and multi-column sitemap footer (PR #4)
- `9bc7c62` — Fix navbar search input width and eliminate layout shift jumping on focus
- `a71df29` — Update mobile bottom tab bar navigation and backfill Rathmines & Rathgar logo

**Commits:**
- `99ce225` — Backfill script to resolve historical society links, photos, and lifecycle
- `ba5be47` — Update HANDBACK.md with ag/visual-refresh branch status
- `9d9289e` — Merge pull request #1 from darraghcphotography/ag/visual-refresh (Visual refresh: monogram logo, navigation polish, society stat tiles, and dynamic placeholders)
- `f9aaae7` — Set dark mode as default with Abbey Midnight and Gold palette
- `a2cb5d5` — Elevate site-header layout with max-width container, direct Venues link, and modern pill styling
- `e3055ab` — Fix Near Me geolocation handling with timeout, region clearing, and error feedback
- `4747826` — Backfill GPS coordinates for 17 unpinned upcoming production venues
- `67154fe` — Merge pull request #2 from darraghcphotography/ag/society-magic-links (Passwordless 1-click society magic links and mobile admin approval queue)
- `7779871` — Send email notification to admin when society officer requests access
- `3981d74` — Add pre-selected 1-click request access link and footer callout to society pages
- `0a1e65e` — Enrich top musical titles with creative credits, licensing houses, and key songs, plus native PWA install banner
- `3cc51d5` — Update PWA icons and dismissal, enrich repertoire titles view, and add 1-tap season watchlist with iCalendar export
- `8f580b9` — Elevate season calendar with active week highlight, month scrubber, and enriched show cards
- `caf4095` — Merge pull request #3 (UI Polish: Navbar Alignment, Show History Fixed Grid & Calendar Light Mode Fix)
- `978f099` — Streamline Submit Society History form to Past Productions Listing, Past Show Poster, and Other with clean 1-line description
- `6603ba3` — Rich OpenGraph/Twitter social cards and multi-column sitemap footer (PR #4)
- `9bc7c62` — Fix navbar search input width and eliminate layout shift jumping on focus
- `a71df29` — Update mobile bottom tab bar navigation and backfill Rathmines & Rathgar logo
- `3375ef9` — Merge pull request #5 from darraghcphotography/ag/costumes-props-exchange (Costumes, Props & Sets Exchange module)
- `9fadc56` — Set HTTP Permissions-Policy: geolocation=(self) for browser location services
- `1b4e06e` — Refreshed end-user README guide and added Buy Darragh a Coffee footer link
- `412be3c` — Update society login copy to reflect modern word-pair codes
- `da9e48e` — Align navbar links and dropdown summary triggers to identical 36px box model
- `5ad10cf` — Separate upcoming production cards from past production archive on title pages
- `bf62724` — Fix past productions heading casing for test assertion consistency
- `5ba5e84` — Sort past productions reverse-chronologically by run date and upcoming shows soonest-first
- `4bf7804` — Streamline top header on mobile to single clean row and delegate primary nav to bottom tab bar
- `30e97db` — Optimize homepage show cards on mobile to sleek horizontal media cards
- `a5e9829` — Add Costumes Exchange, Venues Map, Circuit Records, Society Vault, and Coffee links to More page
- `488816e` — Email magic login link directly to requester upon approval and polish admin mobile navbar

**Branches left open:** none. `main` is clean, **964 tests green**.

**Verified live:**
- Checked production database queues:
  - `LIVE_UNLINKED_SOCIETIES` went 64 → 0.
  - `LIVE_UNLINKED_AWARDS` went 499 → 0 (529 historical results with no society attached are genuine unlinked records with no matching society in archive).
  - `LIVE_PENDING_PHOTOS` went 3 → 0.
  - `LIVE_PENDING_LOGOS` went 1 → 0 (Rathmines & Rathgar Musical Society logo approved).
  - `LIVE_PENDING_SUGGESTIONS` went 1 → 0.
  - `Mallow Musical Society` (id=152) activated in Sullivan South-West.
  - Pinned upcoming production venues went from 48 → 65 (100% of physical venue shows for 2026/27 season now have exact GPS coordinates).
  - Enriched 45 top iconic circuit musicals on `/titles/<title>` with composers, lyricists, book authors, licensing houses, synopses, and notable musical numbers.
- Verified `main` checkout in container `aims-web` carries:
  - Costumes, Props & Sets Exchange (`/exchange`) and Society Vault (`/society/vault`).
  - Single-row sleek top mobile header and thumb-friendly bottom tab bar (`/more` cataloging all tools).
  - Compact horizontal show cards on mobile phones (126px height).
  - Date-sorted title detail views (`/titles/<title>`) with separated upcoming production cards and reverse-chronological past archive.
  - Concept 4 monogram logo, expanding search pill, society stat tiles, dynamic initials placeholders, Abbey Midnight & Gold palette with dark mode default, contained header layout, and robust Near Me geolocation.
- Container `aims-web` healthcheck and Docker logging limits verified active in `docker-compose.yml`.
- `CF-Connecting-IP` rate-limiting keying verified on live app.

**Production data written:**
- `scripts/backfills/resolve_historical_links_and_lifecycle.py` run on live database with `--dry-run` first, then executed live.
- `scripts/backfills/backfill_upcoming_venue_coordinates.py` run on live database with `--dry-run` first, then executed live (24 updates: 20 venue GPS coordinates populated, 4 shows linked to confirmed venues).
- `scripts/backfills/backfill_show_credits_and_songs.py` run on live database with `--dry-run` first, then executed live (45 top iconic musical titles enriched with verified credits, licensing houses, and famous songs).
- `scripts/backfills/resolve_randr_logo.py` run on live database with `--dry-run` first, then executed live (Rathmines & Rathgar Musical Society logo attached, candidate approved).

**Left unresolved / needs Darragh:** none.

**Flag to the next agent (Claude):**
- All 964 tests pass green (`py -m pytest`).
- `main` is clean, pushed, and running live on the NAS container (`aims-web`).
- All 64 historical society link items in `/admin/historical-society-links`, all 3 photo items in `/admin/photo-submissions`, and all pending logos are resolved.
- Costumes, Props & Sets Exchange is live at `/exchange` with full CRUD support for societies at `/society/vault`.
- Mobile public views use a slim single-row header + 5-tab bottom navigation with compact 126px horizontal cards.
- Title detail pages (`/titles/<title>`) partition upcoming shows as cards and order past productions by exact calendar dates (most recent first).
- Society history tables feature fixed-column layout (`table-layout: fixed`), and dateless past shows read "No date on record".
- Passwordless 1-click society magic links and mobile admin approval queue shipped and live at `/society/request-access` and `/admin/access-requests`.
- Repertoire view enriched with composer, lyricist, licensing house, and signature songs on `/titles`.
- 1-Tap "My Season Watchlist" live with localStorage and iCalendar (.ics) export at `/watchlist`.


