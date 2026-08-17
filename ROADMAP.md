# Roadmap

Tracks the current phase of work so a new session (after `/clear` or a fresh
start) can pick up where the last one left off without re-deriving context.
Update this file - don't just say the plan out loud in chat - whenever the
phase changes.

## Phase 0 - Incident response & hardening (done, 2026-08-03)
- Recovered from the broken `/data` mount that wiped the database (absolute
  volume path fix, `aims-backup` sidecar, HBS3 off-NAS backup, startup guard).
- Security/stability audit: response headers, rate limiting, DB index,
  confirmed no dead code / SQL injection / auth gaps.
- UX polish: favicon/manifest/404, responsive tables on mobile, compact
  dates, venue+Maps links, trophy case runner-up/third place.

## Phase 1 - Test suite (done, 2026-08-03)
Added a `pytest` suite in `tests/` (19 tests, `py -m pytest` from repo root -
`requirements-dev.txt` adds `pytest` on top of `requirements.txt`):
- Auth gates (`login_required`/`admin_required`/`society_required`/
  `invite_required`) actually block unauthenticated and under-privileged
  access - `tests/test_auth_gates.py`.
- `import_csv.py` / `export_csv.py` round-trip, plus the re-import-never-
  regresses-a-moderator-set-review rule - `tests/test_import_export_roundtrip.py`.
- The 27/28 unconfirmed-tier blanking rule in `import_csv.py` -
  `tests/test_import_unconfirmed_tier.py`.
- The trophy-case query (win/runner-up/third-place counts) -
  `tests/test_trophy_case.py`.
- The startup guard (missing-db warning) and the mount-path (`AIMS_DB_PATH`)
  assumption - `tests/test_startup_guard.py`.
Sanity-checked by temporarily disabling the admin-role check and confirming
`test_admin_required_blocks_non_admin` actually fails - the suite catches
real regressions, not just passing by construction.

## Phase 1.5 - Feature/UX polish (done, 2026-08-03)
A long session of smaller, mostly independent asks rather than a single
sweep - each planned/tested/shipped separately:
- **Society pages**: a "Future announced show" block split out of the main
  history table (and a follow-up fix - it was invisible on desktop, wrapped
  in a mobile-only CSS class); "Tier" renamed to "Section" everywhere
  Gilbert/Sullivan is shown (display text only, no column/data renamed).
- **Invite codes**: switched from random `AIMS-XXXXXX` codes to two
  dictionary words (e.g. `silver-otter`), case-insensitive login; a
  suggested-code prefill + "Suggest another" on `/admin/invite-codes`;
  delete + bulk-cleanup of the old `AIMS-` codes; a "generate/reveal this
  society's login code" panel right on the society's own public page
  (admin-only) - faster than the general invite-codes page for handing a
  code out on request.
- **Email notifications**: a new show submission or feature suggestion now
  emails a fixed inbox in real time (`app/notify.py`, stdlib SMTP, inert
  until `SMTP_USER`/`SMTP_PASSWORD` are set - see docs/deployment.md).
- **Homepage poster gallery**: now derived directly from the "Upcoming
  shows" list (same shows, same region filter, soonest first) instead of a
  separate query - a past show's poster no longer lingers there once
  there aren't enough upcoming posters to fill the row.
- **Society profile**: a society can now add an "about/get involved" blurb
  plus Website/Facebook/Instagram/TikTok/Other links from their own
  self-service login, shown on their public page. Every URL is validated
  to start with `http(s)://` before saving (it lands in a public `<a
  href>`, so a `javascript:`/`data:` URL is rejected outright, not just
  escaped).
- Test suite grew from 19 to 40 tests across this work; all pushed and
  live via Portainer "Pull and redeploy".

Parked, not started: a dedicated historical-posters browse page (scroll
through every poster ever uploaded, not just upcoming ones) - flagged as
"a big effort," worth its own planning pass when picked up.

## Live user feedback backlog (Rounds 1-3 done, 2026-08-04)
The site is live and has real (anonymous) users submitting shows and
feature requests - Phase 3's planned "fresh session + LAUNCH.md spec" never
formally happened, it just launched organically. Worth circling back to
that conversation at some point (onboarding all ~150 societies rather than
word-of-mouth, edge cases, what "done" means), but Rounds 1-3 below - a
running backlog triaged from a batch of anonymous feature requests Darragh
collected - are done, tested (40 -> 59 tests), and pushed.

**Round 1 - quick wins:**
- "Current season" nav/page renamed (later renamed again to "Season
  Archive" as part of Round 3's nav rework).
- Bulk-add-shows form gets venue + production team columns.
- Copy-ready login-code message on the society-page code panel.
- Fix: submitting a show via the public form when a blank "TBA" placeholder
  already exists for that society+season now replaces it instead of
  inserting a duplicate row.

**Round 2 - suggestions system rebuild:**
- `feature_suggestions` gets a submitter-chosen `category` (Idea/Feature,
  Bug report, Data error - picked on the public form, not admin-assigned)
  and a moderator-set `triage_status` (New -> Planned -> In Progress ->
  Done/Not planned), plus an optional `contact` field.
- New public `/suggestions` "Roadmap" page: triaged suggestions (so a
  duplicate idea can be spotted before resubmitting) plus a changelog fed
  by a small new `/admin/changelog` editor.

**Round 3 - nav rework + homepage split:**
Turned out simpler than originally scoped once Darragh weighed in on real
usage (Upcoming/Societies/Awards/Stats are what people actually use; Shows
A-Z is the least-used page) and pushed back on the first mockup (wanted to
*keep* the poster gallery + Upcoming Shows content on the homepage, not
shrink it to a teaser):
- Site rebranded "Unofficial AIMS Show Tracker" -> "DC Show Tracker"
  everywhere (title tags, nav, footer, PWA manifest, calendar feed) - the
  About page's "not an official AIMS site" disclaimer is unchanged.
- "Browse societies" moved out to its own `/societies` page; the homepage
  keeps poster gallery + Upcoming Shows exactly as before, plus a
  "Recently shipped" changelog teaser.
- Nav: `Upcoming shows / Societies / Awards / Statistics / Season Archive`
  up front; `Shows A-Z / Suggest a feature / Roadmap / Moderator login`
  moved to the footer.
- "Submit a show" removed as a standalone nav/homepage destination per
  Darragh's call - it only shows once a society is logged in, pointing at
  their own live add-show page. The old one-off/moderation-queue form
  still works, just isn't advertised anywhere - reachable only via a
  direct link Darragh shares.
- Follow-up review fixes: every "AIMS's" reworded to plain "AIMS" across
  user-facing pages/docs; suggest-a-feature form field order changed to
  Name/Contact/Type/Your idea.

**Round 4 - suggestions cleanup + changelog timestamps (2026-08-04):**
Raised in chat right after the Round 3 push, from Darragh spotting an
accidentally-double-submitted suggestion live:
- `/admin/suggestions` gets a Delete button per card (with confirm).
- Done/Not planned suggestions collapse behind a "Show N archived
  suggestions" disclosure instead of piling up in the main list forever -
  same pattern as the stats page's earlier-seasons collapse. They're not
  deleted, still feed the public Roadmap's "Recently shipped".
- Changelog entries on the public Roadmap page now show a full
  date + time (`irish_datetime` filter) instead of just a date.
- Test suite grew 69 -> 73. Committed as `c8f7b81` in a session that got
  interrupted by an accidental `/clear` right before the commit - recovered
  by reading the prior session's `.jsonl` transcript out of
  `~/.claude/projects/`, since `/clear` doesn't delete history from disk.

**Round 5 - Roadmap page redesign + About page rewrite (2026-08-04):**
Mockup-first: 3 layout variants (kanban columns, striped list, colour-headed
lanes) built as a published Artifact reusing `style.css`'s real tokens and
sample data, reviewed before touching any template - Darragh picked lanes,
then asked for a Done lane and category colour-coding, which got folded
into the same mockup and re-reviewed before implementing for real.
- `/suggestions` Roadmap page: Planned / In Progress / Done / Not planned
  status lanes replace the old flat list - colour reuses the existing
  tag-gold/tag-active/tag-cancelled language, just extended from a pill to
  the whole lane. A small dot per category (bug/data/feature) sits
  alongside so it doesn't compete with the lane colour.
- Suggestions now get their own **Done lane** so someone can see their own
  idea actually ship, instead of only checking "Recently shipped" (which
  drops back to the manual/curated changelog only now, since a Done
  suggestion would otherwise be listed twice).
- About page rewritten in Darragh's own voice (AIMS Council/spreadsheet
  backstory, "how you can help") - the "not an official AIMS website"
  disclaimer is unchanged.
