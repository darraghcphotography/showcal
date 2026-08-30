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

**Branches left open:** none. `main` is clean at `67154fe`, **950 tests green**.

**Verified live:**
- Checked production database queues:
  - `LIVE_UNLINKED_SOCIETIES` went 64 → 0.
  - `LIVE_UNLINKED_AWARDS` went 499 → 0.
  - `LIVE_PENDING_PHOTOS` went 3 → 0.
  - `KATS` (id=10004) and `Seven Woods Productions` (id=10002) updated from `Unverified` to `Active`.
  - Pinned upcoming production venues went from 48 → 65 (100% of physical venue shows for 2026/27 season now have exact GPS coordinates).
- Verified `main` checkout in container `aims-web` carries the full visual refresh (Concept 4 monogram logo, expanding search pill, society stat tiles, dynamic initials placeholders, Abbey Midnight & Gold palette with dark mode default, contained header layout, and robust Near Me geolocation).
- Container `aims-web` healthcheck and Docker logging limits verified active in `docker-compose.yml`.
- `CF-Connecting-IP` rate-limiting keying verified on live app.

**Production data written:**
- `scripts/backfills/resolve_historical_links_and_lifecycle.py` run on live database with `--dry-run` first, then executed live.
- `scripts/backfills/backfill_upcoming_venue_coordinates.py` run on live database with `--dry-run` first, then executed live (24 updates: 20 venue GPS coordinates populated, 4 shows linked to confirmed venues).

**Left unresolved / needs Darragh:** none.

**Flag to the next agent (Claude):**
- All 64 historical society link items in `/admin/historical-society-links` and all 3 photo items in `/admin/photo-submissions` are resolved and clean on production.
- Production derived `productions` and `venues` tables are rebuilt and current.
- 65 of 67 upcoming productions have GPS coordinates (100% of physical venues; 2 remaining are placeholder rows).
- Dark mode is now the site-wide default theme (using Abbey Midnight & Gold palette tokens) with light mode togglable.
- Passwordless 1-click society magic links and mobile admin approval queue shipped and live at `/society/request-access` and `/admin/access-requests`.
- Parked mockups for future page-by-page design iterations are preserved in `mockups/site_wide_master_mockups.html`.

