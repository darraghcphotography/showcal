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

## START HERE - where things stand (2026-08-25)

**The backlog planning session cleared four of the five remaining coding items.** All pushed, all
tests green (718). What shipped: the credits import (300 titles), the box office import (72 venues),
venue categorization (`venue_type` + `/venues` filter + badge), the orphaned-title fix, and the
award-archive society links. Wikidata was dropped as superseded. The full reasoning, options and
trade-offs are in `C:\Users\Darragh\.claude\plans\ok-i-ve-done-a-nifty-star.md`.

**READ THIS BEFORE DELEGATING RESEARCH AGAIN.** Antigravity's four returned worklists split cleanly
by task type, and one was fabricated:

| Worklist | Verdict | Evidence |
|---|---|---|
| `show_credits_worklist.json` (300) | **Good - imported** | 15/15 well-known titles exactly right, including the fiddly ones (Chicago's book = Ebb & Fosse, Sweeney Todd's = Hugh Wheeler) |
| `venue_box_office_worklist.json` (108) | **Good - imported (72)** | St. Michael's New Ross matches its own contact page exactly; border-town area codes correct where a county guess would fail (New Ross/Carrick-on-Suir 051, Ballinasloe 090, Ratoath 01); all 8 shared numbers are duplicate rows for one building; 36 left blank rather than padded |
| `society_founding_years_worklist.json` (143) | **REJECTED - not imported** | **18 of 143 claim a founding year LATER than a production we already hold for that society** (WLOS claims 1952 against a 1912 record). 12-19% demonstrable error rate in *both* the Facebook-sourced and own-website-sourced halves, and 0 blanks out of 143 despite "a blank beats a guess" |
| `venues_coordinate_verification.json` (108) | **REJECTED - fabricated** | 3 of 3 sampled OSM way ids bogus: `way/437996384` is **a fence**, `way/236173007` **404s**, `way/146059174` is an unnamed building. Reported 107/108 "verified" while only appending decimal digits to our existing numbers |

**The rule:** widely-published, frequently-repeated facts (musical theatre credits, venue phone
numbers) come back reliable. Obscure single identifiers (OSM way ids, coordinates, one founding year
per society) get fabricated with confident-looking detail - especially when the task shape pressures
completeness. Delegate the former; verify the latter mechanically or do it in-house.

**Known-imprecise, accepted:** the ~87 venue coordinates imported 2026-08-24 have real drift (An
Grianán Theatre is ~290m out). Darragh's call is to leave them. Worth knowing why that's low-stakes:
`venue_detail.html`'s "Get directions" link passes the venue *name* to Google, which resolves it
properly - only the secondary "See the exact spot" link uses our stored lat/long.

## Earlier - where things stood (2026-08-24, night)

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
thing here; nothing auto-applies. 649 tests green (10 new). Deployed and verified live same day,
found two real bugs from Darragh's own phone test and fixed both (`db84764`): the link was
footer-only (invisible on mobile - added to the More page, renamed "Submit society history" per his
suggestion), and upload failed outright on a real iPhone photo (HEIC format wasn't accepted or even
renderable - both save functions now convert it via pillow-heif).

**First real submission through it closed the long-parked "OCR test on a programme photo" item** -
Darragh photographed Naas Musical Society's own 30th-anniversary programme (a 6x5 grid of poster
tiles, 1996-2026) and submitted it same day. No OCR tool needed - read directly, cross-checked all
30 productions against the database (24 already on record), and `naas_history_backfill.py`
(`a1da900`) added the 6 genuine gaps (Anything Goes 2002, The Music Man 2004, Brigadoon 2006,
Carousel 2008, Fiddler on the Roof 2010, Sister Act 2020) straight to production - verified live on
the society's own page. Real validation that this whole pipeline (submission -> read -> cross-check
-> backfill) works end to end on a real example, not just in theory.