- Test suite grew 73 -> 76. Pushed as `536f024` (About) and `4eb1925`
  (Roadmap lanes).

**Round 5 follow-up - multi-line changelog + deploy timestamp (2026-08-04):**
Requested while reviewing the live audit - "Recently shipped" entries were
capped at one terse line, not enough room for a real release summary:
- A changelog entry can now be multiple lines - each line renders as its
  own bullet under the date, instead of being squeezed onto one line.
- The Roadmap page shows "Latest version deployed: &lt;timestamp&gt;" above
  the list, sourced from when the app process started (a Portainer redeploy
  restarts the container, so process-start time is an accurate deploy time
  without tracking deploys separately).
- Test suite grew 76 -> 78. Pushed as `128daeb`.

**Process note:** started Round 1 straight from the approved backlog
without a preview - Darragh expected a look-before-it-ships step even for
"obviously small" changes, not just big redesigns. Fixed by spinning up a
disposable local preview server (`create_app()` pointed at a scratch DB,
never touches `aims.db`) for every round after that. See
[[workflow-habits]] for the fuller lesson - treat anything touching layout
or UI elements like a big redesign, not just literal text edits.

**Round 6 - Stats page: award category leaderboard picker (2026-08-05):**
Mockup-first again, two rounds of it: a first pass (variant B grid, every
category as its own mini-card, grouped Societies/Production team/Cast) got
"that's a lot to display at once" - reworked into a second mockup (single
picker: award-category dropdown + Gilbert/Sullivan tier toggle, one
leaderboard updates) that got "love." straight off:
- Replaced the old fixed "Most 'Best Overall Show' wins" card on `/stats`
  with an interactive picker - a dropdown (grouped Show / Production team /
  Cast, matching the mockup's taxonomy) plus a Gilbert/Sullivan tier select,
  GET-param driven like the page's existing region filter (`award_category`/
  `award_tier`), not JS - a specific combination is a shareable/bookmarkable
  URL. Threads through the page's existing region filter too, no new control
  needed for that dimension.
- Covers all 33 real `historical_results.category_name` values (verified by
  a direct DB-vs-constant diff, not just eyeballed) via a new
  `AWARD_CATEGORIES` list in `app/constants.py`, each tagged `person: True`
  (leaderboard groups by `nominee_name` - Director, Musical Director,
  Choreography, Stage Management, Chorus Master/Mistress, every on-stage
  award) or `person: False` (groups by `society_name`) - classified from
  actual data, not the column name: `Best Technical`/`Visual`/`Programme`/
  `House Management` all store a *society* name in `nominee_name` despite
  the column. "Best Choreography" and "Best Choreographer" turned out to be
  the same award under two historical names, both still in use as late as
  2025 rather than a clean rename - merged into one picker entry.
- Fixes the original complaint (Wexford Light Opera topping every "most X"
  card) not by hiding the real numbers but by only showing one category at a
  time - e.g. Best Technical is led by Carrick-on-Suir, Best Programme by
  Tullamore, Best House Management by Shannon; Best Overall Show splits
  sharply by tier too (Wexford leads Gilbert, but Sullivan's list is 9
  different one-off winning societies).
- Test suite grew 78 -> 83 (default-category rendering, person-vs-society
  grouping, tier filtering, the Choreography/Choreographer merge, and
  invalid-param fallback).
- Two published mockups this round: the grid-of-cards first pass
  (`stats-redesign-v2`) and the picker that shipped (`stats-redesign-v3`).

