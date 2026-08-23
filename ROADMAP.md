# Roadmap

Tracks the current phase of work and genuinely open items, so a new session (after `/clear` or a fresh
start) can pick up without re-deriving context. Update this file - don't just say the plan out loud in
chat - whenever the phase changes.

**This file was pruned on 2026-08-20** - it had grown to ~3,000 lines/90K+ tokens of chronological
session log, almost entirely shipped/superseded work, and CLAUDE.md's own rule says to read it at the
start of every session. Full history (every Round, every Phase, every mockup write-up) is preserved
verbatim in `ROADMAP_ARCHIVE.md` - nothing was deleted, just moved out of the file that gets read every
session. This file now holds only: the current phase, and a flat list of items that are genuinely still
open (not started, explicitly parked, or blocked on something).

## Full public-site UX audit, 2026-08-23 - READ THIS BEFORE PLANNING NEW FEATURES

Darragh asked for a step-back walkthrough of the whole public site as (a) a society committee member
and (b) an ordinary musical-theatre fan. Non-technical write-up with mockups, published as an Artifact:
**https://claude.ai/code/artifact/a546fc7e-ef6e-42c3-b6e5-400634708318**

**The headline finding, and the thing most future work should be sequenced around: the site's
infrastructure is far ahead of its content.** Every one of these fields already exists, already renders
the moment it's filled, and is already editable by societies themselves - nobody has been asked:

| Supported field | Filled in |
|---|---|
| Society "about" blurb | 1 of 194 |
| Society website link | 0 of 194 |
| Society Facebook / Instagram / TikTok | 2 / 3 / 3 |
| Society logo | 7 of 194 |
| Venue capacity / map pin | 0 of 147 each |
| Ticket link on an upcoming show | 7 of 50 |
| Poster on an upcoming show | 9 of 50 |
| Society login codes ever issued | 14 (of 143 active societies) |

**Verified broken journeys** (all re-confirmed against the live site 2026-08-23, not inferred):
- A show page contains **zero** links to its own venue page (checked shows 415/369/403) - it links to
  Google Maps instead. Society pages the same. The venue pages exist and nothing points at them.
- **"Submit a show" is unreachable on desktop** - linked only from `/more`, which is linked only from
  the mobile bottom tab bar.
- **Adjudicator names on `/reviews` aren't links**, though `/adjudicators/<id>` exists.
- **`sitemap.xml` omits** `/titles`, `/venues`, `/awards`, `/reviews`, `/stats/trends`, `/about` and
  every title/venue/adjudicator detail page - only shows, societies, stats, season, adjudicators, root.
- `/reviews` is a **362KB single page** (all 1,086 reviews, no pagination); `/season` is 123KB.
- **Gilbert/Sullivan is explained only on `/about`** but used as a filter label on 5+ pages.

The audit's four bigger bets (each mocked up): homepage leads with what's on; the society page
empty-vs-filled side-by-side (doubles as the recruitment pitch for getting societies to fill theirs in);
the show page as the shared front door; and "what's on near me" - which **cannot be built until venue
coordinates exist** (0 of 147 today), and is written up as a decision to make, not a feature to queue.

