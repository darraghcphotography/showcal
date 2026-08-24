# Roadmap

Tracks the current phase of work and genuinely open items, so a new session (after `/clear` or a fresh
start) can pick up without re-deriving context. Update this file - don't just say the plan out loud in
chat - whenever the phase changes.

**Pruned three times now** (2026-08-20, 2026-08-23, 2026-08-24) - each time because it had grown into a
chronological session log of mostly-shipped work, and CLAUDE.md's own rule says to read it at the start
of every session. Full history (every Round, every Phase, every session's blow-by-blow) is preserved
verbatim in `ROADMAP_ARCHIVE.md` - nothing was ever deleted, just moved out of the file that gets read
every session. This file holds only: the current phase, and a flat list of items that are genuinely
still open (not started, explicitly parked, or blocked on something). When a session fully resolves an
open item, move its entry to `ROADMAP_ARCHIVE.md` rather than letting resolved items accumulate here
again.

## START HERE - where things stand (2026-08-24, night)

**Rehearsal Room theme shipped site-wide, pushed not yet deployed (`48c4044`).** Darragh greenlit
it after reviewing a fuller mockup (7 real page types, not just the homepage comparison from
earlier). Warm paper instead of white, one restrained ink accent instead of burgundy-and-gold,
Archivo replacing Fraunces for headings - all token-driven in `style.css`, no template changes.
Also fixed a stray hardcoded color found along the way (mobile nav's active-tab red wasn't using
`var(--accent)`) and retuned `--gold` to match the new palette (the old goldenrod clashed once
tried against the new background for real). 639 tests green, verified locally with Playwright
screenshots (home light/dark, Awards, a title's circuit-intelligence page). **Needs a Portainer
redeploy to go live** - same pattern as everything else in this repo, not something Claude can
trigger. Also fixed the same session, separately: the 4+4 "Orphaned title data" rows from the
admin data-quality page (`Beauty and the Beast` etc. vs the site's Title-Case-everywhere
convention) - corrected directly on the production database (renamed, not deleted, so the real
synopsis/rights/Wikipedia content attached to them is live again), verified via WebFetch against
the real page. Found a real bug while fixing it: the "Edit" link that page points to for
`show_info` can't actually change the title (the form only edits synopsis/rights fields, keyed by
the existing title), and "Clear" for `show_links` only deletes - so neither affordance can
actually fix what the page describes. Not fixed this session; worth a small admin-UI job later so
the next orphaned title doesn't need an SSH session.

**`/season` page weight, measured and closed** - the next item on the list asked for a real
measurement (Playwright + CDP throttling, same method as the `/titles` check) rather than assuming
the site-wide compression fix from earlier today covered it. It does: 66.7KB over the wire (down
from an uncompressed ~197KB), 16,276px tall, 2.7s interactive on a genuine Slow 3G profile -
comparable to `/titles`'s own post-fix numbers (79KB, 3.3s). No pagination or further work needed;
removed from the open-items list below.

**Everything is shipped, deployed and verified live as of this evening.** The morning queue, all
four phases of the UI-polish plan, and all 8 items of the Second Act backlog (homepage poster
placeholder, two-column show/society detail layout, the reviews card grid, awards page polish,
mobile "back to top," response compression, and admin dashboard urgency dots) are live on
production - checked directly against the real site, not assumed from a `git push`. Test suite is
639 and green. Full detail, commit hashes and the live-check evidence for all of it is in
`ROADMAP_ARCHIVE.md` under "Morning queue, 2026-08-24," "UI-polish plan," and "Second Act backlog"
- nothing below duplicates it.

**The Rehearsal Room theme (`48c4044`) is deployed and verified live** - confirmed the same
evening by a full 11-page screenshot run-through (light+dark+mobile): both Archivo weights serve,
the old Fraunces file 404s, every page renders coherently in the new palette. The run-through's
full findings (poster weight, polish micro-batch - both now open items below), the user-feedback
triage state (all 6 suggestions handled, SpongeBob fix verified live), and a repo tidy-up list
(2 stale worktrees totalling 24MB, stale branches, ~2.7MB of root-directory strays, empty scratch
dirs) are in the "Opening Night Notes" artifact:
https://claude.ai/code/artifact/c82c78fa-e1b8-4beb-9a73-158e39a0d409 - tidy-up suggested, not
executed, awaiting Darragh's go-ahead. Nothing else is queued for deploy.

## Next feasible things, roughly in order

- **Poster thumbnail pipeline** - found in the 2026-08-24 evening run-through: posters serve at
  original upload size (homepage total 3,154KB across 8 images, one alone 1.36MB, all rendered
  54px wide). `loading="lazy"` softens it but above-fold posters always pay full price, and the
  planned poster drive would make it worse. Fix: generate a small WebP at upload time + a one-off
  backfill script for the ~41 existing files. Needs Pillow - same dependency the housekeeping
  list's "image-content validation" item already wants, so one job delivers both. Biggest
  user-facing perf lever now that compression shipped (this is ~25x the compression win).
- **Theme-polish micro-batch** (from the same run-through, all small): (1) date formats disagree -
  homepage says "28-29 Aug 2026", a title page's productions table says "20-04-2027 - 25-04-2027";
  human form should win everywhere. (2) venue cards print "Dublin, Dublin" when town == county.
  (3) title-case normalizer produces "The 25Th Annual Putnam County Spelling Bee" - capitalizes
  after a digit; ordinals are common in titles. (4) society show-history prints literal "None" in
  the Review column where Awards uses an em-dash. (5) society detail hero leaves its right column
  empty at desktop - region/tier line sits above the logo and badges below it, unlike the show
  page's proper two-column hero.
- **`/admin/data-quality`'s Orphaned title data section can't actually fix what it describes** -
  found 2026-08-24 while resolving a real instance of it. The "Edit" link for `show_info` only
  edits synopsis/rights fields (keyed by the existing title, no rename field); "Clear" for
  `show_links` only deletes. Neither can correct a title-casing mismatch, which is the entire
  premise of that section's own hint text. A small job: add a way to rename the `show` key on both
  tables (to a real match already in `shows`/`historical_results`, not a free-text field - keeps
  the site's no-fuzzy-matching rule intact) so the next orphaned title doesn't need direct database
  access to fix.
- **FAQ page** - real questions already gathered (what is AIMS, how do I join, which societies are
  near me). Smallest self-contained new page on the list. Confirmed not built yet (`/faq` still
  404s on the live site).
- **Merge duplicate/near-duplicate titles the A-Z now shows** (`/admin/duplicate-titles`) - 7
  spelling variants of titles already on the list became visible when the productions cutover
  stopped hiding them: `Annie - The Musical`, `Big The Musical`, `Elf - The Musical`,
  `Fame: The Musical`, `Shrek`, `Peter Pan, A Musical Adventure`,
  `Sugar The Musical - Some Like It Hot`. Real merge work, deliberately kept out of the cutover so
  the migration wasn't blocked behind a manual title pass.
- **Show/title enrichment, Source C follow-ups** - Source C (circuit intelligence) already shipped.
  Source A (Wikidata) has a real bug in its proposed query (`wdt:P58` should be `wdt:P87`) and only
  reliably resolves 48 of 306 titles without fuzzy title-matching, which this repo avoids - fix the
  query before building. Source B (licensing-house specs) isn't a pipeline, it's manual data entry.
- **Venue research, the long tail** - the 30 venues with 5+ productions were done already
  (`enrich_venues.py`); ~110 venues with 1-4 productions still have nothing. Same script, extend
  its `DATA` table. Lower value per venue, so only worth doing if the first pass proves itself.
  Six of the 30 also still have no map pin: **St. Mary's College Arklow, The Abbey Clane and
  Loughrea Temperance Hall**. All three are confirmed real - OpenStreetMap simply has no entry for
  them findable by name, and Eircodes don't help (Nominatim doesn't index them and fuzzy-matches to
  unrelated addresses). They need a different source, not another search.
- **`GOOGLE_MAPS_INTEGRATION_PROPOSAL.md`, section 3** - a 109-venue list (54 of them venues this
  repo has no record of at all), but the coordinates need OSM verification first (76 of 83 new ones
  are suspiciously rounded, and spot-checks found real drift - see the archive for the specific
  measurements). Mechanical work, not manual: geocode each one, accept where it agrees with OSM
  within a couple hundred metres, flag where it doesn't. Sections 1-2 of the same proposal are
  already adopted.

## Data-accuracy follow-ups (from the 2026-08-23 report check), need Darragh's input or real research

- **297 `historical_results` rows with `category_name IS NULL`, 274 of them pre-2001** - needs real
  historical AIMS awards-programme research; a Gemini report only sampled 6 of them.
- **~10 unmapped historical societies with no existing `societies` row** (Bangor Operatic Society, De La
  Salle Musical Society Waterford, others) - creating new historical society records is a structural
  decision, not a data-quality bugfix.
- **28 orphaned Inactive societies with zero shows/awards** - retain or remove is a judgment call, no
  urgency signal.
- **19 of 23 researched societies' online production archives not yet backfilled** (research inventory
  exists, only 4 done so far).