**Round 6 follow-up - full card-based redesign (2026-08-05):**
Shipped, then immediately corrected on two counts once Darragh actually saw
it live: the picker used the site's existing bar-chart component (a choice
made without flagging it, not what the v3 mockup showed), and it was
visually buried two-thirds down the page under "Awards." A same-night
follow-up mockup (`stats-redesign-v4`) fixed both and got "i like it - lets
keep going," then was built out to cover the *entire* page, not just the
Award Explorer:
- **Every leaderboard now uses numbered gold/silver/bronze rank badges**
  (competition-style - a tie shares a rank, e.g. Sister Act and The Addams
  Family both rank #1 in "Most selected shows") instead of the old red
  bar-fills. New `rank_list`/`rank_list_pct` macros in `stats.html`, new
  `.rank-list`/`.rank-row`/`.rank-badge`/`.lb-card`/`.lb-grid`/`.chip-strip`/
  `.explorer` component CSS in `style.css` - the old `.bar-list`/`.bar-row`/
  `.bar-track`/`.bar-fill`/`.bar-count` rules were removed outright (grepped
  first to confirm nothing else on the site used them).
- **Award Explorer moved from a buried h3 to a prominent tinted hero card**
  right under the overview stat tiles - first thing under the page title
  besides the region filter.
- Non-competitive breakdowns (shows by region, by section, award wins by
  region) became compact chip strips, not ranked - deliberately no rank
  badges there, since nobody's "#1" at being the Eastern region.
- Every remaining "most X" list (most performed, most selected x2, most
  prolific societies, most award wins, most nominated never won, win-rate)
  consolidated into one `.lb-grid` card grid; signature show, one-offs, and
  "did you know" wrapped in matching cards too - "fully card based," per
  Darragh's ask, not just the Award Explorer.
- Test suite unaffected in count (83) but two assertions updated for the
  new markup (`bar-count` -> `rank-n`, `(by society)`/`(by person)` ->
  `By society`/`By person` inside a `.kind-tag` pill).
- **Lesson**: flag any visual deviation from an approved mockup before
  shipping, even a "matches existing site conventions" one - see
  [[workflow-habits]].

**Round 7 - Awards page polish + a real data-safety gap found (2026-08-05):**
Raised while reviewing the 2026-08-05 site review doc below - two quick Awards-page requests
plus a real fix that fell out of the "how do I safely update/export enriched data" question:
- `/awards` gets pagination (50/100 per page, selectable) - was rendering ~1,500+ rows in one
  page with the default Winner filter.
- Nominee column now hidden for society-level categories (Best Technical/Programme/House
  Management/Visual/etc.) - `nominee_name` on those rows was always just a duplicate of the
  Society column, not a real individual. Reuses the same `person`/society classification
  built for the Award Explorer (`AWARD_CATEGORIES` in `constants.py`), now also exposed as
  `SOCIETY_AWARD_CATEGORY_NAMES`.
- **Real gap found and fixed**: `import_csv.py`'s re-import guard only ever protected
  `review_status`/`review_url` from being blanked out by a stale spreadsheet - `venue`,
  `director`, `musical_director`, and `choreographer` had no such protection and were
  unconditionally overwritten on every re-import. Anyone manually filling one of these in
  directly in the app (not yet reflected in the tracked CSV) was one re-import away from
  losing it silently. Now uses the same "blank spreadsheet value never overwrites a real db
  value, but a real spreadsheet value still wins" guard as review_status/review_url. `CLAUDE.md`
  updated to reflect the wider guarantee.
- Test suite grew 83 -> 88 (Awards pagination x2, hide-nominee x2, the new import guard).

**Round 8 - venue backfill tool + self-publishing changelog (2026-08-05):**
Two more from the same evening - a real admin tool built from an approved mockup, and a fix for
"don't rely on me to write the changelog manually":
- **New `/admin/venues`**: a per-region grid of all 127 active societies with a venue field each,
  for backfilling `societies.default_venue` (0/179 filled prior to this - see the site review).
  Autosave-per-field on blur (first `fetch()`-based JS in the codebase - everything else is plain
  forms) rather than one big submit, per the approved mockup's own reasoning: safer for a ~130-row
  form than losing an hour of typing to one failed request. A sticky progress bar tracks how many
  are filled. New `{% block scripts %}` added to `base.html` so a template can opt into a
  page-specific `<script>` without every page getting one.
- Dashboard's "Needs attention" table gets a matching row (`missing_venue_count`) alongside the
  existing pending-submissions/needs-review/etc counts.
- **Changelog entries now publish themselves.** `CHANGELOG.md` (git-tracked, `---`-separated
  entries) is synced into `changelog_entries` once on every app startup via
  `app/changelog_sync.py` - write an entry into the file, commit, redeploy, done. A new
  `changelog_synced_entries` table remembers what's already been published so a manually-deleted
  entry never gets resurrected by the next restart just because the text is still in the file.
  `add_changelog.py` (a one-command CLI publish, added earlier this session) stays as the escape
  hatch for a one-off entry outside the normal commit/redeploy flow.
- Test suite grew 88 -> 104 (venues page + save endpoint x6, changelog_sync parsing/idempotency/
  no-resurrection x7).

**Round 9 - hide-a-society, adjudication form copy, CSV refresh closed out (2026-08-05):**
- **`societies.hidden`** (new column, moderator-only toggle on `/admin/societies/<id>/edit`) -
  for a society that's asked not to be publicly associated with AIMS. Scoped via two explicit
  questions rather than assumed: 404s their own public page and drops them from `/societies`
  (same logged-in-only reveal pattern as `Inactive`), but deliberately does **not** touch
  historical stats/Awards/Season Archive - those stay accurate history, not rewritten. Kept as a
  separate flag from `section = 'Inactive'` on purpose - "not currently competing" and "asked not
  to be mentioned" are different real-world reasons and conflating them would make Inactive mean
  two things. Their own self-service login is unaffected either way.
- Public submission form's adjudication question reworded to Darragh's exact phrasing ("Do you
  plan on getting this show adjudicated?") with the 6-week-rule disclaimer added underneath -
  the underlying yes/no field already existed, this was copy only.
- **Phase 2's CSV export item finally closed out**: Darragh pulled the freshly-exported
  `societies.csv`/`shows.csv` off the NAS and replaced the git-tracked copies (241
  insertions/238 deletions - real accumulated corrections, not just North Wexford's tier).
- Test suite grew 104 -> 111 (hidden-society visibility x7).

**Round 10 - live production crash fix, 179 vs 127 copy, awards CSV export (2026-08-05):**
- **Fixed a real production 500** Darragh hit live while resolving duplicate titles
  (`/admin/duplicate-titles/bulk`): `shows` has a UNIQUE index on `(society_id, season, show)`,
  and merging two titles did a blind `UPDATE ... WHERE show = ?` - if one specific society had
  already logged *both* the canonical and duplicate title for the same season (exactly the
  situation this tool exists to fix), the rename collided with that constraint and crashed. Worse,
  since the whole bulk form commits as one transaction, a single colliding pair took down every
  other pair in the same batch, not just itself. Fixed by moving `shows` rows one at a time -
  where renaming would collide, the row is a redundant duplicate of what's already there, so it's
  deleted instead of updated; where it wouldn't collide, renames normally. Same `_merge_titles()`
  helper backs both the single-merge and bulk-merge routes, so one fix covers both.
- **"179 vs 127" copy fix** - `/about` now says "179 societies... (127 currently active - the
  rest are kept for historical record)" instead of a bare total that reads as a mismatch once you
  click through to `/societies`. The active count reuses the exact same filter as `/societies`'
  default view (`section != 'Inactive' AND NOT hidden`).
- **`export_awards.py`** - `historical_results`'s inverse-of-`import_awards.py` export, same
  pattern as `export_csv.py`. Unlike that script, exports every row regardless of
  `source='import'`/`'manual'` - editing an existing award record in `/admin/awards` sets its
  source to `'manual'` too (not just brand-new additions), so filtering to `'import'` would drop
  exactly the corrections this exists to capture. Verified with a full export -> re-import round
  trip through the real `import_awards.py` CLI, not just a unit test in isolation.
- Test suite grew 111 -> 117 (duplicate-title collision x2, about-page counts, export_awards x3).

**Round 11 - Dockerfile gap, timezone bug, duplicate-titles count stuck at 60 (2026-08-05):**
Found through Darragh actually using tonight's features live, right after redeploying:
- **The Dockerfile only ever `COPY`'d an explicit per-file list**, not the whole repo. Every
  round tonight that added a new top-level script or file (`CHANGELOG.md`, `export_awards.py`,
  `add_changelog.py`) was silently missing from the built image regardless of how many times the
  stack got redeployed, since nothing updated that list. Switched to `COPY . .` plus a real
  `.dockerignore` (excluding `aims.db`, `.env`, `uploads/`, `tests/`, root-level images/xlsx -
  mirrors what `.gitignore` already keeps out of the repo Portainer clones from) so this entire
  class of bug can't recur - a new file just needs to be `git add`-ed, nothing Docker-specific.
- **Fixed a real timezone bug**: "Latest version deployed" (and every changelog entry timestamp)
  was showing exactly one hour behind actual Irish time. `irish_datetime` never did any timezone
  conversion at all - just reformatted whatever naive timestamp it was given, silently relying on
  it already being Irish local time. Both `deployed_at` (Python `datetime.now()`, the container's
  own clock - not guaranteed to be anything in particular) and every DB timestamp (SQLite's
  `datetime('now')`, always UTC) are actually UTC. Fixed properly via `zoneinfo`
  (`Europe/Dublin`), not a fixed +1 offset - Ireland alternates GMT/BST, so a fixed offset would
  be wrong half the year. Added `tzdata` to `requirements.txt` so the conversion works
  regardless of whether the base image ships the OS timezone database.
- **Duplicate-titles count was permanently stuck at 60** on the admin dashboard, even as Darragh
  resolved pairs. `find_candidates()` silently truncated to 60 internally *before* the caller
  ever saw a length - resolving the top pair just let the next-highest one below the cutoff take
  its place, so the count never moved until the true total dropped below 60. The full list was
  always built and sorted before that truncation happened anyway, so returning it uncapped costs
  nothing extra - truncation is now the *caller's* job. The dashboard count is the true total;
  the review page shows the top 60 with an explicit "showing top 60 of N" note instead of
  silently capping with no indication.
- Test suite grew 117 -> 124 (timezone conversion x4, dedupe true-count x2, display-limit
  messaging x1).
- **Lesson**: an explicit Dockerfile `COPY` allowlist is a footgun that will keep recurring -
  logged in [[deployment-environment]] alongside the earlier "don't suggest shell
  `docker compose` commands for this Portainer-managed stack" correction from the same night.
- **Follow-up, same evening**: Darragh actually started working the real 235-pair queue and
  immediately found real false positives - "Ghost the Musical" vs "Snoopy The Musical" (74%
  similar), "Bare" vs "Cabaret" (73%), etc. Root cause: short/generic titles sharing a common
  trailing phrase like "the musical" dominated the character-similarity ratio even though the
  actual distinctive words share nothing. Fixed by stripping known generic suffixes
  (" the musical", " jr.", etc.) before computing the ratio, and skipping the ratio check below a
  minimum length where it's unreliable regardless. Verified against both the reported false
  positives (now correctly unflagged) and known-good cases (typos, "X" vs "X Jr." still caught).
  Test suite grew 124 -> 126.
- **Follow-up**: even after the suffix fix, Darragh judged the queue still too loose below ~70%
  similarity (mostly coincidental character overlap, not real near-duplicates) - raised
  `find_candidates`' default `threshold` from 0.55 to 0.70. The word-subset check ("X" vs
  "X Jr.") is a separate mechanism and unaffected. Test suite grew 126 -> 127.

**Parked, raised but not started (2026-08-05):**
- **A "suggested date" column for `/admin/fix-dates`**, sourced from web search, for Darragh to
  manually approve - same idea as the historical-society-region suggest/confirm pattern. Tested
  live rather than guessed: a naive search ("society name" + show title) mostly failed (society
  websites are typically stale; popular titles get drowned out by big US touring productions).
  A follow-up search targeting the actual **venue** (when known) found a real, plausible-looking
  result on the venue's own box-office site - but WebFetch was blocked (403) on that specific
  page, and the actual source Darragh found it through (an Instagram post, likely surfaced via
  Google's AI Overview) isn't accessible through this session's WebSearch tool at all. So: more
  promising than the venue-scrape idea once `/admin/venues` is filled in enough to search by
  venue instead of society name, but not proven at scale, and there's a real capability gap
  (no Instagram access) worth knowing about before promising this works. Darragh's read: not
  reliable enough as-is. Offered to run a proper batch test (~10 shows, venue-anchored) before
  building anything; not done yet.

**Parked for their own dedicated sessions:**
- A society-page section for costume/prop rental listings, ideally matched
  to shows the society has actually performed - the biggest lift on the
  list (new data model, new admin UI, a matching concept), not a quick
  add-on.
- A staging/test environment separate from production, so a bad change
  can't hit the live site directly - scope still to be discussed (what's
  actually prompting this, and how far to take it given the NAS/Portainer
  setup).
- An FAQ page - Darragh's own suggestion, explicitly deferred ("maybe for a
  next revision").
- **Edit history/versioning + revert for society-editable data (2026-08-06)** - each society
  shares one login code (not per-user accounts), so there's currently no way to tell who made a
  given edit, or to undo it if a shared code is misused or a change corrupts data - only the
  current value of anything a society can self-edit (their own shows, profile/about text, links)
  is stored, nothing before it. Would need an audit-log table capturing old/new values per edit
  plus an admin-facing way to browse and revert, similar in spirit to how `changelog_sync.py`
  tracks what's already been published but for arbitrary field changes instead of a fixed file.
  Not scoped beyond that - worth its own planning pass (which tables/fields need it, how far back
  to retain, whether moderator edits need the same trail as society self-edits) rather than
  guessing at a design now.

**Round 12 - light/dark toggle, Season Archive labels, hidden-society scope (2026-08-05):**
Follow-through on the UX audit below plus a live gap Darragh spotted:
- Shipped the light/dark toggle and Season Archive date-range label from the audit's "simple
  stuff" - see the audit doc for details.
- **Season Archive relabelled per season type**, based on a live screenshot Darragh sent showing
  a confusing empty "upcoming" table on a past season: a past season now renders a single "Past
  productions" table (no pointless empty upcoming box); the current season keeps the Upcoming/
  Past split, just renamed from "Already finished"; a future season's table is labelled "Future
  Season / Early Announcements" instead of "Upcoming productions" - `is_past_season`/
  `is_future_season` computed by string-comparing against `current_season()`, same convention
  `all_seasons` already sorts by.
- **`societies.hidden` now also hides a hidden society's shows from the homepage (upcoming table
  + poster gallery), Season Archive, and the `calendar.ics` feed** - not just the `/societies`
  directory and their own page, closing the gap Darragh flagged wanting to fully hide Sligo
  Musical Society and Glenamaddy. Scoped via an explicit question first: Awards/Stats leaderboards
  (the historical archive) deliberately still include them, same "history stays accurate"
  principle as the original Round 9 design - narrowed to mean actual history, not current/
  upcoming shows too. The full CSV dataset export (`/export/shows.csv`, linked from Stats) is
  treated as part of that same historical-archive bucket and left untouched.
