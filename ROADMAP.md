# Roadmap

Tracks the current phase of work so a new session (after `/clear` or a fresh
start) can pick up where the last one left off without re-deriving context.
Update this file - don't just say the plan out loud in chat - whenever the
phase changes.

## Start here (updated 2026-08-19)

**Deployed state**: Round 27 (864-review verified extraction) and Round 28 (bulk-approve 500 fix,
two extraction bugs, matching against the older `historical_results` awards archive) are both
**live and confirmed deployed** (`/suggestions` read "19 Aug 2026, 12:16" after the Round 28 push;
`load_historical_reviews.py` was re-run against production - 1 inserted, 849 already loaded, 14
refreshed with corrected text, matching the full 864-review set). Darragh started actively
moderating the real queue live on production, which is exactly what surfaced Round 28's bugs in the
first place, then hit **one more real bug** using `/admin/historical-shows/title-check`: accepting
a suggested title for a skeleton show 500'd when that title already belonged to a *different*,
independently-existing show (a member submission entered separately from the review pipeline - see
"Round 28.1" note at the end of the Round 28 entry below for the full story and the fix). **That
fix (commit `0565a66`) is pushed but not yet redeployed** - the one specific stuck row
(Thurles Musical Society, "Ragtime" 17/18) was already fixed directly on production via SQL so
Darragh isn't blocked, but the *tool itself* will 500 again on any of the other ~34 remaining
title-check entries that hit the same collision pattern until this gets redeployed.

