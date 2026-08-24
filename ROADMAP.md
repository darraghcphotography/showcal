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

**Antigravity enrichment pass: spot-checked and imported to production, done.** Three worklists
Claude generated from real production gaps (`societies_worklist.json` - 189 societies with zero
social/about info, `venues_worklist.json` - 87 venues missing capacity/coordinates/website,
`shows_worklist.json` - 239 titles with no synopsis/rights data) came back from Antigravity filled
in. Spot-checking `societies_worklist.json` caught a real bug before import: the `about`/social
fields were shifted +2 rows out of alignment (database ids aren't contiguous - a dict keyed by
sequential position instead of the real id desynced wherever the sequence skips). Flagged, fixed,
re-verified clean.

Three new fill-blanks-only scripts import each file (`import_society_enrichment.py`,
`import_venue_enrichment.py`, `import_show_enrichment.py`, committed `2cc26bc`) - same trust model
as `enrich_venues.py`: only ever write a currently-NULL field, so a real value a society/moderator
already entered always wins, safe to re-run. Societies matched by stable id, venues matched by name
through `venue_aliases` (ids aren't stable across a rebuild), shows matched by exact title. Ran
`--dry-run` locally and against production before committing for real; verified the committed values
directly in the database afterward. **135 of 189 societies, 87 of 87 venues, and 239 of 239 shows
now have real data** (the other 54 societies already had something in every field offered).

`venue_type` (82 values Antigravity provided per-venue) was deliberately **not** written anywhere -
there's no column for it yet. Adding one is the real feature decision the "Venue categorization"
item below still describes (schema + `/venues` filter + badges), not a data-import task. The
researched values are sitting in `D:\showdb\enrichment\venues_worklist.json` (gitignored, still on
disk) whenever that item gets picked up - re-running `import_venue_enrichment.py` after the column
exists will report them again instead of needing to regenerate them.

Four rows were deliberately excluded from `venues_worklist.json` before handoff - `Cork`,
`Wexford`, `Cork run`, `40th Anniversary (March run)` (known data-entry artifacts, not real
venues) - still need a source-level fix, unrelated to this import.

**Public photo-submission intake built** (`c12b927`, pushed, awaiting redeploy) - resolves the
"Member-contributed historical photo upload" item that used to sit in Parked below. `/submit/photo`
(footer-linked, no login, rate-limited, honeypot) takes pre-2009 ShowTimes review clippings (older
than the digitized PDF archive `extract_historical_reviews.py` works from) and old production
photos/programmes, into a new `photo_submissions` table and `/admin/photo-submissions` queue.
Darragh's calls on the open questions this item used to carry: one combined form (not two), open to
the public (not gated behind a society login), and an upload can sit unmatched - society/show/date
are free text, no requirement to pick an existing production. A moderator reads each one and enters
what it confirms into the real tables by hand, same trust model as every other member-contributed
thing here; nothing auto-applies. 649 tests green (10 new). Not yet verified live - needs the same
Portainer redeploy as everything else pushed this session.

**After the enrichment import, the next three items are scoped and ready for a Sonnet session**
(not Fable - implementation work, no open design questions left): the poster thumbnail pipeline,
the theme-polish micro-batch, and the duplicate-title merges. All three are written up in full
below with enough detail that a fresh session can start directly from this file - no need to
re-derive anything from chat history. Point a cleared/new session at this file and this section.

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

- **Poster thumbnail pipeline - built, awaiting redeploy + backfill run.** `save_poster` now
  downscales to 600px and re-encodes as WebP at upload time (`beead5b`, pushed); Pillow added to
  requirements.txt. `backfill_poster_thumbnails.py` does the same conversion for the ~44 posters
  uploaded before this shipped - **needs a Portainer redeploy first** (Pillow has to actually be
  installed in the image), then run it for real against `/data/uploads` (dry-run first to see the
  before/after sizes). 654 tests green (5 new, first time any test exercised real image bytes
  through save_poster). Housekeeping's "image-content validation" item can reuse this same Pillow
  dependency once picked up.
- **Theme-polish micro-batch - built and pushed** (`0ca3d95`), awaiting the same Portainer redeploy
  as everything else this session. All five from the run-through: dates now use `date_range`
  everywhere (was mixing in `irish_date`'s numeric form on the title page and society dashboard);
  a new `place_label` filter drops the repeat when a venue's town and county share a name; the
  literal `'None'` `review_status` value now renders as an em-dash via the existing `destub` filter
  (society and show detail pages); `extract_historical_reviews.py`'s title-casing no longer
  capitalizes after a digit (ordinals); the society detail hero's region/tier line and trophy case
  now live inside its right column instead of outside the hero grid. 661 tests green (7 new).
  **One follow-up still needed once deployed**: `fix_ordinal_titlecasing.py` corrects 7
  already-affected `historical_reviews`/`shows` rows (`42nd Street`, `The 25th Annual Putnam County
  Spelling Bee`) - run with `--dry-run` first, then for real, same pattern as every other one-off
  script here.
- **Venue categorization (`venue_type` column + directory filter)** - data gathering done
  (2026-08-24: 82 venues now have a researched `venue_type` sitting in
  `enrichment/venues_worklist.json`, not yet written anywhere - see START HERE). What's left is the
  actual feature: the worthwhile core of Antigravity's `VENUE_CATEGORIZATION_PROPOSAL.md`
  (2026-08-24, gitignored input doc, reviewed same day) is the 5-category schema idea, the
  `/venues` filter, badges on venue pages - fits the existing tier-badge/filter-chip patterns, and
  the doc correctly identified that `venues` is a derived table needing `CURATED_COLUMNS`
  treatment. **Do not adopt as-is**: its CSS is hardcoded Tailwind-dark-palette hexes that violate
  the token system and the Rehearsal Room theme (restyle in our tokens); its master directory is
  unvetted - it lists Mandela Hall as an operational 1,000-seat venue when this repo already
  flagged that building as demolished 2018-2020, and its claimed per-category counts don't match
  its own table lengths.
- **Society social-links harvest** - done 2026-08-24: 135 of 189 societies with a real gap now have
  `about`/`facebook_url`/`instagram_url` (and some `website_url`), imported and verified live (see
  START HERE). Originated from Antigravity's `DATA_ENRICHMENT_AND_SCRAPING_OPPORTUNITIES.md`
  (gitignored, reviewed 2026-08-24), whose fill-rate audit checked out against production before
  the work started. **Not adopted from the same doc**: automated scraping of MTI/Concord (repo
  already concluded that's manual entry; ToS-hostile), Facebook/Instagram content scraping (ToS),
  its "~280 of 300 titles" Wikidata yield claim (contradicts this repo's measured 48/306 without
  fuzzy matching), and piping scraped society archives "directly into shows" (conflicts with the
  moderation-first/skeleton-row pattern; the archive-backfill item above already tracks this
  properly). Its Ticketsolve ticket_url idea is plausible for a later pass.
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
- **Merge duplicate/near-duplicate titles - narrowed down, script built, awaiting redeploy.** The
  original list of 7 (from the cutover) turned out stale on inspection (`7d57e6c`) - `Annie - The
  Musical`/`Elf - The Musical`/`Shrek` no longer have a variant to merge, `Big Fish`/`Big The
  Musical` are different shows entirely, and the site's own fuzzy detector currently flags zero
  candidates. Only two have real evidence (a society staging the same show under both spellings):
  `Fame` -> `Fame: The Musical`, `Sugar The Musical - Some Like It Hot` -> `Sugar`.
  `merge_duplicate_titles.py` does both, plus untangles a show_info collision the plain merge tool
  doesn't handle (both Fame titles already carry their own show_info row from this session's
  enrichment import). **`Peter Pan` / `Peter Pan, A Musical Adventure` deliberately left alone** -
  no overlapping society, and the latter is a real distinct licensed title (Piers Chater-Robinson) -
  needs Darragh's own knowledge of the two productions, not more digging.
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