- **~112 stale orphaned `historical_reviews` rows** - cross-referenced as real, but explicitly not
  deleted pending a more rigorous verification method than what was used to find them.

## UX-audit remaining slivers (the bigger bets themselves shipped 2026-08-24 - see archive)

- **Society page** - venue links + next-show callout shipped; still open: the original mockup's
  fuller "empty vs. filled" pitch beyond that.
- **Show page** - venue capacity/town, about-the-society blurb and circuit summary all shipped;
  still open: cross-links to other societies who've staged the same show, a share affordance.
- **Outreach/onboarding track** (non-technical, Darragh's lever, not a coding task) - a nudge on a
  society's own page when its profile is thin, 2-3 exemplar societies filled in completely as a
  reference, a draft message to send a committee, a "claim your page" request route.

## Parked, each wants its own dedicated session or decision, none started

- **Member-contributed historical photo upload, for backfilling gaps in old productions.** Raised
  2026-08-24 (Darragh may contribute himself). Doesn't exist today - the only upload path is a
  poster field tied to one specific show's own edit form (a society or moderator editing that
  show), not a general "here's an old programme photo, use it" flow. Distinct from two related
  parked ideas below: the posters-gallery/programme-museum page is *display* of posters already in
  the system; this is *intake* of new material to fill data gaps (cast, director, venue, date) on
  productions that have little or no record. Recommended v1 scope, needs Darragh's sign-off before
  a mockup: an upload form (which production is this, from a picker or free-text if no match
  exists) that stores the photo plus the uploader's own free-text notes, landing in a moderation
  queue - same pattern already used for member submissions and historical reviews, nothing
  auto-applies to real data. A moderator reads the photo and manually enters whatever it confirms;
  OCR is explicitly out of v1, revisited once the already-parked "OCR test on a programme photo"
  below has a real sample to test against. Open questions for Darragh: who can upload (any AIMS
  member via society login, or open to the public) and whether an upload needs to match an
  existing production row or can sit unmatched for a moderator to triage later.
