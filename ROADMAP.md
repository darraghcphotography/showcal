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

## START HERE - next session is the productions-table migration (agreed 2026-08-21)

**Next session's job, decided at the end of 2026-08-21: the productions-table migration.** Darragh picked
it explicitly and switched to Opus for it. It has its own entry in Open items below with the brief's
location and - importantly - what's changed since that brief was written. Do it in an **isolated
worktree**, additive-only first pass, staged cutover. Don't start it as a bolt-on to an existing session.

Everything below this line is the previous session's completed work, kept for context.

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

**Productions table migration - NEXT SESSION, agreed 2026-08-21.** Darragh picked this as the next piece
of work and switched to Opus for it; the plan is a **fresh session** (`/clear` first) in an **isolated
worktree**, additive-only first pass - not a same-session addition, per the brief's own step 5. Real
architecture decision (`shows`/`historical_results`/`historical_reviews` becoming one source of truth via
a `productions` table), touches most of the app's query surface, high blast radius if got wrong.

Full scoping brief (what exists today, proposed shape, backfill/verification plan, staged cutover order)
is in `ROADMAP_ARCHIVE.md` - search for "Scoping brief for the productions-table session". **Read it, but
treat its "what exists today" section as dated** - it says so itself, and two things have genuinely moved:
- `ux_shows_natural_key` **has since gained `COLLATE NOCASE`** (done 2026-08-20, see `schema.sql`'s own
  comment) - the brief predates that.
- **Three new features shipped 2026-08-21 that each add query surface over exactly these tables**, and the
  brief's step-1 inventory won't mention them because they didn't exist yet. All three must be in that
  inventory: `/stats/trends` (`info.py`'s `stats_trends()` - reads `historical_results` by decade),
  `/reviews` (`public.py`'s `reviews_index()` - **unions `shows` and `historical_reviews` and reconciles
  adjudicator identity across both**, which is the productions problem in miniature and probably the single
  most useful worked example of it in the codebase right now), and `/venues` (`public.py`'s
  `venues_index()`/`venue_detail()` - groups on free-text `shows.venue`, and is *only* scoped to `shows`
  because `historical_results` has no venue column at all - a real example of the split forcing a feature
  to be thinner than the data could support).
- Re-derive the brief's production counts (it cites 788 skeleton rows / 371 unmatched) against live data
  rather than trusting those figures - a stale-number correction already bit this file twice this session
  (the venue gap, and the search entry that claimed "not fixed" long after it was fixed).

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
