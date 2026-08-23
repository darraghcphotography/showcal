# Roadmap

Tracks the current phase of work and genuinely open items, so a new session (after `/clear` or a fresh
start) can pick up without re-deriving context. Update this file - don't just say the plan out loud in
chat - whenever the phase changes.

**Pruned twice** (2026-08-20, then again 2026-08-23) - each time because it had grown into a
chronological session log of mostly-shipped work, and CLAUDE.md's own rule says to read it at the start
of every session. Full history (every Round, every Phase, every session's blow-by-blow) is preserved
verbatim in `ROADMAP_ARCHIVE.md` - nothing was ever deleted, just moved out of the file that gets read
every session. This file holds only: the current phase, and a flat list of items that are genuinely
still open (not started, explicitly parked, or blocked on something). When a session fully resolves an
open item, move its entry to `ROADMAP_ARCHIVE.md` rather than letting resolved items accumulate here
again.

## START HERE - where things stand (2026-08-23)

Live and confirmed deployed: the productions table (stats cut over), the real venues table (147 venues,
merge queue mostly worked), the header nav restructure + polish + mobile fix, Decades/Reviews pages,
show circuit intelligence on `/titles/<title>`, two rounds of UX-audit quick wins (venue/adjudicator
linking, sitemap coverage, wording fixes, Gilbert/Sullivan explainers), and the review-author byline
(`review_author` column, admin edit form + reviews-queue quick save, explicit-beats-inferred credit on
the public show page). A large batch of venue-data and society-section data fixes also went out today,
plus a fresh full-archive sweep for the truncated-extraction garbled-title bug (2 more instances found
and fixed) - see the archive for the detail if a specific fix needs re-checking.

**Two open reference documents worth knowing about before starting anything new:**
- **Full public-site UX audit** (non-technical, mockups included):
  https://claude.ai/code/artifact/a546fc7e-ef6e-42c3-b6e5-400634708318 - headline finding is that the
  site's infrastructure is far ahead of its content (0 of 194 societies have a website link, 0 of 147
  venues have a map pin). Its four "bigger bets" and outreach track are still open, listed below.
- **`DATA_ACCURACY_AND_CORRECTIONS_REPORT.md`** (repo root, untracked, Gemini-generated) - checked
  against reality 2026-08-23, most of it already fixed or already stale; the genuinely open remainder is
  listed below. Treat any *new* Gemini-sourced report the same way before acting on it: verify against a
  fresh prod snapshot first, don't trust its specific claims - it got at least one flat wrong this round.

## Next feasible things, roughly in order

- **`/reviews` + `/season` page weight** - 362KB/123KB, no pagination. Flagged in the UX audit as the
  one remaining quick win too big/risky to bundle into the two batches already shipped.
- **Show/title enrichment, Source C follow-ups** - Source C (circuit intelligence) shipped 2026-08-23.
  Source A (Wikidata) has a real bug in its proposed query (`wdt:P58` should be `wdt:P87`) and only
  reliably resolves 48 of 306 titles without fuzzy title-matching, which this repo avoids - fix the
  query before building. Source B (licensing-house specs) isn't a pipeline, it's manual data entry.
- **Venue capacity/type/website/map research** - the fields exist and render already; 0 of 147 venues
  have any of it filled in. Real-world research, not a coding task - a WebSearch pass against the
  highest-traffic venues would be the way to start.
- **FAQ page** - real questions already gathered (what is AIMS, how do I join, which societies are near
  me). Smallest self-contained new page on the list.
- **Productions-table migration, stages 3-4** - public show/society pages, the last of the four staged
  cutover surfaces. **A full execution plan now exists: `docs/productions-stage-3-4-plan.md`** (written
  by Opus 2026-08-23, numbers re-verified against a real prod snapshot). Start there, not from scratch.
  Headline: this is a bugfix, not a refactor - Shows A-Z counts award *nominations* rather than
  stagings, so it overstates the circuit by 1.67x (4,677 vs 2,805); society pages list every 2024+
  production twice; ~16 real titles have no page at all. Stage 4's recommendation is "keep the table
  derived, don't build the authored version" with the reasoning and the trigger conditions written down.

## Data-accuracy follow-ups (from the 2026-08-23 report check), need Darragh's input or real research

- **11 shows with `review_status='Published'` and no `review_url`** - each needs a real per-show
  judgment call (was it actually reviewed and just missing the link, or never adjudicated at all), not
  a bulk guess.
- **154 `historical_results` rows (1983-2000) with `category_name IS NULL`** - needs real historical
  AIMS awards-programme research; a Gemini report only sampled 6 of them.
- **~10 unmapped historical societies with no existing `societies` row** (Bangor Operatic Society, De La
  Salle Musical Society Waterford, others) - creating new historical society records is a structural
  decision, not a data-quality bugfix.
- **28 orphaned Inactive societies with zero shows/awards** - retain or remove is a judgment call, no
  urgency signal.
- **Cancelled-show data reliability - not investigated.** Darragh: the `status='Cancelled'` field "has
  been inaccurate anywhere I found it." Only the season calendar's filter control was removed in
  response so far - whether the underlying data needs a real fix, and whether the "Cancelled" tag shown
  elsewhere on the site should stop rendering until it's trustworthy, is still open.
- **19 of 23 researched societies' online production archives not yet backfilled** (research inventory
  exists, only 4 done so far).