- **`match_show_for_edit` never fuzzy-matches** against `shows` (exact match only) - a systemic version
  of a title-mismatch bug already fixed once for a specific case, not yet generalized.
- **Person/person-page identity resolution** - parked on Darragh's privacy objection to public person
  pages. Internal-only dedup was agreed as the resolution path but never built.
- **`/admin/duplicate-titles` UX redesign** - asked for once, later called "not really an issue" when a
  real mockup existed. Low priority.
- **`DESIGN_AUDIT_AND_PROPOSALS.md`** (repo root, untracked) - a Gemini nav/design-system audit from
  2026-08-22, not reviewed in depth. Likely mostly superseded by the 2026-08-23 UX audit - check
  there first before reading this one.
- **Reviews page: a show dropdown instead of season grouping.** Darragh's instinct: people don't look
  for a specific season's reviews. `page_views` can't settle this (see tech debt item below) - a
  judgement call, not a data question.
- A browsable historical-posters gallery page; costume/prop rental listings; a staging/test environment;
  edit-history/versioning with revert for society-editable data; a pantomime award category.
- From an untracked `FEATURE_IDEAS.md` (deleted 2026-08-24, everything else in it either already shipped
  or already tracked above) - three genuinely new, unclaimed ideas: a 1-click Instagram/Facebook social
  card generator per show (poster + logo + opening countdown + QR code); automated society milestone
  badges (e.g. "100+ productions", "3+ Best Overall Show wins"); a browsable programme-cover/poster
  museum page (overlaps the posters-gallery idea above, but framed as a designer-credited visual archive
  rather than a plain gallery).