- Test suite held at 127 (existing coverage already exercised these query paths; no test asserted
  the old "Already finished" copy so nothing needed updating there).

**Round 13 - All Shows: last-performed, world premiere data, link cleanup (2026-08-06):**
Prompted by Darragh flagging the All Shows page as still messy (`show_links` - the confirmed-URL
"More info" column - had 0/270 titles filled in) and asking for something to help societies spot a
show worth reviving:
- **"Last performed" column + "Longest since performed" sort** on All Shows, computed from the
  true most recent year across `shows`/`historical_results` (unfiltered by the
  `SHOWS_COVERAGE_START_YEAR` dedup cutoff the performance-count column uses, since a recency
  question has no double-counting problem).
- **New `show_info.premiere_year`/`premiere_place`** (moderator-entered, same "never guessed"
  trust model as the rest of that table) shown alongside a computed "AIMS debut" year on each
  show's own page - scoped to the show detail page rather than adding two more columns to the
  already-wide All Shows table, confirmed with Darragh first.
- Wanted to cross-reference against ovrtur.com for premiere data - it 403s on any fetch, so
  pivoted to Wikipedia instead (same source the "More info" links already point at).
- **`enrich_show_links.py`**: a background research pass verified (Wikipedia infobox, not
  guessed) confirmed URLs + world premiere year/place for the top 50 most-performed titles.
  2 of the 50 ("The New Pirates of Penzance", "Michael Collins - A Musical Drama") have no
  genuine, internationally notable Wikipedia article and were deliberately left blank rather than
  linked to something unrelated. One judgment call worth revisiting if it ever comes up: "The
  Wizard of Oz" is ambiguous between a 1902 Broadway musical and a 1987 RSC stage adaptation -
  seeded with the 1987 version since that's the one actually licensed to amateur societies today.
  First attempt at this research task failed twice (a transient API error, then a session usage
  cap) before succeeding on retry - the agent's own web research isn't infallible/free, budget for
  possible retries on a task this size.
- **Found and fixed a real bug while in there**: 2 of the original 30 `enrich_show_info.py` titles
  ("Fiddler On The Roof", "Man Of La Mancha") were silently orphaned since that script's first run
  - wrong capitalization meant they never matched the real `shows`/`historical_results` title
  strings, so their synopsis/rights info never actually rendered anywhere. Fixed the casing and
  taught the script to merge into an already-correctly-cased row instead of erroring, since
  `enrich_show_links.py` may create that row first.
- **Compacted the admin "confirm exact URL" controls** on All Shows behind a `<details>`
  disclosure instead of two stacked forms in every row.
- Test suite held at 127.

**Round 14 - Signature show threshold, historical-productions bulk-add tool (2026-08-06):**
- **Stats page Signature show** raised from "2+ stagings" to "3+ stagings" - 2 read as too weak/
  coincidental. Added an empty-state message for when a region (or the whole page) has no society
  meeting the higher bar, instead of silently rendering an empty list.
- **New `/admin/historical-productions/bulk`**: paste a society's own "previous productions" list
  (`YEAR Title` per line, straight off their website) and it inserts bare `historical_results` rows
  - no award/category attached, just a record the production happened - deduped against what's
  already on record so a list can be safely re-pasted later. Prompted by Darragh having a full
  history for Marian Choral Society, Tuam and no way to bulk-enter it as admin.
- **Found AIMS's year convention while building it, then corrected an overgeneralization the same
  day**: `historical_results.year` is the *season's ending* calendar year, not the year a show
  physically opened - matches how season "23/24" maps to `SHOWS_COVERAGE_START_YEAR = 2024`.
  Diffing Marian's full 49-title list against their existing 40 `historical_results` rows showed
  every one of 21 overlapping titles off by exactly +1 - but Darragh pointed out that's only true
  because Marian happens to always stage in October (autumn/winter); a society that stages
  January-June has its production year already equal to the AIMS year, no +1, and some societies
  stage twice a year in *different* halves - a single batch-wide offset can't be right for both
  shows at once. The tool now asks the moderator which timing this society/batch uses (autumn/
  spring/"entering the AIMS year directly") instead of assuming Jul-Dec-and-add-1 for everyone, and
  the form explicitly tells a two-show-a-year moderator to compute the AIMS year themselves rather
  than trust the automatic offset. Marian's own 24 backfilled rows needed no correction - October
  is safely "autumn" - only the tool's default assumption for *other* societies was the bug.
- **Known pre-existing gap surfaced, not yet fixed**: one inserted row ("Hello Dolly", 1995) landed
  on a title that already exists elsewhere in `historical_results` under a different spelling
  ("Hello, Dolly!") - fixed that one row by hand, but `fix_show_titles.py`'s title-cleanup RENAMES
  only ever touches the `shows` table, never `historical_results`. The same class of orphaned-title
  bug fixed twice already this cycle (`show_info`'s "Fiddler On The Roof"/"Man Of La Mancha" in
  Round 13) likely has more instances sitting in `historical_results` untouched - worth a dedicated
  audit pass rather than fixing opportunistically one row at a time.
- Test suite grew 127 -> 135 (7 tests for the bulk-add tool: insert with the autumn offset, spring/
  exact conventions keeping the year as typed, note extraction, dedupe, login gate, and
  unparsed-line handling not blocking the rest of the batch).
- **Follow-up, same day**: once Darragh actually ran the tool against production and looked at
  Marian Choral Society's real page, the 24 bare productions were rendering inside "Awards &
  nominations" as nomination-shaped rows full of "—" placeholders (no category/result to show) -
  confusing, since they were never award records. Split them into their own "Earlier show history
  (pre-23/24)" section, positioned between "Show history" and "Awards & nominations" - mirrors the
  since-23/24-vs-earlier-archive split `/titles/<title>` already uses. Test suite grew 135 -> 138.