- **~112 stale orphaned `historical_reviews` rows** - cross-referenced as real, but explicitly not
  deleted pending a more rigorous verification method than what was used to find them.

## UX-audit bigger bets and outreach track (not started, need Darragh's design input)

- **Homepage reorder** - lead with what's on, group by month, add poster thumbnails inline.
- **Society page, empty vs. filled** - the mockup already doubles as the pitch for getting societies to
  fill their own pages in; this bet is building that page for real.
- **Show page as the shared front door** - venue detail linked inline, other societies who've staged
  this show, the society's own social links, a share affordance.
- **"What's on near me"** - genuinely blocked on venue coordinates existing first (see venue research
  above); the mockup states this plainly rather than promising it.
- **Outreach/onboarding track** (non-technical, Darragh's lever, not a coding task) - a nudge on a
  society's own page when its profile is thin, 2-3 exemplar societies filled in completely as a
  reference, a draft message to send a committee, a "claim your page" request route.

## Mockups approved or built, not yet applied to real templates

- Shows A-Z redesign: https://claude.ai/code/artifact/8748ee86-2422-4df3-aae6-7ee5973bc5c3
- Society head-to-head compare: https://claude.ai/code/artifact/a3b6ce5c-1bbc-4eb3-aea9-8f480a51e209

To update either with feedback, republish the same Artifact URL (via the Artifact tool's `url` param)
rather than creating a new one, so these links stay correct.

## Waiting on Darragh, not a coding task

- **Posters** - 41 exist against ~200 current-era shows. Gates the whole visual redesign (type/palette
  pass, then per-page components) - a poster-led design would be mostly empty frames without more of
  these.
- **OCR test on a programme photo** - blocked on Darragh sending one.

## Technical debt

Two of the six items measured 2026-08-23 are done (the admin.py package split, test-suite
parallelization) - see the archive. Still open:

1. **`ensure_current()` is a call site you have to remember.** Many call sites now across `admin/`,
   `info.py` and `public.py`. Any route reading `production_id` or `venue_id` must call it first;
   forgetting doesn't error, it silently under-reports. Worth replacing with a `before_request` on the
   blueprint, or a decorator, so it can't be forgotten.
2. **`productions_build.py` and `venues_build.py` duplicate the same freshness machinery** -
   `FINGERPRINT_SQL`, `fingerprint()`, `mark_stale()`, `ensure_current()` and a one-row `*_build_state`
   table, written twice. Worth folding into one small shared helper; pairs naturally with item 1.
3. **FTS indexes rebuild on every startup.** Known, deliberate, documented in `db.py` - the obvious
   `COUNT(*)` guard doesn't work on an external-content FTS5 table. Left alone on purpose.
4. **`page_views` is keyed on path only**, so no query-string question can ever be answered from it.
   Fine as a popularity counter, useless as analytics. Only worth changing if a real question needs it.
5. **Five untracked `.md` files sit in the repo root** (`DESIGN_AUDIT_AND_PROPOSALS.md`,
   `FEATURE_IDEAS.md`, `SHOW_ENRICHMENT_PROPOSAL.md`, `venues_report.md`,
   `DATA_ACCURACY_AND_CORRECTIONS_REPORT.md`). Source documents, not repo content, deliberately left
   untracked - but they show up in every `git status`. Either commit them to a `docs/proposals/` folder
   or add them to `.gitignore`.

## Parked, each wants its own dedicated session or decision, none started

- **`match_show_for_edit` never fuzzy-matches** against `shows` (exact match only) - a systemic version
  of a title-mismatch bug already fixed once for a specific case, not yet generalized.
- **Person/person-page identity resolution** - parked on Darragh's privacy objection to public person
  pages. Internal-only dedup was agreed as the resolution path but never built.
- **`/admin/duplicate-titles` UX redesign** - asked for once, later called "not really an issue" when a
  real mockup existed. Low priority.
- **`DESIGN_AUDIT_AND_PROPOSALS.md`** (repo root, untracked) - a Gemini nav/design-system audit from
  2026-08-22, not reviewed in depth. Likely mostly superseded by the 2026-08-23 UX audit above - check
  there first before reading this one.
- **Reviews page: a show dropdown instead of season grouping.** Darragh's instinct: people don't look
  for a specific season's reviews. `page_views` can't settle this (see tech debt item 4) - a judgement
  call, not a data question.
- A browsable historical-posters gallery page; costume/prop rental listings; a staging/test environment;
  edit-history/versioning with revert for society-editable data; a pantomime award category.

## Housekeeping, low priority, no urgency signal

- Audit other societies for similarly stale/presumptive data (same shape as the venue-data fixes already
  done).
- A formal `LAUNCH.md` spec, written up retroactively (the site launched organically instead).
- Real image-content validation on poster uploads (would need Pillow, not built).
- Periodically verify the nightly backup actually restores cleanly.

## Working agreements (from the 2026-08-03 process review)

- `/clear` (or a fresh session) between genuinely distinct workstreams -
  don't chain unrelated incidents/features/audits in one long thread.
- Mockup-first for anything visual - already working well, keep doing it.
- For a sweep touching many files (like Phase 0's audit), write the plan
  and get sign-off before editing, rather than fixing things as found.
- Lessons that matter beyond one session go in `docs/`, not just chat -
  already the habit for this repo, keep it up.