- From an untracked `AUDIT_AND_RECOMMENDATIONS.md` (deleted 2026-08-24 - its case-insensitive-index,
  WAL-mode/busy-timeout, and admin.py-split recommendations were all already independently done) - five
  genuinely new, unclaimed ideas: a poster lightbox/zoom on show pages; a zero-login "My Season
  Watchlist" (localStorage bookmarks + a personal .ics export); an "On This Day in AIMS History"
  homepage widget; an embeddable per-society JSON feed/widget for a society's own website. (Its
  "removable filter chips" idea shipped on `/awards` 2026-08-24 - still open for `/season`/`/stats` if
  either grows a filter form worth the same treatment.) Also worth a note: a fuller interactive
  Leaflet/OSM pin map (colour-coded by region, filterable by tier) as a richer successor to the
  list-based Near-me toggle, once venue pin coverage is higher.

## Waiting on Darragh, not a coding task

- **Posters** - 41 exist against ~200 current-era shows. Gates the whole visual redesign (type/palette
  pass, then per-page components) - a poster-led design would be mostly empty frames without more of
  these.
- **OCR test on a programme photo** - blocked on Darragh sending one.

## Technical debt

1. **`productions_build.py` and `venues_build.py` duplicate the same freshness machinery** -
   `FINGERPRINT_SQL`, `fingerprint()`, `mark_stale()`, `ensure_current()` and a one-row `*_build_state`
   table, written twice. Less pressing now that `ensure_current()` itself has one caller for both
   (a shared `before_request`) rather than sixteen scattered call sites - the duplication left is
   two near-identical private helpers, not a rule spread over six modules.
2. **FTS indexes rebuild on every startup.** Known, deliberate, documented in `db.py` - the obvious
   `COUNT(*)` guard doesn't work on an external-content FTS5 table. Left alone on purpose.
3. **`page_views` is keyed on path only**, so no query-string question can ever be answered from it.
   Fine as a popularity counter, useless as analytics. Only worth changing if a real question needs it.

## Housekeeping, low priority, no urgency signal

- Audit other societies for similarly stale/presumptive data (same shape as the venue-data fixes already
  done).
- A formal `LAUNCH.md` spec, written up retroactively (the site launched organically instead).
- Real image-content validation on poster uploads (would need Pillow, not built).
- **Backups sit on the same volume as the database** (`/data/backups` beside `/data/aims.db`). They
  survive a bad script or a bad deploy, which is what they're mostly for - but not the disk. An
  off-box copy (QNAP HBS3 pointed at `/share/CACHEDEV1_DATA/Data/config/aims-web`) is the missing
  half, and it's a NAS configuration job rather than a code one.

## Working agreements (from the 2026-08-03 process review)

- `/clear` (or a fresh session) between genuinely distinct workstreams -
  don't chain unrelated incidents/features/audits in one long thread.
- Mockup-first for anything visual - already working well, keep doing it.
- For a sweep touching many files (like Phase 0's audit), write the plan
  and get sign-off before editing, rather than fixing things as found.
- Lessons that matter beyond one session go in `docs/`, not just chat -
  already the habit for this repo, keep it up.
