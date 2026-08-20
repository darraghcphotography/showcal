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

## START HERE - society misattribution fix applied and verified live (2026-08-20)

Darragh spotted a wrong society on a live show page (Calamity Jane filed under Carnew Musical Society
when the review's own text names Clane) via `/admin/society-corrections` - that page only ever fixes
the internal `society_raw` citation label, never `show_id`, so approving the suggestion there couldn't
have fixed it. Investigated properly: read all 80 `society_gate_suggestions.json` entries' own review
text against a real copy of production (the extractor-gate branch itself has a known remaining gap, so
its suggestions needed checking, not trusting).

**Result: 43 real misattributions confirmed and fixed, applied and verified live this session.**
`fix_society_misattributions.py` (repo root) - dry-run and test-applied against a disposable copy
first, then run for real over SSH, then independently re-verified against a fresh pull of production.
Fixed: 25 shows repointed to an already-registered society, 7 new society records created for real
societies that had no record at all (Belfast Music and Drama Society, Meath Youth Musical Society,
Encore Theatre Company, Patrician Musical Society, Headford Musical Society, New Lyric Operatic
Company Belfast) with 11 shows repointed to them, 2 duplicate ShowTimes reviews removed, 1 review's
title+society both corrected (was linked to a show with a completely different title), 5 stale
`/admin/society-corrections` suggestions dismissed (confirmed wrong from the review's own text).

**Left deliberately unfixed, carried forward below**: 5 confirmed-real misattributions where the
correct society's region/identity is still ambiguous, and 3 the review text alone couldn't settle
either way.

## Open items

Flat list, no particular order beyond roughly how it was prioritized when last discussed. Full
reasoning/history for any of these is in `ROADMAP_ARCHIVE.md` if needed - search there for a keyword
before re-deriving from scratch.

**Society misattribution follow-ups (from today's fix, see above):**
- 5 reviews confirmed misattributed but not fixed - correct society's region/identity needs a real
  decision, not a guess: **ESB Musical and Dramatic Society** (review 673, region unconfirmed), **"SONG"**
  (review 595, Dundalk-based, full name/expansion unknown), **The Real Theatre Company** (review 367,
  confirmed real, no location found), **National Youth Musical Theatre** (review 366, confirmed via
  "NYMT" acronym, but it's a touring/national group not tied to one AIMS region), **UL Musical Theatre
  Society** (review 951, confirmed via text, but unclear if it's the same entity as the already-
  registered "University of Limerick Musical Theatre Society" id 124 or a separate group).
- 3 reviews still unresolved from the text alone: review 577 (Ratoath vs Meath Youth, same pattern as
  two already-fixed cases but this one's text doesn't name either), review 440 (Craic Theatre vs
  suggested Civic Theatre - "Civic" may be the venue, not the society), review 790 (Kill vs Belfast
  Music and Drama Society - plausible via venue, not textually confirmed).
- `extractor-society-gate` branch (`edd445e`) still unmerged - has its own known remaining gap
  (confuses "Newcastle Glees" with "Newcastlewest"). Needs that fixed before merging.
- Worth a fresh sweep for other near-identical-society pairs beyond what's already been caught - the
  Carnew/Clane pattern alone hid 5 misattributed reviews before today's proper cross-check.

**Search - diagnosed 2026-08-19, not fixed.** Searching a real award-winner's name ('april kelly')
returns correct hits but they render dead last, under noise matches - the actual bugs:
- Award-nominee results render below Societies/Shows/Reviews even on an exact full-name hit - should be
  a layout/ordering fix, not a ranking algorithm change.
- No phrase search - `app/search.py` ANDs whitespace-split terms anywhere in the text, so "april kelly"
  matches "in April... Jonathan Kelly" as a false positive.
- Snippet centers on the earliest matching term, not where terms cluster - shows misleading snippets
  even on a correct match.
- Typed quotes break the Shows/Titles search specifically (`LIKE %...%` on the raw string treats them
  as literal characters) while FTS-backed sections strip them fine.
- No relevance ranking - reviews sort by season, not match quality. Wants bm25.

**Productions table migration - flagged for Opus specifically**, real architecture decision (`shows`/
`historical_results`/`historical_reviews` becoming one source of truth via a `productions` table),
touches most of the app's query surface, high blast radius if got wrong. Full scoping brief (what
exists today, proposed shape, backfill/verification plan, staged cutover order) is in
`ROADMAP_ARCHIVE.md` - search for "Scoping brief for the productions-table session". Do it in an
isolated worktree, additive-only first pass.

**OCR test on a programme photo** - blocked on Darragh sending one. Small once a photo exists (test
extraction accuracy first, design nothing before seeing real output).

**Venue-data gap** - still ~88 shows missing a venue as of the last check, despite the venue-backfill
tool already existing.

**People/person-page identity resolution** - parked on Darragh's privacy objection to public person
pages. Agreed resolution path (internal-only dedup/matching, no public person pages) was never built.

**Review-author byline** - a `review_author` column + admin form + template change, discussed but never
built. Two open design questions block it: backfill existing reviews or forward-only, and whether
authorship is per-person or per-publication.

**`/admin/duplicate-titles` UX redesign** - Darragh asked for mockups specifically at one point, later
called the underlying issue "not really an issue" when a real mockup existed. Parked, low priority.

**Junk skeleton-show-title cleanup** - 8 garbled titles fixed from the same truncated-extraction bug,
but a fresh full-archive sweep for more instances (the fix pattern's match threshold might miss some)
was flagged as worth doing and never run.

**Two smaller open design questions**: what should happen when a society later fills in real detail on
a skeleton show (created just to host a ShowTimes review); and the society self-service "add a show"
form has no check against `historical_results` for double-counting a show that's already on record via
an award entry (flagged, not confirmed to have actually bitten anyone yet).

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