**Research pass - which other societies have an online production history (2026-08-06):**
Checked the 23 AIMS societies with the thinnest recorded history against their own websites, to see
whether Marian's "Previous Productions" page was a one-off or worth actively hunting for elsewhere.
- **Ballyshannon Musical Society** (id 9) - a genuine "Through The Ages" decade-by-decade archive
  back to the 1950s: https://ballyshannonmusicalsociety.ie/through-the-ages/. 36 shows confirmed
  (1963-2019, titles normalized to match existing DB spelling conventions e.g. "H.M.S. Pinafore",
  "Oklahoma!", "The Gypsy Princess") - not yet pasted into the live site, ready to go via the bulk
  tool. **Spring (Jan-Jun) timing** - their current shows all open late February. Real gaps, not
  guessed: the 1950s and 1990s decade pages exist but embed titles as images with no extractable alt
  text, so those years are still unconfirmed; a few scattered years (1985, 2002, 2013, 2015,
  2020-2023) are similarly image-only. 2024/2025/2026 are already covered via the `shows` table.
- **Kilrush Choral Society** and **Rathmines & Rathgar Musical Society** both reference a real
  archive ("Digital Archive" / "Our Legacy" with a century of programmes) but neither was
  automated-fetch-friendly - Kilrush's site is a JS single-page app with no crawlable URLs for that
  section, R&R's archive is scanned programme/poster images via an embedded Issuu viewer. Worth a
  manual (human-browser) look, not confirmed as backfill-ready.
- Everything else in the batch of 23 came back Facebook-only or no independent web presence at all
  - genuinely thin, not just unsearched. Marian's page looks like the exception, not the rule, at
  least among societies already known to be light on history.

**Research pass 2 - all 104 remaining active societies (2026-08-06):** Darragh asked to scale this
up rather than stop at the weakest-coverage sample - run via 4 parallel background agents on Haiku
(cheap/fast model) instead of Sonnet, ~26 societies each. Turned out Marian and Ballyshannon weren't
the exception after all once the *whole* list was checked, not just the thinnest-coverage slice -
**23 more societies have a genuine online production archive**, not yet pulled into the database:

| Society | URL | Years | Format |
|---|---|---|---|
| Castlebar Musical & Dramatic Society | castlebarmds.com | 2014-2026 | clean list |
| Kilmacud Musical Society | kilmacudmusicalsociety.ie/the-history-of-kms/ | 1982-present | history page + programme archive |
| Waterford Musical Society | waterfordtheatrearchive.com | 2015-2025 | dedicated archive site (video/audio too) |
| Pop-Up Theatre, Sligo | popuptheatresligo.com | 2016-2026 | clean list |
| Muse Productions | museproductions.org | 2011-present | per-year pages + photos |
| Glencullen Dundrum MDS | glencullendundrum.com | 1971-present | "Past Show Archive", posters/programmes |
| 9 Arch (Claregalway) Musical Society | 9archms.weebly.com | 2002-present | "Previous Shows" + AIMS critiques |
| Castlerea Musical Society | castlereamusicalsociety.com | 1968-present | "Past Shows" nav section |
| Roscrea Musical Society | roscreams.com | 1940-present | "Past Productions" page |
| Boyle Musical Society | boylemusicalsociety.com | 1984-present | "History" + per-show pages |
| Oyster Lane Theatre Group | oysterlane.wordpress.com/previous-shows/ | 1994-2025 | clean year-by-year list |
| Ennis Musical Society | ennismusicalsociety.ie/past-productions.html | 1959-2024 | detailed archive |
| **Ballywillan Drama Group** | ballywillan.com/wp/history/past-productions/ | **1952-2025** | detailed year-by-year, 70+ years |
| Fortwilliam Musical Society | fortwilliammusicalsociety.org/past-shows | 1978-2025 | detailed year-by-year |
| Limerick Musical Society | limerickmusicalsocietydotcom.wordpress.com/previous-productions/ | 2000-2017+ | clean "Year: Title" |
| Dun Laoghaire Musical & Dramatic Society | dmds.ie | 1959-present | "Show History"/"Past Performances" |
| Harolds Cross Tallaght Musical Society | hxt.ie | 1967-present | "Show History", 50+ years |
| Carnew Musical Society | carnewmusicalsociety.wordpress.com/previous-shows/ | 1967-present | "Previous Shows" |
| Killarney Musical Society | killarneymusicalsociety.ie | ~40 years | "Past Shows"/"History" sections |
| Baldoyle Musical Society | baldoylemusicalsociety.ie/pages/past-shows | 1973-2026 | table: Year/Show/Pantomime |
| Kilcock Musical & Dramatic Society | kilcockms.com/productions-to-date | 1970-2026 | categorized (musicals/pantos/plays) |
| **Carrick-on-Suir Musical Society** | carrickmusicals.wordpress.com/past-productions | **1944-2017** | chronological list, 150+ productions |
| **Wexford Light Opera Society** | wlos.ie/history.html | **1911-present** | history page (SSL issues blocked full fetch - confirm via search) |

Worth a second look but not confirmed backfill-ready (partial/inconsistent dating, access issues, or
gallery format instead of a real list): Encore Performing Arts Academy, Rush Musical Society, Naas
Musical Society, Newcastle Glees Musical Society, Kilmainham Inchicore Musical Society (403
blocked), Enniscorthy Musical Society (DNS/SSL issues), Belfast Operatic Company, St. Agnes Choral
Society (Belfast, photo gallery not a list), Galway Musical Society (archive only covers 2023-2025
despite a 1985 founding), Cecilian Musical Society Limerick (130 shows referenced historically, no
structured public archive found).

**Not started yet**: 19 of these 23 have not been pulled into the database - this is a research
inventory, not a completed backfill. 4 done so far (see the "biggest history first" round below).
Given the volume (several with 50-70+ years of history each), this needs prioritization before
diving into the rest - see chat for how Darragh wants to sequence it.

**Round 15 - biggest-history-first backfill, two more real bugs caught (2026-08-06):** Darragh chose
"biggest history first" - Wexford Light Opera (1911-), Carrick-on-Suir (1944-2017), Ballywillan
(1952-2025), Roscrea (1940-present). Wexford's site 403s/SSL-fails on every fetch attempt (same
class of blocker as ovrtur.com) - Darragh screenshotted their history page directly instead. All
four backfilled: Wexford 68 productions (1912-2011), Roscrea 63 (1940-2017, excludes self-labelled
pantos), Carrick-on-Suir ~60 (1944-2017, pantos/variety nights excluded by title judgment since not
self-labelled), Ballywillan's musicals-only era (1996-2012 - their first 35+ years are pantomime,
per Darragh's call below). Confirmed via chat: **pantomimes are out of scope for this site** (AIMS
musical theatre circuit specifically) for now - may get their own category in the future, parked as
an idea, not started.
- **Two more real bugs in `admin.bulk_historical_productions` found and fixed before Darragh ran
  these four** (on top of the two from Round 14): the dedup check only matched an existing *bare*
  row, not a real award-archive row or a `shows` table entry for the same production - a society
  with real pre-existing coverage (Carrick-on-Suir had 132 rows, Wexford 146, Roscrea 26) would get
  a duplicate bare row inserted for any overlapping year. Fixed in `be5f186`/`105684c`.
- **Caught in production, not just theory**: the live site was still running code from before these
  fixes when Darragh ran the four backfills (confirmed via direct fetch - the homepage suggestion
  callout and later changelog entries were missing live despite being pushed). A second Pull and
  redeploy was needed. `find_duplicate_historical_rows.py` (report-only by default, `--fix` deletes
  only the redundant bare rows, never a real award/shows record) found and removed **67 duplicate
  rows** the pre-fix tool had created - 30 at Carrick-on-Suir, 11 at Roscrea, 26 at Wexford,
  0 at Ballywillan (no actual overlaps there). Re-ran clean after.
- **Lesson**: after pushing a fix to a tool a moderator is about to use for real data entry, verify
  the fix is actually *live* before they use it - a push isn't a deploy, and this session had several
  commits queued up between redeploys.

**Round 16 - Data quality dashboard (2026-08-06):** Darragh asked what else could go on the admin
"Needs attention" board and how to get each row to 0, before wrapping up for the day.
- Clarified that most existing rows are already optimally filtered (the link is the pre-filtered
  view) - the one genuinely misleading number is "Award records with no society match", which is
  mostly permanent (a genuinely defunct historical society has no modern `societies` row to match,
  by design) - softened the dashboard label to say so rather than reading as an actionable backlog.
- **Two new live checks added**, both reusing existing fix actions rather than building new ones:
  - **Duplicate historical productions** - same query as `find_duplicate_historical_rows.py` (the
    bug class from Round 15), now a live dashboard count with a per-row Delete button on a new
    `/admin/data-quality` page, instead of needing shell access to catch a recurrence.
  - **Orphaned title data** - `show_info`/`show_links` rows whose title has no exact match in
    `shows`/`historical_results` (the "Fiddler On The Roof" casing bug from Round 13) - links to
    the existing edit-show-info and clear-show-link actions.