**A systemic gap worth investigating next session, not just this one bug**: the reason this
collision could happen at all is that review-approval (`match_show_for_edit`, used both when a
review gets approved and when a moderator edits one) only ever checks for an **exact** `show_raw`
match against `shows` - it has no fuzzy/near-title matching against *existing shows rows*, only
against the older `historical_results` archive (Round 28's `find_historical_results_candidates`).
That means the same failure mode (a review creates its own skeleton instead of linking to an
already-existing, differently-worded show) can still happen going forward for any of the ~700
reviews still pending, not just the one already found. Worth extending the "ready" category's own
check in `categorize_pending_reviews` to also run `find_historical_results_candidates`-style fuzzy
matching against `shows` itself (not just `historical_results`) before calling a review safe to
bulk-approve - see "Suggestions for future scope" below for the fuller shape of this.

**Immediate, no-build task**: finish hand-entering the 29 confirmed season/tier/adjudicator combos
(2009-2023) into `/admin/adjudicators` - Darragh had started this already. Full list is in Round 21
below.

**Step 4 pilot build (2026-08-18) - schema, extraction, and the moderation queue are built and
tested; not deployed.** Full session detail below the fold ("Round 24"). Short version:
- New `historical_reviews` table + `shows.source = 'historical'` (migration verified against a
  copy of the real `aims.db` - preserves every row/id exactly, idempotent). `extract_historical_reviews.py`
  pulls reviews out of the ShowTimes PDFs at `E:\showtimes archive` by *positioned* text blocks (not
  raw reading order) so photo captions and the Calendar section can't leak into review text - the
  adjudicator's sign-off line is what actually splits the page into individual reviews.
- Piloted on the 2022-2023 season (4 issues, 47 reviews, zero parse failures) - `/admin/historical-reviews`
  is a real moderation queue (Approve & publish / Edit fields / Skip), and an approved review with no
  matching `shows` row creates the "skeleton show" agreed in scoping. `show_detail()`/`show_detail.html`
  render the approved review text with its ShowTimes citation.
- **Correction to the pilot-season pick**: 2022-2023 was chosen expecting "most shows already exist,
  fewer skeleton cases" - wrong, since `SHOWS_COVERAGE_START_YEAR = 2024` means `shows` has *no*
  coverage at all before 23/24. Every one of the 47 pilot reviews needs a skeleton row. Not a
  problem in practice (it's exactly the mechanism this build exists to prove out, and it now has
  real test coverage), but worth remembering when picking language for how "clean" any given season
  will be - only 23/24 onward would actually have pre-existing `shows` rows to match against.
- **Stats-exclusion gap found and fixed the same session**: `/titles` and `/search`'s title-count
  queries could double-count a skeleton show against its own `historical_results` award record
  (most of `info.py`'s stats() leaderboards turned out to be naturally safe already - they filter
  on "has this happened by today", which a dateless skeleton show always fails). Fixed, plus two
  admin dashboard counts that would otherwise count a skeleton show's blank dates/review-link as an
  actionable gap forever. Proven with a real regression test (see Round 24 below), not added on faith.
- **Not built yet**: the adjudicator-page season-grouping refinement and the new `/reviews` search
  hub (the mockup's Pieces 1 and 2) - deferred past this pilot.

**Next build priorities, in order:**
1. **Step 4 - historical review import** - fully scoped as of the "Step 4 scoping session" below
   (2026-08-18): full review text public, shown on the show's own page; browse via adjudicator pages
   (Option A) + a new `/reviews` search hub (Option B); moderation-queue mockup accepted as-is
   ([admin grid + moderation queue](https://claude.ai/code/artifact/d206e4c8-c213-4370-900d-70df1c441db7)).
   Ready for its own build session - pilot on one small season end-to-end (Claude picks which) before
   running the full 920-review archive through. The extracted/verified data itself lives in a published
   report: [Showtimes Archive Report](https://claude.ai/code/artifact/2a9a4602-f06a-4906-a0a7-276fee40ad4a).
2. ~~Round 2 from the original site audit - Stats page reframing~~ **DONE (Round 23, 2026-08-18)** -
   see below. **Superseded almost immediately** - see item 2a, flagged the same evening.
2a. **Stats page needs a full rework, not another patch** - flagged by Darragh 2026-08-18, right
   after Round 23 shipped the reframing above. His words: the Award Explorer doesn't update when
   category/tier is changed, the whole page needs a refresh and re-planning with mockups, the
   information presented is messy, the leaderboards are "unhealthy", and Signature show doesn't add
   value. **Checked the Explorer bug directly against the live site before logging this**: the
   backend genuinely does respond correctly to `award_category`/`award_tier` changing (compared two
   real requests - Best Director correctly returns different names than Best Overall Show) - so
   this isn't a dead query, the fault is somewhere in the page's own interactivity. Two real leads,
   not confirmed yet: the Explorer's category/tier dropdowns sit in a *separate* `<form>` from the
   region/era filter (`stats.html`), so switching category silently drops any region/era selection;
   and/or a JS error elsewhere on the page could be stopping the `onchange="this.form.submit()"`
   handlers from firing at all in some browsers. Ruled out the PWA service worker (`sw.js` only
   caches `/static/` assets, HTML pages always hit the network) so it's not a stale-cache issue.
   **Next session**: reproduce the actual failure mode first (which browser/device, does *any*
   dropdown change work), then mockup-first per this repo's established pattern before touching
   `stats.html`/`info.py` again - this needs real re-planning (what "unhealthy" leaderboards and
   "messy" information mean in concrete terms, whether Signature show gets cut or reworked), not a
   quick fix bolted onto the existing layout.
3. Everything else in the long-standing backlog is unchanged: adjudicator planning calendar,
   remaining historical-production backfill (19 of 23 researched societies), edit history/versioning
   for society self-edits, costume/prop rental listings, a staging/test environment, the formal
   `LAUNCH.md` spec. See the "Parked" sections further down for detail on each.

**Step 4 scoping session - historical review import decisions (2026-08-18):** Planning only, no code -
reviewed both published mockups (admin grid/moderation queue, reviews page layout options) and got
Darragh's calls on the open questions before this becomes a real build session:
- **Full review text will be public**, same as a real archive - Darragh's explicit call, made aware of
  the copyright flag (the ShowTimes magazine states its own content is AIMS Ltd's copyright, and this
  site already carries a "not an official AIMS website" disclaimer). Not revisited/hedged - going ahead
  as full text, public.
- **The review text itself renders on the show's own page** (`public.show_detail()`/`show_detail.html`),
  not a separate `/reviews/<id>` page - folds in alongside the existing review-link/adjudication section
  where a show already has *something* review-related shown. Needs its own design pass during the build
  session (how it reads alongside the existing "Read the AIMS review" external-link pattern, which stays
  for recent/23-24-onward shows that only ever have a link, not extracted full text).
- **Browsing/discovery: Option A + Option B combined**, not the season-archive-style Option C.
  - **Option A** - refine the existing (admin-only today) adjudicator concept into a real public
    `/adjudicators/<id>` page grouped by season, with a tier toggle. (Public adjudicator pages already
    exist as of Round 20 - this is a refinement, not new ground.)
  - **Option B** - new `/reviews` hub: one searchable/filterable table (season, tier, adjudicator, free
    text over show/society), linking out to both the show's own page (full text) and the adjudicator's
    page.
- **Step 3's mockup (season grid with a substitute slot) is already superseded** - Round 22 built the
  real mid-season adjudicator grid. Only Step 4's moderation-queue mockup is still live guidance.
- **Step 4's moderation-queue mockup accepted largely as-is** - same shape as the existing submission
  queue (Approve & publish / Edit fields / Skip per review), with flags for "show/society need a check"
  and "no matching show on record" surfaced inline rather than silently dropped. Nothing to change here
  before building.
- **Still open, deliberately deferred to the build session itself** (per Darragh's call): which season to
  pilot end-to-end before running the full 920-review archive through - not pre-decided, Claude picks
  based on what's cleanest to verify once actually in that session, same reasoning as Round 21's
  feasibility check (started with the oldest, cleanest-text-layer issue rather than assuming).
- **Not yet scoped, worth flagging before the build session starts**: the new table's shape (own table,
  not `shows`/`historical_results` - review text plus a foreign-key-ish link to the matched show/society,
  season, tier, adjudicator, source issue) and exactly how it coexists with the existing
  `shows.review_status`/`review_url` fields (a link-only field for 23/24-onward shows that were never in
  the PDF archive, vs. full extracted text for pre-24/25 shows) - needs a first pass at build time, not
  guessed here.

**Step 4 scoping, continued (2026-08-18) - copyright resolved, a real gap found and answered:**
Published a [mockup](https://claude.ai/code/artifact/76dd6415-a1a8-4dcf-887f-26a69aea0909) of the show
page/adjudicator page/reviews hub pieces above; two corrections came out of Darragh's reaction to it:
- **Copyright isn't actually a concern** - Darragh is part of AIMS.ie and manages ShowTimes and the AIMS
  website himself now. The earlier "worth Darragh's own explicit sign-off given the site's own disclaimer"
  caution from Round 21 was write-once for third-party content; it doesn't apply here. The review credit
  becomes a plain citation - "Originally published in AIMS ShowTimes Digital Edition, Issue X, Month Year" -
  not a hedge.
- **Real gap found while mocking up "the show's own page": most reviews have no page to live on.**
  `show_detail()` only exists for real `shows` rows, and most of the 920 reviews are for productions no
  society has backfilled. Darragh's own answer, pointing at a live example (`/shows/1170`, a society's own
  self-backfilled 2011/12 show): **a moderator-approved review with no matching show creates a minimal
  "skeleton" `shows` row** (show/society/season/tier only) so a real page exists - same page type a society
  gets from backfilling their own history via their login, just moderator-triggered instead of self-service.
- **A second, independent bug surfaced while working that out**: the society self-service "add a show" form
  (`society.py`) already lets someone backfill *any* past season into `shows` with **no check against
  `historical_results`** for an existing award/nomination record on that same production -
  `SHOWS_COVERAGE_START_YEAR`'s entire job across every stats query is keeping `shows` and
  `historical_results` from double-counting the same production, and this path already has a hole in that
  assumption. Not yet confirmed whether it's actually bitten anyone in production (would need a live query
  to check) - flagged, not fixed, out of scope for this scoping pass.
- **Resolved**: a skeleton show gets a new `shows.source = 'historical'` (alongside today's
  `'import'`/`'submission'`), and every stats/leaderboard query explicitly excludes it -
  `historical_results` stays the one source of truth for counting pre-24/25 productions, unchanged from
  today. The skeleton row's only job is giving the review a real page to live on, never a second countable
  production.
- **Still open, not decided**: what happens when a society later logs in and fills real detail into a show
  that started as a skeleton - does it just become an ordinary `'submission'` row, or does something need to
  track "review-verified, detail added later"?

**Round 23 - Stats page reframing (2026-08-18):** Built directly (no mockup) since it reuses the
site's existing GET-param filter-form convention (same pattern as the region filter), not new UI.
- **Explorer headline reframed**: "Who's won the most?" -> "Explore any award category" - the
  leaderboard-picker mechanic itself already de-personalizes the "who's #1" framing per category;
  the headline was the last piece still phrased as a leaderboard.
- **New "Since 23/24" / "All-time" Timeframe toggle**, same GET-param/select pattern as the Region
  filter, applied to the Award Explorer and all six Leaderboards cards (most selected, most
  performed, most prolific societies, most award wins, most nominated-never-won, win-rate).
  **Defaults to "Since 23/24"** - a real (smaller, closer) set of numbers rather than the full
  58-years-of-Wexford-dominance picture, without hiding it: all-time is one click away and unchanged
  in what it shows. Reused `SHOWS_COVERAGE_START_YEAR` (already the site's "recent era" boundary) as
  the cutoff for every leaderboard query. Collapsed the old always-both "Most selected shows" /
  "Most selected shows, all time" pair of cards into one card driven by the same toggle, consistent
  with the other five.
- Test suite grew 225 -> 229 (`tests/test_stats_and_season_filters.py`: headline reframed, leaderboards
  default to recent-era, Explorer respects `era`, invalid `era` falls back to recent).
- Not deployed yet, same as Rounds 21/22 - Darragh can't reach Portainer remotely right now.

**Round 24 - Step 4 pilot build: schema, PDF extraction, moderation queue (2026-08-18):**
The first real build session on Step 4, following on directly from the scoping sessions above -
checkpointed with Darragh after each piece (schema, then extraction, then queue+public rendering)
rather than building the whole thing blind.
- **Schema**: `historical_reviews` (season, tier, raw show/society text as extracted, adjudicator_id,
  review_text, source_issue citation, matched show_id/society_id, a moderator-facing `flag`, its own
  moderation_status) plus `shows.source` gains `'historical'` for skeleton rows. SQLite can't ALTER a
  CHECK constraint, so the latter needed the same rebuild-the-table migration pattern as the earlier
  adjudicator_assignments fix - verified against a **copy** of the real `aims.db` (never the live
  file): row count and every `id` preserved exactly (public `/shows/<id>` links can't break), the
  migration is idempotent, and a fresh insert after migrating correctly continues the id sequence
  rather than colliding or resetting it.
- **`extract_historical_reviews.py`**: reads the PDFs directly from `E:\showtimes archive`. The key
  decision, per Darragh's explicit ask to keep photo captions out of review text and rely on the
  adjudicator's sign-off as the anchor: extract text as *positioned blocks* (`page.get_text('blocks')`,
  with bounding boxes) rather than raw reading-order text, and classify each block by geometry -
  a short block (1-2 lines) is a photo caption/page-furniture and gets dropped, *unless* it exactly
  matches one of the two adjudicator names for that issue, in which case it's kept as the review's
  sign-off. That sign-off line is what actually splits the page text into individual reviews (and
  identifies each one's tier, since AIMS assigns one adjudicator per tier per season) - confirmed
  clean by grepping the final extracted text for caption-shaped phrases ("cast of", "chorus of",
  "steals a selfie" etc.) and checking every hit was genuine review prose, not a leaked caption.
  The one page where an issue's Calendar section and a review's tail text were interleaved in the
  raw block list is handled by the same y-position-based approach (keep only blocks above the
  Calendar header's own y-position).
- **Piloted on 2022-2023** (4 issues: Nov '22, Feb '23, Apr '23, Autumn '23) - **47 reviews, zero
  parse failures**. Two real bugs caught and fixed while verifying, not just assumed correct: an
  adjudicator name was mis-paired with the wrong tier (a stray "ShowTimes" watermark line leaking
  into the header-parsing loop), and the very last review in an issue was silently dropped because
  its sign-off has nothing after it but end-of-string, not a trailing newline the split regex
  required. Society-name matching against the live `societies` table is exact-only (same
  deliberately-not-fuzzy convention as the rest of this site) - roughly half matched cleanly, the
  rest correctly flagged `needs_check` for a moderator to resolve via the queue's society picker.
- **`/admin/historical-reviews`**: Approve & publish / Edit fields / Skip, matching the accepted
  mockup shape. Approve on a review with no matching `shows` row creates the skeleton show agreed in
  scoping (`source='historical'`, minimal fields only) and links the review to it; Edit fields lets a
  moderator pick the real society from a dropdown and recomputes the match flag on save without
  approving. `show_detail()`/`show_detail.html` now render an approved review's full text with its
  "Originally published in AIMS ShowTimes Digital Edition, Issue X" citation and a "Reviewed by"
  link to the adjudicator's page.
- **Correction to the pilot-season pick, found while building rather than assumed away**: 2022-2023
  was picked expecting fewer skeleton-show cases since it's recent - wrong, because
  `SHOWS_COVERAGE_START_YEAR = 2024` means `shows` has no coverage at all before season 23/24.
  Every one of the 47 pilot reviews needs a skeleton row, not a minority of them. Not a real problem
  (skeleton creation is exactly the path this build needs proven, and it's now got real test
  coverage) - just a reminder that only 23/24-onward seasons would actually have existing `shows`
  rows to match against; nothing about the archive itself was misjudged.
- Verified end-to-end against a scratch copy of the real `aims.db`, not just pytest: logged in as a
  throwaway admin, approved one review (confirmed the skeleton show and its public page render
  correctly, citation included), skipped one, and edited-then-matched a third - all three actions
  behaved as expected before the throwaway login was deleted again.
- Test suite grew 229 -> 238 (`tests/test_historical_reviews.py`: queue listing, approve with/without
  an existing show, approve refused with no society matched, skip, edit-fields flag recomputation,
  the approved review rendering on the resulting show's page, and a skeleton show not double-counting
  against its own `historical_results` award record).
- **Stats-exclusion gap found while auditing this, fixed the same session**: checked every place in
  the app that counts/aggregates `shows` rows to see what a real skeleton row would do to it (there
  was now one to test against, from verification above). Most of `info.py`'s stats() leaderboards
  turned out to already be safe - they filter on "has this happened by today"
  (`COALESCE(closing_date, opening_date) <= today`), which a dateless skeleton show always fails.
  Two spots genuinely needed the explicit `shows.source != 'historical'` exclusion since they don't
  depend on dates at all: `/titles` and `/search`'s title-count queries (would otherwise double-count
  a skeleton show against its own pre-2024 `historical_results` award record). Also excluded skeleton
  shows from two admin dashboard counts (`needs_review_count`, `missing_dates_count`) - a skeleton
  row's blank dates/review-link are permanent by design (the real review lives in `historical_reviews`,
  not `review_url`), so leaving them counted would make those counters permanently non-zero for
  something that will never be "fixed" - same pattern as Round 16's `Not adjudicated` exclusion.
  Verified the `/titles` fix actually does something (not just cosmetic): temporarily reverted it,
  watched the new double-count test fail (count came back 2, not 1), restored it, watched it pass.
- **Not built yet, deferred past this pilot**: the adjudicator-page season-grouping refinement and
  the new `/reviews` search hub (the mockup's Pieces 1 and 2) - only the show-page review rendering
  (Piece 0) shipped this round.
- Not deployed - local `aims.db` has the 47 pilot reviews loaded (one approved for real during
  verification, one rejected, one edited/matched, 44 still pending) via `extract_historical_reviews.py`;
  production needs the migration (automatic on next redeploy) *and* that script run manually
  afterward (it's a one-off loader, not something the app runs itself).

**Round 25 - post-redeploy fixes: review formatting, adjudicator grid rework (2026-08-18):**
Same evening, after Darragh redeployed and started actually loading/using tonight's features.
- **Redeploy confirmed live** (`/suggestions` deployed timestamp read "18 Aug 2026, 21:11";
  `/admin/historical-reviews` resolves to the login page, not a 404).
- **`docker compose exec` failed with "no configuration file provided"** when Darragh tried to run
  the loader from the NAS shell - pointed him at `docker exec <container-name>` instead (works from
  anywhere once you have the name from `docker ps`, unlike `docker compose exec` which needs to run
  from the directory holding `docker-compose.yml`) - matches an existing note in CLAUDE.md, just the
  first time it's actually come up live rather than being theoretical.
- **Real formatting bug in the extracted review text, caught from a live screenshot, fixed in two
  passes**: `review_text` had one line break per *printed column line* (PyMuPDF's block text puts a
  `\n` at every line-wrap, not at paragraph breaks) - rendered as dozens of tiny choppy paragraphs
  both on the public show page and in the moderation queue's Edit fields textarea.
  - **First pass**: joined wrapped lines with a space instead of `\n` - a real improvement, but Darragh
    correctly flagged the result as one giant undifferentiated block per review, still not right for
    a 600+ word review.
  - **Second pass**: real paragraph detection, using the PDF's own justified-text convention - a
    paragraph's last line is never stretched to fill the column, so a line noticeably narrower than
    its block's normal width marks a paragraph end. Calibrated against actual PDF line bounding boxes
    (not guessed) on a real review. Width alone wasn't reliable on its own though - it produced
    single-word "paragraphs" ("many" / "different" / "characters") where an inline image temporarily
    narrowed a block's column - fixed by also requiring the short line to end a complete sentence
    (real terminal punctuation), which only a genuine paragraph break can do. Swept all 47 pilot
    reviews afterward: 46 came back as clean, well-formed paragraphs; the handful of short paragraphs
    left are genuine one-line stylistic beats ("Elvis has left the Building!"), not artifacts.
  `load_historical_reviews.py` can also refresh an already-loaded *pending* review's text on a re-run
  (never touches an approved one) so each fix reached already-loaded rows too, not just future
  extractions - re-ran it locally after both passes and confirmed the rows came back clean each time.
- **Adjudicator season-assignment grid reworked** per Darragh's UX complaint (too tall, too much
  wasted space per row) - did the two changes he explicitly greenlit without a mockup this time
  ("just get ahead and do 1+3, i trust you"):
  1. The rarely-used second adjudicator slot (for a real mid-season change) now lives behind a
     "+ Add a mid-season change" `<details>`, open automatically only when one's already recorded -
     previously every season/tier cell always showed a second blank dropdown + notes field even
     though the huge majority of seasons only ever have one adjudicator per tier.
  2. Seasons with both tiers already fully assigned collapse into their own "N seasons already fully
     assigned" disclosure below the main table - same collapse pattern as the suggestions board's
     archived lane and the stats page's earlier-seasons split. Chosen over a simple date-based
     old/new split since Darragh's actual task right now is bulk-entering *old* seasons (09/10-19/20)
     - collapsing by completeness surfaces exactly the rows that still need attention regardless of
     whether "still needs attention" happens to be an old or a recent season.
  - **A real, previously-invisible bug found while building the completeness split, not assumed**:
    `_adjudicator_grid_seasons()`'s 09/10 floor-padding compared two-digit season *strings* with
    `<=`/`<` to decide whether padding was needed - unsafe across the 1999/2000 rollover ('76/77'
    sorts *after* '09/10' as plain text despite being an earlier season). Once the real awards
    archive reached back to 1977 (it already had, in production), this silently duplicated every
    season from 09/10 through the current one in the grid - each one rendered as two separate table
    rows. Fixed by checking simple list membership instead of string comparison. Verified the fix
    actually does something: temporarily reverted it, watched the new test fail (116 seasons, 16
    duplicates), restored it, watched it pass.
- Test suite grew 238 -> 241 (the season-string duplication bug, the completed-seasons split
  rendering correctly, and the mid-season `<details>` open/closed state).

**Round 26 - extending the historical review archive past the pilot season (2026-08-18):**
Darragh asked to load in the rest of the 920-review archive. Turned into real reconnaissance
before any bulk loading, once it became clear the pilot's parser doesn't generalize cleanly -
checkpointed with Darragh mid-way ("newest to oldest, stop when it breaks") rather than guessing
at how far to push it.
- **`extract_historical_reviews.py` now auto-discovers every issue from its own front cover**
  (issue number + date) instead of a hand-maintained list - far more reliable than anything in the
  ShowReviews section itself, which drifts a lot more across 14 years of layout changes. Dedupes
  issues that exist twice under two different filenames (confirmed by matching page counts/file
  size, not assumed) without wrongly treating AIMS's own occasional duplicate-printed issue number
  (two real, different issues both say "Issue 64" in print - a genuine editorial slip, not a
  parsing bug) as the same thing.
- **Two real, high-impact bugs found while surveying the full archive, both fixed**:
  - A literal "Reviews" label was getting misread as an adjudicator's own name in older issues,
    where that word and "ShowReviews" render as one combined text block instead of two separate
    ones.
  - An adjudicator's sign-off doesn't always match the header banner's spelling of their name
    across 14 years of hand-typed issues (e.g. "Ritchie Ryan" in the header vs "Richie Ryan" on
    the actual sign-off line, in the same issue) - exact string matching silently dropped every
    review signed with the variant spelling, sometimes an entire tier's worth in one issue. Fixed
    with a close-but-not-exact match (safe here specifically because sign-off lines are short,
    distinctive full names, not generic text a false match could plausibly collide with) - found
    two more real repeated typos this way while auditing the result ("Gred Currid" for "Greg
    Currid", appearing 64 times across real printed issues of that era), corrected both.
  - A season with no adjudicator names in its own issue's header now falls back to whichever names
    were found for other issues in the same season, by majority vote across the data itself
    (not hand-typed) - covers the handful of issues where that specific layout gap exists.
- **Found the real blocker while running this at scale**: older issues (confirmed as far back as
  2010-11) use a different heading order entirely - `Show Title` (Title Case, not ALL-CAPS) then
  `Society Name` then `Venue, City`, the reverse of the pilot's `Society Name` then `ALL-CAPS
  TITLE` - so the current parser, which leans entirely on the ALL-CAPS line to find where a review
  starts, finds nothing there. Not attempted this round - would need a second heading parser, not
  a tweak to the first.
- **Checkpointed with Darragh once this was clear** rather than guessing how far back to push -
  chose "newest to oldest, stop when it breaks." Ran the (now-fixed) parser across the full
  archive to see exactly where quality holds up: turned out to be genuinely uneven rather than a
  single clean date cutoff.
- **Loaded 353 reviews (seasons 16/17-18/19 plus the rest of 22/23) on the strength of a
  verification pass that turned out to be inadequate - caught by Darragh within minutes of looking
  at the real queue, not by anything I checked first.** That pass only confirmed review length and
  paragraph structure; it never validated that the extracted fields were actually plausible.
  Two real bugs slipped through as a result:
  - **~28 reviews had the show title and society name swapped** - the older title-first heading
    format (found and deliberately excluded for 2010-11 earlier this same round) turned out to
    also recur *within* nominally-modern-format issues (confirmed in Issue 121, May 2017) - not
    confined to the oldest years the way the initial "stop when it breaks" check assumed.
  - **At least one review had text from a completely unrelated article mixed into its body** (an
    interview/bio snippet - "...so I will keep auditioning and working hard...", nothing to do
    with the actual show) - a longer non-review block that the short-block caption filter doesn't
    catch, absorbed during heading detection instead of being correctly discarded as furniture.
  - **Reverted immediately** (`5caa220`) - `historical_reviews_pilot.json` back to the original
    47-review pilot only, and the 315 newly-loaded rows deleted from the local queue. Nothing had
    reached production or been approved, so no public damage, but real trust was overclaimed.
  - **Lesson, not just a fact**: "zero anomalies on a structural scan" is not the same as "correct"
    - a scan that only checks shape (length, paragraph count) can't catch wrong content in the
    right shape. Any future re-attempt at seasons beyond the pilot needs field-plausibility checks
    (does `society_raw` look like a society name, does the review text actually mention its own
    show) and spot-checks against the real source PDF, not just structural checks, before being
    called ready to load.
- Also added (same round, not yet verified live): a bulk-approve action on the moderation queue for
  reviews that already have a confident society match, so 200+ individually-clicked approvals
  aren't the only way through a large batch - the 148-vs-212 split it was built against came from
  the now-reverted data, so it needs re-checking against whatever a corrected re-extraction
  produces. **A real 500 error surfaced testing this locally** (missing `g.csp_nonce` on the
  redirect response) - not yet root-caused, flagged here rather than silently left for a future
  session to rediscover.
- **Not done, real remaining scope for a future round**: seasons 09/10-15/16 and 19/20-21/22 (the
  rest of the archive) still need work - the title-first heading format (now known to recur even in
  "modern" issues, not just the oldest years), the long-block caption-contamination bug, and
  root-causing the uneven per-issue yields in the 2012-2015 range. All three are scoped findings
  with real examples attached, not vague TODOs - see this entry and the parser's own docstring.
  **Any re-attempt needs field-level verification (not just structural) before loading anything.**

**Round 27 - re-attempting the full archive with real field-level verification (2026-08-18/19):**
Darragh's instruction going in: "rigorously check and validate the reviews... take as long as you
need to do it meticulously" - explicitly not a rush job, and not treated as one. Re-extracted the
full archive **seven times** (v7 through v13), each pass triggered by a real bug caught spot-
checking the *previous* pass's output against the actual source PDF - not by trusting a structural
scan, per Round 26's own lesson.
- **v7 - the swallow bug**: when a society wasn't in `societies.csv` (a defunct/historical one),
  the no-confident-match fallback heading parser had no real stopping condition and kept consuming
  lines as "society name" until it hit an ALL-CAPS/large-font line - which, for ordinary body
  prose, never comes. Ate up to 5 lines of the review's own opening sentences into `society_raw`
  and lost them from the published text entirely (Issue 76 April 2012, "Fusion Theatre" - the
  review's real opening line, "If I could time travel...", had vanished). Fixed to cap at the
  society line plus one optional venue line, same as the confident-match path already does.
- **v8/v9 - a non-review feature parsed as a fake review, then a self-inflicted regression fixing
  it**: "Top Three Tunes" (a member's favourite-songs write-up) sits between the masthead and the
  real ShowReviews banner in some issues and was getting swept into the body as if it were a
  review (Issue 141 Summer 2019 - `society_raw` became the feature's own tagline, `show_raw`
  became the member's name). Root cause traced two levels deep: the season/adjudicator-name lines
  themselves were being missed too (falling back to majority-vote names) because the fixed
  120pt-from-top cutoff didn't reach them either - fixed by matching header content (year-range,
  "Gilbert/Sullivan Section") by *text* as well as position, and sorting the matched blocks into
  real reading order (PDF block order doesn't reliably match visual position - confirmed
  responsible for a wrong name/tier pairing on its own). Fixing *that* exposed a missing
  `re.MULTILINE` silently breaking the content match on wrapped text. **Then a self-inflicted
  regression**: the name-shape check written for this used an ASCII-only character class,
  silently dropping every accented name ("Ciarán Mooney") and breaking sign-off matching across
  several whole 2017-18 issues (-42 reviews) - caught only by diffing the new run's per-issue
  counts against the prior one, not by the total looking wrong. Fixed with a Unicode-safe
  `str.isupper()` check instead of an `[A-Z]` regex class.
- **v10/v11 - the same contamination pattern recurring under different names**: "Top Three Tunes"
  reappeared in a different issue *without* the slash that the first fix keyed on, and turned out
  to sit in an inconsistent position relative to the real adjudicator name across issues (before
  it in one, immediately after in another) - no single positional rule (oldest-first, most-recent-
  first) works in every case. Landed on treating name-to-Section assignment as "most recently seen
  name wins" (a stack, not a queue) as the general fix, which incidentally also explains a
  previously-unexplained count jump (Issue 106 Summer 2015, 13 -> 23 reviews) - a *third* recurring
  heading, "Regional Round-Up", was resolved by the same stack-based fix, confirmed against the
  source PDF's own block layout rather than just trusted because the count looked plausible.
- **v12 - a general fix tried and reverted**: attempted to replace one-off heading blacklists with
  a general mechanism - cross-validate each parsed name against the season's own majority-vote
  consensus (built from every other issue in the same season) and auto-correct on disagreement.
  **This silently corrupted three previously-correct issues** (124-126) by importing a consensus
  vote scoped to the wrong season - some issues' own in-body season detection doesn't agree with
  which season they really belong to, and the vote isn't per-(tier-pair), so a name correct for
  one tier can still get overwritten by data bleeding in from a different, wrongly-bucketed season.
  A wrong correction that looks confident is worse than no correction - reverted in v13 in favour
  of two direct, individually source-PDF-verified exclusions ("News" alongside "Top Three Tunes")
  rather than a broader automatic mechanism.
- **Final state (v13, 864 reviews)**: zero issues skipped, diffed clean against the last-known-good
  baseline at every step (not just re-run and re-trusted), all 243 tests pass. Structural
  verification (`empty society_raw`, `not-canonical society`, `venue-shaped show_raw`, `<300-char
  review`) all at or near zero, with every non-zero category spot-checked against source PDFs
  rather than accepted on the numbers alone - e.g. the "no title mentioned in body" category is
  confirmed a false alarm of the check itself (pun-heavy reviews that never literally repeat the
  show's title), not an extraction problem.
- `historical_reviews_pilot.json` updated to the verified 864-review set and loaded into the
  **local** `aims.db` only (836 inserted, 27 already-loaded from earlier testing, 1 refreshed) -
  production untouched. Committed but not deployed; not yet approved/published by a moderator.
  Ready for Darragh's own pass through `/admin/historical-reviews` before deciding on the real
  production import.

**Round 28 - live moderation, two more real extraction bugs, and matching against the older
awards archive (2026-08-19):** Round 27's set got pulled and deployed; Darragh started actually
working through the real queue on the live site, which is exactly what surfaced the next layer of
real problems - a "meticulous audit" only ever finds what it thinks to check for, and a live
moderator using the tool for real found things it hadn't.

- **Production 500 on bulk-approve, root-caused and fixed**: 9 real productions in the archive got
  extracted twice from two different source issues (a near-identical reprint of the same review) -
  approving the second one collided with `ux_shows_natural_key` when it tried to create a second
  skeleton show for the same (society, season, show). Every row in the batch shared one
  uncommitted transaction, so the single collision took the whole 800+ row approval down with it.
  Confirmed via a scratch copy of the real dataset that nothing had actually been written (the
  crash happened before the batch's own `commit()`). Fixed with a per-row `SAVEPOINT`.
- **Two more real extraction bugs, found from screenshots of the live queue, not a re-run of the
  archive-wide audit**:
  - A venue line right after the title in the common `Society / TITLE / Venue / body` heading
    order was falling straight into the review's own text as its leading sentence - one whole
    parse_heading branch had no venue-skip step at all, unlike its sibling branch just above it
    (confirmed - Marian Choral Society's Titanic review opened with "St Jarlath's Hall, Tuam").
  - A society name written as a dotted acronym ("S.O.N.G.") matched the same ALL-CAPS title regex
    used to detect real show titles (the regex allows periods, needed for real titles like "Mr.
    Carter, The Musical") and got picked as the title itself, ahead of the real one right after it.
    Fixed with a narrow exclusion for that specific shape rather than loosening the regex generally.
  - Re-extracted as v14 (864 reviews, same count as v13 - these were field-correctness fixes, not
    review-count changes), diffed clean against v13, reloaded into `aims.db` (121 reviews refreshed
    with the corrected venue-free text).
- **A much bigger structural gap, surfaced by Darragh asking "why hasn't this matched" about a
  production that visibly already existed on the site under a different title**: show-matching
  only ever checked the `shows` table, which has zero coverage before 23/24 (`SHOWS_COVERAGE_
  START_YEAR`) - so it *always* missed that the same production is very often already in the much
  older `historical_results` awards archive (back to ~2005), just worded slightly differently than
  the review's own heading ("Titanic" vs the awards archive's "Titanic The Musical" - confirmed the
  same 2011 Marian Choral Society production). Quantified before fixing anything: at least 323 of
  802 pending reviews (40%, likely more - that's only the *exact*-title-match count) already exist
  in `historical_results` under a real record. Approving as-is didn't break anything visible (the
  `/titles` page already excludes skeleton shows from its count, so no double-counting), but it
  orphaned the review onto a standalone page disconnected from the production's real award history
  - a real loss of discoverability, not a crash.
  - Confirmed the season->year mapping empirically rather than guessing (`historical_results.year`
    is the AIMS awards CSV's own column, unrelated to any season-string arithmetic elsewhere in the
    codebase) - `'10/11' -> 2011` (the *second* calendar year) scored 323 hits; the other plausible
    convention scored 0. Shared as `season.historical_results_year()`.
  - Reused the site's own existing duplicate-title scorer (`app.dedupe.find_candidates`, built for
    the admin "possible duplicate societies/shows" tool) for the fuzzy side of this instead of
    writing a second implementation - it already strips generic suffixes like "the musical" before
    scoring, so "Titanic" vs "Titanic The Musical" comes back a perfect 1.0 for free.
  - `/admin/historical-reviews` now groups the queue by *why* each review is stuck (needs a
    society matched / shares a show with another pending review / likely has award history under a
    different title / ready to approve) instead of one flat list - directly requested ("need to
    make it easy for the admin to resolve and approve these... instead of just one long list").
    Bulk-approve now only touches the "ready" category (also now correctly includes reviews already
    matched to a real `shows` row, which it used to skip entirely - a small existing gap this
    surfaced along the way). A one-click "use this title" action lets a moderator accept the
    suggested awards-archive title without a full Edit-fields round trip.
  - `public.show_detail()` now actually displays matching award history on a show's own page -
    matched at display time by (society, year, exact-normalized title), since `historical_results`
    predates this whole system and has no foreign key to `shows`. Deliberately exact-normalized
    matching only on this public page, not fuzzy - a genuine title mismatch is exactly what the
    admin queue's history_match step exists to catch before a review is ever approved.
  - **Retroactively audited the 784 skeleton shows already live from Round 27's approvals**: 141
    had a title not byte-identical to a plausible awards-archive record, but most of those (106)
    were pure case/punctuation differences ("Made In Dagenham" vs "Made in Dagenham") already
    tolerated by the new display-time lookup - only 35 were a real wording gap needing an actual
    fix. Built `/admin/historical-shows/title-check` as a permanent tool (not a one-off script) for
    this, since the same gap can recur any time a review gets approved with a title that doesn't
    quite match the archive.
- All 251 tests pass (16 new/updated this round). Committed and deployed (`0584c59`, confirmed live
  and `load_historical_reviews.py` re-run against production - matches the full 864-review set).

**Round 28.1 - the title-check tool's own 500, found using it live (2026-08-19):** Darragh started
working through `/admin/historical-shows/title-check` for real and hit a 500 clicking "Use...".
- **Root cause**: Thurles Musical Society already had *two* separate `shows` rows for the same real
  17/18 production - one a skeleton from approving the historical review ("Ragtime"), one a member
  submission entered independently ("Ragtime The Musical"). `match_show_for_edit` only checks for
  an *exact* `show_raw` match at approval time, so the review never found the submission and made
  its own skeleton instead. Accepting the suggested title tried to rename the skeleton into the
  submission's exact title, colliding with `ux_shows_natural_key`.
  - Confirmed only `historical_reviews.show_id` references `shows.id` (checked schema.sql directly,
    not assumed) before treating this as safe to fix by merging: re-point the skeleton's review(s)
    onto the real show, then delete the now-redundant skeleton, instead of renaming into a collision.
    Applied directly to the one live stuck row via SSH so Darragh wasn't blocked, then shipped the
    same fix in code (commit `0565a66`) for the rest of the queue.
- **The deeper implication** (see "Start here" above): this is the same class of gap as Round 28's
  main finding, just against `shows` instead of `historical_results` - `match_show_for_edit` never
  fuzzy-matches against *either* archive, only exact-matches against `shows`. Not yet generalized -
  see "Suggestions for future scope" below.
- 20 tests pass (1 new this round: the merge-not-rename case). Committed (`0565a66`); pushed but
  **not yet redeployed** as of this note.

## Next steps / open questions for a future session

**Immediate (blocking further title-check use)**: redeploy commit `0565a66` so
`/admin/historical-shows/title-check` stops 500ing on any of the remaining ~34 entries that hit the
same real-show-already-exists collision as the Thurles/Ragtime case. Nothing else is blocked -
`/admin/historical-reviews` itself (the main queue) doesn't have this bug, only the retroactive
skeleton-title-check tool does.

**Worth investigating - the systemic version of the Ragtime bug**: `match_show_for_edit` (used at
both review-approval and review-edit time) only ever does an *exact* string match against `shows`.
Round 28 added fuzzy matching against `historical_results` for the moderation queue's own
categorization (`find_historical_results_candidates`), but never extended the same idea to `shows`
itself - so a review can still create a redundant skeleton instead of linking to an already-existing,
differently-titled show (submission or import), for any of the ~700 reviews still pending. Concretely
worth trying next session: run `find_historical_results_candidates`-shaped fuzzy matching against
`shows` too (not just `historical_results`) as part of `categorize_pending_reviews`'s "ready" bucket,
so a review with a plausible-but-not-exact existing show gets routed into a "needs a title/show check"
category *before* approval, rather than only being caught after the fact by a title-check audit (which
only exists for already-approved skeletons, not shows created any other way).

**Deferred ideas, not started, lower priority than the above**:
- Fuzzy-matching show *titles* to warn on likely duplicates more broadly, not just within this
  review-import pipeline - Darragh's own earlier "a show match would be great too" ask. The
  Round 28/28.1 work is really a specific instance of this same idea (title variants of the same
  real production); `app.dedupe.find_candidates` already exists and is reused now, so extending its
  use beyond the historical-review flow (e.g. flagging likely-duplicate `shows` rows generally, the
  way the admin dashboard already flags likely-duplicate societies) is a natural next step, not a
  new mechanism.
- Extracting Director/Musical Director/Choreographer names from review text - explicitly flagged by
  Darragh early on as "food for thought for later," not urgent.
- A worthwhile cleanup, not urgent: `find_historical_results_candidates`, `match_show_for_edit`, and
  `find_mismatched_skeleton_shows` are three separate, not-quite-unified matching code paths that
  grew one at a time this session as each new problem surfaced. Once the current backlog (queue +
  title-check) is actually cleared, consider whether these should collapse into one shared matching
  utility rather than three similar-but-distinct ones - not urgent while there's still real,
  unprocessed queue data to work through.
- Continue working through the main `/admin/historical-reviews` queue itself (the "needs society
  matched" / "same show, two reviews" / "likely has award history" categories, ~90 reviews as of
  the last count) - the bulk-approvable "ready" bucket was already cleared during this session, but
  those three categories all genuinely need a person to look at each one.

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

**Site audit (2026-08-17):** Quick pass at Darragh's request - found `.hint` (used in 12 templates)
had no matching CSS rule, ever, so it rendered unstyled everywhere; and that "Gilbert"/"Sullivan"
were never explained anywhere on the public site despite being used constantly. Both fixed - `.hint`
styled to match `.meta`, and a new "What are the Gilbert and Sullivan sections?" section added to
`/about` (Darragh's own text). Also flagged, not yet acted on: duplicated "is this show upcoming"
logic in `public.py`/`society.py` (small refactor), and that the parked adjudicator-planning-calendar
backlog item is now partly superseded by the tier `.ics` feeds from the round above. A deeper
redundancy/dead-code pass was started but not finished (background agent hit the session's usage
cap) - worth resuming if a full codebase health check is wanted.

**Round 19 - Adjudicator tracking, admin-only (2026-08-17):** Darragh's own idea, raised right after
the site audit above: AIMS assigns one adjudicator per tier (Gilbert/Sullivan) per season, and knowing
who that was each year would help him match a published review's byline to its likely author, plus
find every review a given adjudicator wrote.
- **New `adjudicators` table** (name, free-text notes) and **`adjudicator_assignments`** (one row per
  season+tier that's been filled in, `PRIMARY KEY (season, section)`) - a reusable picker rather than
  free text per season, so "Jane Smith" typed once stays consistent across every year she judged
  instead of drifting spelling season to season. Brand-new tables, so no `COLUMN_MIGRATIONS` entry
  needed (`CREATE TABLE IF NOT EXISTS` in `schema.sql` handles it).
- **New `/admin/adjudicators`**: add an adjudicator, then a plain Season / Gilbert / Sullivan grid
  (one `<select>` per season/tier, single Save button - no per-field autosave JS, unlike `/admin/
  venues`, since this grid is far smaller) to assign who covered each. Each adjudicator's name links
  to **`/admin/adjudicators/<id>`**, which lists every show from a season/tier they were assigned to
  (joining `shows` on `season`+`section`) alongside its review link, for Darragh to cross-check the
  byline against. Delete is blocked while an adjudicator is still assigned to any season.
- **Scoped via an explicit question first**: kept admin-only for now (no public "Reviewed by X" credit
  or public reviews-by-adjudicator page yet) - Darragh can revisit making it public-facing once the
  data's actually filled in. Darragh's offered to backfill past seasons from memory via the new grid.
- Test suite grew 174 -> 183 (`tests/test_adjudicators.py`: add/dedupe, assignment save/clear, the
  per-adjudicator show list joining correctly on season+tier and excluding other seasons, 404 on an
  unknown id, delete blocked-while-assigned vs. removed-when-unassigned).

## Full site audit + plan of attack (2026-08-17) - reviewed, nothing built yet
Requested pass at Darragh's request: live site (darraghc.ie/showcal) + codebase, covering UX, security,
redundant code, stability, feature ideas, and a prioritized order to act on them - published as its own
document with mockups: https://claude.ai/code/artifact/65dd6ff0-b78a-4f39-bf00-cdd946f3bb10
- **Real bug found**: every URL the app builds itself via `url_for(_external=True)` comes out `http://`
  instead of `https://` - Cloudflare Tunnel forwards to the container over plain HTTP and nothing tells
  Flask the real scheme (no `PREFERRED_URL_SCHEME`/`ProxyFix`). Confirmed live in `sitemap.xml`,
  `robots.txt`'s `Sitemap:` line, `calendar.ics` event URLs, and show-page `og:image` tags. Real impact:
  a shared show-page link (the traffic audit's own top usage pattern - individual society pages
  outperform the directory) likely renders with no poster thumbnail in Slack/WhatsApp/iMessage previews,
  since most platforms refuse a plain-http image. One existing workaround (`notify.link()`/`SITE_URL`)
  covers a single admin-only call site, not the others. Not fixed yet - proposed as Round 1's headline
  item, one-line fix (`PREFERRED_URL_SCHEME` under the existing `is_production` flag).
- **Confirmed clean**: no SQL injection surface (every dynamic query is parameterized or builds from
  static fragments; the one f-string touching a table name only ever receives a hardcoded literal), zero
  `|safe`/`Markup()` usage, CSRF/hashing/cookie flags/rate-limiting/upload validation all correctly in
  place, dependencies current, no dead code/TODOs.
- **Smaller findings**: no CSP/Referrer-Policy/Permissions-Policy headers (CSP still blocked on 11 inline
  `onsubmit` handlers across 9 templates); the "is this show upcoming" duplication flagged in the
  2026-08-17 audit note is still unfixed; no custom 500 page; no plain `<meta name="description">`; Stats
  still opens on its most lopsided all-time framing (scoped since 2026-08-05, never shipped); no sitewide
  search despite two working FTS5 indexes already sitting unused for it.
- **New feature ideas**: sitewide search (reuses existing FTS), a public Adjudicators directory (natural
  follow-on to the round above), Event JSON-LD on show pages for Google rich results, bundled
  custom-500 + extra headers.
- **Proposed order**: (1) foundation fixes - URL scheme, 500 page, headers, dedupe the upcoming-check;
  (2) Stats reframing; (3) sitewide search; (4) CSP hardening now that round 1 practiced the exact kind
  of mechanical change it needs; (5) public Adjudicators page, contingent on Darragh actually filling in
  season data first. Everything already in the backlog (adjudicator calendar, historical backfill, edit
  history, costume/prop listings, staging env, LAUNCH.md) is unchanged, just re-surfaced in the doc.

**Round 20 - executed rounds 1, 3, 4, 5 of the audit's plan (2026-08-17):** Darragh asked to skip round 2
(Stats reframing) for now and build the rest. All four shipped in one session:
- **Round 1 - foundation fixes**: the http-vs-https bug turned out to need more than the audit doc's
  proposed one-liner - `PREFERRED_URL_SCHEME` only affects `url_for()` calls made *outside* a request
  context, which none of these are, so it would have been a no-op. The real fix is Werkzeug's `ProxyFix`
  (`app/__init__.py`, trusting exactly one hop's `X-Forwarded-Proto`, applied unconditionally since it's
  a no-op with no such header present - i.e. harmless in local `flask run`/tests). Also shipped: a themed
  custom 500 page (matching 404's voice), `Referrer-Policy`/`Permissions-Policy` headers, a plain
  `<meta name="description">` (reusing the existing `og_description` block), and `app/shows.py`'s
  `is_upcoming()` - de-duplicating `public.py` and `society.py`'s copies (left `info.py`'s version alone;
  it's a SQL fragment computed across many rows for a stats query, not the same kind of duplication a
  Python helper could actually fix).
- **Round 3 - sitewide search**: new `/search` (`public.search()`), spanning `societies_fts` and every
  show title (current `shows` + the older awards archive, same query shape as `titles_list()`), plus a
  search box added to the header nav on every page. **Flagging two deviations from the mockup**: it's a
  full results page you land on after submitting, not a live-typeahead dropdown - matches the site's
  existing near-zero-JS convention (every other filter is a plain GET form) rather than adding
  fetch-based live search; and results are grouped into two kinds (Societies / Shows) instead of the
  mockup's three (Societies / Shows / Awards) - a title's own page (`/titles/<title>`) already surfaces
  both its production history and its awards together, so a third "Award" result kind with its own link
  target would have been redundant.
- **Round 4 - CSP hardening**: all 11 inline `onsubmit="return confirm(...)"` handlers (9 templates) and
  the one inline `onclick` (society page's copy-code button) replaced with `data-confirm="..."`/
  `data-copy-target="..."` attributes plus one delegated listener in `base.html`. Shipped a real,
  nonce-gated `Content-Security-Policy` - a fresh per-request nonce (`app/__init__.py`'s `before_request`,
  exposed to templates via `csp_nonce`) on every `<script>` tag, `script-src 'self' 'nonce-...'` with no
  `'unsafe-inline'` (the part that actually matters for XSS protection). `style-src` still allows
  `'unsafe-inline'` - the site's handful of inline `style="..."` attributes (one with a dynamically
  computed width, the venues page's progress bar) aren't nonce-able, and CSS-only injection is a much
  smaller risk than script injection.
- **Round 5 - public Adjudicators page**: new `/adjudicators` (directory, only adjudicators with at
  least one real season/tier assignment) and `/adjudicators/<id>` (their published reviews only -
  deliberately narrower than `/admin/adjudicators/<id>`'s cross-check view, which shows every show in
  their assigned seasons regardless of review status). A published-review show page now credits
  "reviewed by X", linking to their page, computed the same way as the admin tool - via the show's own
  season+section matched against `adjudicator_assignments`, no per-show author field. Same
  hidden-society exclusion as the homepage/Season Archive/calendar feed. Linked from the footer and the
  mobile "More" page, and added to `sitemap.xml`.
- Test suite grew 183 -> 214 (`tests/test_round1_foundation.py`, `tests/test_search.py`,
  `tests/test_csp.py`, `tests/test_public_adjudicators.py`) - full local preview pass confirmed the CSP
  nonce matches every `<script>` tag on a real page, zero inline handlers remain anywhere, and the
  scheme fix actually flips to `https://` when `X-Forwarded-Proto` is present and stays `http://`
  without it (so local dev is unaffected).
- Not deployed - Darragh reviews and redeploys via Portainer when ready. Round 2 (Stats reframing)
  remains open, not attempted this round.

**Round 21 - ShowTimes PDF archive: adjudicator backfill research (2026-08-18):** Darragh has ~14 years
of the AIMS *ShowTimes* magazine as PDFs (`E:\showtimes archive`) - the reviews for every season before
the site's own 23/24 coverage started. Explored whether these could backfill `adjudicator_assignments`
(Round 19) and, longer-term, real historical review content.
- **Feasibility confirmed on the oldest issue first** (Dec 2010) - real text layer, not scanned images.
  A one-off `pypdf`-based parser (scratch script, not shipped) extracts each review's show/society/venue/
  adjudicator/full text cleanly, keyed off a "ShowReviews" section header that names that season's two
  adjudicators (one Gilbert, one Sullivan) - the same one-per-tier-per-season model already built.
- **Ran the parser across the full archive**: 106 unique PDF issues after dedup (the folder's several
  `.zip` files turned out to be pure backup duplicates of PDFs already loose in the folder, confirmed by
  hash, not extra content) - 920 reviews extracted, published as a browsable/searchable report (adjudicator
  candidates, every review's full text, and a "no matching show in the CSVs" gap list) rather than raw CSVs
  alone, so Darragh could look things up without touching a spreadsheet.
- **Real bug caught before it reached anyone**: told Darragh a fix was live and republished when it
  wasn't (a `Gred Currid` → `Greg Currid` typo-fix that was only *said*, not actually done). Caught on
  the next round when the correction still wasn't showing - verified with `WebFetch` against the live
  artifact before claiming success again, not just re-trusting the local file.
- **Three findings walked back or confirmed only after direct evidence, not assumption** - worth noting
  as the actual lesson of this round, not just the individual facts:
  - **2012-2013 and 2013-2014**: no adjudicator names in the extracted text at all for these years -
    turned out the names are printed as part of a photo banner image, not real text, so no amount of
    parser tuning would ever find them. Resolved once Darragh sent screenshots of the actual banners:
    2012-2013 = Pat McElwain (Gilbert) / Richie Ryan (Sullivan); 2013-2014 = a genuine mid-season change,
    Richie Ryan → Damien Murray on Gilbert, John Grayden Sullivan throughout.
  - **2016-2017 "mid-season swap" - claimed confirmed, then found wrong on push-back.** Darragh
    correctly doubted the finding rather than accepting it; laying out issue-by-issue dates against the
    banner's own season label showed it was never a real swap - Peter Kennedy/Greg Currid were 2016-2017's
    only pair. The apparent second half (Ciarán Mooney/Peter Kennedy) was actually 2017-2018 starting
    early (October), just printed under a stale season label for its first three issues before the
    banner caught up in February - same kind of one-off editorial lag as an unrelated stray "10 March
    2011" leftover date found earlier in a 2013 issue. Real lesson: "the banner says X" isn't the same
    as "X is true" without checking the actual chronology.
  - **2020-2021: genuinely no reviews, confirmed as COVID, not a parser failure.** Five consecutive
    issues (June 2020 - Winter 2021/22) have no ShowReviews section at all - confirmed by reading the
    Summer 2020 issue directly ("keep in touch during the pandemic... cancellation of AIMS Award in
    Killarney... from our stage to your home" - a livestreamed awards night, not real productions).
    Nothing to backfill for that stretch because nothing happened.
- **Final result: 29 confirmed season/tier/adjudicator combos, 2009-2023**, ready to hand-enter via
  `/admin/adjudicators` - not yet done, no code or data has actually changed. See chat for the full list
  (also captured in the published report).
- **A real schema gap surfaced by the 2013-2014/2016-2017 investigation**: `adjudicator_assignments`
  has `PRIMARY KEY (season, section)` - it can't represent a real mid-season change at all right now.
  Planned fix (not yet built): drop to a non-unique key plus a free-text `notes` column, same
  "simple text log, not a structured audit trail" pattern `societies.section_history` already uses -
  deliberately not a date-range/versioning system.
- **Longer-term, only planned so far**: importing the 920 reviews' own full text as real historical
  content (own table, not `shows`/`historical_results` - different shape entirely), landing in a
  moderation queue before anything public, same `pending/approved/rejected` shape the submission system
  already uses. Mockups published for both the schema-change admin UI and the moderation queue; nothing
  built. Recommended to pilot on one small season end-to-end before running the full archive through.
- Also flagged, not decided: the magazine states its own content is AIMS Ltd's copyright - worth
  Darragh's own explicit sign-off before publishing full review text, given the site's own "not an
  official AIMS website" disclaimer.
- **Two findings from Round 21 corrected on Darragh's own push-back, not accepted first-pass**: the
  "2016-2017 mid-season swap" turned out to be a stale season label on 2017-2018's first three issues,
  not a real swap - only caught because Darragh doubted a "confirmed" claim that was really just one
  image, not a checked timeline. 2020-2021's missing reviews are genuinely COVID (no productions), not
  a parser failure - confirmed by reading the issue's own text ("cancellation of AIMS Award in
  Killarney... from our stage to your home"). Final list: 29 combos, 2009-2023 (2020-2021 excluded,
  nothing to record).

**Round 22 - Step 3: mid-season adjudicator support (2026-08-18):** Built and shipped (not yet deployed) -
the schema gap Round 21 surfaced.
- **`adjudicator_assignments` rebuilt** from `PRIMARY KEY (season, section)` (physically only one row per
  season/tier) to `id` + `UNIQUE (season, section, adjudicator_id)` + a free-text `notes` column - same
  "simple text log, not a structured history table" pattern `societies.section_history` already uses.
  SQLite can't `ALTER` a primary key in place, so `app/db.py` rebuilds the table (new table, copy, drop,
  rename) on any database still in the old shape - a no-op once migrated, including a brand-new database
  where `schema.sql` already creates it in the final shape.
- **`/admin/adjudicators` grid gets a second slot per season/tier**, each with its own optional note -
  only shows as a real second row when actually filled in, so the ~90% of seasons with one adjudicator
  look exactly as before. Fixed-two-slots rather than an open-ended "add more" control (no season has
  ever needed a third), keeping this JS-free like the rest of the admin forms.
- **Real second bug caught mid-build, unrelated to the schema work**: Darragh found he couldn't enter
  09/10 or 10/11 on the live grid at all - `season_range()` anchors its earliest season to `MIN(year)
  FROM historical_results` (the awards archive), which doesn't go back that far on production even
  though the ShowTimes-archive backfill does. Fixed by having the adjudicators route independently
  extend the season list back to 09/10 regardless of what the awards archive covers, rather than trying
  to fix `season_range()` itself (still correct for its other callers - the society login's historical
  entry dropdown, which has no reason to go back further than real award data exists).
- **Public "reviewed by" credit deliberately declines to guess** when a season/tier has two adjudicators
  on record - there's no per-show date data to say which of the two actually wrote a specific review, so
  `show_detail()` only credits when exactly one candidate exists, rather than picking one arbitrarily.
- Test suite grew 214 -> 225 (`tests/test_adjudicator_assignments_migration.py`: rebuild preserves data,
  allows a second row, is idempotent; `tests/test_adjudicator_mid_season.py`: two-slot save/clear,
  the 09/10 floor, and the show-page non-guessing behavour x2). Local preview seeded with the real
  confirmed 09/10 and 13/14 (Richie Ryan -> Damien Murray) data before calling it done.
- Not deployed - Darragh reviews and redeploys via Portainer when ready. He'd already started
  hand-entering the Round 21 combo list into the live (pre-fix) grid - safe, since the migration only
  ever adds structure and preserves every existing row exactly.

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