**Quick-win batch 1 shipped 2026-08-23** (`b729565`): venue text on the show page and homepage is now a
link to `/venues/<slug>` (Maps link kept alongside on the homepage - different questions); adjudicator
names on `/reviews` link to `/adjudicators/<id>` (needed restructuring `review_row` from one big `<a>`
wrapping the whole row - can't nest a link inside a link - into a `<div>` with the show title carrying
the row's original destination); `sitemap.xml` gains `/titles`, `/venues`, `/awards`, `/reviews`,
`/stats/trends`, `/about`, and every individual title/venue/adjudicator page. `show_detail()`/`index()`
now call `venues_build.ensure_current(db)` themselves - needed for the venue link to ever appear on a
freshly-added show, same `ensure_current()` gotcha as everywhere else. 18 new/updated tests, full suite
514 green.
- **Deliberately dropped from the batch**: the audit's "Submit a show is unreachable on desktop" finding
  is factually true but not a bug - `test_homepage_split.py` already asserts it must NOT be in the
  footer, and `ROADMAP_ARCHIVE.md` confirms Darragh removed it from the nav/footer on purpose (prefers
  the logged-in society flow; shares the one-off form only via a direct link). Caught before
  implementing, not after.
- **Quick-win batch 2 shipped 2026-08-23** (`590e1f4`, `74dc693`, `f8d1041`, `d20f9be`): "Not recorded"
  replaces "TBA" for a past show with no date on `society_detail.html`/`venue_detail.html` (extends the
  2026-08-19 fix that only covered `season.html`/`show_detail.html`); the stale "before the end of
  August" promise removed from `/about`; a "see the full season" link added under the homepage's
  6-show table; empty-state messages added to `/titles` search and `/stats`' one-off productions; a
  short Gilbert/Sullivan explainer added under the filter form on Awards, Reviews, Season and
  Societies, linking to `/about` rather than re-explaining inline (and deliberately not claiming it's
  about production size - checked `/about`'s real text first, it's a workload-driven adjudicator split
  on nomination history). 13 new tests, full suite 527 green.
- **Three audit findings turned out to be deliberate decisions, not bugs - caught before implementing,
  not after, by checking git history/comments rather than trusting the audit's own read:**
  - "Homepage notices above the fold" - Darragh explicitly asked for this placement
    (`39f7276`, 19 Aug: "I'd like people to submit ideas"). Left alone.
  - "Public adjudication-cutoff display" - added on purpose (`31ae512`, commit title literally "add
    public cut-off date"), and the code comment already reasons why it's fine (pure arithmetic on a
    date already shown, not real AIMS scheduling data). Left alone.
  - "Random Award Explorer default" - documented in-line in `info.py`: deliberately avoids the
    Explorer's default view becoming a fixed "who's won the most" leaderboard for one category. Left
    alone.
  - Also nearly shipped a bad "fix" for `/awards`' blank Nominee cells - the cell isn't blank by
    oversight, `nominee_name` for a society-level category literally duplicates the Society column
    (verified against real data: both columns read "Boyle Musical Society"). Reverted before
    committing.
- **Still open, genuinely**: `/reviews`+`/season` page weight (362KB/123KB, no pagination) - the one
  remaining quick win, bigger/riskier than the others so held back rather than rushed into this batch.

**Mobile nav bug fixed 2026-08-23** (`82617ae`) - Darragh caught it live on his phone, screenshot and
all: the Explore menu ran off the left edge of the screen, unreadable. Root cause: the narrow-viewport
fix from the nav restructure (`right: -0.6rem`) was written for History, which sits near the right of
the row - the same anchor pushed Explore's menu (near the left) off the opposite edge. Fixed properly
rather than just flipping the anchor for one trigger: below 40rem the menu is now a normal full-width
block under whichever trigger opened it (`flex-basis: 100%` on the open `<details>`), so neither
trigger's menu can overflow either edge. Verified locally at 390px with the menu force-opened (headless
screenshots can't click) for both Explore and History.

Section 5 of the audit is a non-technical outreach plan (nudge on their own page, fill 2-3 exemplar
societies, ask for posters/ticket links first, a draft message to send a committee, and a "claim your
page" route). That track is Darragh's lever, not a coding task.

## START HERE - productions-table migration, stage 1 of 4 LIVE (2026-08-22)

Built in the `worktree-productions-table` worktree, merged to main (`94f0e2f`), **deployed and
independently verified running in production**. Full suite 443 green.

Verified after the redeploy, not assumed - `aims-web` restarted with the new code present, the table
built itself on first startup (2,805 productions, 1911-2027, 1,242 shows rows and 4,707 award records
linked), and `GET /stats` from inside the container returns **2,711 productions / 1,092 reviewed** with
the folded 1911-1976 row and its note. The freshness check is a genuine no-op in steady state -
`productions_build_state.built_at` stayed at the startup timestamp across four page loads. Page serves in
~180ms on the NAS.

**What's done:**
1. **The table itself** (`productions` in `schema.sql`) - one row per real staging, natural key
   `(society_key, season_start_year, title_key)`. Derived, not authored: `app/productions_build.py` is
   the only writer, and it upserts on that key so a production keeps its id across rebuilds.
   `production_id` links added to `shows` / `historical_results` / `historical_reviews`.
   `app/productions.py` holds the key derivation so the definition can't drift between callers.
2. **The rebuild** - runs on every app start, and lazily on `/stats` when a cheap fingerprint shows the
   source tables have moved (so a moderator approving a show doesn't wait for a redeploy). ~700ms cold,
   ~50ms when there's nothing to do. `build_productions.py` at the repo root is the CLI half (`--dry-run`
   verifies and rolls back). Every run ends with a verification pass that re-derives the totals from the
   database and raises rather than trusting its own write.
3. **Statistics cut over** (`info.py`'s `stats()`) - the first of the four staged surfaces. Five GROUP BY
   queries merged in Python became one query over `productions`; the region filter became a single
   equality test instead of the three-way COALESCE fallback join.

**Two century bugs this found, both real and both now fixed by construction:**
- `historical_results_year()` ('yy/yy' -> 2000+yy+1) can't express an award year before 2001 - 1912 came
  back as 2012, 2000 as 2100. 75 of the archive's 100 award years didn't round-trip, so **/stats reported
  0 productions for every season before 00/01** while the same page's own tile said "1912-present". The
  headline total goes 1,837 -> 2,711.
- `season_start_year()`'s pivot at 50 assumed the archive starts in 1977. It starts in **1912**, so 9
  pre-1950 award years filed under a modern season that also exists for real. Both helpers now carry a
  docstring saying exactly what they're safe for; anything spanning the full archive uses the new
  `award_year_to_season_start` / `season_label` pair and a four-digit year.

**Real-data verification** (read-only copy of the live db, `scp`'d down): 2,805 productions spanning
1911-2027 - 1,242 with a shows row, 2,271 with an award record, 708 both; region resolved for all but 18;
rebuild idempotent (second run: 0 new, 0 changed, 0 removed). Every unlinked source row is one that names
no production (145 title-TBA placeholders, 172 award records with a blank show column, 74 reviews still in
the moderation queue). /stats renders in ~35ms against that copy.

**Presentation decision Darragh made this session:** the 1911-1976 seasons (98 productions across 51
seasons, 1-4 each, from only Wexford Light Opera / Roscrea / Carrick-on-Suir) fold into **one labelled
summary row** rather than 51 near-empty ones - see `ARCHIVE_CIRCUIT_START_YEAR` in `constants.py`. Nothing
is hidden; the total still includes them.

**Stage 2 done 2026-08-22 (admin counts), not yet deployed.** `NEEDS_REVIEW_WHERE` in `admin.py` is now
the single definition of "this production has run and nobody has written it up", shared by the dashboard
counter, the shows-list `needs_review` filter it links to, and the Reviews queue. They disagreed before
(115 / 115 / 29 against real data) - the queue was the right one, the other two were season-based and so
counted 86 shows that hadn't happened yet. All three now say 29. `_duplicate_historical_rows` matches on
`production_id` instead of comparing a show's opening *calendar year* to the award year (never true for an
autumn production, never true at all for a dateless skeleton row): 0 duplicates found before, **9 real
ones now** - bulk-added rows for productions that already have a shows row, all from the four backfilled
societies. `awards_pending_season` uses the shared `historical_results_year()` rather than its own inline
copy. 12 new tests, full suite 455 green.
- One thing checked and found NOT to be true, recorded so it isn't re-claimed: reading the review through
  `production_id` rather than `show_id` returns the identical set today, because a production only ever
  has one shows row (the rebuild's verification enforces exactly that). It's written that way because it's
  the question actually being asked, not because it changed a number.
- Any route reading `production_id` must call `productions_build.ensure_current(db)` first - four do now
  (dashboard, shows_list, reviews_queue, data_quality). Forgetting it doesn't error, it silently
  under-reports; that's how the data-quality test caught it.

**Venues given a real record, 2026-08-22 (`00797c8`), deployed and confirmed live.** Separate workstream from the
productions migration but built on the same pattern. `venues` + `venue_aliases` + `shows.venue_id`;
`app/venues_build.py` rebuilds on start and lazily. 177 free-text spellings → 166 venue records (the same
building was recorded up to 8 ways). Identity is `normalize_venue()` and nothing looser - a rule loose
enough to merge "Civic Theatre Tallaght"/"Civic Theatre, Tallaght" also merges the Galway, Ballinasloe and
Claremorris Town Hall Theatres, checked against real data. Anything beyond that is a moderator merge at
`/admin/venue-directory`. Region seeds from the productions staged there (158 of 177 resolve outright);
town parses from a comma suffix (67 of 177).
- **Darragh's scoping call:** structure + location now, spec fields drip-fed. Fields built: capacity,
  auditorium type, lat/long, website, tech-spec link. Each renders only once set. **Deliberately not
  built:** orchestra pit, fly tower, box-office phone.
- **Merge queue worked 2026-08-23**: 28 unique suggested pairs triaged (15 confident + 4 more that
  `merge_candidates()` itself never surfaces - it skips a pair outright when the two names strip to
  *exactly* equal distinctive words, which hid "An Táin Arts"/"An Táin Arts Centre" and similar). 15
  merges applied directly to prod (161 venues -> 146), each carrying forward any curated field the
  losing spelling had. 8 pairs left genuinely distinct (the "Town Hall Theatre" cluster still
  conflates Galway/Ballinasloe/Claremorris - real, not a bug) and 5 unsure, not applied. Also applied:
  2 of the 4 `backfill_2627_venues.py` CONFLICTS rows that don't collide with a merge just made
  (Thurles' Premier Hall, Leixlip's St. Mary's GAA Club Hall); 2 more skipped on purpose (An Táin/
  O'Reilly Belvedere text switches would have re-fragmented the venue just consolidated); 2 of the 16
  CONFLICTS still need Darragh directly - Bellvue's "Cork run" and Trim's "40th Anniversary" aren't
  real venues on record at all, and Gemini's research names more than one candidate for each.
- **Still to do:** capacity/type/website/map research (0 of 146 venues have any of it filled in - the
  fields render already, nobody's entered data yet).
- **Waterford Musical Society's bad `default_venue` fixed 2026-08-23** - Darragh spotted Gorey Little
  Theatre showing wrong productions; root cause was `societies.default_venue` (id 125) wrongly set to
  `'Gorey Little Theatre'`, which had fed 10 bulk-created historical show rows (all one 2026-08-19
  import batch). Cleared both the `default_venue` and the 10 rows' `venue`/`venue_id`, plus one
  unrelated single-row case on the same venue (Headford Musical Society, uncorroborated, blanked
  rather than guessed). Confirmed live - neither society appears on `/venues/gorey-little-theatre`
  any more. Swept every other society's `default_venue` against its own shows for the same bug
  pattern; found no other confirmed instances. **Follow-up, not done here:** research Waterford
  Musical Society's actual venue (Theatre Royal, Waterford is a plausible real-world candidate but
  wasn't confirmed against data, so nothing was written in).
- **Mockup built 2026-08-23**, alongside a Show enrichment (circuit intelligence) mockup on the same
  page: https://claude.ai/code/artifact/cbe72116-066d-4594-96a8-94a99b2500fd - a fully-enriched venue
  page (National Opera House, Wexford: capacity/type/website/map clearly flagged as illustrative
  placeholders, everything else - productions, residents, stage history - real) and a title's "About
  this show" circuit-intelligence panel (Jesus Christ Superstar: 51 wins/97 nominations/2 Best Overall,
  signature category, regional distribution, all real queries against `productions`/`historical_results`
  - this is Source C from `SHOW_ENRICHMENT_PROPOSAL.md`, free and buildable now) plus a revival-watch
  aside using a genuine example (Show Boat, 25 productions 1976-2013, none since) rather than the
  proposal's own "Geisha, last staged 1948" dead-show trap. **Darragh approved the mockup 2026-08-23.**
- **Show circuit intelligence: BUILT AND SHIPPED 2026-08-23** (`app/circuit_intelligence.py`,
  `public.py`'s `title_detail()`, `title_detail.html`) - award tally, Best Overall Show wins, signature
  category (folded through `AWARD_CATEGORIES`'s renamed-category groups), regional distribution across
  all 6 regions, and a per-title revival flag (`>=8` productions, 10-30 year gap, checked against the
  real archive). One real deviation from the mockup: the revival aside runs against the page's own
  title, not a different illustrative one - a title talks about itself. Caught via an actual screenshot
  during the build: the panel was originally placed after the "Since 23/24"/"Earlier history" tables per
  the plan's literal instruction, which buries it below 50+ rows on a long-running title like JCS -
  moved before those tables, matching how the mockup had it laid out in the first place. No new CSS -
  every element reuses existing site classes. 15 new tests, full suite 506 green. Verified against real
  local data (JCS renders the full panel; a zero-award title renders the page with no panel, not an
  empty one). Venue enrichment (the mockup's other half) stays parked - needs real capacity/coordinate
  research first, which isn't a coding task.
- Old `/venues/<raw name>` URLs 301 to the slug.

**Next, in order (stages 3-4 of the staged cutover):**
- **Public show/society pages** (`public.py`) - last, highest traffic. `reviews_index()` is the most
  useful worked example in the codebase of the problem this table solves (it unions `shows` and
  `historical_reviews` and reconciles adjudicator identity across both); `venues_index()` is the example
  of the split forcing a feature to be thinner than the data could support.
- Only after all four: consider making the table **authored** rather than derived (a moderator editing a
  production directly). Deliberately not part of the additive pass.
- Two small data findings to act on separately: `'Greenhills Variety Group'` and `'New Lyric Operatic
  Company, Belfast'` appear in `historical_results` with no `society_id` even though a matching societies
  row exists; and 13 award-archive productions have no society name at all (they group under a single
  "Unknown society" bucket).

Everything below this line is earlier context, kept as background.

**Update 2026-08-21: Decades Time Machine, Reviews, and Venues are all live for real** - committed, pushed,
deployed, and independently verified running in production (not just the `/suggestions` timestamp - actually
grepped `stats_trends`/`reviews_index`/`venues_index`/`reviews_queue` markers inside the running `aims-web`
container's code, and confirmed `GET /stats/trends` returns 200 from inside the container). Darragh's
Portainer redeploy briefly looked stuck/erroring from his side; turned out to just be Portainer mid-cycle
(container legitimately stopping/recreating/starting) - nothing was actually wrong, no action needed.

**Decades Time Machine** (`/stats/trends`, `info.py`'s `stats_trends()`) - grounded in the awards archive
(`historical_results`, 1912-2026), not the thinner `shows` catalogue. A decade-scrubber pill row (GET
`?decade=1980`, no JS) picks one decade; its era card shows top 5 most-staged shows (deduped to distinct
(show, year, society) productions, not raw nomination rows), top 5 most-nominated societies (raw nomination
count, deliberately not deduped), and every Best Overall Show winner that decade. Default decade is the
current one if it has data, else the latest that does. Linked from `/stats` as a prominent clickable banner
(moved there after Darragh flagged the first version - a small inline text link - as "feels hidden"). 10
tests in `tests/test_stats_trends.py`.

**Reviews** (public `/reviews` + admin `/admin/reviews-queue`) - `public.py`'s `reviews_index()` merges two
eras into one list (AIMS's own aims.ie link-out reviews and the extracted ShowTimes archive full text), same
`source`-tag pattern already used on an adjudicator's own page. A show/society search matches across every
season and tier by default - the season/tier/adjudicator dropdowns only narrow it, never implicitly scope it
(the specific fix requested after the first mockup draft). Adjudicator credit is direct for a full-text
review, inferred via `adjudicator_assignments` for a link-out one (only when exactly one adjudicator covered
that season/tier - never guessed across a recorded mid-season change). Default browse view groups by season
(collapsed `<details>`, 2 most recent open - same pattern as an adjudicator's own reviews list) rather than
paginating; a full mockup detail (a "Page 1 of 44" footer) wasn't carried over since it was a rough
placeholder, not a reasoned part of the design. New "Reviews" nav link (site-wide) + `/more` entry. Admin
queue (`admin.reviews_queue()`) lists every already-finished, non-"Not adjudicated" show with no review link
yet (closing_date-based, deliberately more precise than the existing season-based dashboard "needs review"
counter, which was left untouched) - paste-and-save per row, same shape as Society name corrections, plus a
"Mark not adjudicated instead" action. Linked from the admin dashboard's Tools grid. 14 + 12 tests
(`tests/test_reviews_index.py`, `tests/test_admin_reviews_queue.py`) - one pre-existing test
(`test_show_detail_review_adjudication.py`) had to be rescoped to the page-content area, since it asserted
"Review" never appears anywhere in the page and the new sitewide nav link broke that assumption. Full suite
392 tests, all green.

**Venues fixed twice post-launch, 2026-08-21** - Darragh caught both from the real deployed page within
minutes: (1) it was only linked from the mobile-only `/more` page, no desktop path existed at all - "code
verified running" isn't the same as "verified reachable"; fixed by adding it to the footer (the actual
thing that makes Adjudicators desktop-reachable, which is what I'd meant to match but got wrong). (2) the
index sorted alphabetically, which put real free-text noise ("40th Anniversary (March run)", a data-entry
slip) at the very top as the first thing anyone saw - now sorts by production count instead, so the real,
recognizable venues lead and the noise sinks down (still there, not hidden, just not first impression).
Both pushed in a follow-up commit, 2 new tests, full suite 406 green.

**Venues** (public `/venues` + `/venues/<venue>`) - deliberately the **thin version**, per Darragh's explicit
call when asked: no capacity/type/map fields at all (that structured data doesn't exist anywhere in the
schema - `/admin/venues` is just a per-society free-text `default_venue` backfill, not a real venues table).
`public.py`'s `venues_index()`/`venue_detail()` compute everything live from `shows.venue` - production
count, resident societies (ranked by production count), stage history, and an "Upcoming here" table (reusing
`shows.is_upcoming()`). Exact string match only, same "not fuzzy" policy as title matching elsewhere on the
site (real messy data confirmed working as designed: "Aghada" shows up as its own 1-production venue,
untouched rather than guessed at). `historical_results` has no venue column at all, so this is necessarily
scoped to the `shows` table (05/06 on) - pre-05/06 venue history doesn't exist to show. Only linked from
`/more` (not the main nav, which was already at 7 items after Reviews - same treatment Adjudicators gets).
**Building the full data-model version (a real `venues` table + admin form + ongoing manual backfill of
~140 venues) is still an open, undecided commitment** - this thin version was explicitly chosen instead for
now, not a placeholder for it. 12 tests in `tests/test_venues.py`. Full suite 404 tests, all green.

**2 mockups still waiting on a coding pass**, links saved below so they survive a `/clear` (Artifacts are
private to Darragh's account until shared, not secret, but still don't paste these anywhere public):
- Shows A-Z redesign: https://claude.ai/code/artifact/8748ee86-2422-4df3-aae6-7ee5973bc5c3
- Society head-to-head compare: https://claude.ai/code/artifact/a3b6ce5c-1bbc-4eb3-aea9-8f480a51e209

Neither has been applied to real templates/routes yet. Per-feature scoping decisions made while mocking are
recorded in each feature's own bullet below. Next session should either build one of these 2 for real or
gather feedback on the mockups first if Darragh hasn't reacted to them yet - to update a mockup with
feedback, republish the same Artifact URL (via the Artifact tool's `url` param) rather than creating a new
one, so the links above stay correct.

## (original framing below, kept for context on how this pass was run)

**2026-08-20 was a long, productive session** - full detail of everything shipped/fixed/investigated is
in the "Open items" list below (search for "SHIPPED 2026-08-20" to find each one) rather than repeated
here. Quick summary: 8 society misattributions resolved, 5 search bugs fixed, Society Milestone Badges
shipped, two small society-dashboard UX fixes shipped, the season calendar UX mockup built/approved/
applied, 28 review links backfilled from aims.ie, and the reviews-page feature scoped.

**Darragh's explicit instruction for next session: mockup-only, do NOT commit code.** Work through the
"big features" list below one at a time - question him first (same interactive style that worked well
all through 2026-08-20 - AskUserQuestion, not assumption), *then* build a mockup (published Artifact,
real site tokens per `artifact-design`/established convention, grounded in real production data where
possible - the pattern used for the badges and season-calendar mockups this session). The explicit goal
is to see how the features would all look and feel *together* as one cohesive design pass, not each one
built in isolation. No template/route edits, no commits, until he says otherwise.

**Big features to mock up, in the order they were prioritized (2026-08-20's triage - not rigid, ask if
priorities have shifted):**
1. **Reviews page** (public + admin) - scope already settled, mockup built 2026-08-20 (see its own entry
   below). Search/filter iterated once on feedback - default search now crosses every season/tier rather
   than being scoped by whatever the dropdowns happen to show, and an adjudicator dropdown + reviewer
   name were added per-row (both filter rows and search results).
2. **Decades Time Machine** (`/stats/trends`) - scoped 2026-08-20. Build on the **awards archive
   (`historical_results`), which actually spans 1912-2026** - not the `shows` catalogue, which only
   covers 05/06-27/28 (~22 years, too thin for the original "50 years of evolving taste" pitch). Era
   breakdowns/decade leaderboards should read off real award nominees/winners across that full span.
3. **Venues Explorer** (`/venues` + `/venues/<slug>`) - scoped 2026-08-20. There's no capacity/stage-type/
   tech-spec/map data anywhere in the schema today - not just missing venue names (905 of 1387 shows have
   no `venue` value at all; 395 excluding historical skeleton rows - the "~88" figure previously logged
   here was stale/scoped differently and shouldn't be trusted). Darragh's call: mock the **full aspirational
   vision** anyway (capacity, stage type, map, resident societies) with realistic placeholder data clearly
   flagged as not yet collected, to see the destination before deciding whether to commit to gathering it -
   this is the biggest new-data commitment of the four, more than a page-design question.
4. **Shows A-Z redesign** (`/titles`) - `mockups/1_titles_az_mockup.html` (Gemini Antigravity's own
   prototype, referenced from `FEATURE_IDEAS.md`) does exist in-repo, but uses its own invented design
   tokens (`--font-display`, `--gold`, `--bg-card`...), not the real site's CSS. Darragh's call: take its
   ideas (alphabet scrubber, staples carousel, revival-candidate/rare-gem filters) but rebuild in real site
   tokens grounded in real title-staging data, same treatment as every other mockup this pass.
5. **Society head-to-head compare** (`/compare`) - scoped 2026-08-20. Entry point is a "Compare" picker
   from each society's own page (pick society A's page, click Compare, search for society B) rather than a
   standalone page with two search boxes - stays a strict 2-society comparison, not multi-way. Trophy
   counts, shared repertoire, and clash log (same category/year in `historical_results`) all have real data
   behind them already.

**Not mockup candidates** (no UI, or too small to warrant this treatment) - **productions-table
migration** (backend architecture, flagged for its own Opus session separately) and **review-author
byline** (a column + small form + template tweak, design questions already resolved - just build it
directly when its turn comes, doesn't need a big mockup pass).

**Header nav restructured 2026-08-23, deployed and confirmed live.** Mockup-first (interactive drag-and-drop
builder, `https://claude.ai/code/artifact/7a1c3f2c-f360-4ba2-a674-d9b79f79e9a9` - Darragh arranged it
himself rather than picking from options). Final shape, his call: **Home** as a direct link, then
**Explore** (All Shows, Seasons, Societies, Venues, Reviews, Adjudicators) and **History** (Awards,
Decades, Statistics). "Shows A-Z" renamed "All Shows" throughout; the footer keeps its sitemap links
for All Shows and Seasons as well. `/more` regrouped under the same headings.
- Native `<details>`, the same disclosure used on /stats and /season, so the menus need no JS. The
  nonce'd script only adds close-on-outside-click and Escape. No new dependency, no CSP change.
- Venues and Adjudicators are in the header for the first time - they were footer-only, which is why
  they had 6 and 52 views.
- "Upcoming shows" is gone as a nav item: `/` **is** that page and the logo already links there.
- 3 tests including one asserting every pre-existing destination is still linked from the chrome, so
  a future regrouping can't silently drop one. Full suite 491 green.
- **Traffic can't be used to justify nav decisions** - Darragh's catch, and he's right: pages get
  views because they're in the nav, so citing those numbers to decide what belongs in the nav is
  circular. It was used in the first draft of this work and withdrawn. The only honest signal in it
  is that footer-only pages are invisible.
- **Polish pass 2026-08-23**: Darragh called it "a bit sketchy" - not the dropdown mechanism, but
  mismatched button styles and flat spacing in the account cluster (Society login/Admin/Log out/theme
  toggle sat as three different affordances - plain link, bordered box, plain link - in the same flat
  row as the content nav). Split into `.nav-content`/`.nav-account` with a wider gap between them and
  one shared `.nav-pill` shape for every account control, Admin keeping its gold color as the one
  moderator-only distinction. Checked signed-out/signed-in, light/dark, and a narrow width via headless
  Edge screenshots before shipping. No change to the dropdown/chevron styling.
- Deferred deliberately, still wanted: the type/palette pass (needs a self-hosted display font) and
  the per-page component pass. Both wait on **posters** - 41 exist in total, 13 for 25/26 onward
  against 193 shows, so a poster-led design would be mostly empty frames. Gathering artwork from
  societies is the real bottleneck on the site looking better.

## Technical debt, measured 2026-08-23

Real numbers, not impressions. Nothing here is urgent; the first two are the ones that will actually
bite.

1. **DONE 2026-08-23.** `app/blueprints/admin.py` (3,325 lines) is now `app/blueprints/admin/`, a
   package split by concern (auth, dashboard, shows, invite_codes, societies, venues, misc, duplicates,
   reviews, awards, adjudicators, historical_reviews - plus a `_shared.py` for cross-cutting helpers).
   Pure structural move, no endpoint names or route logic changed. Full suite green (491) both inside
   the split's own worktree and again after merging to main. Next biggest file is now `public.py` at
   1,422 lines - not touched, not urgent.
2. **`ensure_current()` is a call site you have to remember.** 8 of them now across `admin.py`,
   `info.py` and `public.py`. Any route reading `production_id` or `venue_id` must call it first;
   forgetting doesn't error, it silently under-reports - which is exactly how the data-quality page
   shipped wrong for ten minutes. Worth replacing with a `before_request` on the blueprint, or a
   decorator, so it can't be forgotten. Small change, real payoff.
3. **`productions_build.py` and `venues_build.py` duplicate the same freshness machinery** -
   `FINGERPRINT_SQL`, `fingerprint()`, `mark_stale()`, `ensure_current()` and a one-row
   `*_build_state` table, written twice with different table names. A third derived table would make
   it three. Worth folding into one small shared helper, and it pairs naturally with item 2.
4. **FTS indexes rebuild on every startup.** Known, deliberate, and documented in `db.py` - the
   obvious `COUNT(*)` guard doesn't work on an external-content FTS5 table. Left alone on purpose;
   noted here so it isn't "discovered" again.
5. **`page_views` is keyed on path only**, so no query-string question can ever be answered from it
   (`/reviews?season=X` collapses into `/reviews`). Fine as a popularity counter, useless as
   analytics. Only worth changing if a real question needs it.
6. **DONE 2026-08-23.** The test suite took ~2m15s for 491 tests, serially - no individual test was slow,
   just per-test fixture overhead (fresh app + sqlite file) on an idle 16-core box. `pytest-xdist` +
   `addopts = -n auto` in `pytest.ini` cuts it to ~40s, confirmed stable across several runs.
7. **Four untracked `.md` files sit in the repo root** (`DESIGN_AUDIT_AND_PROPOSALS.md`,
   `FEATURE_IDEAS.md`, `SHOW_ENRICHMENT_PROPOSAL.md`, `venues_report.md`). They're source documents,
   not repo content, and they've been deliberately left untracked - but they show up in every `git
   status`. Either commit them to a `docs/proposals/` folder or add them to `.gitignore`, rather than
   leaving them in limbo. (`mockups/` is already gitignored.)

## What's left, roughly in the order it makes sense

- **Deploy the nav** (and the venues work, if it hasn't gone out).
- **Venues finishing**: work the 51-venue merge queue in `/admin/venue-directory`, then research
  capacities. No code needed for either - and the page improves with each merge.
- **Productions stages 3-4**: public show and society pages. `reviews_index()` is the best worked
  example of the problem in the codebase; `venues_index()` no longer is, now that venues has its own
  table.
- **Show/title enrichment** - `SHOW_ENRICHMENT_PROPOSAL.md`. Source C first; it's free and works
  today. Fix the `P58` -> `P87` error before touching the Wikidata half.
- **FAQ page** - smallest self-contained thing on the list.
- **Posters** - Darragh's, not Claude's. 41 exist against 193 current-era shows, and this gates the
  whole visual redesign.
- **Type/palette pass, then per-page components** - Phases B and C of the nav plan, waiting on
  posters.
- **Reviews page: a show dropdown instead of season grouping.** Note the traffic data can't settle
  this (see `page_views` above) - it's a judgement call.

## Newly raised 2026-08-22, not yet scoped

Darragh's own list, plus two documents Gemini Antigravity dropped in the repo root the same day. Nothing
here is started. Recorded verbatim enough to pick up cold; triage still to happen.

**Darragh's list, as given:**
- **Venues** - map, specs, who uses them, upcoming musicals there. (Structure is now built, see above -
  what's left of this is the map render, the spec research, and the merges.)
- **FAQ page** - what is AIMS? how do I join a musical society? which ones are near me? (There's already a
  parked "FAQ page" item further down; this is the same thing with real questions attached, which is what
  it was missing.)
- **Show page** - info, credits, and: which societies have staged it recently (they may have costumes/sets
  to rent), and which are staging it soon (dates, links to each production's page).
- **Refined nav bar.**
- **New UI pass - evolve it.**
- **Reviews page** - a *show* dropdown instead of grouping by season. Darragh's reasoning: he doesn't
  think people look for a specific season's reviews. Worth checking against `page_views` before rebuilding
  the default view on an assumption.

**`SHOW_ENRICHMENT_PROPOSAL.md`** (repo root, untracked) - enrich `/titles/<title>` with creative credits,
notable songs, casting/orchestration specs, and AIMS circuit intelligence. Reviewed 2026-08-22, verdict
below; not started.
- **Its Source C (circuit intelligence) is free and works today** - award tally per title, signature
  categories, regional distribution and revival gap are each one query against `productions` now. Ran all
  of them against live data while reviewing: JCS 51 wins / 160 records / 2 Best Overall; West Side Story 4
  Best Overall. This is the part to build first.
- **Its Source A (Wikidata) is feasible but its SPARQL is wrong as written.** `wdt:P58` is *screenwriter*
  (verified on Wikidata) - a musical's book author is `wdt:P87` (librettist), whose own docs say exactly
  that. The query also chains composer/lyricist as mandatory triples, so any musical missing either in
  Wikidata drops out entirely; they need `OPTIONAL`. Scope is 306 distinct titles, of which only 48 have a
  `show_links` row - and every one of those 48 is a Wikipedia URL, so those 48 can resolve to a Wikidata
  item reliably. The other 258 need title matching, which is exactly the fuzzy-matching this repo avoids.
- **Its Source B (licensing-house specs) is not a pipeline.** MTI/Concord/TRW have no public API, and
  vocal ranges live in paid perusal materials. Treat as manual data entry, priced accordingly: 113 titles
  are staged 5+ times, 100 exactly once.
- **Answers to its three questions:** (1) `notable_songs` should be a normalized `show_songs` table, not
  JSON in a TEXT column - the site already has FTS5, and a real table makes a song title searchable
  ("who's done Gethsemane"), which a JSON blob can't. (2) Yes to a seed script for licensing houses, but
  it's data entry, not import. (3) On the fly, no caching - confirmed by running the queries.
- Its revival-gap idea needs a floor: the query's top hits are "The Geisha, last staged 1948", which is a
  dead show, not a revival candidate.

**`DESIGN_AUDIT_AND_PROPOSALS.md`** (repo root, untracked) - nav overhaul, design-system upgrade, and four
feature proposals. Not reviewed in depth yet. Overlaps heavily with Darragh's own list above (nav bar, UI
pass) and with already-tracked items (My Season watchlist, Ireland map, On This Day - all already in the
Gemini audit backlog in `ROADMAP_ARCHIVE.md`). **Its `mockups/` prototypes do exist** (12 files, checked -
unlike the last time a Gemini doc cited a path). One thing in it is factually settled and should not be
re-litigated: it says the society head-to-head compare was "explicitly rejected" as against AIMS's
collaborative ethos - Darragh actually scoped and approved that feature and a mockup exists
(`a3b6ce5c-1bbc-4eb3-aea9-8f480a51e209`), so that claim is the document's own inference, not a decision.

## Open items

Flat list, no particular order beyond roughly how it was prioritized when last discussed. Full
reasoning/history for any of these is in `ROADMAP_ARCHIVE.md` if needed - search there for a keyword
before re-deriving from scratch.

**Season calendar UX feedback - SHIPPED 2026-08-20.** Mockup-first (published Artifact, real tokens/
production data), iterated once on feedback, then applied to `app/templates/season.html` /
`info.py`'s `season_summary()`. Season calendar is now a `<details>` disclosure (open by default,
closed on a past season, same native element already used on /stats), a grouped Future/Current/Past
season dropdown replaced the inline "Jump to:" list (sorted by real `season_start_year`, not a plain
string DESC - the archive now spans the 1999/2000 rollover), past-season copy switched to past tense,
and the sort toggle + "Hide cancelled shows" filter were both removed. The cancelled-status question is
carried forward below, scoped narrowly for now (just this page's filter control removed - the
underlying `status='Cancelled'` data and the "Cancelled" tag shown elsewhere on the site are untouched).

**Cancelled-show data reliability - not investigated.** Darragh: the `status='Cancelled'` field "has
been inaccurate anywhere I found it." Only the season calendar's filter control was removed in response
(above) - whether the underlying data needs a real fix, and whether the "Cancelled" tag shown on
chips/rows elsewhere (society pages, admin) should stop rendering until it's trustworthy, is still open
and deliberately not decided or investigated yet.

**Reviews page, both public-facing and admin-side - SHIPPED 2026-08-21.** See START HERE for the real
implementation detail. Nav question resolved: "Reviews" is now a real top-level nav item.

**Society misattribution follow-ups (from the 43-fix session, 2026-08-20):**
- **6 of the 8 remaining cases resolved and applied live 2026-08-20** (`fix_society_misattributions_2.py`,
  same dry-run/test-apply/apply-for-real/independently-reverify discipline as the original 43) - going
  back to each society's own official award-entry record (not just the review text) settled most of
  these: review 951 merged into the existing University of Limerick Musical Theatre Society (id 124,
  timeline evidence - 2019 founding, pandemic-delayed debut, id 124's own earliest record one season
  later); review 440 repointed to a newly-created "Greenhills Variety Group" (the original auto-gate
  suggestion "Civic Theatre" was wrong - Craic Theatre's own record already had its own separate,
  correctly-attributed production that season); review 595 repointed to newly-created "SONG Dundalk"
  (Darragh confirmed full name: Stage One New-Musical Group); review 673 repointed to newly-created "ESB
  Musical and Dramatic Society" (region Eastern is a flagged best-guess, stored in the society's own
  `notes` field rather than a schema change to the region CHECK constraint). Reviews 577 and 790 turned
  out to be **false positives** - both societies' own official records already had the exact show/season
  in question, dismissed on `/admin/society-corrections` rather than repointed.
- **2 left, explicitly skipped this session (Darragh's call):** review 367 (The Real Theatre Company -
  confirmed real via text, no region evidence anywhere, not on AIMS's current public list) and review 366
  (National Youth Musical Theatre - confirmed via "NYMT" acronym, but a touring/national group not tied
  to one AIMS region - needs its own structural decision, not a quick call).
- `extractor-society-gate` branch (`edd445e`) still unmerged - has its own known remaining gap
  (confuses "Newcastle Glees" with "Newcastlewest"). Needs that fixed before merging.
- Worth a fresh sweep for other near-identical-society pairs beyond what's already been caught - the
  Carnew/Clane pattern alone hid 5 misattributed reviews before the first proper cross-check.

**Search - RESOLVED, entry was stale (verified 2026-08-21).** All five bugs diagnosed 2026-08-19 have
since been fixed; this entry sat here claiming "not fixed" long after the work landed. Verified against
real data, not just by reading code - the original failing query ('april kelly') now returns Award
nominees as the *first* section, 2 genuine April Kelly hits, and zero "Jonathan Kelly" false positives.
Where each fix lives, for anyone re-checking: phrase search + per-token prefixes in
`app/search.py`'s `build_phrase_query()`; bm25 relevance ranking in `public.py`'s search route; the
promote-awards-to-top branch in `search.html` (`awards_exact_match`); cluster-centred snippets in
`public.py`'s `_review_snippet()`; smart/straight quote stripping via `_QUOTE_CHARS` before any LIKE
pattern is built. **Lesson worth keeping:** check whether an open ROADMAP item is actually still open
before scheduling work against it - this one would have wasted a whole session.

**Productions table migration - STAGE 1 DONE 2026-08-22, see START HERE.** Table, rebuild and the
Statistics cutover are built and verified in the `productions-table` worktree, unmerged. Stages 2-4 (admin
counts, then public pages) are listed there. The original scoping brief in `ROADMAP_ARCHIVE.md` ("Scoping
brief for the productions-table session") is now superseded for everything except its cutover ordering -
its figures were dated as it warned (it cited 788 skeleton rows / 371 unmatched; live data says 784 / 292
once matched season-aware rather than on society+title alone).

**OCR test on a programme photo** - blocked on Darragh sending one. Small once a photo exists (test
extraction accuracy first, design nothing before seeing real output).

**Venue-data gap** - down from 395 to 357 shows missing a venue (2026-08-21: `backfill_2627_venues.py`
applied 38 real venues for 26/27-season shows, sourced from Darragh's `venues_report.md` - Gemini
Antigravity's own research against the site's 26/27 season page). Not the ~88 originally logged here (that
figure was stale - see the earlier correction below). 16 more shows from that same report already have a
*different* venue on record and were deliberately left alone (see the script's own docstring/`CONFLICTS`
list) - worth a human look, one at a time, rather than either auto-applied or ignored:
- **Likely just needs picking one wording** (same real venue, differently detailed): shows 366, 386, 392,
  360, 399, 457, 410, 384, 426, 420, 406, 407, 421.
- **Worth actually checking**: show 385 (Bellvue Academy's Newsies - on record just says "Cork run", not a
  real venue name; report suggests "The Everyman / Firkin Crane / Strand Theatre") and show 398 (Trim MS's
  Sweet Charity - on record says "40th Anniversary (March run)", not a venue at all; report suggests "Swift
  Cultural Centre / Scoil Mhuire Hall, Trim").
- **Genuine disagreement, not just phrasing**: show 352 (Bravo Theatre Group's Dear Evan Hansen) - on record
  says "Temperance Hall, Loughrea", the report says "Town Hall Theatre, Loughrea" - two different-sounding
  venues in the same town, not a wording difference.
The venue-backfill tool (`/admin/venues`) also still exists for filling in the rest by hand.

**People/person-page identity resolution** - parked on Darragh's privacy objection to public person
pages. Agreed resolution path (internal-only dedup/matching, no public person pages) was never built.
Reaffirmed 2026-08-20 against Gemini Antigravity's `FEATURE_IDEAS.md` "Talent Directory" proposal -
Darragh likes the underlying idea (director/MD/choreographer profiles with accolades/collaborations)
but still only wants the internal-only version; the GDPR legitimate-interest argument for a *public*
version was considered and didn't change his mind - the objection was never about legality, it's that
the people involved may not want a page about themselves.

**FEATURE_IDEAS.md triage (2026-08-20)** - Darragh's been using Gemini Antigravity alongside this repo;
it dropped `FEATURE_IDEAS.md` (repo root) with 8 feature proposals, triaged together this session on his
actual gut read, not just cost/risk:
- **Wants to prioritize**: **Venues Explorer** (`/venues` + `/venues/<slug>` - capacity/tech specs,
  resident societies, stage history, map - sequence the venue-data backfill work around this as the
  real payoff, rather than filling gaps with no visible use) and **Decades Time Machine**
  (`/stats/trends` - era breakdowns G&S->megamusicals->pop/rock, decade leaderboards - fits naturally
  alongside the existing /stats rebuild).
- **Interested, not urgent**: **Shows A-Z redesign** (`/titles` - alphabet scrubber, staples carousel,
  revival-candidate/rare-gem filters - check whether `mockups/1_titles_az_mockup.html` referenced in
  the doc actually exists or Gemini invented the path), **Society head-to-head compare** (`/compare` -
  trophy counts, shared repertoire, direct clash history).
- **Not interested**: Instagram/social-card generator (`/shows/<id>/card`).
- **Duplicate, not new**: programme cover gallery (`/gallery/programmes`) - same idea as the
  already-parked historical-posters gallery page below.
- **Society milestone badges - SHIPPED 2026-08-20.** Mockup-first (published Artifact, real site tokens,
  grounded in real production data), iterated once - Darragh didn't like the originally-proposed Gilbert
  Grandmaster badge (icon clashed with the existing trophy case's own 🏆), asked for alternatives instead
  of just dropping it. Ended up with 7 live badges: Century Club, Triple Crown, The Clean Sweep, Golden
  Jubilee Society, Dual Tier Champions, The All-Rounder, Debut Delight - all computed in
  `_society_badges()` (`app/blueprints/public.py`), rendered on `/societies/<id>`. Gilbert Grandmaster
  itself is parked, not built - can be activated later if wanted after all.

**Review-author byline** - a `review_author` column + admin form + template change, discussed but never
built. Both design questions that were blocking it are resolved (2026-08-20): backfill existing reviews
(not forward-only), authorship is per-person (not per-publication, despite the free-text-name fragility
that already dogs the parked person-identity work above - accepted knowingly, not overlooked). Just
needs building now.

**`/admin/duplicate-titles` UX redesign** - Darragh asked for mockups specifically at one point, later
called the underlying issue "not really an issue" when a real mockup existed. Parked, low priority.

**Junk skeleton-show-title cleanup** - 8 garbled titles fixed from the same truncated-extraction bug,
but a fresh full-archive sweep for more instances (the fix pattern's match threshold might miss some)
was flagged as worth doing and never run.

**Skeleton-show fill-in and double-count check - SHIPPED 2026-08-20.** Turned out the skeleton-show
fill-in "gap" was already solved mechanically (dashboard/edit already allow it, no source filter
anywhere) - just needed discoverability, so a skeleton show missing a venue now shows "Has a review -
add details" / "Add details" instead of a plain "Edit". The double-count question got a real yes: the
self-service "add a show" form now warns (same soft-warn/confirm-checkbox pattern as the existing
near-duplicate-title check) when this society already has an award-archive record for the same season
under a matching title (`similarity.find_award_record_match`).

**~112 stale orphaned `historical_reviews` rows** - cross-referenced as real, but explicitly not deleted
pending a more rigorous verification method than what was used to find them.

**`match_show_for_edit` never fuzzy-matches** against `shows` (exact match only) - a systemic version of
a title-mismatch bug already fixed once for a specific case, not yet generalized.

**19 of 23 researched societies' online production archives not yet backfilled** into the database
(research inventory exists, only 4 done so far).

**Parked, each wants its own dedicated session, none started**: a browsable historical-posters gallery
page; costume/prop rental listings; a staging/test environment; a FAQ page; edit-history/versioning
with revert for society-editable data; a pantomime award category.

**Housekeeping, low priority, no urgency signal**: audit other societies for similarly stale/presumptive
data (same shape as the venue-gap and 179/127-copy fixes already done); a formal `LAUNCH.md` spec
(the site launched organically instead - worth writing up retroactively at some point, never has been);
real image-content validation on poster uploads (would need Pillow, not built); periodically verify the
nightly backup actually restores cleanly (recurring, not a one-time deliverable).

## Working agreements (from the 2026-08-03 process review)

- `/clear` (or a fresh session) between genuinely distinct workstreams -
  don't chain unrelated incidents/features/audits in one long thread.
- Mockup-first for anything visual - already working well, keep doing it.
- For a sweep touching many files (like Phase 0's audit), write the plan
  and get sign-off before editing, rather than fixing things as found.
- Lessons that matter beyond one session go in `docs/`, not just chat -
  already the habit for this repo, keep it up.