**Second real batch, 2026-08-24 night: Tullamore and Castlerea Musical Societies' own anniversary
programmes** (3 photos, one a duplicate of another - marked rejected). Same pipeline, bigger scale -
an initial by-hand cross-check undercounted the real gap by nearly 3x (27 vs 76), caught by
re-checking programmatically against the database before writing anything.
`tullamore_castlerea_history_backfill.py` (`214debb`) added 42 Tullamore productions (mostly
1955-1976, years this database's award records never covered for them) and 34 Castlerea productions
(mostly 1968-1999, same story) - bare "this happened" rows, no award/category detail even though
both programmes have it, Darragh's call to match the Naas backfill's scope. Verified live on both
societies' pages. Left alone: Tullamore's 2018 "Sister Act" (conflicts with an existing "The Wizard
of Oz" record for that season - needs a human look, not a guess) and a couple of ±1-year date drifts
already covered within a year either way (same recorded-a-year-later pattern seen elsewhere).

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

**Antigravity's own 5-item follow-up proposal, reviewed and scoped down 2026-08-24 night**
(`52f0562`, pushed, awaiting redeploy) - before handing it the coordinate-verification homework's
results, Antigravity separately proposed 5 new data gaps unprompted. Reviewed each against real
production numbers (all were accurate) before deciding: adopted 3 as new columns + display +
homework (`founded_year` on societies, `composer`/`lyricist`/`book_author`/`licensing_house` on
show_info, `box_office_phone`/`box_office_url` on venues - all wired into their admin edit forms
and public pages, not just bare columns), rejected 2 outright - ticket-URL scraping (time-sensitive
links for shows mostly not yet on sale, and `ticket_url` is meant to be the society's own submitted
link) and historical-awards linkage (570 `historical_results` rows missing `society_id`/
`production_id` - internal/derived keys, not something an external worklist can safely guess; needs
doing directly with this repo's own matching tools instead - **not done yet, next up**). Also
declined a `stage_dimensions` column Antigravity suggested - `venue_form.html` already has a
deliberate past decision to link to a venue's own tech-spec page rather than copy dimensions in,
specifically to avoid exactly the staleness problem this would reintroduce. 680 tests green (4 new).
Second homework batch sent: `show_credits_worklist.json` (300 titles), `society_founding_years_
worklist.json` (143), `venue_box_office_worklist.json` (108), all in the gitignored `enrichment/`
folder with `CREDITS_AND_CONTACTS_BRIEF.md`.

## Next feasible things, roughly in order

- ~~**Historical awards linkage**~~ - **built 2026-08-25** (`54b7609`), awaiting redeploy. The real
  bug turned out to be silent data loss, not the missing links: `import_awards.py` wipes and reloads
  every `source='import'` row, which is *all* 540 of them, so any `society_id` set by hand was
  destroyed on the next import. Now stored in a `historical_society_links` side table keyed on the
  printed name and re-applied by the importer. New `/admin/historical-society-links` queue: 69
  distinct names, not 540 rows. Expect a small yield - only 9 names get any suggestion, and several
  of those are false positives (`distinctive_score` scores "Headford Choral" vs "Headford Musical" at
  1.00, since both reduce to a bare town name) - so the queue is built around bulk "no current
  society", with warnings and a mandatory Undo. `production_id` deliberately untouched: it's derived,
  and the rebuild recomputes it once a link marks productions stale.

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
- ~~**Venue categorization**~~ - **built 2026-08-25** (`0f97e39`), awaiting redeploy. Five types
  (Theatre / Arts Centre / School or College / Community or Parish Hall / Other), a `/venues` type
  filter with removable chips, and a neutral `.tag-tier` badge on cards and venue pages. Types are
  derived from the venue's own *name* by `classify_venue_types.py`, not from the enrichment
  worklist - that came from the same delegated pass whose coordinate half was fabricated, and its
  categories never once used "Arts Centre" despite a dozen venues being named that. Name-derivation
  is deterministic, auditable and can't invent anything; 82 of 118 classify cleanly, 7 need an
  explicit override, and the archive's place-name artifacts are never typed. Historical detail on the
  original proposal: the worthwhile core of Antigravity's `VENUE_CATEGORIZATION_PROPOSAL.md`
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
- ~~**`/admin/data-quality`'s Orphaned title data section**~~ - **fixed 2026-08-25** (`07171fe`),
  awaiting redeploy. Turned out to be two bugs: the section couldn't rename (no route anywhere could
  touch `show_info`/`show_links`' `show` primary key), *and* `_merge_titles` was manufacturing fresh
  orphans on every merge by retitling shows/historical_results while leaving the title-keyed tables
  behind. Both fixed - a Re-point action constrained to a real existing title, and a shared
  `move_title_keyed_rows()` the merge tool now calls.
- **FAQ page - built and pushed** (`0bf084b`), awaiting redeploy. Admin-managed rather than
  hardcoded, per Darragh's ask: `/admin/faq` add/edit/reorder/publish, a question stays a draft
  until explicitly published, public `/faq` only shows published ones in order. No actual questions
  written yet - that's a content task for whoever's ready to populate it, not a coding one.
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
- ~~**Show/title enrichment, Source A (Wikidata)**~~ - **dropped 2026-08-25 as superseded.** It
  targeted exactly the fields the credits worklist has now filled correctly for all 300 titles
  (composer/lyricist/book_author/licensing_house), and it was always capped at 48 of 306 titles by
  this repo's exact-title-matching rule. Source C (circuit intelligence) shipped long ago; Source B
  (licensing-house specs) was never a pipeline, just manual data entry.
- **Venue research, the long tail - mostly closed by this session's enrichment import.** Re-checked
  2026-08-24 evening: only 13 real venues (excluding known artifacts and slash-joined dual-venue
  names) still have a gap, and every one of them now has capacity/coordinates/auditorium type
  already - the only thing missing is a website. Two of the 13 turned out to be duplicate venue rows
  split by apostrophe placement (`Scout's Hall, Nenagh` / `Scouts' Hall, Nenagh`, and `Tullyvin
  Community Centre` / `Tullyvin Community Centre, Cavan`) - a quick manual merge via
  `/admin/venue-directory`, not research. Six of the 30 highest-traffic venues still have no map
  pin: **St. Mary's College Arklow, The Abbey Clane and Loughrea Temperance Hall**. All three are
  confirmed real - OpenStreetMap simply has no entry for them findable by name, and Eircodes don't
  help (Nominatim doesn't index them and fuzzy-matches to unrelated addresses). They need a
  different source, not another search.
- **Venue coordinate verification - homework handed to Antigravity 2026-08-24 evening**
  (`enrichment/venues_coordinate_verification.json` + brief, gitignored). Diffed
  `GOOGLE_MAPS_INTEGRATION_PROPOSAL.md`'s 109-venue list against production directly rather than
  trusting the proposal doc's own claims: 85 matched an existing venue by name (not 87 as
  previously estimated - some were already covered by this session's own import), only 24 had no
  match at all, and a rough distance check found just 2 with notable drift - much better than the
  proposal's own "76 of 83 suspiciously rounded" claim, though that was a loose check (~1km
  threshold), which is exactly why this is going to a second, independent research pass rather than
  being trusted either way. The homework is broader than just those flagged 2: verify all 108 real
  venues (5 known artifacts/slash-combos excluded) against OpenStreetMap, plus find a website for
  the 19 that don't have one. Sections 1-2 of the same proposal are already adopted.

- **Society founding years - needs a different method, not another delegated pass.** The
  `founded_year` column, admin field and public display all shipped (`52f0562`), but the researched
  data was rejected: 18 of 143 claimed a year later than a production we already hold, a 12-19%
  demonstrable error rate in both the Facebook-sourced and own-website-sourced halves. Two are
  independently corroborated from the programme photos already read (Castlerea 1968, Tullamore 1954)
  and could be entered by hand. A workable automated approach would be to only accept a year that a
  society's own site states explicitly *and* that doesn't contradict our earliest record for them -
  that contradiction check is cheap and already written, and it's a genuine floor: a society with a
  1912 award record was demonstrably founded on or before 1912.

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