- Test suite grew 140 -> 145.
- **Follow-up, same evening**: Darragh spotted a second instance of the exact same "mostly
  permanent, not actually a backlog" pattern - "Shows missing a review link" (183) counted any show
  where `review_status != 'Published'`, which included shows correctly marked **Not adjudicated** -
  a deliberate, permanent state (that show will never have a review). Excluded it from both the
  dashboard count and the `/admin/shows?needs_review=1` filtered list itself (not just the count),
  so the number now only reflects genuinely fillable-in gaps. `Scheduled` still counts (temporarily
  unresolved, worth chasing once published) - only `Not adjudicated` is excluded. Test suite grew
  145 -> 148.

**Round 17 - Installable mobile PWA + bottom tab bar (2026-08-17):** Darragh came back from a
break with two asks - this round covers the first (PWA/bottom nav); the second (show-page Google
Calendar link + adjudication-deadline email reminders) was deliberately split off into its own
future session, since it needs real backend/schema/infra work (a generalized mailer, new `shows`
columns, a GDPR consent flow, a new daily sidecar job) - see the plan notes for that scoping.
- **Mockup-first, twice** - a published Artifact (phone-frame mockups reusing the site's real CSS
  tokens, not placeholders) was built and iterated on before any real template was touched, per
  Darragh's explicit ask ("can we do a mockup first too? what if you break the website?"). Tab
  composition changed twice during review: Awards briefly swapped in for Stats as the 4th tab, then
  reverted once actual `/admin/traffic` history showed Stats (116 views) narrowly ahead of Awards
  (99) as of the last snapshot - Stats kept its tab, Awards moved to the new More page instead.
- **Manifest + icons + service worker**: real `icon-192`/`icon-512`/`icon-maskable-512`/
  `apple-touch-icon` PNGs generated from the existing `favicon.svg` brand mark via a new
  `generate_icons.py` (Pillow, dev-only, not a runtime dependency) - iOS doesn't accept SVG for its
  home-screen icon at all, so this was silently non-functional before. A minimal app-shell service
  worker (`app/static/sw.js`, registered at `/sw.js` so its scope covers the whole site even under
  the `/showcal` URL_PREFIX) caches only the unchanging static assets - enough to satisfy Chrome/
  Android's installability checklist without pretending to be full offline support.
- **Bottom tab bar** (Home / Societies / This season / Stats / More) - mobile-only (hidden ≥768px),
  brand-red active state, safe-area padding for notches. Deliberately hidden on `/admin` and
  `/society` pages (`request.blueprint` check in `base.html`) - those are Darragh's own task screens,
  already dense with forms, not places that need "Home/Societies/Stats" navigation.
- **New `/more` page** (not a slide-up bottom sheet - lower-risk, reuses the existing `.queue-item`
  card component) holds everything not in the main 5: Awards, Submit a show, Suggest a feature,
  Society login, Moderator login, About.
- **iOS-only "Add to Home Screen" hint** - Android/Chrome prompts to install automatically; iPhone
  Safari never does, so without this most iPhone visitors would never discover the feature exists.
  Dismissible, remembers the dismissal.
- **Homepage's Upcoming Shows table now swaps to stacked cards on phones** (same pattern as Season
  Archive/Awards/society pages), closing the "I need the same info as desktop" gap Darragh flagged -
  the old 5-column table forced sideways scrolling on a phone.
- **Real bug found and fixed, not something this round introduced**: while verifying the card-swap
  in an actual browser, found the site's existing table&rarr;cards responsive pattern has had a CSS
  specificity/source-order bug since it was introduced - `.table-wide`/`.table-cards` were bare
  class selectors losing the cascade to earlier unconditional rules on the same elements, so the
  swap has **never actually applied on any page that uses it**, including in production. Fixed by
  qualifying both selectors with their element type (`table.table-wide` / `div.table-cards`) so they
  reliably win regardless of source order - a 4-line CSS fix in `style.css` with a wide blast radius
  fix (Season Archive, Awards, and society pages all get working mobile card views as a side effect).
