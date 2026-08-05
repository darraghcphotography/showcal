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

**Open questions before building:**
- Access: a dedicated adjudicator login, or a shared unlisted link (same
  pattern as the unadvertised `/submit/unlock` one-off form)?
- Does "colour coded" mean two colours (Gilbert/Sullivan) on a shared
  calendar, or two separate calendars?
- Worth surfacing danger weeks (e.g. 3+ shows opening the same week) with
  their own visual treatment, per the adjudicator's own example?

Flagged by Darragh as "may end up being a large side request" - mockup
first, own session, not started.

## Phase 2 - Data integrity sweep (next)
- [Pending: run `export_csv.py` against production](see Claude's memory -
  "pending-csv-export-refresh") to pull the North Wexford tier fix (and
  anything else manually corrected since) back into the tracked CSVs.
- Audit for other societies with similarly stale/presumptive data.
- Fold in the audit findings above: the "179 vs 127" copy fix and the
  changelog typo are both one-line content edits, cheap to bundle in here.

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