- Test suite grew 148 -> 153 (`tests/test_pwa.py`: manifest icon purposes, the `/sw.js` route, the
  More page's links, and that the bottom bar is present on public pages but absent on admin/society).
- **Lesson**: the local screenshot tooling used to verify this (headless Edge on this Windows
  machine) has its own bug at narrow/phone-width window sizes - confirmed via an isolated red-border
  test page, not a real site issue - so final verification used a 550px-wide screenshot (below the
  table-cards breakpoint, above whatever narrow-width threshold triggers the tool's own glitch) plus
  the passing test suite, rather than a literal 390px phone-width screenshot. Worth Darragh
  double-checking the real mobile layout on an actual phone once deployed.

**Round 18 - Show-page "Add to Google Calendar" + adjudication reminder link (2026-08-17):** Once
Round 17 was live, Darragh came back with a much smaller version of the "Part 2" ask parked at the
end of that round - not the full email/GDPR/scheduler system, just two plain calendar-render links
on each show page:
- **"Add show to Google Calendar"** - covers the full run, opening night to closing night.
- **"Remind me: check adjudication forms were submitted (8 weeks before opening)"** - a single-day
  reminder event 8 weeks before opening. AIMS's real rule is an application at least 6 weeks out, so
  this lands 2 weeks ahead of that deadline as a buffer, not right on it. Automatically hidden for a
  show marked `review_status = 'Not adjudicated'`.
- Both are just `https://calendar.google.com/calendar/render?action=TEMPLATE&...` URLs built in
  `public.show_detail()` (`_google_calendar_url()`) - no Google auth/API integration, no new
  `shows`/`societies` columns, no outbound email, no scheduled job. This covers the "save the show"
  and "don't forget adjudication" asks from the original Part 2 scoping without any of the backend
  work that was deliberately deferred in Round 17 - the fuller email-both-contacts version is only
  still worth building if Darragh wants a nag that doesn't depend on someone remembering to click a
  link.
- Test suite grew 153 -> 157 (`tests/test_show_calendar_links.py`: date-range math, the exact 8-week
  offset, the not-adjudicated hide case, and no links at all when `opening_date` is unset).

**Round 18 follow-up - hide past-show links, Gilbert/Sullivan calendar subscriptions (2026-08-17):**
Two more requests once Round 18 was live:
- **Both calendar links now hidden once a show is finished** - "maybe hide the links as they are
  redundant" - reuses the same `is_upcoming` flag already computed on the page for the ticket/poster
  nudge, so a past show's Dates/Adjudication fields just show plain info with no dead links.
- **`/calendar.ics` gets an optional `?section=Gilbert`/`Sullivan` filter** - asked for "a Google
  calendar that... auto-updates with all Sullivan shows and all Gilbert shows." The real answer is
  `.ics` (a subscribable feed a calendar app periodically re-fetches), not a Google-specific
  one-click "add event" link like the show-page ones - those two are different mechanisms, and only
  `.ics` actually supports "keeps itself updated." Reused the existing unfiltered feed's logic rather
  than building a new one; `X-WR-CALNAME` changes per tier so a subscribed calendar is
  distinguishable in the calendar app's own list. Linked from the homepage next to the existing full
  feed, with a plain-language line on how to actually subscribe to a calendar URL in Google Calendar
  (Other calendars &rarr; + &rarr; From URL) since that's a less obvious flow than clicking a normal
  link.
- **Caught mid-round: `CHANGELOG.md` (the public-facing file that feeds the homepage's "Recently
  shipped" and the public Roadmap page) hadn't been touched all day** - Rounds 17 and 18's work was
  only ever logged here in `ROADMAP.md` (internal/dev-facing). Added a real entry for both rounds in
  plain visitor-facing language, published the moment this gets redeployed - see
  `app/changelog_sync.py`.
- Test suite grew 157 -> 162 (`tests/test_calendar_feeds.py`: unfiltered/Gilbert/Sullivan/invalid
  section filtering + calendar name x4; past-show link-hiding x1).

**Round 18 second follow-up - hide adjudication date + empty Review field (2026-08-17):** Two more
small show-page privacy/polish asks:
- **The raw adjudication date is no longer shown publicly** - "it is just information that's on the
  review," not meant to be broadcast ahead of time. That row now shows only the "remind me to check
  adjudication forms were submitted" calendar link (from the second follow-up above) where one
  applies - nothing is deleted from the database, `shows.adjudication_date` still exists and still
  feeds the admin side, just no longer rendered on the public page.
- **"Review: None" hidden for a show that hasn't happened yet** - an unpopulated default reads as a
  gap, not information. Scoped to upcoming shows only (`is_upcoming and review_status == 'None'`) - a
  *past* show still showing "None" stays visible, since that's a real, actionable data gap rather than
  noise.
- Also prompted Darragh to ask directly whether `CHANGELOG.md` (public-facing) was being kept in sync
  with `ROADMAP.md` (internal) as work shipped - it hadn't been, every round today (see the
  "Caught mid-round" note above). Now both get updated every round, not just `ROADMAP.md`.
- Test suite grew 162 -> 166 (`tests/test_show_detail_review_adjudication.py`: Review hidden/shown
  across upcoming vs. past vs. real-status cases x3, raw adjudication date never rendered x1).

**Round 18 third follow-up - reminder link moved to society login, public cut-off date, admin notes
on Done suggestions (2026-08-17):** Darragh reconsidered where the adjudication reminder link
actually belongs, then separately asked for a way to leave his own commentary on shipped suggestions:
- **The "remind me to check adjudication forms" calendar link moved off the public show page
  entirely, onto the society's own logged-in edit-show page** (`society.edit_show()` /
  `society_show_form.html`) - it's only actually useful to that show's own committee, not a random
  visitor, so it didn't belong on the public page in the first place. New shared
  `app/calendar_links.py` (the URL-builder moved out of `public.py` since `society.py` needs it now
  too) so the logic isn't duplicated.
- **The public show page gained a plain "Adjudication submission cut-off" date instead** - just
  `opening_date` minus 6 weeks (AIMS's real rule), computed on the fly. Safe to show publicly, unlike
  the actual scheduled `adjudication_date` (hidden in the second follow-up above) - this one is pure
  arithmetic on a date the page already displays, never AIMS's own internal scheduling.
- **New `feature_suggestions.admin_note`** - a free-text field Darragh can fill in from
  `/admin/suggestions` (same inline form as the existing category/status dropdowns), shown on the
  public Roadmap page **only next to a suggestion once it's marked Done** - "I'd like to add a
  comment beside 'done suggestions' where they can see how I've interpreted it." Scoped to the Done
  lane specifically (checked in `suggestions_board.html`'s `lane()` macro) so it doesn't clutter
  Planned/In Progress/Not planned.
- Test suite grew 166 -> 171 (`tests/test_society_adjudication_reminder.py`: reminder shown for own
  upcoming show, hidden when not-adjudicated/finished, 404 for a different society's show x4;
  `tests/test_suggestions_roadmap.py` gained the admin-note-only-shown-once-Done case).

**Round 18 fourth follow-up - per-region .ics calendars (2026-08-17):** "I like the ics link - could
we get one per region as well?" Extended `/calendar.ics`'s existing `?section=` filter with a
combinable `?region=<region>` one (validated against `constants.REGIONS`, same "invalid ->
unfiltered" fallback convention). Homepage subscribe block reorganized into three short lines (All
shows / By tier / By region) instead of one run-on paragraph now that there are 9 links total
instead of 3. Only the two single-dimension link sets are surfaced on the page - the combined
`?section=X&region=Y` form works for anyone who constructs the URL by hand, but listing all 12
tier-region combinations as clickable links would have been too much. Test suite grew 171 -> 174
(region-only filter, invalid-region fallback, section+region combined).

## UX & feature audit (2026-08-05) - reviewed, nothing built yet
Requested pass focused on four specific asks, published as its own document (not chat-only):
https://claude.ai/code/artifact/20e94177-8676-4b83-8242-1d330b08dfde
- **Stats page "Who's won the most?" framing** - real data confirms the ego-stroke complaint
  (Wexford leads Best Overall Show 7x, most productions 135, most award wins 59 - all three
  all-time totals). The Award Explorer already fixes this *per category* when you actually use
  it (Tullamore leads Best Programme, Shannon leads House Management, etc.) - the problem is the
  headline framing and the default view landing on the one category where the gap is widest.
  Proposed: reframe the headline, pick a less lopsided default, add a recency-weighted
  ("since 23/24" vs all-time) toggle to the Explorer and the all-time leaderboard cards - don't
  skew or hide the real historical numbers, same principle as Round 6.
- **Review author byline** - no `review_author` column exists yet (checked `schema.sql`); the
  "Read the AIMS review" link has never carried an author. Scoped as a small schema +
  admin-form + template change, but two open questions before building: backfill existing
  review links or let it grow forward-only, and is "author" always an individual adjudicator or
  sometimes a publication.
- **Light/dark toggle** - the site already has a full dark theme (`style.css`, driven by
  `prefers-color-scheme`), just no manual override. Proposed: small `data-theme` +
  `localStorage` toggle, no backend/schema involved.
- **Season Archive date-range label** - confirmed still open from the 2026-08-04 audit (checked
  `season.html` directly, no range text present) - not shipped despite being flagged before.
- **Adjudicator restricted view scoping** - see the resolved decisions above (unlisted link, one
  shared colour-coded calendar, 3+ danger-week flag, historical view first).

## Site review (2026-08-05) - questions for Darragh, not started
Full pass over the live site, the codebase, and `aims.db` at Darragh's request, specifically to
surface open questions/decisions rather than just findings. Written up as its own document
(published: https://claude.ai/code/artifact/64fd82a8-a982-45f2-aa91-ed57d6736271) so it's
reviewable outside chat - summary of what's in it:

- **New:** changelog is empty on production (0 rows - the typo'd entry from the 2026-08-04
  audit is gone, nothing replaced it); venue data has collapsed to 0% filled for 25/26-27/28
  (confirmed the gap is in the source `shows.csv`, not an import bug) despite the Phase 0
  venue+Maps-link feature depending on it.
- **Correction (2026-08-05):** the "67 historical societies unconfirmed" finding was wrong -
  based on a stale local `aims.db`, not production (see [[workflow-habits]] memory - the local
  dev db has no sync mechanism with `/data/aims.db` on the NAS). Darragh had actually confirmed
  68 of 72 directly on the live site; the remaining 4 (3 with no location clue at all, plus
  "AIMS" itself - not a real society, a national-level award attribution) are genuinely
  unresolvable, not an oversight. Nothing to do here.
- **Still pending, already known:** the Phase 2 `export_csv.py` item below, plus whether
  `AIMS_AwardsHistory.xlsx` needs an `export_awards.py` counterpart or can be treated as a
  frozen historical snapshot now that the DB corrections have diverged from it.
- **Minor:** `/awards` renders ~1,500+ rows with no pagination; society-level award categories
  show "&mdash;" for Nominee (expected, but reads like a gap).
- **Needs a scoping decision before starting:** the adjudicator calendar's open questions
  (unchanged from 2026-08-04), costume/prop rental listings (now with one real suggestion
  sitting in the Planned lane - a live demand signal), and the staging/test environment (scope
  was never actually defined).
- **Checkpoint only, no new info:** FAQ page, CSP, poster image-content validation - still
  correctly parked.

## Live site audit (2026-08-04)
A full pass over the live production site (darraghc.ie/showcal) - real pages,
real data, not local dev - to find what's working and what isn't before
picking the next phase.

**Traffic (`/admin/traffic`, 2,482 total page views recorded so far):**
- Homepage dominates at 697 views (~28% of all traffic) - expected as the
  main entry point.
- `/season` (134) beats both `/stats` (116) and `/awards` (99) - validates
  Round 3's call to keep Season Archive as a top-level nav item rather than
  folding it away.
- Society self-service is genuinely landing: `/society/` (dashboard, 106) +
  `/society/login` (72) = 178 views - real usage of the invite-code login
  system, not just a feature nobody found.
- **Individual society pages (numeric IDs) collectively dwarf the
  `/societies` directory** (39 views) - just the ones visible on the
  traffic page sum to 230+. Most visitors are landing on *one specific*
  society's page directly (a shared link), not browsing the directory to
  find it. `/societies/108` (Stage One New-Musical Group) alone has 79 -
  far ahead of the next-busiest, suggesting that society is actively
  sharing their page link somewhere. Worth keeping in mind for the
  "179 vs 127" copy fix above - the directory itself may matter less to
  real usage than the individual pages do.
- `/calendar.ics` has 24 views - the ICS export feature is genuinely used,
  not dead weight.
- `/submit/unlock` has 16 - confirms the deliberately-unadvertised one-off
  submission form is reaching people the way it's meant to (Darragh sharing
  the direct link on request).
- `/suggest` (23) outpaces `/suggestions` the Roadmap page (14) - more
  people submit a suggestion than check the Roadmap first, despite both
  nudging that. Minor, not worth chasing.
- **Data limitation**: `page_views` only stores a running total + last-seen
  timestamp per path, no history over time - this single snapshot can't
  show growth rate, day-of-week pattern, or where traffic is coming from.
  Not recommending building that out now, just noting it as a ceiling on
  how far traffic analysis can go without a schema change.

**Confirmed working well:**
- Round 5's About rewrite and Roadmap lanes (incl. the Done lane) are live
  and rendering correctly with real data - a real user-facing bug (Mary I/
  SpongeBob-style awards-link 404) and a real award-attribution correction
  already show up in the Done lane, and the season/society/awards pages all
  serve real, coherent data with no broken links found.
- North Wexford's manually-corrected section (Gilbert, "as of 26/27") is
  live and correct on its society page - confirms the Phase 2 CSV-export
  item below is about syncing the *source* CSVs, not a live-data bug.

**New findings:**
- **"179 societies" is a headline stat, but only 127 are publicly browsable**
  - `/societies` filters out `section = 'Inactive'` by default (by design,
    for anonymous visitors), and 52 of the 179 rows (29%) are Inactive.
    Worth a copy tweak on the About/Stats pages ("179 societies on record,
    127 currently active") so the touted number matches what a visitor
    actually finds when they click through.
- **Homepage changelog has a live typo**: "Upcoming shows page reowrked
  Socities now a separate page!" - a content fix via `/admin/changelog`
  (edit the entry), not a code change.
- **Season Archive's date range isn't labelled** - season "26/27" runs
  Sept 2025-Aug 2026 by convention, so shows finishing May-July 2026
  correctly show as "already finished" within it, but that's not obvious
  from the "26/27" label alone. A small "(Sept 2025 - Aug 2026)" next to
  the season heading would remove the ambiguity.
- **Stats page confirmed as the weakest page**, matching the existing
  "ugliest page" flag below - now scoped concretely (see the published
  mockup): ~8 separately-formatted "most X" rankings back to back with no
  shared visual language, a "Signature show" section that only 2 societies
  currently qualify for with no inline explanation of why, and a
  54-item one-off-productions list with no collapse. A redesign mockup
  using today's real numbers (two leaderboard-consolidation variants) is
  published - see [[stats-page-redesign-mockup]] - ready to build once a
  direction's picked.

## Backlog - Adjudicator planning calendar (not started, needs its own session)
Raised 2026-08-04 via Darragh, relaying feedback from one of the two AIMS
adjudicators (one covers Gilbert, one covers Sullivan - each has to route-plan
to see every show in their section and get a review out, and technically
only need ~6 weeks' notice):

> "I wonder would it be possible to have a colour coded month by month
> calendar? One colour for Gilbert and one for Sullivan... I can already see
> one week where, if all shows announced to date avail of adjudication, the
> last one to apply will be disappointed. A visual calendar may prompt early
> applications."

Darragh's framing: a week-by-week view, per section, showing how many shows
are running that week - so an adjudicator (and a society deciding when to
apply) can spot an overloaded week at a glance. Internal/admin-only, not a
public-facing feature.

**Feasibility check (2026-08-04), now grounded in real historical data:**
Darragh's own `AIMS 2025_26 Show Season (Unofficial).xlsx` (gitignored,
personal working file, not the tracked CSVs) has an "Adjudicator/Adjudication
Date" column per show - and that data is **already imported into `aims.db`**
(`shows.adjudication_date`, 300 real historical records across 23/24-25/26,
matched exactly against the source spreadsheet). Two distinct things this
enables, not one:

1. **A historical "which weeks are typically busiest" view** - fully
   buildable *right now*, no new/live data needed at all. Real numbers from
   those 300 records, split Gilbert/Sullivan:
   - **April is the crunch month by a wide margin**: 94 combined visits
     (55 Gilbert / 39 Sullivan) vs. a ~10-40/month baseline most of the
     year. November is the second peak (56: 33G/23S). July has zero.
   - The single busiest recurring week is **ISO week 15 (mid-April)**: 31
     combined visits across the 3 seasons (17G/14S) - a real, repeating
     danger week, not a one-off. ISO week 47 (late Nov) is second at 26.
   - Adjudicator visits cluster tightly: 83% happen within 0-4 days of a
     show's **opening night** (248 of 300 records) - so `opening_date`
     alone is a reliable stand-in for "when the adjudicator needs to be
     there," confirming a live calendar doesn't need `adjudication_date`
     filled in ahead of time to be useful.
2. **A live current-season view** using `shows.opening_date`/`closing_date`
   + `section` - this is the one that depends on confirmed dates rather
   than "TBA," and fills in as the season goes on (see below).

**The real dependency for the live view, exactly as Darragh's adjudicator
flagged**: only as good as how many shows have a confirmed `opening_date`.
Per the live site audit above, a meaningful chunk of even the *current*
season is still TBA. Not a blocker (arguably the point - an early nudge),
but it'll look sparse if shipped too early in a season - which is exactly
why the historical view (1, above) is worth having independently: it's
useful on day one, doesn't wait on anything.

**Scoping decisions (2026-08-05, via the UX audit below) - ready to build:**
- Access: **unlisted shared link**, same pattern as `/submit/unlock` - no login system.
- Layout: **one shared calendar**, Gilbert/Sullivan shows colour-coded together (not two
  separate calendars) - shows real overlap between sections, not just each one in isolation.
- Danger weeks: **explicit flag at 3+ shows opening the same week**, matching the
  adjudicator's own example - not just density/count alone.
- Sequencing: **historical view first** (buildable now, no live-data dependency - see the
  April/week-15 numbers above), live current-season view as a fast-follow once enough of the
  season has confirmed `opening_date`s to not look sparse.

Flagged by Darragh as "may end up being a large side request" - mockup
first, own session, not started building yet.

## Phase 2 - Data integrity sweep (next)
- ~~`export_csv.py` against production, pull down, commit~~ **DONE (Round 9, 2026-08-05)** -
  `societies.csv`/`shows.csv` refreshed and committed.
- ~~"179 vs 127" copy fix~~ **DONE (Round 10, 2026-08-05)** - see below.
- ~~`AIMS_AwardsHistory.xlsx` export~~ **DONE differently (Round 10, 2026-08-05)** - turned out
  the xlsx itself isn't what `import_awards.py` reads (it reads the git-tracked
  `AIMS_Awards - Results.csv`, exported from the xlsx's "Results" sheet at some point in the
  past) - built `export_awards.py` as that CSV's inverse instead. The untracked xlsx is now just
  Darragh's original personal working file, superseded by the CSV.
- Audit for other societies with similarly stale/presumptive data.

## Phase 3 - Public launch
**Reality check (2026-08-04): the site is already live and has real
anonymous users** - this happened organically rather than through the
formal process below. The interview/`LAUNCH.md` step is still worth doing
at some point (scaling onboarding to all ~150 societies, edge cases, what
"done" means), just retroactively rather than as a gate before launch.

Before announcing this to AIMS societies/fans at large:
- Start a **fresh session** for this phase specifically.
- Have Claude interview you with `AskUserQuestion` about launch scope,
  onboarding at scale (how do all ~150 societies actually get invite codes -
  not just the ones who happen to ask), edge cases, and what "done" means.
- Write the outcome to `LAUNCH.md` as a real spec before implementing
  anything further.

## Phase 4 - Post-launch maintenance cadence
- Periodically verify the nightly backup (`aims-backup` sidecar) is still
  actually producing files, not just running.
- Revisit deferred items from the security audit: CSP (blocked on inline
  `onsubmit` handlers), real image-content validation for poster uploads
  (would need Pillow).

## Working agreements (from the 2026-08-03 process review)
- `/clear` (or a fresh session) between genuinely distinct workstreams -
  don't chain unrelated incidents/features/audits in one long thread.
- Mockup-first for anything visual - already working well, keep doing it.
- For a sweep touching many files (like Phase 0's audit), write the plan
  and get sign-off before editing, rather than fixing things as found.
- Lessons that matter beyond one session go in `docs/`, not just chat -
  already the habit for this repo, keep it up.
