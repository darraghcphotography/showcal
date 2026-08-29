# Roadmap Archive

Full history of ROADMAP.md as it stood through 2026-08-20, before it was split into a lean
live ROADMAP.md (current phase + genuinely open items only) and this archive (everything shipped,
delivered, or superseded, kept for reference). Nothing here needs action - if an item below turned
out to still be open, it was carried forward into ROADMAP.md's Open Items list separately.

---

## 2026-08-29 - the two ranked dev items closed

**R6 - `SECRET_KEY` fail-fast.** `create_app` now raises `RuntimeError` instead of logging a
warning when the insecure default key is in use *and* `AIMS_DB_PATH` is set (the production
signal already used for `SESSION_COOKIE_SECURE`). A known key lets anyone forge a moderator
session cookie, and the warning scrolled past in the container log while the site came up
looking perfectly healthy. Local `flask run` never sets `AIMS_DB_PATH`, so dev still works on
the default and only warns. `stack.env` holds a real 64-char key, so this cannot take
production down.

**4b - photo form to three kinds** (four, in the end). `photo_submissions.kind` was
`review`/`production_photo`, with a programme page listing a society's past productions lumped
in with cast photos. Those pages backfill whole decades of the record, so they are now
`programme_history` in their own right, with `programme_cover` split out as well. SQLite cannot
`ALTER` a `CHECK` constraint, so `app/db.py`'s `_migrate_photo_submission_kinds` rebuilds the
table the standard way, keyed off the live table's own `CHECK` text from `sqlite_master` (same
pattern as `_migrate_shows_source_check`). Existing rows keep the kind they were submitted
under - re-sorting them is a judgement only a moderator looking at the photo can make, so every
reader must keep handling `production_photo`. Labels live once in
`app/constants.py`'s `PHOTO_KIND_LABELS` and drive both the public form and the admin queue.

906 tests green.

## Session of 2026-08-24/25 - the backlog clear-out - DELIVERED

Everything below shipped, was verified live on production, and is no longer an open item. Moved out
of ROADMAP.md on 2026-08-25 under that file's own rule (resolved items go here rather than
accumulating there again - it had drifted back into a chronological log for the fourth time).

Headline: the last of the ready-to-build backlog was cleared. 680 -> 718 tests. Shipped across the
two days: the public photo-submission intake and its two same-day bug fixes, the poster thumbnail
pipeline (plus the WebP Content-Type regression it caused and its fix), the theme-polish micro-batch,
the FAQ page, duplicate-title merges, venue categorization, the orphaned-title fix, the award-archive
society links, the credits and box-office imports, and four programme-photo backfills.

### What was in "Next feasible things" and is now done


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

- **Society founding years - re-run handed to Antigravity 2026-08-25** with a method that makes a
  guess fail visibly: `society_founding_years_v2.json` carries a hard `must_be_on_or_before` per row
  (119 of 143), derived from our own earliest award record for that society, and requires a verbatim
  `evidence_quote` from the page stating the year. Two rows are effectively known-answer controls -
  Tullamore and Castlerea are independently corroborated at 1954 and 1968 from the programme photos
  already read, so their answers can be checked without fetching anything. **Background on why the
  first attempt was rejected:** The
  `founded_year` column, admin field and public display all shipped (`52f0562`), but the researched
  data was rejected: 18 of 143 claimed a year later than a production we already hold, a 12-19%
  demonstrable error rate in both the Facebook-sourced and own-website-sourced halves. Two are
  independently corroborated from the programme photos already read (Castlerea 1968, Tullamore 1954)
  and could be entered by hand. A workable automated approach would be to only accept a year that a
  society's own site states explicitly *and* that doesn't contradict our earliest record for them -
  that contradiction check is cheap and already written, and it's a genuine floor: a society with a
  1912 award record was demonstrably founded on or before 1912.


### The 2026-08-24 evening state, verbatim


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


---

## Admin: "Shows missing a date" counter mismatch - FIXED 2026-08-23 (late session)

Second instance of the same bug shape as the 115-vs-29 review-link counter. The dashboard counter
(`dashboard.py`) excluded `source='historical'` skeleton rows, which can never have real dates;
`fix_dates()`'s `missing=1` filter (`admin/misc.py`) didn't. Measured on real data: counter said 30,
page listed 812, so a moderator clicking "30" met 782 unactionable rows. Fixed the same way as the
precedent - one shared `MISSING_DATES_WHERE` in `admin/_shared.py`, used by both sides, with the
history in the comment above it. Three tests in `tests/test_missing_dates_filter.py`, mirroring
`test_needs_review_filter.py`; suite 582 green.

---

# Roadmap

## START HERE - fix_society_misattributions.py ready to run, NOT yet applied (2026-08-20, later session)

Darragh spotted a wrong society on a live show page (`/shows/1825`, Calamity Jane filed under Carnew
Musical Society when the review's own text names Clane) via `/admin/society-corrections`, and asked
"how can I sanity check the reviews... how can I fix this?" - that page only ever fixes the internal
`society_raw` citation label, never `show_id`, so it couldn't have fixed this even if approved (see the
banner text on that page). Investigated properly rather than fixing the one instance:

- **Read every one of the 80 `society_gate_suggestions.json` entries' own review text** (not just
  trusting the extractor-gate branch's suggestion) against a real read-only copy of production pulled
  over SSH (`aims_prod.db`, see this file's SSH/scp notes further down for the mechanism) - the branch
  itself has a known remaining gap (Newcastle Glees vs Newcastlewest, see the "Near-identical-society
  audit" section below), so its suggestions needed checking, not trusting.
- **Confirmed 43 real misattributions this way, plus 5 suggestions that are themselves WRONG** (the
  review's own text confirms its current society is already correct - e.g. one literally says "at the
  Venue in Ratoath") and **3 genuinely unresolved** (text doesn't settle it either way, left for
  Darragh). Full detail and reasoning trail is in this conversation's history, not repeated here.
- **Carnew Musical Society's skeleton shows turned out to be a repeat dumping ground for Clane's
  reviews** - beyond the Little Shop of Horrors instance already fixed in Round 35, 4 more (Hello
  Dolly, Sweeney Todd, Godspell, Carousel, plus Darragh's own Calamity Jane find) all explicitly name
  Clane's small Abbey venue in their own opening lines. Same root cause, just not fully swept last time.
- **Also found real reviews for genuinely unregistered societies** - "Belfast Music and Drama Society"
  (3 reviews explicitly name it, one gives its 2015 founding year), "Meath Youth Musical Society",
  "Encore Theatre Company", "Patrician Musical Society" (Trim), "Headford Musical Society", "New Lyric
  Operatic Company, Belfast" - none of these had a `societies` row at all, so simply repointing wasn't
  enough; the fix creates them first.
- **A second, independent bug found along the way**: review 441's own `show_raw` ("RENT (School
  Edition)") didn't even match the skeleton show's title it was linked to ("Miss Saigon (School
  Edition)") - confirmed via the review's own text (unambiguously about Rent). One combined title+society
  fix, not two separate ones.
- **2 of the 43 turned out to be the same ShowTimes review extracted twice** (>99.8% identical text,
  same issue) - one copy already correctly placed, the other on a wrong show. Same shape as Round 35's
  ShowTimes duplicate cleanup - delete the wrong copy, not a repoint.
- **`fix_society_misattributions.py` written, dry-run AND full test-applied against a disposable copy of
  the real data** - every assertion passed, ran clean end-to-end (36 shows repointed/retitled, 2
  duplicate reviews removed, 7 new societies created, 5 stale suggestions dismissed), spot-checked the
  Calamity Jane case now reads Clane correctly. **Not run against real production yet** - per this
  file's own working agreement, Claude can't write to production directly even with in-chat approval;
  Darragh needs to run `py fix_society_misattributions.py --db aims.db --apply` himself (or the
  container equivalent, see this file's Docker command block, with `--db /data/aims.db`). Defaults to a
  dry run without `--apply`.
- **5 more real misattributions confirmed via text but deliberately NOT included** - the correct
  society's region/identity is still ambiguous (ESB Musical and Dramatic Society's region, "SONG"'s full
  name, The Real Theatre Company's location, National Youth Musical Theatre being a touring group not
  tied to one region, and whether "UL Musical Theatre Society" is the same entity as the already-
  registered "University of Limerick Musical Theatre Society" or a separate one) - see the script's own
  `NEEDS_DECISION` list and docstring for exactly which review ids and what each needs decided.
- **New societies' region/section are inferred, not confirmed against AIMS's own current list** - worth
  a sanity check against the real AIMS section list before treating as final, same caveat as every other
  new-society creation this project has done.

## Previous START HERE - big session closed out, everything below is DEPLOYED and confirmed live (2026-08-20)

Darragh pulled and redeployed (`5feffaf`..`d2f1977`, 13 commits) - checked live at `darraghc.ie/showcal`
rather than just trusting the push: `/awards` defaults to All results with the dropdown showing it
selected, `/season` renders the new calendar with the softened "Busy for..." wording, `/admin/login`
serves clean. Shipped this session, in order:

1. **Season calendar** on `/season` - Gilbert/Sullivan split by week, a section flagged **busy** (not
   "congested" - too clinical for public copy, see below) at 4+ of its own shows genuinely overlapping,
   judged per-section. Iterated through several real rounds of feedback: combined->per-section threshold,
   already-finished weeks hidden for the current season, homepage teaser cut entirely (`/season` only),
   the empty other-section column hidden when filtered to one tier, congestion copy simplified for a
   general audience. `season_weeks()` lives in `app/season.py`.
2. **`/admin/shows/dates` (Fix dates) - two real fixes**: opening date now jumps closing date to the same
   month (`data-sync-close`, reuses the delegated CSP-safe listener in `base.html`), and a real bug fixed
   where saving one row's date silently discarded every other row's unsaved edits (one shared `<form>`
   with indexed fields now, applies the whole visible batch atomically).
3. **`/admin/society-corrections`** (new) - review queue for the `extractor-society-gate` branch's 80
   proposed society-name corrections (not the 77 its own commit claimed - the archive had drifted).
   Approve/Reject/Skip per row, same pattern as `/admin/duplicate-titles`; approving corrects one
   `historical_reviews` row in place rather than risking duplicate rows from a blind re-extract+reload.
   **Still needs Darragh's own pass through the 80 suggestions** - nothing there applies itself. The
   `extractor-society-gate` branch itself stays unmerged (a real gap found in its own matching logic:
   Newcastle Glees vs Newcastlewest still isn't told apart).
4. **`/awards` defaults to All results, not Winner-only** - was hiding every nomination unless you knew
   to change the filter.
5. **32 shows' confirmed dates entered directly on production** (two batches, 17 + 15, all season 26/27) -
   matched by exact ID against a read-only copy first, applied via an assertion-guarded script Darragh ran
   himself over SSH (the auto-mode classifier blocks Claude from writing to production directly, even
   with in-chat approval - needs a real settings.json permission change, which Claude also can't make on
   its own behalf. See git history around `2026-08-20 17:00` in chat for the exact scripts if more dates
   come in the same shape).

**A `/admin/duplicate-titles` mockup was also built this session** (real 27 candidates, confidence-tiered,
shows each title's actual society/season history) - Darragh called it "not really an issue," parked, not
built into real code.

## Previous START HERE - season calendar + fix-dates tweak done, needs deploy (2026-08-20, later session)

**Item 1 from the triage below is done: the season calendar, mockup-first, built, iterated on real
feedback, and pushed - not yet redeployed.** Final shape: `/season` gets a new "Season calendar" section
above the existing sortable tables (unchanged) - Gilbert left / Sullivan right per week, real run dates
on every chip (`season_weeks()` in `app/season.py`), a section flagged **congested** at 4+ of its own
non-cancelled shows actually running at once (judged separately per section - 2 Gilbert + 2 Sullivan
isn't a clash for either adjudicator), already-finished weeks dropped from the current/a future season
(a genuinely past season keeps its full history via the season picker). No homepage teaser - cut after
Darragh's "don't show congested on homepage", so `/season` is the only place it lives. New
`--tier-gilbert`/`--tier-sullivan` CSS tokens. Test suite 307 -> 316. Commits `5feffaf`..`c23c76b`
(season calendar) plus one more small one bundled into the same unreleased batch:
- **`/admin/shows/dates` (fix-dates): opening date now jumps an empty closing date to the same month**
  ("clunky... having to click through each month") - reuses the delegated CSP-safe `change` listener
  already in `base.html` (`data-sync-close`, same pattern as `data-auto-submit`), never overwrites a
  closing date already filled in. Verified structurally (right markup renders) and by the same mechanism
  already proven for `data-auto-submit` - not click-tested in a real browser, no Selenium/Playwright
  available here.

**Not yet redeployed** - production is still running the very first commit of this arc and has the old
combined-threshold/no-past-filter/homepage-teaser behaviour. Needs a Portainer redeploy.

**New backlog item, not scoped, from the fix-dates conversation**: pre-fill opening/closing dates on
`/admin/shows/dates` as an editable guess based on the same society's most recent prior-season show,
rather than leaving them blank. Needs its own quick scoping pass (what "similar timing" means - same
week last year? same month? - and what to do for a society with no prior record) before building.

## Previous START HERE - full backlog triage after a marathon session (2026-08-20, late, pre-`/clear`)

Darragh hit his usage limits after one very long session (Statistics rebuild, 3 misattributed-review
investigations, a full 26/27 section reassignment, the 4 quick-win items, and the calendar/OCR scoping
below) and asked for the backlog triaged before clearing: what's next, what's a big rework, what should
wait for Opus. This is that triage - read this section first, before anything below it.

**Pick up here, in order:**

1. ~~**Season calendar mockup**~~ **DONE** - see this file's current top "START HERE" section. Built,
   iterated through real feedback, pushed - just needs a redeploy.
2. **OCR test on a programme photo** - blocked on Darragh actually sending one. Small and self-contained
   once a photo exists (test extraction accuracy first, design nothing before seeing real output) - can
   slot in any time, doesn't need its own session.
3. **`/admin/duplicate-titles` redesign** - mockup-first, Darragh asked for this one specifically. Same
   size/shape as the calendar mockup was - real work, no special reasoning needs.
4. ~~**Near-identical-society audit + merge `extractor-society-gate`**~~ **Half done** - the audit is now
   a review queue at `/admin/society-corrections` (see this file's current top section), waiting on
   Darragh's own approve/reject passes, not further Claude action. The branch itself stays unmerged - a
   real gap found in its own matching logic (Newcastle Glees vs Newcastlewest) needs addressing first.
5. **Date guesstimate on `/admin/shows/dates`** - new, from tonight's fix-dates feedback (see this file's
   top section) - pre-fill opening/closing as an editable guess from the same society's most recent
   prior-season show. Needs a quick scoping pass first, not a straight build. Small/cheap, can slot in
   any time, doesn't need its own session.

**Flagged for Opus specifically - the one item where the extra reasoning depth actually earns its keep:**
- **The productions table migration** - `shows`/`historical_results`/`historical_reviews` becoming one
  real table instead of three things joined by string/date matching. Real architecture decision, touches
  most of the app's query surface, high blast radius if got wrong - this is genuinely different in kind
  from everything else on this list, not just bigger. Full scoping brief already written - search this
  file for "Scoping brief for the productions-table session". Darragh's own instinct to reserve Opus for
  this specifically (not the calendar or duplicate-titles work) was right - confirmed while triaging
  tonight, nothing found that changes that call.

**Everything else already shipped tonight, for confidence, not action** - Statistics redesign, WAL mode,
the case-insensitive shows-key fix (4 real duplicates found and merged), 8 garbled skeleton-show titles
fixed, the unified society show/award timeline, the 3 tier-mismatch review investigations (which turned
into a full misattribution/duplicate-society cleanup), and the 26/27 Gilbert/Sullivan section
reassignment. All committed (`2e4c626`..`d4fa97a`), pushed, deployed, and verified live - nothing
uncommitted, nothing to lose by clearing.

**Trigger to paste after `/clear`:**
```
Read ROADMAP.md's "START HERE" section at the top and pick up from there.
```
If sending the programme photo in that same message, add: `Also testing OCR on this photo first.`

## NEXT SESSION - season calendar mockup, and an OCR test once a programme photo exists (2026-08-20, late)

Two new decisions from Darragh tonight, picking up the season-calendar item from the "Real priority
order" list (item 8) and a brand-new idea - both scoped, neither started:

**Season calendar - access model changed from the original Aug 5 scoping.** That session decided an
**unlisted shared link** (no login, same pattern as `/submit/unlock`), historical view first. Darragh's
ask tonight is bigger: **public, embedded directly on `/season` and the homepage**, not a separate
unlisted link - for theatregoers planning their year across regions as much as for adjudicators. Everything
else from the Aug 5 scoping still stands and should carry forward:
- **Layout**: one shared calendar, Gilbert/Sullivan colour-coded together (not two separate calendars) -
  shows real cross-section overlap, not each tier in isolation.
- **Danger weeks**: explicit flag at 3+ shows opening the same week (the adjudicator's own example), not
  just a density/count heuristic.
- **Sequencing**: historical view first (buildable now, no live-data dependency - real numbers already
  pulled: April is the crunch month by a wide margin, 94 combined Gilbert+Sullivan adjudicator visits vs a
  ~10-40/month baseline; ISO week 15 (mid-April) is the single busiest recurring week at 31 combined
  visits; 83% of adjudicator visits happen within 0-4 days of a show's `opening_date`, so that field alone
  is a reliable stand-in without needing `adjudication_date` filled in ahead of time). Live current-season
  view is the fast-follow, once enough of the season has confirmed dates to not look sparse - see the full
  numbers/reasoning in this file's Round-numbered "adjudication_date" section (search "which weeks are
  typically busiest").
- **Not started** - mockup-first per this repo's established pattern, own session.

**Programme-photo OCR backfill - a new idea, genuinely untested.** Darragh has old society show
programmes listing production history and wants to photograph them over time to backfill the archive.
Confirmed he wants OCR extraction tried, not manual typing - there's already a manual-entry tool for this
exact data shape (`/admin/historical-productions/bulk`, one "YEAR Title" line per society, skips anything
already on record), so the only new work is the extraction step itself. **Blocked on a real test photo** -
nothing about print quality, layout (list? table? mixed with photos/text?), or OCR accuracy on an actual
programme page is known yet. Do not design an ingestion pipeline before seeing one - same discipline as
every other extraction tool in this repo (`extract_historical_reviews.py` was built against real PDFs, not
assumed). Once a photo exists: test OCR accuracy on it directly first, then decide the parsing/matching
approach against what the real output actually looks like.

Tracks the current phase of work so a new session (after `/clear` or a fresh
start) can pick up where the last one left off without re-deriving context.
Update this file - don't just say the plan out loud in chat - whenever the
phase changes.

## NEXT SESSION - deploy, then items 4-9 (2026-08-20, end of session, updated)

**Items 3, 6, 7, 9 done this session too - the four Darragh flagged as cheap enough to do without
Opus.** All code changes tested (full suite 300 -> 307), the two production-data fixes already applied
directly via SSH (won't reappear/don't need redeploy); the code changes below **do** need a redeploy.
- **7. WAL mode + busy_timeout** - `app/db.py`'s `get_db()` now sets `PRAGMA journal_mode = WAL` and
  `PRAGMA busy_timeout = 5000` on every connection.
- **3. Case-insensitive shows-key fix** - swept production first, per the caveat: **4 real case-only
  duplicate pairs already existed** (e.g. "Made in Dagenham" vs "Made In Dagenham," same society/season) -
  3 were a member-submitted show duplicated by a review-created skeleton with different title casing, the
  4th was a near-identical-text duplicate review (Round 35's pattern, not this bug). Merged all 4 on
  production, then added `COLLATE NOCASE` to `ux_shows_natural_key` in `schema.sql` plus a migration
  (`_migrate_shows_natural_key_collation` in `app/db.py`, same drop/recreate pattern as the existing
  `_migrate_shows_source_check`) so an existing database picks it up automatically. Confirmed
  `import_csv.py`'s `ON CONFLICT(society_id, season, COALESCE(show, ''))` still resolves correctly against
  the collated index without needing its own change - tested directly before trusting it, not assumed.
  Index fix also applied directly to production so it's protected immediately, not just after redeploy.
- **6. Junk skeleton show titles** - swept every `source='historical'` show with a linked approved review
  for whether its title actually appears anywhere in its own review text (787 checked, 174 didn't match -
  almost all false positives, real titles just not quoted verbatim in the prose). Read through by eye and
  found **8 genuinely garbled ones** (sentence fragments like "Whisper it quietly but this is one" and
  "Somewhat appropriately for a," from the same truncated-extraction bug fixed twice already tonight),
  confirmed each against its own review text before fixing (e.g. "Rydell High" + "cigarette smoking pupils"
  = Grease; "MIRACLE ON 34th STREET - The" reordered to "Miracle on 34th Street"). Applied directly to
  production.
- **9. Unified society show/award timeline** - `society_detail.html` used to split a society's pre-23/24
  history into two separate tables ("Earlier show history" for bare productions, "Awards & nominations"
  with one row per award *category* below it - a show that won 5 categories was 5 separate rows). Now one
  timeline, one row per production, award categories folded in as inline badges (gold for Winner, muted for
  Nominee/other) - `public.py`'s `society_detail()` groups `historical_results` by `(year, show)` in Python
  rather than a second query. Person-level awards with no `show` (Mary Kelly/Unsung Hero Award) get their
  own small list since they have nothing to group onto. `tests/test_society_historical_show_split.py`
  rewritten for the new unified shape (it was pinning the old two-table split, now pins the merge).

**Deploy status**: none of tonight's code changes (Statistics redesign, the collation migration, WAL mode,
the unified timeline) are deployed yet. All the *data* fixes across the whole session (section
reassignments, the tier-mismatch resolutions, the case-dupe merges, the 8 title fixes) are already live on
production regardless, applied directly over SSH.

**Left for their own session - not urgent, not necessarily Opus either (see Darragh's "lowest hanging
fruit" question this session for the reasoning):**
- **4. `/admin/duplicate-titles` redesign** - mockup-first, same shape as tonight's Statistics work.
- **5. Near-identical-society audit + merge `extractor-society-gate`** - eyeball the 77 changes first.
- **8. Season production calendar** - the one real new-feature build, wants its own dedicated session.
- **The productions-table migration** - the one item that actually benefits from Opus's extra reasoning
  depth (real architecture decision, high blast radius). Scoping brief already written, see below.

## Previous "NEXT SESSION" entry, superseded above (2026-08-20 evening)

Tonight covered items 1 and 2 of the "Real priority order" list below (Statistics redesign, the 3 tier-
mismatch reviews), plus a run of real-usage bugs Darragh found while testing that weren't on any list.
**Next session starts at item 3 - the case-insensitive shows-key fix (`COLLATE NOCASE` on
`ux_shows_natural_key`)** - see that item's own entry further down for the "sweep for other case-only
duplicates before enforcing the constraint" caveat. After that, keep working down the list in order (4-9)
unless Darragh redirects.

**Item 1, Statistics redesign - built, still not deployed.** See the full write-up immediately below this
one. Nothing further to do here except an eventual redeploy.

**Item 2, the 3 tier-mismatch reviews - done, and turned out bigger than expected.** None of the three were
actually a same-show duplicate needing separation - every one was the extractor pinning the wrong society
name onto what was really a second society's own genuine production:
- **Sister Act**: Kilkenny's review (id 218) was already correct. The "duplicate" (id 840) was actually
  **Kilcock Musical & Dramatic Society**'s own 2018 production - confirmed by cross-checking the cast
  against the awards archive (Amanda Cunningham/Helena Begley both on record under Kilcock's 2018 Sister
  Act, tier Sullivan, matching the review's own credits exactly). Repointed, gave Kilcock a proper skeleton
  show (id 1972) for what had been a total gap in their record.
- **The Merry Widow**: Gorey's review (id 428) was correct. The other (id 414) named "Island Hall Theatre,
  Lisburn" in its own opening line - not Gorey at all. Traced to **Fusion Theatre** (Lisburn, Northern) -
  which turned out to already have **11 other reviews sitting completely unmatched since extraction**
  (2011-2019, every one `show_id`/`society_id` NULL, still `pending`). Darragh confirmed this is the same
  real society as **Fusion Theatre Group**, the brand-new entry just added this session from the 26/27
  Gilbert/Sullivan list (see the section-reassignment work below) - so all 12 reviews are now linked to that
  one society (id 10003), 8+ years of real history recovered for what looked like a brand-new AIMS member.
  **The 11 pending ones are still unapproved** - only the society link was fixed, not the moderation
  decision itself; they're sitting at `/admin/historical-reviews` for a real content review.
- **Little Shop of Horrors**: neither review was Carnew's. One was **Clane Musical & Dramatic Society**'s
  (self-named twice in the text - "Congratulations to everyone in Clane Musical Society"). The other was
  **Maree Musical Society** (Clarinbridge, Co. Galway) - had real award history in the archive
  (`historical_results`, 2014) but no societies row and no match at all; created it (Western, Sullivan).
  Carnew's skeleton show (id 1593) had nothing left supporting it once both reviews were moved off it -
  deleted; Carnew apparently never staged this title.
- Net new: 2 societies (Fusion Theatre Group's history recovered, Maree Musical Society created), 5 new
  skeleton shows, 5 misattributed reviews now on the right society.

**Also fixed this session, found by Darragh live-testing rather than from any list:**
- Two more instances of the same truncated-extraction bug fixed earlier for the Addams Family (shows
  1924/1962, 9 Arch Musical Society) - a single review re-extracted 2-3 times with progressively more of
  its opening line missing, each truncated copy spawning its own garbled-title skeleton show. Deleted the
  duplicates, kept the complete one.
- Show 1377 "Pop-Up" corrected to "Urinetown" (Teachers' Musical Society) - an isolated wrong-title
  extraction, confirmed via the review's own text (names Urinetown twice, credits match exactly) and swept
  the rest of that ShowTimes issue to confirm it wasn't a heading-bleed pattern.
- Teachers' Musical Society's 17/18 gap filled: **The Producers**, March 2018, DCU St Patrick's College -
  had 3 real award wins (Best Chorus/Comedian/Stage Management) but zero shows-table presence and no
  review, invisible from the show-page experience even though technically on record via the awards archive.
  Created from details Darragh supplied directly (no ShowTimes review exists for it - checked the full
  archive, confirmed).
- **The 26/27 Gilbert/Sullivan society-section reassignment**, from AIMS's own published list (two images):
  23 real section changes, 7 stale `section_as_of` refreshes, one real duplicate-society merge found along
  the way (**CIT Musical Society id 10000 merged into MTU Musical Society id 151** - same real entity
  recorded twice, only found because renaming one to match the other hit a UNIQUE constraint; moved 3
  shows/3 reviews across before deleting the emptied row), and 4 new societies created (Armagh Creative
  Theatre Group, Fusion Theatre Group, Seven Woods Productions, KATS - regions confirmed by Darragh
  directly for the three with no locational clue in the name).

**Every production-data fix above was applied directly to the production database over SSH, not through
git** - none of it will reappear or need redeploying; all of it is already live.

## Statistics redesign - full write-up (2026-08-20 evening)

**Statistics redesign: built and tested tonight, NOT yet deployed.** Mockup session (this file's previous
top entry, item 1 of the "Real priority order") went through two real revisions from Darragh's direct
feedback before landing, then got built same session once he said "yes go for that":
- **The old page split `shows`/`historical_results`/`historical_reviews` into three sections that read as
  three different populations you'd add up.** Darragh's correction: "combined they should cover a majority
  of the past productions on record. We should treat it as so." Checking that properly turned up a real bug,
  not just a framing problem - see below.
- **Rebuilt around one unified "productions on record" total** - `shows` (23/24+) unioned with
  `historical_results` (pre-24/25, distinct by year+show+society), plus any `shows.source='historical'`
  skeleton show (created purely to host a ShowTimes review) that has **no** matching award record - a
  production doesn't need to have been nominated for anything to count, most never are.
- **Found and fixed a real undercount while building this, not a hypothetical one**: 371 real productions
  (pre-24/25, on production data as of 20 Aug) existed only as review-linked skeleton shows with zero award
  record, and were invisible from every count on the old page - it only ever read `historical_results`.
  Confirmed via a direct check against production over SSH, not assumed.
- **"Reviewed" is one continuous idea across the whole timeline, not tied to ShowTimes alone** - second
  correction from Darragh: "'with a review available online' should be any review... this replaced ShowTimes
  publication in 2023." So coverage = `historical_reviews` (pre-23/24 ShowTimes archive) **plus**
  `shows.review_status='Published'` with a `review_url` set (23/24 on, AIMS's own aims.ie link-out workflow).
  On production data this raised all-time review coverage from 806 to 1,068 and closed a visible gap right at
  the 23/24 boundary (coverage now reads ~90%+ just after the switch instead of falling to zero).
- **Signature Show cut** (flagged low-value twice by Darragh), **the "Since 23/24 / All-time" Timeframe toggle
  removed** (standing backlog item - was making per-person leaderboards degenerate), **the whole standalone
  Leaderboards grid cut** ("remove the 'all time' leaderboards, the awards explorer is fine" - Award Explorer
  already covers award-outcome rankings interactively per category, the six static cards under it duplicated
  that job). Award Explorer itself untouched beyond losing its now-redundant Timeframe control - it's tested
  well twice already (Round 6, and again this session).
- Two mockup rounds published and iterated live against Darragh's feedback:
  https://claude.ai/code/artifact/436606a7-188a-4225-a2fa-a4d4140be5df (same URL, redeployed twice - final
  version is what got built).
- **Implementation**: `app/blueprints/info.py`'s `stats()` rewritten (era param and six leaderboard/signature
  queries removed; new unified season-by-season aggregation built from five single GROUP BY queries - no
  per-row loop, see [[perf_per_row_expensive_ops]] - merged in Python via `season_start_year`, never a string
  compare, closing off the same rollover bug class fixed twice before in this codebase). New
  `historical_results_season()` helper added to `app/season.py` (the inverse of the existing
  `historical_results_year()`). `app/templates/stats.html` and `app/static/style.css` (`.stat-sub`) updated to
  match. Test suite: two pre-existing tests updated for the new reality (`test_csp.py`'s dropdown check no
  longer expects an `era` control; `test_hidden_societies.py`'s "hidden society still counts" test now checks
  the numeric total instead of a leaderboard name, since the name-bearing leaderboards are gone) plus three new
  tests covering the actual new logic (review-only skeleton shows get counted, matched skeleton shows don't
  double-count, Signature Show/Leaderboards confirmed gone). 297 -> 300, full suite green. Verified against a
  real local dev server too, not just the test client - stat tiles, season table, collapsed earlier-seasons
  detail and Award Explorer all checked directly in rendered HTML.
- **Not yet deployed.** Next session (or whenever Darragh next redeploys): confirm the live `/stats` page
  shows the new "Productions on record" gold tile and "Productions by season" table, not the old three-source
  layout.

**Two live production bugs found and fixed the same session, via Darragh reporting real 500s while working:**
- `/admin/shows/1924/edit` and `/admin/shows/1962/edit` were both 500ing (`ux_shows_natural_key` UNIQUE
  constraint) - root cause: the same ShowTimes review (Issue 162, "Carry On Addams!", 9 Arch Musical Society,
  22/23) got extracted **three times**, each copy missing a bit more of its opening line, and each truncated
  copy's leftover fragment ("based", then "in") got picked up as a bogus show title, spawning its own garbled
  skeleton show. The complete, correctly-titled copy (show 1361, review 334, "The Addams Family") was already
  live and correct throughout. Confirmed via `SequenceMatcher` diff (99.67%/99.98% identical, only a leading-
  text truncation different) before touching anything, then confirmed nothing else in the schema references
  `shows(id)` except `historical_reviews.show_id`. Deleted reviews 957/999 and shows 1924/1962 directly on
  production via SSH (user confirmed before the write) - 883 -> 881 reviews, 1393 -> 1391 shows. Same bug
  shape as Round 35's 110-group ShowTimes duplicate cleanup, just a fresh instance that sweep didn't catch
  (its ratio, 99.67%, sits just under some of that sweep's matching buckets) - **worth a fresh archive-wide
  sweep for more instances like this one, not yet done, low urgency.**

**NEW - a real productions table: Darragh has now steered toward building it, not just discussed it.**
While reacting to the Statistics mockup he said: "I think a new combined productions database/table would be
a good way to have a single source of truth matching awards, societies, etc" - **this is the parked Round 34
architecture question again** ("can `shows` and `historical_results` be one source of truth?" - answered then
as "yes to one source of truth, no to a table merge; the real fix is a `productions` table both sides point
at" - see this file's Round 34 section further down), but this time with an actual steer to build it rather
than a request to write up cost/benefit for later. Darragh also suggested switching to **Opus** for this
specific piece of work, reasoning it's a bigger, more careful task than finishing a mockup - agreed, and this
write-up is the handoff for that session.

### Scoping brief for the productions-table session (start here, Opus)

**Why now, concretely - not hypothetical.** Tonight's Statistics rebuild had to hand-roll exactly the
problem a real table would solve: five separate GROUP BY queries (`historical_results` by year, unmatched
`shows.source='historical'` skeletons by season via a `NOT EXISTS` anti-join, `historical_reviews` by season,
`shows` by season twice more for the post-24 split) merged together in Python via a season-string dance, just
to answer "how many productions, and how many are reviewed" - one honest number. That logic now lives once,
in `info.py`'s `stats()`. It will need re-deriving, slightly differently, the next time `admin.py` or
`public.py` needs the same honest count (the 371-production undercount this session found existed **because**
no shared definition of "a production" existed to check against). A real table makes the union/anti-join a
one-time backfill instead of a recurring query pattern.

**What exists today (confirmed, not assumed - re-verify at scoping time in case anything's moved):**
- `shows` (`schema.sql` ~line 61) - one row per staging, 23/24 onward for real ('import'/'submission') rows,
  plus `source='historical'` skeleton rows (pre-24/25, created only to give a ShowTimes review a page to live
  on - 788 of these in production as of tonight, 371 with no matching award record at all).
- `historical_results` (~line 223) - one row per **award record**, 1912-2026, not one row per production (a
  show with 5 category results is 5 rows; a show nominated for nothing isn't there at all). `source_id` links
  loosely to `societies`, `society_name` is the free-text fallback for anything unmatched.
- `historical_reviews` (~line 352) - one row per review, 09/10-22/23 (ShowTimes archive) plus any
  `source='manual'` review typed in directly via Edit Show. Links to `shows.id` via `show_id`, `societies.id`
  via `society_id` (both nullable until matched/approved).
- Cross-cutting: `shows.review_status`/`review_url` (23/24+, AIMS's own aims.ie link-out, unrelated table/
  column to the above but conceptually the same "is this production reviewed" question from tonight's fix).
- The already-parked **people** identity question (award nominees / credit names / adjudicators - see this
  file's "PARKED on Darragh's privacy objection" section) is the same shape of problem one level down - a
  production and a person are both "this entity has no real identity, so every query joins on strings and
  splits on date ranges." Worth keeping in view while scoping this, but Darragh's privacy objection on public
  person pages stands regardless of what happens to productions - don't conflate the two decisions.

**Proposed shape (a starting hypothesis for the scoping session, not a final schema):** one `productions`
table, one row per real staging, with `shows.id`, `historical_results` rows (many-to-one, via a new
`production_id` FK) and `historical_reviews.production_id` all pointing at it instead of at each other by
string/date matching. Region and society resolve once per production, not re-derived per query the way
`hist_region_clause`'s fallback join does today.

**What the scoping session actually needs to produce, in order:**
1. **A full inventory** of every current query that stands in for "how many productions" or "is this
   production reviewed" today - `info.py` (now current), `admin.py`'s dashboard counts, `public.py`'s
   society/show pages, `export_csv.py`/`export_awards.py`. Grep for `SHOWS_COVERAGE_START_YEAR` and
   `hist_join`/`hist_region_clause` as starting points - both are proxies for exactly this problem today.
2. **A backfill script with verification asserts**, not a leap of faith - reuse tonight's exact matching
   logic as the starting recipe (shows-table rows since 23/24 anchor 1:1; `historical_results` distinct
   `(year, show, society)` anchors pre-24 award-linked productions; unmatched `source='historical'` skeleton
   shows anchor the review-only productions). Assert the backfilled totals match tonight's corrected unified
   counts before trusting it on production - same discipline as every other production data script this
   session and Round 35's cleanup used.
3. **Additive only for the first pass** - new table plus FKs, old tables/columns stay exactly as they are
   until the new one's proven safe in real use. No dropping or renaming anything on the first cut.
4. **A staged cutover, one surface at a time** - Statistics first (freshest in mind, smallest blast radius),
   then the admin dashboard counts, then public show/society pages last (highest traffic, most to lose from a
   subtle regression).
5. **Do this in an isolated worktree**, given the blast radius crosses most of the query surface in the app -
   not a quick same-session addition the way tonight's Statistics fixes were.
## NEXT SESSION - start here: the Gemini/Antigravity audit backlog (2026-08-20)

Darragh had Gemini Antigravity run a fresh-eyes audit of the codebase (`AUDIT_AND_RECOMMENDATIONS.md`,
untracked, still sitting in the repo root - not deleted, it's the source doc for everything below).
Reviewed it critically rather than relaying it as-is: two of its claims were checked against the
actual code/data before being trusted, one confirmed right, one confirmed wrong. Darragh's instruction:
track everything from it, then pick up in a fresh session in the order below.

**Confirmed independently correct - do this one first.** The audit's #1 finding (Part 1) is
`ux_shows_natural_key`'s missing `COLLATE NOCASE` - the exact root cause behind the 5 duplicate
show-page pairs found and merged earlier this same session (`d5a3f0c`), rediscovered completely
independently by a tool with no visibility into that work. Strong signal, and the context is still
fresh (I already know the 5 pairs, already merged them).
- **Before enforcing the constraint**: sweep for any OTHER latent case-only duplicate pairs beyond
  those 5 - a new UNIQUE index will fail to apply if any existing row still violates it.
- Add `COLLATE NOCASE` to the index in `schema.sql`, and add the equivalent migration to `app/db.py`
  (SQLite can drop/recreate an index without a full table rebuild, unlike the `adjudicator_
  assignments` PRIMARY KEY change - simpler than that pattern, still needs its own care).

**One of the audit's own suggestions is wrong - do NOT implement as written.** Part 1, #4 proposes
only rebuilding the FTS5 index on first creation, checking row count to skip it otherwise. Already
tried and rejected - `app/db.py`'s own comment right above `_backfill_fts_indexes()` explains why: a
`COUNT(*)` check on an external-content FTS5 table reads through to the real content table regardless
of whether the index was ever built, so it never actually detects an unbuilt index. The audit tool
had no way to see that history. Leave this one alone.

**One "new feature" is already fully scoped elsewhere, further along than the audit realizes.** Part
3's implicit ask for a season timeline/calendar view is the same idea as the "Phase 1" backlog item
below (search this file for "which weeks are typically busiest") - real numbers already pulled (April
is the crunch month, ISO week 15 is the busiest recurring week), and Darragh's own access/layout/
sequencing decisions already recorded. Never started building. Don't re-scope from scratch - read
that section first.

**Everything else from the audit, tracked, not yet started:**

*Technical/DB (Part 1):*
- **WAL mode + busy_timeout in `app/db.py`'s `get_db()`** - standard SQLite-under-concurrent-writes
  hardening (pageviews, submissions, backups, changelog sync all writing under Waitress's threads).
  Safe, small, no reason to delay - but no evidence yet that locking has actually bitten in
  production; worth asking Darragh whether this is preventative or answering a real symptom.
- **Split `app/blueprints/admin.py` (2,925 lines, confirmed) into a package** (`shows.py`,
  `societies.py`, `awards.py`, `reviews.py`, `adjudicators.py`, `suggestions.py`, `fixes.py` or similar
  domain split). Real maintainability issue, but a nontrivial refactor (route registration, imports,
  risk of a subtle breakage with zero user-visible benefit) - wants Darragh's explicit go-ahead before
  starting, not something to fold in silently alongside other work.

*UI/UX polish (Part 2):*
- **Filter "chip" badges** (removable `[Eastern ×]`-style pills above filtered tables) on `/season`,
  `/awards`, and `/stats`. The `/stats` instance should probably wait for the Statistics redesign
  session rather than being styled twice - build it on `/season`/`/awards` first if picked up before
  Statistics gets its own session.
- **Unified show + award timeline on `society_detail.html`** - integrate award wins/nominations into
  the show-history table rows instead of a separate table below. A display/query change, not a data
  model change - doesn't need to wait on the still-undecided "one `productions` table" architecture
  question (see Round 34's "Architecture question... NOT acted on"), though it's the same shape of
  problem and worth keeping in mind while touching this.
- **Poster lightbox/zoom modal** - small, isolated, low risk.

*New feature concepts (Part 3) - each needs its own scoping pass, not just a build:*
- **Show Discovery Hub** - filter `/titles` by amateur rights status/licensing house (both already
  real columns on `show_info`) and by "dormant vs recent circuit staple". Builds on data that already
  exists; the filtering logic is the actual work.
- **"My Season Watchlist"** - zero-login, localStorage-based bookmark list + per-user `.ics` export.
  Self-contained, no dependency on anything else in this list.
- **Interactive Ireland map** (Leaflet/OpenStreetMap, no API key needed) - genuinely new frontend
  surface (first map/JS-library dependency on the site). Bigger, more novel, lower urgency.
- **"On This Day in AIMS History" homepage widget** - fun, low-effort, low-urgency engagement feature.
- **Embeddable society widget / JSON feed** (`/api/society/<id>/upcoming.json` or an iframe widget) -
  **needs a real security-scoping conversation before any build**: this is a new public API surface
  with its own rate-limiting/abuse-prevention questions (what stops a society embedding it wrong, or
  someone hammering it), not a quick add like the others in this section.

**SUPERSEDED below - Darragh asked for a real recommendation, not just the audit items in isolation
("what do you really recommend, what should we skip, what should we not do"). Revised 20 Aug: the
audit is a fresh-eyes *code* review with zero visibility into how this site is actually used or
what's already been asked for - it's good at spotting real technical patterns (confirmed once,
independently, above) and bad at judging what's worth building for a niche, single-moderator,
volunteer-association site. Several of its "new feature concepts" are the kind of thing any tool
would suggest for any small web app, with no evidence they solve a problem anyone here actually has.
The pre-existing backlog (things Darragh has personally flagged more than once, or that came from
real user feedback, or that this session found while working) has far more validated urgency than
most of the audit's speculative ideas, and should go first.**

**Real priority order - integrates the audit items with the rest of the standing backlog:**
1. **Statistics redesign** (mockup session) - flagged as confusing by Darragh on three separate
   occasions now. Nothing else on any list has been reported as broken more often. Highest value
   single item outstanding.
2. **The 3 tier-mismatch duplicate reviews** (Sister Act/Kilkenny, Merry Widow/Gorey, Little Shop/
   Carnew) - real data bug found this session, not yet fixed.
3. **Case-insensitive shows-key fix** - from the audit, earns its place: caused real, confirmed damage
   found only hours before the audit surfaced the same root cause independently.
4. **`/admin/duplicate-titles` redesign** - Darragh explicitly asked for mockups on this one.
5. **Near-identical-society audit + merge the `extractor-society-gate` branch** (eyeball the 77
   changes first, per that item's own note) - real, previously-found bug, lower urgency than 1-4.
6. **Junk skeleton show titles** - small tidy-up.
7. **WAL mode + busy_timeout** - cheap insurance, no urgency signal, bundle in whenever convenient.
8. **Season production calendar/timeline** - the one genuinely good "new feature" idea in the audit,
   because it has a real origin (an adjudicator's actual complaint about clashing show dates), not a
   guess. Already fully scoped with real numbers (see "which weeks are typically busiest" above).
   Worth its own session once there's appetite for a bigger build - don't squeeze it into a quick-wins
   day.
9. **Unified society show/award timeline display** - nice cleanup, no urgency.

**Skip, or don't build without asking first - and why:**
- **FTS reindex "optimization"** - not low-priority, actively WRONG. Would undo a bug fix already in
  the code (see above). Do not build this one at all.
- **Filter chip badges** - only worth it as part of the Statistics redesign (item 1). Building it
  standalone on `/season`/`/awards` first is polish nobody asked for.
- **My Season Watchlist, the interactive map, "On This Day" widget** - no one has ever asked for any
  of these. Generic small-web-app feature suggestions with no evidence they solve a real problem for
  this specific audience (a regional volunteer theatre association, not a mass-consumer app). Skip
  unless Darragh reports a specific real request for one of them.
- **Embeddable widget / JSON API** - the one to actively caution against, not just deprioritize. Opens
  a public API surface with no rate-limiting infrastructure built for it, for a feature nobody's
  requested. Don't build speculative public surface "just in case" - only if a specific society
  actually asks to embed something.
- **Splitting `admin.py`** - a real internal tidiness observation, but pure refactor risk (route
  registration, imports) for zero user-visible benefit, and Claude works in the file fine as it is
  across this entire session's heavy use of it. Only worth doing if it starts actually causing
  problems, not pre-emptively "because a file is long."
- **Show Discovery Hub (licensing/rights filters)** - the one idea worth a second look, but ask
  Darragh directly whether this solves a problem he or a society has actually raised before scoping
  it - unlike the season calendar, this one has no validated origin story yet.
- **Poster lightbox** - harmless, but not needed. Do only if everything else above is done and there's
  spare time with nothing else queued.

## Round 35 - dcfeedback.docx: analysis, then a full build session (2026-08-19/20)

Darragh brought a Word doc of ten observations from real use (screenshots included) and asked for a
full software-expert pass: analyse, find gaps/oversights, propose mockups, "consolidate clean data",
then said "happy for you to build" once the plan looked right. Every item was checked against the
live code and production database before writing anything down - two turned out to share one root
cause, and chasing that surfaced a data problem three times the size of anything in the original list.
Full written analysis (with mockups for the four feature asks) published before building:
https://claude.ai/code/artifact/ae039ca4-b3b5-4915-88b5-1918b6cd9c96

**The headline finding - every auto-refreshing filter dropdown site-wide was dead.** Six
`onchange="this.form.submit()"` controls (homepage region filter, all four Statistics filters, two
admin award-category "Other" toggles) had been silently blocked since `dd8f5ce` added a nonce-gated
CSP - a nonce permits `<script>` tags, never inline event-handler attributes. This is what two
separate feedback reports turned out to be, **and almost certainly the real cause of the Award
Explorer bug from 18 Aug that was investigated and left unresolved** (two unconfirmed theories were
on the table; neither was it - the dropdown just never fired). Fixed by extending the delegated-
listener pattern already built for `data-confirm`/`data-copy-target` (this repo's own existing answer
to the same CSP constraint) with `data-auto-submit` and `data-toggle-target`/`data-toggle-value`,
rather than inventing a second mechanism. `test_no_inline_event_handlers_remain` had only ever checked
`onsubmit=`/`onclick=` - widened to `onchange=` too, which is the exact gap that let this ship
unnoticed for weeks.

**All ten items, built or explicitly deferred - commits `148edfa`..`39f7276`:**
1. **Six broken filter dropdowns, fixed** (`148edfa`) - see above.
2. **111→then 112 duplicate ShowTimes reviews, cleaned up (data only, on production).** Darragh's
   "Peter Pan is there three times" caught the tip of a real, quantified problem: 110 groups of
   byte-identical review text (221 rows, 111 excess), every duplicate pair tracing to Round 26's batch
   re-extraction of seasons 16/17-18/19 + rest of 22/23 - the loader's dedupe key
   (`source_issue`+`society_raw`+`show_raw`) didn't match between runs because `society_raw` came out
   spelled slightly differently the second time (a trailing ", Dublin"/", Galway" present once, absent
   the other). **First draft of the cleanup script got its own keep/drop heuristic wrong on the very
   first dry-run output** - sorted on society-name length before moderation status, which would have
   deleted an approved review linked to a live public show page in favour of a pending, unlinked stub.
   Caught by reading the dry run before writing anything, not assumed correct - fixed the priority
   order (approved > pending > rejected, real show-link, *then* fuller name as a tie-break only) and
   added an orphan-risk guard (refuse to auto-resolve if a drop would leave any show without its
   review). 104 groups applied automatically; a further 8 near-duplicates (>97% similar, not
   byte-identical - a stray punctuation mark) found by a second, bucketed sweep and applied the same
   way, confirmed against which row `show_detail()` was actually rendering so no live page's content
   changed. **`show_detail()`'s own review lookup had no `ORDER BY`** - ten shows were carrying two
   approved reviews apiece with which one rendered down to SQLite's incidental scan order; added
   `ORDER BY id ASC LIMIT 1` (`f9dc9df`), verified it doesn't flip what's currently live on any of them.
   **The five duplicate-show-page pairs: RESOLVED 20 Aug, using the site's own `/admin/duplicate-titles`
   merge logic (`_merge_titles`, copied into a standalone script since this ran directly against
   production).** Merged each pair (e.g. "9 to 5" -> "9 To 5") keeping the earlier-created, Title-Case
   row in every case - checked first that both sides of each pair had identical review length and
   equal field-fill counts, confirming genuine duplication rather than two different productions.
   **This is a title-spelling merge, not a single-production fix** - `_merge_titles` operates on every
   row with that exact title string site-wide (by design; it's what the tool backing `/titles` and
   stats groupings needs), so each merge consolidated *every* society's use of that spelling, not just
   the one pair originally found - a bigger, correct effect than first planned, confirmed by checking
   the full before/after id lists rather than assuming only 2 rows moved per pair.
   **A second-order effect, caught by re-sweeping rather than assumed clean**: merging each pair
   reunited a review with an exact-duplicate sibling that an earlier pass had deliberately left alone
   (splitting them at the time would have orphaned a second show page - no longer true once the title
   merge put them on one page). Six such pairs turned up (five exact, one 99.95%-similar with a stray
   "9 TO 5 " fragment leaked into the review text itself, from the same heading-parsing bug that caused
   the Castleblayney title error) - resolved the same way as Round 35's earlier cleanup: kept whichever
   row `show_detail()` was already rendering, confirmed against the live page, so nothing public
   changed except the redundant copy disappearing. `historical_reviews` now at 883 (was 1001 at the
   start of this whole cleanup arc). Spot-checked two of the five merged pages live afterward.
   **Still open, NOT touched - three groups where the two reviews disagree on TIER and differ ~2x in
   length** (Sister Act/Kilkenny Musical Society, The Merry Widow/Gorey Musical Society, Little Shop Of
   Horrors/Carnew Musical Society) - NOT a spelling-variant duplicate, confirmed unchanged by this
   round's cleanup. Two genuinely different reviews got matched to one skeleton show, likely because
   the approval-time show-matching step doesn't check tier. Needs investigation, probably needs
   separating into two skeleton shows. Not attempted.
3. **Three garbled ShowTimes titles fixed**, each confirmed by reading the review's own text before
   writing anything (not guessed): review 976/show 1940 `'Castleblayney'` (a town, not a show) →
   `'9 To 5'` (named explicitly in the review's own opening line); review 898/show 1871
   `'production of Calendar Girls the Musical'` → stripped the stray prefix → `'Calendar Girls the
   Musical'`; review 936/show 1904 `"Trinity's"` → `'Sweet Charity'` (the society, "Muse Productions",
   was already correct and real - only the title was a fragment, likely leaked from an adjacent
   review's heading; confirmed via unmistakable Bob Fosse references and director/MD credits already
   on the skeleton show matching the review's own credits word for word). Swept for the same two
   patterns archive-wide first - confirmed these were the only instances of each, not systemic.
4. **`/societies` groups Non-AIMS societies into their own section at the bottom** (`56e91c4`) rather
   than scattering them alphabetically among real members - same query, same pagination, just
   `ORDER BY (section = 'Non-AIMS'), name` plus an inline `row-note` heading.
5. **`/season` gets an "Unannounced" section for the current season** (`56e91c4`) - turned out to be
   more than a layout ask: a "slotted, TBA" placeholder show (`shows.show IS NULL`) was being filtered
   out of the query entirely, so those rows had nowhere to appear at all. Scoped to the current season
   only - a past season's unfilled slot is a gap in the record, not "unannounced".
6. **Edit Show can hold a full review directly** (`ebb5954`) - writes into the same
   `historical_reviews` table the ShowTimes import uses (new `source` column, `'showtimes'` vs
   `'manual'`, same CHECK-constrained pattern `historical_results.source` already uses), so a
   manually-added review renders through the identical show-page component and citation stays honest
   (no false "Originally published in AIMS ShowTimes..." line). Written straight to `'approved'` -
   reaching this screen at all is already the human review step. Refuses a second review on a show
   that already has one (guards against recreating the exact bug fixed in item 2), with a Remove
   button scoped to `source='manual'` only.
7. **Adjudicators can have a bio and a photo, editable after creation** (`f89421e`) - `notes` already
   rendered publicly if present but nothing ever let a moderator set it after the one-time "add
   adjudicator" form; photo is a new column reusing `save_poster()`, the same mechanism a show poster
   and society logo already use.
8. **Suggestions banner moved from literally the last thing on the homepage to the top** (`39f7276`) -
   it already existed, just below Upcoming Shows and Recently Shipped; relocated next to the existing
   top banner, no new copy invented.
9. **Statistics - deliberately deferred, not patched.** Five separate comments in the feedback doc
   (`"I just don't understand"`, `"I don't see value here"`, `"Signature show? Pointless"`, two
   variants of "does this factor in ShowTimes") all point at the same root cause: the page mixes three
   data sources (`shows`, `historical_results`, `historical_reviews`) with three different counting
   rules and never says which one a given number is using. Recommendation on record: give it its own
   mockup session like the adjudicator pages got, not another patch - see the artifact above for the
   source-vs-coverage table this needs to work from. **Still the plan** - not started as of this
   writing (20 Aug).

**Round 35 continued, 20 Aug - three more decided items from the standing UX-audit backlog, all
shipped same session, in the order Darragh confirmed ("yes let's go in that order"):**

11. **The 6 literal-`'None'` award rows fixed** (`1c83bf0`) - and the sentinel bug behind them was
    live in five templates, not the one originally flagged. A legacy import (predating the CSV
    pipeline) stored the literal string `'None'`/`'NULL'` instead of a real blank in
    `reason`/`role`/`nominee_name`; a plain `or '—'`/`if x` check treats a non-empty string as
    present, so `/awards` rendered an italic "None" note and a "(None)" next to a nominee. New
    `destub` filter (`app/filters.py`) normalizes both sentinels; applied to `awards.html`,
    `show_detail.html`, `society_detail.html`, `search.html`, and the admin awards list - checked all
    five rather than assuming the one page was the only one affected. The 6 rows fixed directly on
    production too.
12. **Award category lineage built** (`b855353`) - implements Darragh's decided merges as a
    query/display-time alias map in `AWARD_CATEGORIES` (`app/constants.py`), no data rewrite:
    - Best Chorus (1977-2025) -> Best Choral Singing (2026-): clean rename, merged.
    - Adjudicator's Special Award -> Spirit of AIMS: **turned out to be a three-name lineage, not
      two** - "Spirit of AIMS/Adjudicator's Special Award" was a real printed category for two
      decades (2001-2022), missed when the original decision only checked the outer two names.
      Verified year-by-year that no two of the three names ever overlap in the same year before
      merging all three.
    - Best Choreography -> Best Moment of Theatre: NOT merged (award's meaning changed) - a
      cross-link note now surfaces on the Award Explorer result for both entries instead.
    - **A real, previously-unknown bug found and fixed while verifying this year-by-year**: "Best
      Choreography" and "Best Choreographer" have been wrongly merged into one Explorer entry since
      Round 6 (2026-08-05), on the assumption they were a renamed award. They're not - both
      categories ran in parallel, side by side, every single year from 2019 through 2025 (a rename
      can't coexist with its own old name for 7 straight years). Reverted to two separate entries.
      **Also corrected a wrong assumption made earlier in this same investigation**: "Best
      Choreography"'s low nominee-fill-rate (88/203) looked like evidence it was society-level, but
      the nominees it does have are real people's names, not societies - it's a person award with
      incomplete historical data, not a show award. Checked the actual nominee values before
      classifying, rather than trusting the fill-rate alone.
13. **Nav labels + Shows A-Z promoted** (`188f52b`) - `/season` said "Season Archive" in the header
    and "This season" in the mobile tab bar, opposite meanings for the same page; both now say
    "Seasons". Shows A-Z (287 titles) added to the header nav and `/more`, ahead of Awards on both -
    it was only ever reachable from the footer. Deliberately did NOT touch "Home"/"Upcoming shows" or
    "Stats"/"Statistics" mobile-vs-desktop wording - those are shorter labels for tight mobile space,
    not the opposite-meanings contradiction the decision was actually about; flagged this scoping
    choice rather than silently applying a broader rule than what was asked.
    Screenshotted both desktop and mobile nav in a real browser to confirm no wrapping/cramping.

All three verified against real running-server data (not just the test client) before committing -
the constants.py fix in particular was checked against local `historical_results` (4,731 rows,
counts matching production) with the dev server actually serving `/stats?award_category=...` for
every affected category, not just trusted from the test suite. Test suite 297 -> 299.
10. **Verification discipline held throughout** - every piece checked against a real running server
    (not just the pytest client, which disables CSRF): a throwaway admin login, real multipart file
    uploads (the adjudicator photo), the full add/refuse-duplicate/remove review cycle, all exercised
    end to end and cleaned up afterward. Test suite 279 → 297. The one thing NOT independently verified
    in a real browser: that the CSP fix's `addEventListener('change', ...)` actually fires on a real
    user click - no Selenium/Playwright/CDP tooling available in this environment, and headless Edge's
    console logging didn't surface anything either way. Confidence rests on the mechanism being
    structurally identical to the already-proven `data-confirm`/`data-copy-target` pattern in the same
    script tag, not on an interactive browser test - flagged honestly rather than claiming a checkmark
    that isn't real.

**Not yet deployed** - `148edfa`..`39f7276` are pushed to `main`, none redeployed yet. The
`historical_reviews.source` and `adjudicators.photo_filename` migrations are additive
(`COLUMN_MIGRATIONS`, both nullable/defaulted) and will apply automatically on next redeploy, same as
every other migration in this repo - no manual script needed. The duplicate-review cleanup and the
three title fixes are **data corrections already live on production** (applied via SSH this session,
independent of the code deploy).

## Round 34 - adjudicator pages: design agreed, counts fixed (2026-08-19)

**Round 33 confirmed deployed** first thing (checked the container's own files: `season.html` has
"Not on record", `_pagination.html` exists) - so main is fully live as of `0e59514`.

**The design session found a bug that changed the brief.** The plan said `/adjudicators` reads badly
because most adjudicators have nothing to show. They do have something to show - the page wasn't
counting it. **Both adjudicator queries counted only `shows.review_url` reviews (AIMS's link-out
workflow, 23/24 onward) and never joined `historical_reviews` at all**, so the entire 826-review
ShowTimes archive was invisible on both pages. Tony McCleane-Fay read "0 published reviews" holding
115; Peter Kennedy read 51 holding 197. **Once counted properly exactly one adjudicator has zero** -
Justin Parkes, and only because 26/27 has barely started. The layout problem was real; the emptiness
never was.

**Shipped this round (Darragh's call - fix the counts ahead of the redesign, since it's independent
of which layout wins):**
- `adjudicators_list()` and `adjudicator_detail()` now UNION both review sources. **Verified against
  production first that they can't overlap** - 0 shows carry both a `review_url` and an approved
  historical review, every approved review has a `show_id` and an adjudicator, all linked shows are
  approved - so summing is safe rather than double-counting. 5 reviews sit on hidden societies and
  are excluded on both sides, matching the site-wide convention.
- The detail page lists ShowTimes reviews too, linking to **the show's own page** (where the full
  text lives) rather than out to aims.ie, with a "Full review" / "Read on aims.ie" tag. Its list is
  **sorted in Python via `season_start_year`**, not by season string in SQL - the Round 25 rollover
  trap.
- Grouping is on the **review's own season/tier**, not the assignment table, which is what keeps the
  16/17 anomaly below visible instead of silently dropping 17 reviews.
- Tests 273 -> 278 (`tests/test_public_adjudicators.py`). Confirmed the four new ones fail with the
  fix reverted (`git stash`), per this repo's habit. The fifth (hidden-society) passes either way by
  design - it guards the new query from leaking, it doesn't prove the fix.

**Production data correction applied directly (not in git, won't reappear from a redeploy):**
`Pat McEMealwain` (`adjudicators.id = 19`) was an OCR garble of Pat McElwain holding reviews 513/514
(*Annie*, Oyster Lane; *The Music Man*, Pioneer), both 12/13 Gilbert - the exact season and tier the
real Pat McElwain is assigned to. Same class as the "Gred Currid" typo fixed in Round 26. **He had no
assignment row, which is why he was invisible on the public list and never surfaced.** Reviews moved
to id 1 (32 -> 34 approved), id 19 deleted, behind an assertion that the row was exactly what had
been measured.

**RESOLVED same session - the 16/17 anomaly was a stale printed banner, NOT a mid-season change.**
(First call was "reads like a mid-season change" - wrong, and corrected once the PDFs were actually
read. Worth remembering: the assignment table and the review rows disagreeing is not by itself
evidence of a mid-season change.)
- **What the PDFs print**: Issues 116-123 all carry `2016-2017 | Gred Currid | Sullivan Section |
  Peter Kennedy | Gilbert Section` - so 16/17's line-up is unambiguous, and Darragh independently
  confirmed it. But **Issues 124, 125 and 126 (Oct/Nov/Dec 2017) print the banner `2016-2017` while
  listing Peter Kennedy/Sullivan and Ciarán Mooney/Gilbert** - the 17/18 pair, exactly what Issue 127
  (Feb 2018) prints under `2017-2018`. ShowTimes ran a stale year-range for three issues after the
  adjudicators had already changed over.
- **`extract_historical_reviews.py` trusts the printed banner over the cover date** (`extract_issue`:
  `season = parse_header(...) or season_hint`, where `season_hint` is the cover-derived one from
  `parse_cover`). Normally right; here it filed a season early.
- **Swept all 101 issues for the same disagreement**: 10 issues print a year-range contradicting their
  cover date, and **most are benign - the October issue legitimately carries the previous season**
  (Issues 89, 98, 115, 133, 142 all do, with the previous season's adjudicators named, consistently).
  Darragh's explanation: ShowTimes went to print a few weeks after the reviews were written, so the
  lag is natural. **The real outliers are Issues 125 and 126** - November/December carrying a stale
  banner, where every other year November starts the new season cleanly.
- **Correction applied to production (data, not git - won't reappear from a redeploy)**: 28 reviews
  moved 16/17 -> 17/18 (17 approved + 11 still pending), **and their 17 skeleton shows moved with
  them** - a review whose show stays on the old season shows the wrong season on its own public page
  (the Round 31 UCC/UCD lesson). Guarded by an assertion that every row was signed by the 17/18 pair.
  **Validation: "approved reviews whose (adjudicator, season, tier) has no assignment row" went from
  3 groups to none** - every approved review in the archive now matches a real assignment.
- **Safe from a loader re-run**: `load_historical_reviews.py` dedupes on
  `(source_issue, society_raw, show_raw)`, not season, so it still finds these rows and only ever
  refreshes *pending* review text. Checked, not assumed.
- **STILL OPEN - the extractor itself is unfixed.** A fresh extraction into a fresh database would
  reintroduce this. The fix shape: when the banner's own named adjudicators belong to a different
  season than the banner's year-range, trust the cover date (or at minimum flag the issue for a
  moderator). Related to, but separate from, the `find_society_span` fix parked on the
  `extractor-society-gate` branch - see OPEN item 1.

**DECIDED, mockups published, NOT yet built:**
https://claude.ai/code/artifact/7a9bd478-f194-4edd-ab13-c3b9fa738500
- **`/adjudicators` = Option A plus Option B's coverage bar as a column** (Darragh's call). Hero
  `.explorer` card with the current season's two adjudicators in a two-up grid, then a
  `.data-table` roster: Name | Seasons covered (span bar scaled 09/10->26/27) | Reviews. Stays
  alphabetical - once the counts are honest nobody needs rescuing from burial, and the bar carries
  the chronology. Reuses `.explorer` and `.data-table` (which already collapses to cards below
  600px); the only new pieces are the adjudicator card and the span bar.
- **"Current" = `current_season()` as-is** (Darragh's call), which returns 26/27 today. Justin Parkes
  therefore shows with nothing to click yet - handled with wording ("reviews appear as the season
  runs"), not hidden.
- **`/adjudicators/<id>`** = the Step 4 scoping session's "Option A", finally specced: a stat strip
  (reviews / seasons / active span / tiers) replacing the run-on "Judged Gilbert 15/16, ..." line,
  then `<details>` season groups with the two most recent open, both review sources merged into one
  tagged list.
- **Steps 3 and 4 built and pushed same session** (`be91791`) - both templates rebuilt exactly as
  agreed: the `.explorer` hero card + roster table with coverage bar on `/adjudicators`, the stat
  strip + `<details>` season groups on `/adjudicators/<id>`. Both routes' season/adjudicator
  aggregation now happens in Python via `season_start_year` rather than SQL string ordering, closing
  off the same bug class this file has now hit twice (Round 25's grid duplication, this round's
  16/17 misfile) rather than reintroducing it in new code. Test suite 278 -> 279. Verified in a real
  browser against seeded local data (not committed - test data only), dark and light tokens, the
  mobile `table-cards` fallback, and the season-group collapse all checked. **Committed, NOT yet
  deployed** - templates/queries/CSS only, no migration.

**Then the rest of the "cleaner UI throughout" work.** Other pages the audit flagged as wanting a
design pass rather than a bug fix, in rough priority order: **`/stats`** (Darragh has called it
"messy" and the leaderboards "unhealthy" - note item B below removes the timeframe toggle, which
fixes the *data* problem but not the layout), **`/admin/duplicate-titles`** (he asked for mockups
specifically, it's one long list), and the **`/search` results page** (see the search findings
below - the ordering problem is a layout decision as much as a ranking one).

**Useful context that keeps proving itself**: build mockups from the site's real CSS tokens in
`app/static/style.css` (`--accent`, `--bg`, `--muted`, `--warning`...) rather than a fresh palette,
so they preview accurately in Darragh's actual dark theme. Third session running where this paid off.

**Useful context for whoever picks this up**: the site's real CSS tokens are in
`app/static/style.css` (`--accent`, `--bg`, `--muted`, `--warning`...). Building mockups from those
tokens rather than a fresh palette means they preview accurately in Darragh's actual dark theme -
that worked well for the admin dashboard mockups this session and is worth repeating.

## Search flaws - diagnosed 2026-08-19, NOT fixed

Darragh searched `'april kelly'` (a real two-time award winner) and got four irrelevant review
matches. Investigated properly rather than assumed; the headline is **search did find her, but the
page made her invisible**.
- **Her two wins are in the data and the search returns them correctly** (2023 Best Actress In A
  Supporting Role, Blanche Barrow, Bonnie & Clyde, Quayplayers; 2024 Best Actress, Mimi, Rent, North
  Wexford). They render under "Award nominees", which is the **last section on the page**, below
  Societies, Shows and the noise Reviews. An exact hit on a person's full name is the highest-
  confidence result the site can produce and it's rendered dead last. **This is the main fix, and
  it's a layout/ordering decision - fold it into the search-page mockup above.**
- **No phrase search exists.** `app/search.py` splits on whitespace and ANDs prefix terms, so
  `april kelly` means "contains april AND kelly anywhere". Verified the noise: review 323 has "April"
  at character 97 (the *month* - "at the end of April this year") and "Kelly" at 3,265 (*Jonathan*
  Kelly). A correct AND match, a useless result.
- **The snippet shows the wrong place**, which is why a correct match looked broken -
  `_review_snippet` centres on the *earliest* matching term, so Darragh saw the April-the-month
  sentence with no "Kelly" anywhere in it. Should centre on where the terms cluster, and highlight
  them.
- **Typed quotes silently break the Shows results only** - confirmed live: `Oliver` returns 1 show,
  `'Oliver'` returns 0. The Shows/Titles search uses `LIKE %...%` on the raw string so the quotes
  become literal characters; the FTS-backed sections strip them. Small, unambiguous bug.
- **No relevance ranking** - reviews come back ordered by season, so a review with the terms adjacent
  ranks below a newer one with them scattered. Wants bm25.
- **A content, not code, note**: the one review that actually names her (id 321, Bonnie And Clyde,
  22/23) is **pending**, so correctly excluded from public search. Approving it would surface it.
  172 reviews are still in the queue. Considered surfacing "N more matches in unapproved reviews" for
  logged-in moderators - **not built, needs Darragh's view** on exposing queue state on a public page.

## Start here (updated 2026-08-19, end of the UX-audit session)

**Deployed vs committed, right now (updated Round 34, mid-session):**
- Through `0e59514`, everything is **deployed and verified**, Round 33 included.
- `1d55ff4`/`e24479e` (the count fix) **were confirmed deployed and redeployed mid-session** -
  Darragh redeployed and the live page's per-adjudicator counts were checked directly against the
  before/after table above (Tony McCleane-Fay 0 -> 115, Peter Kennedy 51 -> 196, etc.) before the
  16/17 investigation started.
- `fe873ba` (the 16/17 data correction) is **already live** - applied straight to the production db,
  independent of any redeploy.
- `be91791` (the template rebuild, steps 3-4) is **committed and pushed, NOT yet deployed**. Next
  session (or whenever Darragh next redeploys): confirm with
  `docker exec aims-web grep -c "adj-now" /app/app/static/style.css` (expect non-zero) and eyeball
  the live page - it should show the hero card + roster table, not the old flat card stack.

**The one thing that is easy to lose**: the `extract_historical_reviews.py` society-matching fix is
on the **`extractor-society-gate` branch (`edd445e`)**, not main's working tree. `git status` on main
is clean and gives no hint it exists. See OPEN item 1.

**Round 33 - public list-page fixes (2026-08-19), all from the UX audit below:**
- `/season` rendered dates as `dd-mm-yyyy` while the homepage used the compact `2-5 Sep 2026` range;
  both now use the existing `date_range` filter.
- "TBA" was shown for shows whose season already ended (the date is missing from the record, not
  unannounced). Past seasons now say **"Not on record"**, driven by a new `season_has_ended()` in
  `app/season.py`. **That helper is century-aware on purpose** - plain season-string comparison is
  unsafe across the 1999/2000 rollover ('76/77' sorts *after* '09/10' as text), which is exactly the
  bug that silently duplicated every row of the adjudicator grid in Round 25. Pinned by a test.
- The Review column was a full column of "Not yet" on any unadjudicated season - now collapses when
  no row in that table has a review, computed **per table** so a current season's finished half keeps
  it while its upcoming half drops it.
- `/titles` (287 rows) and `/societies` (125) rendered every row in one response while `/awards`
  already paged; both now page on the same `?page`/`?per_page` convention, and the pager markup moved
  into a shared `app/templates/_pagination.html` macro that `/awards` now uses too (three copies -> one).
- Tests 259 -> 273 (`tests/test_list_pagination_and_dates.py`). Verified the review-column test
  actually catches the regression by reverting the fix and watching it fail, per this repo's habit.

**Round 33 finding - the credit backfill did NOT need re-running.** The audit claimed approved
historical shows were missing credits their own review text names. **That was read off the local db,
where the reviews are still pending - a real mistake worth remembering: local `aims.db` is not
production, and the audit habit of verifying against prod over SSH is what caught it.** Dry-ran
`_credit_backfill_proposals` against production: **0 proposals**, i.e. already fully applied in
Round 31. Real production state across the 826 approved historical shows with an approved review:
director 529 filled / 297 blank, MD 443/383, choreographer 415/411, venue 300/526.
**The remaining blanks are extractor coverage, not un-run work** - confirmed on the audit's own
example (Tullyvin's The Addams Family, show 1176: MD "John Roe" and choreographer "Julianne
McNamara" *are* filled; only director is blank because the review phrases it "Such a director is
Paul Norton" / "Paul Norton not only directed", matching no existing pattern). Extending those
patterns is a real follow-up with its own verification burden (Round 31 had to prove no credit
matched its own review's adjudicator first) - not attempted.

**Architecture question Darragh asked, answered but NOT acted on - "can `shows` and
`historical_results` be one source of truth now?"** Short answer given: yes to one source of truth,
no to merging the two tables. They answer different questions - `shows` is one row per *staging*,
`historical_results` is one row per *award record* (a show that won five awards is five rows; a show
that won nothing isn't there at all). Merging either makes every production count wrong or discards
the award detail. The real fix is **a `productions` table both sides point at** - one row per real
staging at any year, with `shows` detail, award records and historical reviews hanging off it; the
23/24 boundary then disappears from every query because "how many productions" is one table.
**Deliberately not scoped further** - it's the same shape of problem as the parked people table
(both are "this entity has no identity, so we join on strings and split on dates") and Claude offered
to write up cost/benefit/breakage so Darragh can judge the two together. **Awaiting his call; don't
start the migration without it.**

## Previous "Start here" (2026-08-19)

**Deployed state (updated 2026-08-19)**: Rounds 27, 28, 28.1, and 29 are all live and confirmed
deployed (checked the actual running container's code directly, not just a deploy timestamp - a
timestamp alone only proves a restart happened, not which commit). Round 29 itself: a drop-cap
parsing bug and a wrapped-society-name bug (both fixed and shipped), a fuzzy society-name suggestion
feature for the moderation queue (directly requested by Darragh, shipped), and two real findings
investigated but deliberately NOT acted on (a wrong-society fuzzy-matching bug with an unsafe fix,
and ~112 stale orphaned review rows needing a more rigorous cleanup method than what was tried) -
see Round 29 below for the full detail on both.

**Round 29 shipped a real production incident** the same day: the new per-review fuzzy society
matching redid a full O(n²) society-vs-society comparison from scratch on every one of 175 pending
reviews on every load of the moderation queue (~2.8M `SequenceMatcher` calls, ~178s measured) -
hung waitress's workers and 524'd in production, with the container getting OOM/crash-restarted
under the load. Fixed same session by batching the comparison into one call (~4s, 45x) - see
`find_society_candidates_batch` in `app/blueprints/admin.py`. Confirmed deployed and stable.

**Round 30 (2026-08-19, same day)**: three more real-usage fixes, all confirmed deployed -
(1) the historical reviews queue collapsed into `<details>`/`<summary>` at both the per-row and
per-section level (886 pending reviews as always-expanded cards made the queue an enormous scroll;
measured ~16,500px default page height before, ~7,900px after, with the two largest/least-urgent
sections - "Ready to approve" and "Likely has award history" - tucked behind a closed-by-default
"Show all N" toggle); (2) society/show pages now link to a show's own ShowTimes review instead of
showing "None" in the Review column, for shows where `review_status` (AIMS's own official review
workflow) is unset but a historical review is linked - no schema change; (3) `app/production_
credits.py` suggests a historical show's blank venue/director/musical_director/choreographer fields
from its linked review's own prose (tested against all 815 approved reviews first - real but
partial coverage, shown as an edit-show "Use this" suggestion, never auto-applied).

**Round 31 (2026-08-19, same day - all confirmed deployed, container code checked directly):**
- **Bulk society matching** in the reviews queue (`group_needs_society` + `/admin/historical-reviews/
  bulk-apply-society-match`): one match applied to every pending review sharing a printed
  `society_raw`. On live data 172 reviews across 133 distinct names, 22 covering several reviews each.
- **Suggestion ranking rewritten** - `society_names.py` (new, root-level, shared by the app and
  `extract_historical_reviews.py`, which can't import each other). Ranks on the *distinctive* part of
  a name rather than a whole-string ratio. This is the wrong-society bug ROADMAP had been carrying:
  "Clane Musical Society" scored 0.93 against unrelated "Carnew Musical Society" but only 0.79
  against its own "Clane Musical & Dramatic Society". Calibrated against 22 confirmed pairs, all
  classify correctly, pinned by a test. Let the whole-string floor drop 0.85 -> 0.70, which
  surfaced genuine matches the old cutoff hid entirely (this archive abbreviates constantly).
- **Defunct/inactive flag** on suggestions (`societies.section = 'Inactive'`).
- **`/admin/backfill-credits`** - bulk-apply production credits read from review prose. Patterns
  rewritten to match real phrasing ("musical director X" lowercase, "Choreography by X", "Directors X
  and Y", "Under the Direction of X"): coverage went director 29%->63%, MD 16%->52%, choreographer
  12%->49%, 84% of reviews yielding at least one. 1635 values across 725 shows on live data. Verified
  no credit matches its own review's adjudicator (0 of 826) before wiring it up.
- **Search now covers review full text and award nominees** (new `historical_reviews_fts`, plus
  nominee-name matching on the existing awards index). This is the only index over prose rather than
  names - a director/performer/venue exists in no column anywhere. Approved + non-hidden only, pinned
  by a test.
- **Fixed a live 500 on `/admin/duplicate-titles/bulk`** - `_merge_titles` deletes a redundant `shows`
  row, but the ShowTimes import since added `historical_reviews.show_id -> shows(id)`, so deleting a
  skeleton show with a review attached hit a FOREIGN KEY constraint and took the whole bulk save
  down. The review now moves onto the surviving row first.

**Production data corrections applied directly (2026-08-19, via SSH against the container's db -
these are data, not code, so they are NOT in git and will not reappear from a redeploy):**
- 26 reviews had `show_raw`/`society_raw` swapped (society name stored as the title, real title left
  as the first words of `review_text`); corrected, titles recovered from the review text.
- id 79 "Belfast Music & Dramatic Society Footloose" split into title + society.
- 3 duplicate/garbled rows rejected (854, 358, 149) - each already correctly present elsewhere.
- Review 734's doubled drop-cap ("TThe Wexford...") fixed - only instance in the archive.
- **7 Cork reviews were mis-filed on UCD Musical Society** by the near-identical-name bug: 538/599/696
  -> UCC Musical Theatre Society, 979 -> UCD (it was on UCC, the mirror of the same bug), and
  631/685/837 -> a newly created **CIT Musical Society** (id 10000, South-West, section='Inactive' -
  CIT became MTU in 2021). Society ids >= 10000 are the manual range so a societies.csv re-import
  can't collide (matches `admin.new_society()`). Their skeleton shows moved too, or they'd have
  stayed on UCD's public page. UCD went 36 -> 29 shows.

**Site-wide UX audit (2026-08-19) - findings and Darragh's decisions. NOTHING BUILT YET.**
Full audit: https://claude.ai/code/artifact/a8c8a2db-e59e-4697-9362-ead2c58bdb48 (revised after his
review - the published version is the corrected one). Method: live-site screenshots at desktop +
mobile, walked the public routes, every suspicion verified against the **production** db over SSH
before being written down. Mobile (card layouts, bottom nav) is genuinely good - findings are
specific misfires, not "looks bad".

**A wrong finding, corrected - worth keeping as a lesson**: the audit originally claimed "Best
Choreography" and "Best Choreographer" were the same award duplicated. **They were two genuinely
separate awards** (a production award and a person award) - Darragh corrected this immediately.
The data agrees and I should have checked it first: Best Choreographer has a nominee on 45/45
records, Best Choreography on only 88/203. Overlapping year ranges are not sufficient evidence of a
duplicate.

**The real finding underneath (confirmed against the AIMS 25/26 adjudication changes,
https://www.aims.ie/post/news-aims-adjudication-review-changes-in-place-the-2025-26-season):**
three categories were renamed at the 2025->2026 boundary and the archive records old and new as
unrelated, so a 48-year history reads as a one-year-old award. All three break cleanly, no overlap:
- `Best Chorus` (1977-2025, 204) -> `Best Choral Singing` (2026-, 10)
- `Best Choreography` (1977-2025, 203) -> `Best Moment of Theatre` (2026-, 10)
- `Adjudicator's Special Award` (1977-2025, 69) -> `Spirit of AIMS` (2026-, 10)
- `Best Choreographer` (2019-2026, 45) is **unaffected** - separate, still running.
Found by querying for categories that stop at 2025 / start at 2026. **That method only catches
renames at this one boundary** - an older rename wouldn't surface. Darragh: none others known "at
this time", so don't treat the list as exhaustive if something looks odd pre-2025.

**DECIDED (Darragh, 2026-08-19) - build these when picked up:**
1. **Spirit of AIMS = renamed Adjudicator's Special Award.** Same award. Merge as one lineage.
2. **Best Moment of Theatre starts fresh** - does NOT inherit Best Choreography's history. Cross-link
   the two ("formerly..."/"continues as...") but count separately, since the award's meaning changed
   (no longer dance-specific).
3. **Best Chorus + Best Choral Singing merge** as one continuous award (pure rename per AIMS).
   => So: **two merges (Chorus, Special Award), one fresh start (Choreography/Moment of Theatre).**
   Implement as a query/display-time alias map, NOT a data rewrite - reversible, and keeps
   `historical_results` faithful to what AIMS actually published each year.
4. **Drop the "Since 23/24" timeframe toggle** - the archive now has enough depth. **CRITICAL
   CAVEAT: remove the UI control only, keep `SHOWS_COVERAGE_START_YEAR`.** The constant does two
   unrelated jobs: the toggle/default (goes) and the split that stops a production being counted
   once from `shows` and again from `historical_results` (~20 references across `info.py`/
   `public.py`/`admin.py` - removing it inflates essentially every number on the site).
   Root cause it fixes: the "recent" default made per-person leaderboards degenerate - Best
   Choreography since 23/24 showed six people all tied at 1; all-time gives a real ranking
   (Siobhan McQuillan / Mary McDonagh / Barbara Meany at 3).
5. **Navigation - one name per destination**: `/` = **Upcoming shows**, `/season` = **Seasons**
   (was "Season Archive" in the header vs "This season" in the mobile bar - opposite meanings),
   `/stats` = **Statistics**. And **promote `/titles` ("Shows A-Z") into the main nav** - 287 titles,
   a main "has anyone done this show?" answer, currently reachable only from a footer link.
6. **The 6 literal-`'None'` award rows** are a data fix, agreed. ids 12408, 13466, 13519, 13699,
   13966, 14006 (`reason='None'`; 13519 also has `role`/`nominee_name='None'`). Not from the tracked
   CSV (checked, clean) and not from today's admin form (`.strip() or None`) - legacy rows. Also
   widen `awards.html`'s sentinel guard, which today only defends `role != 'NULL'`, to cover
   `'None'`/`'NULL'` across all three fields.

**PARKED on Darragh's privacy objection - the `people` table / person pages.** The underlying
problem is real and measured: people are free text in three places with no link between them -
1,730 distinct award nominee names, 746 credit names (`shows.director`/`musical_director`/
`choreographer`), 18 adjudicators (already a real table with ids); **217 credit names are also an
award nominee** by exact match alone, 8 adjudicators likewise. Duo nominees ("Claire Tighe and Jen
Dawson" vs "Jennifer Dawson & Claire Tighe" vs "Claire Tighe" solo) are a symptom, only 46 of 1,730
names. `/admin/backfill-credits` is actively adding more free-text names, so it grows if left.
**Darragh's objection, which is a good one and should not be argued away**: a public page per
person is a large feature and one those people may not want. **Resolution to carry forward: the
identity layer and the public page are separable.** Internal identity resolution (canonical names +
aliases, moderator-reviewed, reusing `dedupe.find_candidates`) fixes the counting/dedupe problem
with **no new public surface** - no person pages, nothing published that isn't already on the
awards page or in a review today. Any public person page would be a separate, later, opt-in-shaped
decision. Do not build person pages as part of fixing the counting.

**Round 32 - Admin dashboard restructure (2026-08-19, same day):** Darragh flagged `/admin` itself
as the "one long list, poor UX" pattern (not the adjudicators page, which is still open below) -
11-12 "Needs attention" rows and 16 Tools links all in flat lists with no grouping, a permanently-
nonzero count (award records with no society match, mostly defunct societies) sitting at the same
visual weight as a real queue.
- **Mockup-first, two options published**, both built from the site's own real CSS tokens
  (`--bg`/`--accent`/`--warning` etc., not a new palette) so they'd preview accurately in the actual
  theme. Option A (grouped table, same `data-table` component, just labelled sections) vs Option B
  (summary strip + collapsible panels, reusing the historical-reviews-queue pattern). Recommended A
  as lower-risk since it's a template change with no new component; Darragh agreed.
- **Follow-up feedback, not just "ship A"**: even grouped, the counts still felt unmanageable.
  Asked directly rather than guessing which of three plausible causes it was (visual weight, wall-of-
  rows on click-through, no sense of where to start) - Darragh picked two: **clicking through dumps
  you into a wall of individual rows** (true for several of these - checked the actual pages, not
  assumed: `fix_dates.html` is one `<form>` per row with a full page reload per save, `venues.html`
  already has decent inline-autosave-on-blur across the whole list, `shows_list`'s review-link fix
  goes through each show's full edit page) and **no sense of where to start**.
- **Shipped for the "no sense of where to start" half**: a "Quick win" callout (reuses the existing
  `.explorer` hero-card CSS, same tinted-gradient treatment the Stats page's Award Explorer already
  uses) surfacing whichever actionable count is smallest and non-zero, computed server-side in
  `admin.dashboard()` - explicitly excludes the award-records-unmatched count (it's flagged as
  permanent/won't-reach-0 and would otherwise "win" by being the biggest number on the page, the
  opposite of a quick win).
- **Not yet built - the "wall of rows" half**: extending real bulk-edit tooling to the pages that
  don't have it yet. `fix_dates` is the worst of the three (full reload per row) and the cheapest fix
  - give it the same inline-autosave-on-blur pattern `venues.html` already uses, no new mechanism to
  invent. Review-link fixing (via each show's full edit page) and the review-link count itself would
  need their own look at what a bulk view could reasonably do (dates and venues are single fields;
  a review link is tied to `review_status` too, more like the historical-reviews queue's shape).
- Verified in a real browser, not just template review: ran the local dev server, logged in with a
  throwaway admin account, screenshotted the actual rendered page (headless Edge, 900px - the known
  false-positive-narrow-viewport issue is well below that), confirmed groups/dot indicators/quick-win/
  tools grid all render correctly against real local data. Throwaway login deleted and scratch files
  removed afterward. All 259 tests still pass.
- **Committed but not deployed** - `app/blueprints/admin.py`, `app/static/style.css`,
  `app/templates/admin/dashboard.html`.

**OPEN - next session should pick these up:**

*Decided by Darragh in the UX-audit session, specced, not built. Each is small and independent -
these are the obvious next build, in rough size order:*
- **A. The 6 literal-`'None'` award rows** - production ids 12408, 13466, 13519, 13699, 13966, 14006
  (`reason='None'`; 13519 also `role`/`nominee_name='None'`). They render as an italic note reading
  "None" under an award on the public `/awards` page. Fix the data *and* widen `awards.html`'s
  sentinel guard, which today only defends `role != 'NULL'`, to cover `'None'`/`'NULL'` across all
  three fields so a future import can't silently reintroduce it. Smallest job here.
- **B. Remove the "Since 23/24" timeframe toggle** - Darragh's call, the archive has the depth now.
  **Delete the UI control and the `era` param only; KEEP `SHOWS_COVERAGE_START_YEAR`** (~20
  references - it's the split that stops a production being counted once from `shows` and again from
  `historical_results`; removing it inflates essentially every number on the site). This is what
  fixes the degenerate leaderboards: Best Choreography since 23/24 shows six people tied at 1, where
  all-time gives a real ranking (Siobhan McQuillan / Mary McDonagh / Barbara Meany at 3).
- **C. Navigation labels + promote `/titles`** - one name per destination: `/` = **Upcoming shows**,
  `/season` = **Seasons**, `/stats` = **Statistics**. And lift `/titles` ("Shows A-Z", 287 titles)
  out of the footer into the main nav - today it's absent from the header, the mobile bar and
  `/more`. Cheapest high-value change on the list.
- **D. Award category lineage** (biggest of the four) - three categories were renamed at the
  2025->2026 boundary and the archive treats old and new as unrelated, so a 48-year history reads as
  a one-year-old award. Darragh's decisions: **merge** `Best Chorus` -> `Best Choral Singing` and
  `Adjudicator's Special Award` -> `Spirit of AIMS` (same award, renamed); **do NOT merge**
  `Best Choreography` -> `Best Moment of Theatre` (the award's meaning changed - cross-link
  "formerly..."/"continues as..." but count separately). `Best Choreographer` (2019-2026) is a
  **separate, still-running person award - not a duplicate**, do not touch it. Implement as a
  query/display-time alias map, **not** a data rewrite, so `historical_results` stays faithful to
  what AIMS actually published each year. Source:
  https://www.aims.ie/post/news-aims-adjudication-review-changes-in-place-the-2025-26-season

0. **Admin dashboard "wall of rows" follow-up** (Round 32, above) - give `fix_dates` the same inline-
   autosave pattern `venues.html` already has (cheapest, worst offender), then look at whether
   review-link fixing can get something similar or needs its own shape.
0b. **Credit-extractor pattern coverage** (new, Round 33) - ~300-400 blanks per credit field remain
   on approved historical shows because the review prose phrases the credit unusually ("Such a
   director is X", "X not only directed"). Extending `app/production_credits.py`'s patterns needs the
   same verification Round 31 did (prove no credit matches its own review's adjudicator) before
   being wired into the bulk apply.
1. **`extract_historical_reviews.py` still has the root bug** that caused the UCC/UCD mis-filing:
   `find_society_span` picks by whole-string ratio, so "UCC Musical Society" matches "UCD Musical
   Society" (0.95, one character apart) over the correct "UCC Musical Theatre Society", and it
   returns the *canonical* name, overwriting what was actually printed. A fix is written and
   **committed to the `extractor-society-gate` branch (`edd445e`), NOT merged to main** - it is *not*
   in main's working tree, so `git status` on main looks clean and the work is easy to think lost
   (checked 2026-08-19: `git branch -v` and `git reflog` both find it). To pick it up:
   `git checkout extractor-society-gate`. The fix gates candidates through
   `society_names.is_same_society`, and when nothing passes but a society-shaped span is clearly
   there, return the span with no canonical name so the printed text survives and the review lands in
   the queue for a human. Measured over the whole archive: **863 -> 863 reviews, lost 2 / gained 2,
   77 societies corrected** (a naive gate without the position-preserving fallback lost 32 reviews -
   don't ship that version). **Still to do: eyeball those 77 changes before committing** - an earlier
   run of the same measurement showed a few suspicious values from the capitalization fallback
   ('Gilbert Section', 'Kells Musical & Dramatic Society 76'). The measurement script is
   scratchpad-only; re-create it by diffing extraction output against `historical_reviews_pilot.json`.
2. **Audit the other near-identical society pairs** (Darragh approved this): Baldoyle/Boyle,
   Ballinasloe/Ballinrobe, Banbridge/Newbridge, Achill/Kill, Kilcock/Kill, Newcastle Glees/
   Newcastlewest - ~87 reviews between them, same bug class as UCC/UCD. Check each against the
   printed heading in the source PDF, not the stored `society_raw` (which the extractor overwrites).
3. **`/admin/duplicate-titles` UX redesign** - Darragh asked for mockups, not code. Current page is
   one long list; he wants a better layout. Mockup-first, per the established pattern.
4. **Junk skeleton show titles** - some shows are titled `based`, `in`, `Trinity's`, `Sweet`,
   `Whisper it quietly but this is one` etc. from early extraction runs, and they inherit credits on
   the backfill page. Needs its own cleanup pass.
5. ~~**Adjudicators page redesign**~~ - **superseded by Round 34 at the top of this file.** Design is
   agreed and published, the count bug underneath it is fixed and the duplicate adjudicator merged;
   what remains is building the two templates. Item 4 in the older list below is now history - read
   Round 34 instead, it supersedes the open questions there (including the definition of "current").

**Note on the wall-of-text reviews** (asked about twice, so worth recording): ~12% of the archive
renders as one unbroken block. This is **faithful to the source, not an extraction fault** - checked
the PDFs directly (Issue 79 p11-13, Issue 109 p10): those reviews have no ragged paragraph-final
lines, no indentation, and perfectly uniform 9.5pt leading, so there is no paragraph structure to
recover. On the same Issue 109 page one column breaks into paragraphs and the next doesn't. Nothing
was invented to break them up; only the typography was improved (`.review-block p` line-height +
`max-width: 68ch`). Don't re-investigate this as a bug.

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
4. **Public `/adjudicators` list page needs a redesign - flagged by Darragh 2026-08-19, plan/mockup
   first, not code yet ("might be a job for tonight").** Today `adjudicators_list()`/
   `adjudicators_list.html` is one flat alphabetical list mixing every adjudicator who's ever had a
   season/tier assignment - current and decades-past alike - which is exactly the "one long page,
   poor UX" he's pointing at. His proposed shape:
   - **Current-season adjudicators in a grid at the top**, linking to their current-season reviews.
   - **An option to browse a current adjudicator's past seasons** too - by region/show/society was
     his rough idea, not a firm spec.
   - **Past (no-longer-active) adjudicators** get a simpler treatment - just a link through to their
     bio + season history, i.e. the existing `adjudicator_detail()`/`adjudicator_detail.html` page
     (`/adjudicators/<id>`), which already exists (Round 20) and already needs its own season-grouping
     refinement per "Option A" above - these two items should almost certainly be designed together,
     not separately, since the list page's "past adjudicator" link and the detail page's own season
     grouping are two halves of the same browsing path.
   - Needs a real definition of "current" (current_season() already exists and is used elsewhere -
     an adjudicator with an assignment for the current season, vs everyone else) before mockups can
     be built.
   - Mockup-first per this repo's established pattern (see item 2a above) - present options, get
     Darragh's call, then build.

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
- 20 tests pass (1 new this round: the merge-not-rename case). Committed (`0565a66`) and confirmed
  deployed (checked the actual running container's code, not just the deploy timestamp - the
  timestamp alone only proves a restart happened, not which commit).

**Round 29 - three more real extraction bugs from Darragh's own screenshots, plus fuzzy society
suggestions (2026-08-19):** Not a re-run of the archive-wide audit - each bug here was found because
Darragh was looking at the real queue and flagged something that looked wrong.
- **A decorative drop-cap fabricating a fake review**: PyMuPDF gives a large-font drop-cap its own
  text run, separate from the rest of the word it starts - Issue 107 October 2015's season-opening
  "As the new show season begins we welcome two new adjudicators..." editorial had its lone 'A'
  read as a real title, and the adjudicators' own names appearing in that same intro's bio
  paragraphs then looked exactly like their sign-offs, fabricating a fake review from editorial text
  no adjudicator wrote. Fixed (a single character never counts as title-shaped, even large-font) -
  this issue genuinely has 0 recoverable reviews though; the bios' own name-as-heading structure
  breaks the sign-off boundary detection for the real reviews too, a deeper limitation not attempted
  this round (see below).
- **A wrapped society name eating the real title**: 'North East Music & Dramatic Society,' /
  'Castleblayney' (the town, wrapped onto its own line) had 'Castleblayney' picked as the show title
  outright, silently dropping the real title '9 TO 5'. Fixed - a trailing comma on the matched
  society span's own last line now signals a continuation to skip, not a title.
- **A confirmed but NOT fixed bug**: two cases (Malahide Musical Society misattributed to the
  unrelated Baldoyle Musical Society; Leixlip Musical Society misattributed to the unrelated Boyle
  Musical Society) where whole-string character-ratio scoring let a same-shaped but wrong society
  coincidentally outscore the real one. A first-word-must-also-match gate fixed both confirmed
  cases cleanly, but combined with a compensating threshold change it also cost real reviews
  elsewhere in the archive for reasons not root-caused in the time available (e.g. Issue 90's
  Ratoath Musical Society - an exact, unambiguous name match with nothing that should have been
  affected) - reverted rather than ship something not fully understood. **The underlying bug is
  real and confirmed; the fix attempt is not yet safe.** See "Next steps" below before re-attempting.
- **Fuzzy society-name suggestions, directly requested** ("surely there can be suggested society
  matching? ie Harold's Cross vs Harolds Cross?"): reused the same `app.dedupe.find_candidates`
  scorer a third time (after historical_results titles and skeleton show titles) rather than a new
  implementation. `/admin/historical-reviews`'s "needs a society matched" category now shows
  one-click suggestions when a real spelling/punctuation variant scores high enough (confirmed -
  "Harold's Cross Tallaght Musical Society" vs the printed "Harolds Cross Tallaght Musical Society"
  scores 0.99).
- **A verification lesson worth remembering**: while assessing whether ~112 old "orphaned" pending
  review rows (superseded by corrected re-extractions, never approved, safe to delete) were
  actually safe to clean up, a crude "same show title appears elsewhere in the issue" heuristic
  wrongly flagged 2-3 of a 19-row sample as "superseded" when they were actually genuine, distinct
  reviews (the Malahide case above was found exactly this way). **No cleanup was executed** - the
  finding is real (roughly 112 stale pending rows exist, cross-referenced against the verified
  extraction by exact key match) but needs a properly rigorous verification pass, not a pattern-
  matched spot-check, before anyone deletes anything. 23 further rows are already-approved and must
  never be touched regardless (approved rows intentionally freeze their text, per load_reviews.py's
  own design).
- 863 reviews (down 1 from Round 28's 864 - the one fake Issue 107 entry removed, nothing else
  changed in count; the reverted society-matching attempt made no difference to the shipped
  version). 253 tests pass. Reloaded into local `aims.db` (4 inserted, 857 already-loaded,
  2 refreshed). Committed and pushed.

## Next steps / open questions for a future session

**Not blocking anything right now** - Rounds 27, 28, 28.1, and 29 are all shipped and deployed (or
committed and ready for the next redeploy, for Round 29's fixes specifically). Nothing in this list
needs to happen before Darragh can keep using the tool.

**Real bug, not yet safely fixed - wrong-society misattribution**: `find_society_span`'s whole-
string character-ratio scoring can let a same-shaped but *unrelated* society (sharing a generic
suffix like "Musical Society") coincidentally outscore the real match, when the real match has
extra words the printed heading omits. Two confirmed real cases (Issue 120: "Malahide Musical
Society" as printed wrongly matched "Baldoyle Musical Society" over the real "Malahide Musical &
Dramatic Society"; Issue 70: "Leixlip Musical Society" wrongly matched "Boyle Musical Society"
over "Leixlip Musical & Variety Group"). A first-word-must-also-match gate fixed both cleanly in
isolation, but shipping it (even combined with a compensating threshold change to recover
marginal real matches like Leixlip's own 0.74 whole-string score) cost real reviews elsewhere in
the archive - confirmed via a full re-extraction diff, not assumed - for reasons not root-caused
before running out of session time. **Before re-attempting**: isolate exactly why Issue 90's
Ratoath Musical Society review (an exact, unambiguous canonical-name match with no competing
candidate at all) failed under the first-word gate alone, even at the original 0.80 threshold - that
result shouldn't be possible if the gate genuinely never rejects a match the old code would have
accepted, so either the gate has a real bug beyond what this session found, or something else in
that specific issue's PDF (it has visible font-encoding corruption in places) is confusing the
fix. Don't just re-ship the same first-word-gate code without understanding this first.

**Real finding, explicitly not acted on - stale orphaned review rows**: cross-referencing
production's `historical_reviews` table against the current verified extraction by exact
`(source_issue, society_raw, show_raw)` key found ~112 pending rows that don't match anything in
the current dataset - almost certainly leftovers from early, since-corrected extraction rounds
that `load_reviews()`'s text-based dedup key didn't recognize as "the same review, now fixed" (a
structural limitation of that dedup key worth knowing about even outside this specific cleanup -
any future extraction correction will keep doing this). **Before deleting any of them**: a crude
"does this show title appear elsewhere in the same issue" heuristic wrongly flagged 2-3 of a
19-row spot-check sample as safe to delete when they were genuinely distinct, un-superseded
reviews (the Malahide case above was found exactly this way) - a real false-positive rate too high
to act on without a properly rigorous check first (e.g. reusing whatever ends up fixing the
wrong-society-matching bug above, once it's actually trustworthy). 23 further rows are already-
*approved* and must never be touched regardless of any cleanup method, since approved rows
intentionally freeze their text by design.

**Worth investigating - the systemic version of the Ragtime/title-check bug**: `match_show_for_edit`
(used at both review-approval and review-edit time) only ever does an *exact* string match against
`shows`. Round 28 added fuzzy matching against `historical_results` for the moderation queue's own
categorization (`find_historical_results_candidates`), but never extended the same idea to `shows`
itself - so a review can still create a redundant skeleton instead of linking to an already-existing,
differently-titled show (submission or import), for any of the reviews still pending. Concretely
worth trying next session: run `find_historical_results_candidates`-shaped fuzzy matching against
`shows` too (not just `historical_results`) as part of `categorize_pending_reviews`'s "ready" bucket,
so a review with a plausible-but-not-exact existing show gets routed into a "needs a title/show check"
category *before* approval, rather than only being caught after the fact by a title-check audit.

**Deferred ideas, lower priority than the above**:
- Fuzzy-matching show *titles* to warn on likely duplicates more broadly, not just within this
  review-import pipeline - Darragh's own earlier "a show match would be great too" ask. `app.dedupe.
  find_candidates` is now reused three times (historical_results titles, skeleton show titles,
  society names) - extending its use beyond the historical-review flow (e.g. flagging likely-
  duplicate `shows` rows generally, the way the admin dashboard already flags likely-duplicate
  societies) is a natural next step, not a new mechanism.
- Extracting Director/Musical Director/Choreographer names from review text - explicitly flagged by
  Darragh early on as "food for thought for later," not urgent.
- A worthwhile cleanup, not urgent: `find_historical_results_candidates`, `find_society_candidates`,
  `match_show_for_edit`, and `find_mismatched_skeleton_shows` are four separate, not-quite-unified
  matching code paths that grew one at a time as each new problem surfaced. Once the current
  backlog (queue + title-check + the two open items above) is actually resolved, consider whether
  these should collapse into one shared matching utility - not urgent while there's still real work.
- Continue working through the main `/admin/historical-reviews` queue itself (needs-society /
  conflict / history-match categories) - the bulk-approvable "ready" bucket was already cleared
  earlier this session, but those three categories all genuinely need a person to look at each one.
  The needs-society category should now be faster to work through with Round 29's fuzzy-suggestion
  buttons.
- Issue 107 October 2015 (and likely any other issue where a new adjudicator pairing's season-
  opening welcome article runs adjudicator bios with their own name as a heading line) genuinely
  has 0 recoverable reviews with the current segment-boundary logic - the bios' own name headings
  get mistaken for sign-offs, same failure shape as the already-fixed "Top Three Tunes"/"News"/
  "Regional Round-Up" furniture headings but harder to fix generically since a real adjudicator
  name legitimately CAN appear as a heading-shaped line in this one specific context. Not attempted
  this round; likely rare enough (once per adjudicator-pair change) not to be worth much further
  investment unless it turns out to recur often.

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

---

# 2026-08-21 through 2026-08-23 session block

Everything below was live content in ROADMAP.md through 2026-08-23, archived on that date because it's
shipped, deployed, and confirmed live (or otherwise fully resolved/superseded). Nothing here needs
action - genuinely open items that were mixed in below were carried forward into the lean ROADMAP.md
separately.

## DATA_ACCURACY_AND_CORRECTIONS_REPORT.md checked against reality, 2026-08-23

Darragh dropped a Gemini-generated audit (DATA_ACCURACY_AND_CORRECTIONS_REPORT.md, repo root,
untracked) and asked me to check it. Verified every section against a fresh prod snapshot rather than
trusting it - same discipline as venues_report.md earlier. Also separately caught, cross-referencing
this report: St. Marys MS Navan's Evita venue mismatch, found in an earlier session today but never
actually applied - the report re-surfaced it.

Applied (e4a3685):
- 6 of the report's 20 claimed "venue column shift" rows were genuinely still wrong (LOST/JCS, Naas
  MS/Young Frankenstein, Portlaoise MS/Guys and Dolls, Shannon MS/Cry-Baby, St. Michael's Theatre
  MS/Witches of Eastwick, St. Marys Navan/Evita) - confirmed via each society's own other venues, same
  standard as every other venue fix today, and blanked (not the report's specific claimed replacement -
  see below on why).
- Linked 75 historical_results rows to two societies that already had a matching societies row and
  simply weren't connected (Greenhills Variety Group, New Lyric Operatic Company Belfast) - already
  flagged as a known issue in an earlier session's notes, confirmed safe, applied.

Already resolved before I even checked, report is stale on these:
- 14 of the 20 "venue column shift" rows - already fixed earlier this session (same rows, different
  investigation method).
- Show 195 (Oyster Lane/A Christmas Carol) - already correct; the report claimed it was currently wrong
  and named the exact value already on record as the "fix".
- All 4 "venue punctuation drift" examples (St. Michael's Theatre New Ross, National Opera House
  Wexford, Town Hall Theatre Galway, Garter Lane) - already merged in the same day's earlier venue
  merge-queue work.
- The claimed duplicate award row (46140/46164) - both ids no longer exist; already resolved, unclear
  when.
- The 81-shows-missing-a-26/27-venue figure - real number now 34, already worked down via
  venues_report.md's CONFLICTS review earlier the same day.

One clear lesson worth keeping: the report is a good lead generator, not a source of truth - it got at
least one claim stale (195) and its counts drift from current reality on several others (144 vs 154
NULL-category rows, 647 vs 645 unmapped societies, 26 vs 28 orphaned societies) even where the
underlying finding is real. Every specific replacement value it proposed for the venue fixes was left
unwritten - blanked instead, same "don't guess" policy as everything else, since the one claim fully
verifiable (195) turned out wrong.

(The report's remaining un-auto-fixed findings - 11 shows Published with no review URL, 154
NULL-category historical rows, ~10 more unmapped historical societies needing new records, 28 orphaned
Inactive societies - carried forward into the live ROADMAP.md as genuinely open items, condensed.)

## Full public-site UX audit, 2026-08-23

Darragh asked for a step-back walkthrough of the whole public site as (a) a society committee member
and (b) an ordinary musical-theatre fan. Non-technical write-up with mockups, published as an Artifact:
https://claude.ai/code/artifact/a546fc7e-ef6e-42c3-b6e5-400634708318

The headline finding: the site's infrastructure is far ahead of its content. Every one of these fields
already exists, already renders the moment it's filled, and is already editable by societies themselves
- nobody has been asked:

Society about blurb 1 of 194; society website link 0 of 194; society Facebook/Instagram/TikTok 2/3/3;
society logo 7 of 194; venue capacity/map pin 0 of 147 each; ticket link on an upcoming show 7 of 50;
poster on an upcoming show 9 of 50; society login codes ever issued 14 of 143 active societies.

Verified broken journeys, all re-confirmed against the live site 2026-08-23:
- A show page contained zero links to its own venue page - linked to Google Maps instead. Society pages
  the same.
- "Submit a show" unreachable on desktop - linked only from /more, itself mobile-tab-bar-only.
- Adjudicator names on /reviews weren't links, though /adjudicators/<id> existed.
- sitemap.xml omitted /titles, /venues, /awards, /reviews, /stats/trends, /about and every
  title/venue/adjudicator detail page.
- /reviews was a 362KB single page (all 1,086 reviews, no pagination); /season was 123KB.
- Gilbert/Sullivan was explained only on /about but used as a filter label on 5+ pages.

Quick-win batch 1 shipped 2026-08-23 (b729565): venue text on the show page and homepage links to
/venues/<slug> (Maps link kept alongside - different questions); adjudicator names on /reviews link to
/adjudicators/<id> (needed restructuring review_row from one big <a> wrapping the whole row into a <div>
with the show title carrying the row's original destination, since a link can't nest inside a link);
sitemap.xml gained /titles, /venues, /awards, /reviews, /stats/trends, /about, and every individual
title/venue/adjudicator page. show_detail()/index() now call venues_build.ensure_current(db) themselves.
18 new/updated tests, full suite 514 green.
- Deliberately dropped from the batch: "Submit a show unreachable on desktop" is factually true but not
  a bug - test_homepage_split.py already asserts it must NOT be in the footer, and this archive
  confirms Darragh removed it from the nav/footer on purpose (prefers the logged-in society flow;
  shares the one-off form only via a direct link). Caught before implementing, not after.

Quick-win batch 2 shipped 2026-08-23 (590e1f4, 74dc693, f8d1041, d20f9be): "Not recorded" replaces "TBA"
for a past show with no date on society_detail.html/venue_detail.html (extends a 2026-08-19 fix that
only covered season.html/show_detail.html); the stale "before the end of August" promise removed from
/about; a "see the full season" link added under the homepage's 6-show table; empty-state messages
added to /titles search and /stats' one-off productions; a short Gilbert/Sullivan explainer added under
the filter form on Awards, Reviews, Season and Societies, linking to /about rather than re-explaining
inline (checked /about's real text first - it's a workload-driven adjudicator split on nomination
history, not about production size). 13 new tests, full suite 527 green.
- Three audit findings turned out to be deliberate decisions, not bugs - caught before implementing, not
  after, by checking git history/comments rather than trusting the audit's own read:
  - "Homepage notices above the fold" - Darragh explicitly asked for this placement (39f7276, 19 Aug:
    "I'd like people to submit ideas"). Left alone.
  - "Public adjudication-cutoff display" - added on purpose (31ae512, commit title literally "add
    public cut-off date"), and the code comment already reasons why it's fine (pure arithmetic on a
    date already shown, not real AIMS scheduling data). Left alone.
  - "Random Award Explorer default" - documented in-line in info.py: deliberately avoids the Explorer's
    default view becoming a fixed "who's won the most" leaderboard for one category. Left alone.
  - Also nearly shipped a bad "fix" for /awards' blank Nominee cells - the cell isn't blank by
    oversight, nominee_name for a society-level category literally duplicates the Society column
    (verified against real data). Reverted before committing.

Mobile nav bug fixed 2026-08-23 (82617ae) - Darragh caught it live on his phone, screenshot and all: the
Explore menu ran off the left edge of the screen, unreadable. Root cause: the narrow-viewport fix from
the nav restructure (right: -0.6rem) was written for History, which sits near the right of the row - the
same anchor pushed Explore's menu (near the left) off the opposite edge. Fixed properly rather than just
flipping the anchor for one trigger: below 40rem the menu is now a normal full-width block under
whichever trigger opened it (flex-basis: 100% on the open <details>), so neither trigger's menu can
overflow either edge. Verified locally at 390px with the menu force-opened for both Explore and History.

(The audit's four bigger bets - homepage reorder, society page empty-vs-filled, show page as front door,
"what's on near me" - and its outreach/onboarding track are still open; carried forward into the live
ROADMAP.md, condensed, with the artifact link.)

## Productions-table migration, stages 1-2 (2026-08-22)

Built in the worktree-productions-table worktree, merged to main (94f0e2f), deployed and independently
verified running in production. Full suite 443 green.

Verified after the redeploy, not assumed - aims-web restarted with the new code present, the table
built itself on first startup (2,805 productions, 1911-2027, 1,242 shows rows and 4,707 award records
linked), and GET /stats from inside the container returned 2,711 productions / 1,092 reviewed with the
folded 1911-1976 row and its note. Page serves in ~180ms on the NAS.

What's done:
1. The table itself (productions in schema.sql) - one row per real staging, natural key
   (society_key, season_start_year, title_key). Derived, not authored: app/productions_build.py is the
   only writer, and it upserts on that key so a production keeps its id across rebuilds. production_id
   links added to shows / historical_results / historical_reviews. app/productions.py holds the key
   derivation so the definition can't drift between callers.
2. The rebuild - runs on every app start, and lazily on /stats when a cheap fingerprint shows the source
   tables have moved. ~700ms cold, ~50ms when there's nothing to do. build_productions.py at the repo
   root is the CLI half (--dry-run verifies and rolls back). Every run ends with a verification pass
   that re-derives the totals from the database and raises rather than trusting its own write.
3. Statistics cut over (info.py's stats()) - the first of the four staged surfaces. Five GROUP BY
   queries merged in Python became one query over productions; the region filter became a single
   equality test instead of the three-way COALESCE fallback join.

Two century bugs this found, both real and both now fixed by construction:
- historical_results_year() ('yy/yy' -> 2000+yy+1) couldn't express an award year before 2001 - 1912
  came back as 2012, 2000 as 2100. 75 of the archive's 100 award years didn't round-trip, so /stats
  reported 0 productions for every season before 00/01 while the same page's own tile said
  "1912-present". The headline total goes 1,837 -> 2,711.
- season_start_year()'s pivot at 50 assumed the archive starts in 1977. It starts in 1912, so 9
  pre-1950 award years filed under a modern season that also exists for real.

Real-data verification: 2,805 productions spanning 1911-2027 - 1,242 with a shows row, 2,271 with an
award record, 708 both; region resolved for all but 18; rebuild idempotent.

Presentation decision Darragh made this session: the 1911-1976 seasons (98 productions across 51
seasons, from only Wexford Light Opera / Roscrea / Carrick-on-Suir) fold into one labelled summary row
rather than 51 near-empty ones - see ARCHIVE_CIRCUIT_START_YEAR in constants.py.

Stage 2 done 2026-08-22 (admin counts). NEEDS_REVIEW_WHERE is now the single definition of "this
production has run and nobody has written it up", shared by the dashboard counter, the shows-list
needs_review filter, and the Reviews queue - they disagreed before (115 / 115 / 29), the queue was
right. _duplicate_historical_rows matches on production_id instead of comparing calendar years: 0
duplicates found before, 9 real ones now. 12 new tests, full suite 455 green.

## Productions-table migration, stages 3-4 (2026-08-23)

Built in an isolated worktree against `docs/productions-stage-3-4-plan.md`, which was written and
re-verified against a current production snapshot before any code was written. Five commits, one per
plan step, suite green after each: 541 before, **579 after** (38 new tests, `tests/
test_public_productions_cutover.py`). Not yet merged or deployed at time of writing - the §7.3 live
checks are still outstanding.

**What shipped.**
1. `ON_RECORD_PRODUCTION` in `app/productions.py` - the one filter every public surface applies, next to
   the key derivation, because `productions_build.collect()` reads `shows` with no `moderation_status`
   filter, so a pending or rejected submission has a production row. Plus the missing
   `productions_build.ensure_current()` calls on `titles_list`, `search`, `society_detail`,
   `show_detail` and `sitemap_xml` (only `title_detail` had one).
2. Shows A-Z, `/search`'s Shows section and `/sitemap.xml` count real stagings instead of award
   *nomination* rows.
3. `/titles/<title>` joins both its tables through productions and splits them on "is there a show page
   to link to", not on an era.
4. `/societies/<id>` stops listing 2024+ productions twice, and its "Show history" table gains an awards
   column (built in the same step, Darragh's call, so nothing regressed mid-cutover) rendering through a
   macro the archive table now shares. Century Club, Golden Jubilee and "Active since" read productions.
5. `/shows/<id>` matches award records on `production_id` instead of a hand-rolled join on (society,
   decoded year, normalized title).

**Measured on the 2026-08-23 production snapshot (1,385 shows / 4,879 award records / 2,802
productions), old vs new:**
- A-Z: 287 titles summing to 4,677 "times performed" -> **303 titles summing to 2,802**. 1.67x
  overstatement gone. Jesus Christ Superstar 152->78, Fiddler 143->81, West Side Story 100->48,
  Oklahoma! 128->83, Oliver! 95->66.
- 16 titles gain an A-Z row and a sitemap entry; **0 titles disappear**; 26 counts go up, none by more
  than 2 (all `source='historical'` skeleton rows with no award record, which neither branch of the old
  union counted - the same shape as the 371 productions /stats was missing).
- 190 productions were being listed twice on society pages (195 (year, show, society) combinations).
- `/stats` **unchanged**: 2,709 productions on record, 1,090 reviewed, 101 seasons, digest
  `d16f999adc8426e1...`. Stage 3 touches no /stats query; verified rather than assumed.
- Trap #1 (unmoderated submissions leaking onto a public page): **0 such productions exist today**, so
  neither real data nor an accidental test could catch a missing filter. Guarded by tests that seed a
  pending show explicitly.
- Title-spelling collisions: 1 (`Ghost the Musical` / `Ghost: The Musical`, genuinely one show, one
  production). 0 `show_links`/`show_info` rows affected, so no Wikipedia link reverts.
- `reviews_index()` overlap (§8.5) and undecodable `shows.season` values: both 0.

**Where the plan was wrong, and the code/data won.** §1 said 16 titles "have no page at all" today.
Only **one** does - `Fame: The Musical` (25/26, Leixlip, award records only, 2026). The other 15 already
rendered fine: `title_detail()` matched `shows` with no `source` filter, so a `source='historical'`
skeleton row gave them a working page. What they were actually missing was an A-Z row and a sitemap
entry, because `titles_list()` excluded `source='historical'` from its shows branch. Same fix, same 16
titles gained - but only one page was ever a 404. Checked the reverse too: 0 titles that rendered before
would 404 now.

**Two visible display changes to expect**, both fixes, both noticeable: "Last performed" on the A-Z is
now `season_start_year` for every era (archive-derived values read one lower, 2014 -> 2013), and "Active
since" on a society page is the first year on record rather than the year of their first *win* - it
moves earlier on 82 society pages and appears for the first time on 35 more. No page loses it. A third,
smaller one: "AIMS debut" on a title page is a four-digit year for every era rather than "23/24 season".

**One existing test changed**, deliberately: `test_trophy_case.py::test_trophy_case_counts` asserted
`Active since 2021` on a fixture whose earliest record is a 2017 nomination - it was pinning the
first-win bug §4.3 exists to fix. Its award rows now carry a `show` (so they name productions at all)
and it asserts 2017.

**Stage 4: decided, not built.** Keep `productions` derived. Recorded in `schema.sql`'s productions
comment and `docs/data-model.md` with the reasoning and the four trigger conditions that would reopen
it, so a future session doesn't re-litigate from scratch. The cheap fix for the natural key's weakest
point - the ~71 unmatched historical society names - is already an open ROADMAP item and is strictly
better value than a merge UI.

(The 7 near-duplicate titles the A-Z gained are real `/admin/duplicate-titles` work, carried forward
into the live ROADMAP.md rather than folded into this cutover.)

## Venues given a real record (2026-08-22) through capacity-research still open (2026-08-23)

Separate workstream from the productions migration but built on the same pattern. venues +
venue_aliases + shows.venue_id; app/venues_build.py rebuilds on start and lazily. 177 free-text
spellings -> 166 venue records at launch. Identity is normalize_venue() and nothing looser - a rule
loose enough to merge "Civic Theatre Tallaght"/"Civic Theatre, Tallaght" also merges the Galway,
Ballinasloe and Claremorris Town Hall Theatres, checked against real data. Region seeds from the
productions staged there (158 of 177 resolved outright); town parses from a comma suffix (67 of 177).
- Darragh's scoping call: structure + location now, spec fields drip-fed. Fields built: capacity,
  auditorium type, lat/long, website, tech-spec link. Deliberately not built: orchestra pit, fly tower,
  box-office phone.
- Merge queue worked 2026-08-23: 28 unique suggested pairs triaged (15 confident + 4 more that
  merge_candidates() itself never surfaces). 15 merges applied directly to prod (161 venues -> 146). 8
  pairs left genuinely distinct (the "Town Hall Theatre" cluster still conflates Galway/
  Ballinasloe/Claremorris - real, not a bug) and 5 left unsure.
- Waterford Musical Society's bad default_venue fixed 2026-08-23 - Darragh spotted Gorey Little Theatre
  showing wrong productions; root cause was societies.default_venue (id 125) wrongly set to 'Gorey
  Little Theatre', feeding 10 bulk-created historical show rows. Cleared, plus one unrelated single-row
  case. Swept every other society's default_venue for the same bug pattern; found no other instances.
- Mockup built and approved 2026-08-23: https://claude.ai/code/artifact/cbe72116-066d-4594-96a8-94a99b2500fd
  - a fully-enriched venue page and a title's circuit-intelligence panel.
- Show circuit intelligence: BUILT AND SHIPPED 2026-08-23 (app/circuit_intelligence.py, public.py's
  title_detail(), title_detail.html) - award tally, Best Overall Show wins, signature category (folded
  through AWARD_CATEGORIES' renamed-category groups), regional distribution across all 6 regions, and a
  per-title revival flag (>=8 productions, 10-30 year gap, checked against the real archive). Deviation
  from the mockup: the revival aside runs against the page's own title, not a different illustrative
  one. Caught via an actual screenshot during the build: the panel was originally placed after the
  detail tables per the plan's literal instruction, burying it below 50+ rows on a long-running title
  like JCS - moved before those tables. No new CSS. 15 new tests, full suite 506 green.
- Old /venues/<raw name> URLs 301 to the slug.

(Capacity/type/website/map research - 0 of 146 venues have any of it filled in - carried forward into
the live ROADMAP.md as a genuinely open item, since it's real-world research, not a coding task.)

## Decades Time Machine, Reviews, and Venues (thin version) - all live for real, 2026-08-21

Committed, pushed, deployed, and independently verified running in production.

Decades Time Machine (/stats/trends) - grounded in the awards archive (historical_results,
1912-2026), not the thinner shows catalogue. A decade-scrubber pill row (GET ?decade=1980, no JS) picks
one decade; its era card shows top 5 most-staged shows, top 5 most-nominated societies, and every Best
Overall Show winner that decade. 10 tests.

Reviews (public /reviews + admin /admin/reviews-queue) - merges two eras into one list (AIMS's own
aims.ie link-out reviews and the extracted ShowTimes archive full text). A show/society search matches
across every season and tier by default. Adjudicator credit is direct for a full-text review, inferred
via adjudicator_assignments for a link-out one (only when exactly one adjudicator covered that
season/tier). 14 + 12 tests. Full suite 392 tests, all green.

Venues fixed twice post-launch, 2026-08-21 - Darragh caught both from the real deployed page within
minutes: linked from the mobile-only /more page only, no desktop path; index sorted alphabetically,
putting free-text noise at the top - now sorts by production count. 2 new tests, full suite 406 green.

Venues (thin version, since superseded by the real venues table above) - deliberately the thin version
per Darragh's explicit call: no capacity/type/map fields. Computed everything live from shows.venue. 12
tests. Full suite 404 tests, all green.

## Header nav restructured (2026-08-23) through mobile-bug-fixed - shipped, deployed, confirmed live

Mockup-first (interactive drag-and-drop builder,
https://claude.ai/code/artifact/7a1c3f2c-f360-4ba2-a674-d9b79f79e9a9 - Darragh arranged it himself).
Final shape, his call: Home as a direct link, then Explore (All Shows, Seasons, Societies, Venues,
Reviews, Adjudicators) and History (Awards, Decades, Statistics). "Shows A-Z" renamed "All Shows".
- Native <details>, no JS needed for the menus themselves. Venues and Adjudicators are in the header for
  the first time - they were footer-only (6 and 52 views).
- "Upcoming shows" is gone as a nav item: / is that page and the logo already links there.
- Traffic can't be used to justify nav decisions - Darragh's catch: pages get views because they're in
  the nav, so citing those numbers to decide what belongs in the nav is circular.
- Polish pass 2026-08-23: Darragh called it "a bit sketchy" - mismatched button styles and flat spacing
  in the account cluster. Split into .nav-content/.nav-account with a wider gap between them and one
  shared .nav-pill shape for every account control.
- Mobile nav bug fixed 2026-08-23 (82617ae) - see the UX-audit section above for full detail; Darragh
  caught it live on his phone.

(The deferred type/palette pass and per-page component pass, both waiting on posters, carried forward
into the live ROADMAP.md.)

## Technical debt items resolved 2026-08-23

1. app/blueprints/admin.py (3,325 lines) split into app/blueprints/admin/, a package by concern. Pure
   structural move, no endpoint names or route logic changed. Full suite green (491).
2. Test suite parallelized. Took ~2m15s for 491 tests serially, no individual test slow - just per-test
   fixture overhead. pytest-xdist + addopts = -n auto cuts it to ~40s.

## Older shipped items (through 2026-08-20/21), fully resolved

- Season calendar UX feedback - SHIPPED 2026-08-20. <details> disclosure, grouped Future/Current/Past
  season dropdown, past-season copy switched to past tense.
- Reviews page, both public-facing and admin-side - SHIPPED 2026-08-21.
- Society misattribution follow-ups (from the 43-fix session, 2026-08-20) - 6 of 8 remaining cases
  resolved and applied live 2026-08-20. 2 explicitly skipped as Darragh's call (review 367 The Real
  Theatre Company, review 366 National Youth Musical Theatre) - parked, not pursued further.
- Search - RESOLVED, verified 2026-08-21. All five bugs diagnosed 2026-08-19 confirmed fixed against
  real data.
- Skeleton-show fill-in and double-count check - SHIPPED 2026-08-20.
- Society milestone badges - SHIPPED 2026-08-20. 7 live badges in _society_badges(), rendered on
  /societies/<id>. Gilbert Grandmaster parked, not built.
- Review-author byline - SHIPPED 2026-08-23 (commit 87ab288). New `review_author TEXT` column on
  `shows`, added via `COLUMN_MIGRATIONS` in `app/db.py`. Editable on the admin edit-show form and on
  the reviews-queue's quick paste-and-save form (`save_review_link()`); backfillable onto a review
  that's already published, not forward-only. On the public show page, an explicit `review_author`
  takes precedence over the existing inferred credit (matched via `adjudicator_assignments`, only
  shown when exactly one adjudicator covered that season/tier); falls back to the inferred credit,
  then to no byline at all, if neither is set. 9 new tests in `tests/test_review_author_byline.py`,
  full suite 541 passed.
- Junk skeleton-show-title fresh sweep - DONE 2026-08-23, against a fresh prod snapshot (784
  `source='historical'` shows with an approved linked review checked, same methodology as the original
  8-title fix). Title-not-in-own-review-text check re-run (154 misses, all confirmed false positives on
  manual review - real titles just not quoted verbatim in the prose, no lowercase-start or
  sentence-fragment shapes found). Went further than the original sweep and also checked for the
  *sibling* bug (same review extracted 2-3 times with progressively more of its opening line missing,
  same root cause as the Addams Family fix) via `SequenceMatcher` over same-`source_issue` review pairs
  - found 2 more instances, both fixed directly on production via SSH (data, not code, so not in git):
  show 1963 "Sweet" deleted as a truncated duplicate of show 1904 "Sweet Charity" (Muse Productions,
  22/23, reviews 936 kept vs 998 deleted, texts identical from "Charity was energetic..." onward,
  936 has the 6 extra leading chars "Sweet "); show 1925 "which" (Coolmine Musical Society, 19/20)
  retitled to "Made in Dagenham" - confirmed via its own review text ("...Christmas offerings. Made
  in Dagenham was succinctly directed by Sharon") - and its truncated duplicate show 1961 (same
  society/season/section, already correctly titled but missing the review's opening ~40 characters)
  deleted, review 1000 deleted with it. Verified no other table has an FK into `shows.id` besides
  `historical_reviews.show_id` (`historical_results`/`productions` link via `production_id`/derived
  keys, not `shows.id`) before deleting. Confirmed live post-fix: `/shows/1925` renders "Made in
  Dagenham", `/shows/1961` and `/shows/1963` both 404. 1387 -> 1385 shows, 878 -> 876 historical_reviews.

## Morning queue, 2026-08-24 (queue items 1-7, 9-10) - shipped, deployed, verified live

Full plan and reasoning: https://claude.ai/code/artifact/c85710e6-d535-46d1-8041-5e4bad7c5115

Items 1-3, 5-6: the Fame/Fame: The Musical bug (Leixlip's six award nominations now show on its
own page), Annie/Shrek/Elf title merges, and 11 published-no-link reviews cleared back to "None".
Item 4 (default_venue backfill): landed 3 of the targeted 5-10 via
`backfill_default_venues_round2.py` - 68 of the remaining 71 societies genuinely didn't have
enough venue history on record to back a confident call, deliberately not forced further.

Item 7, the 14 "Cancelled" shows: not a "some are wrong, flag which ones" cleanup - Darragh's call
was that the field itself isn't reliably used, so the flag was cleared everywhere (local +
production) rather than corrected row by row. Root cause found: `import_csv.py` read a `status`
column straight from the source spreadsheet and upserted it unconditionally on every import, with
none of `review_status`'s protection - so a routine re-import would have silently resurrected wrong
Cancelled flags. The feature (schema column, admin/society checkboxes, tag rendering, the CSV read
path) was removed entirely, not just the data cleared, so it can't recur.

Queue items 9-10: the society page links every venue in its show history and highlights the next
announced show; the show page shows venue capacity/town, an "About the society" blurb with social
links, and a one-line circuit summary; the homepage got a "Near me" toggle (browser geolocation,
distance-sorted, honest about the ~third of venues with a map pin so far). The week-by-week season
calendar moved off `/season` onto its own page, `/season/calendar`.

Left unmerged, no confident call either way: Peter Pan and Sugar/Some Like It Hot title pairs.

## UI-polish plan, all four phases - shipped, deployed, verified live (2026-08-24)

Plan: `hello-1-are-sunny-hippo.md` (Fable's read on "the site feels dated"), executed phase by
phase, mockup-first throughout.

- **Phase 0**: spacing/radius tokenised (`--space-*`/`--radius-*` in `style.css`); five
  near-identical card components (venue/resident/adj/lb/stat) and three "hero" gradient cards
  consolidated; ~11 duplicate `border-radius: 999px` pill declarations folded in. Every
  substitution is value-identical to what it replaced - zero rendered-output change.
- **Phase 1**: `/societies` rebuilt as a card grid (logo if maintained, initial-letter placeholder
  if not); `/titles` rebuilt as the Shows A-Z mockup (staples strip, three quick filters, sticky
  letter scrubber, per-title cards - sort dropdown and pagination replaced by the scrubber);
  Section (Gilbert/Sullivan) shows a coloured dot via a shared `_tier.html` macro everywhere it
  used to be plain text. The society head-to-head compare mockup was reviewed and **rejected, not
  built** - Darragh's call, a direct comparison tool doesn't fit an amateur organisation's spirit.
- **Phase 2** (`e530513`): a global `prefers-reduced-motion` kill-switch, then 150ms hover
  transitions on every card/pill. A new `_icons.html` macro set (map-pin/ticket/calendar/
  external-link) wired into six real spots.
- **Phase 3** (`643fdb6`, extended `76ec711`): Fraunces self-hosted under `app/static/fonts/` (the
  CSP blocks Google Fonts), applied to the homepage's `<h1>` at first, then every public page's
  h1/h2s. Dark-mode accent token fixed (`#d45e81`, same ~340° hue as light mode, less pale than the
  old `#f0a8c0` - a 34%→80% lightness swing was the actual problem, not the hue).

A fresh live-site walkthrough followed, after Darragh redeployed these four phases. Two Artifacts:
**Second Act** (`https://claude.ai/code/artifact/9cb573f0-ed17-4301-a4b7-36912c14893b`) - real
findings from screenshots of the live site plus a template-level read of the admin dashboard, and
the week-ahead punch list that became the Second Act backlog below; **Two More Looks**
(`https://claude.ai/code/artifact/d818bc2c-d7f7-4834-a75c-de0e2b6c97c4`) - two alternate visual
directions (Marquee: dark/bold/poster-lettering; Rehearsal Room: warm paper/minimal/editorial,
Darragh's favourite of the two) mocked up against the real homepage listings, not built - kept as
reference only, for if a fuller redesign experiment is ever greenlit.

## Second Act backlog - all 8 items shipped, deployed, verified live (2026-08-24, one session)

Ordered backlog from the Second Act walkthrough above, picked up fresh after a `/clear`. Darragh's
steer on model routing followed throughout: Fable for planning/mockups/vision, Sonnet-shaped
implementation done directly by Fable where the mockup context was already loaded rather than
handed to a fresh Agent call. Every visual item got a mockup first, approved before real templates
changed - two exceptions (items 7 and 8) explicitly skipped the mockup gate because they weren't
visual-design decisions (item 7 was a measurement that led to a backend fix; item 8 was a small,
unambiguous extension of an existing pattern).

1. **Apply the researched venue fixes** (`e49582c`). 49 of the 53 bare-placeholder venues
   corrected (71 (placeholder, society) pairs, 73 show rows) - see `apply_venue_research.py`
   (kept in the repo, safe to re-run) for the full mapping. `enrich_venues.py` re-run immediately
   after (28 of 118 venues gained a capacity, 43 a map pin). Deliberately left open, still need a
   human decision: `Mandela Hall, Belfast` (applied for Queen's Musical Theatre Society) is the
   building already flagged as closed/demolished 2018-2020; Enniscorthy Musical Society and UCC
   Musical Theatre Society need per-show research since their only answer was a slash-joined "two
   buildings" name; `"Cork run"` (venue id 120) and `"40th Anniversary (March run)"` (id 130) are
   malformed data-entry artifacts needing a source-level fix, never in scope for a venue
   correction.
2. **Homepage poster placeholder** (`74f8b28`). Mockup
   (`https://claude.ai/code/artifact/f6f1281e-228b-4566-8485-a724671bba19`) approved by Darragh,
   who asked for the show's initials rather than a single letter. The `upcoming_entry` macro in
   `index.html` (shared by the month list, "Near me", and "Closest first") renders a
   `.whatson-poster.is-placeholder` box - same 54px/2:3 footprint, border and shadow as a real
   poster - via a new `initials` filter (`app/filters.py`, skips small connecting words: "The
   Hired Man" -> "HM"; single-word titles fall back to their own first two letters: "Oklahoma!" ->
   "OK"). Verified with a Playwright screenshot against real upcoming-show data - October's run of
   bare listings now reads the same as August's.
3. **Two-column show/society detail layout at desktop widths** (`e8b03cb`). Mockup
   (`https://claude.ai/code/artifact/82fca774-ad46-466e-a3ca-f1d69282d72b`) approved as-is. A new
   `.detail-hero` grid (260px poster / flex facts column, 160px for a society's square logo via
   `.society-hero`) wraps the poster/logo image and the facts that used to sit in their own
   stacked block below it. Collapses to one column below 700px, same as it already looked on
   mobile. A show/society with no image gets item 2's initials placeholder in the slot rather than
   falling back to one column - the `initials` filter was renamed from `show_initials` to cover
   both uses. 622 tests green (4 new). Verified with local screenshots (poster, placeholder,
   mobile stack) using real dummy image files, since the real uploads aren't reachable locally.
4. **Reviews page card pass** (`fa1427d`). Mockup
   (`https://claude.ai/code/artifact/ae0e41f3-4d0e-4b33-97bc-5628bc13d061`) approved as-is. Same
   treatment `/societies` already got - `.review-row`/`.review-list` renamed and restyled as
   `.review-card`/`.review-grid`, source tag moved to the card's top-right corner, accent-tinted
   only for "Full review". `reviews_index.html` and `adjudicator_detail.html` already shared the
   same CSS classes, so an adjudicator's own review list picked up the card treatment
   automatically, confirmed live with a screenshot. "Read on aims.ie" shortened to "aims.ie" to
   fit the card corner - a deliberate copy change, one test updated to match. 625 tests green (4
   new). The grid collapses to one column at narrow viewports on its own
   (`repeat(auto-fit, minmax(230px, 1fr))`), no separate breakpoint needed.
5. **Awards page polish without touching the table shape** (`dd9ea87`). Mockup
   (`https://claude.ai/code/artifact/e6e73546-a103-47a4-a51c-204adf3a2a3d`) approved as-is,
   including one deviation flagged during review: a fifth chip for the search box (`q`), not just
   the four dropdowns the backlog wording named. A Winner row gets
   `color-mix(in srgb, var(--gold) 14%, transparent)` regardless of the zebra stripe, plus a 🏆 tag
   replacing the plain "Winner" text. Filter chips are plain links, no JS - each is `request.args`
   with just that filter's key popped, built in the template, so "Year: 2025 ×" drops only the
   year and keeps every other active filter. Table stays a table on purpose (4,878 rows). 629
   tests green (5 new).
6. **Mobile "back to top"** on the three longest list pages (`af9fe14`). Mockup
   (`https://claude.ai/code/artifact/a19df731-94f8-4917-a74b-13fcbffa1458`, live-interactive
   rather than a static image) approved as-is. A new shared `_back_to_top.html` partial, imported
   into `societies_list.html`, `titles_list.html` and `reviews_index.html` - each `<h1>` carries
   `id="page-top"`, the button is a real `<a href="#page-top">`, always visible and functional
   with zero JavaScript (same principle the header's `<details>` nav menus already use).
   `base.html`'s one new scroll listener only fades it out near the top and (via
   `scroll-behavior: smooth`, reduced-motion-guarded) smooths the jump. 633 tests green (4 new). A
   debugging detour along the way found several stale `flask run` dev-server processes left
   running from earlier the same session on other ports, serving Jinja-cached templates from
   before the change (`auto_reload` is off without `--debug`) - worth remembering next time a
   local check shows unexpectedly stale output: check for leftover background processes before
   suspecting the code.
7. **Measure the Shows A-Z page weight before deciding whether to change it** (`4fe3084`) -
   resolved differently than the item's own framing expected. The "~30,000px / 2.3MB" figure that
   motivated it was never actually measured. Real numbers (Playwright + CDP network throttling,
   mobile viewport): `/titles` is 48,383px tall but only 385.9KB across 3 requests (HTML/CSS/font,
   no images). Fine on "Fast 3G" (2.2s interactive), but 8.3s on a genuine "Slow 3G" profile
   (400Kbps/400ms RTT, Lighthouse's own preset) - worth caring about for an Ireland-wide amateur-
   theatre audience that includes rural connections. Traced to the real cause: nothing in the
   stack compresses a response, not waitress, no reverse proxy. Added `Flask-Compress`
   (auto-negotiates gzip/brotli/zstd) rather than the three options the item posed (leave it,
   lazy-load, paginate) - none of those would have fixed a compression gap. Confirmed under both
   `flask run` and waitress. Re-measured: 79.0KB over the wire (4.9x smaller), Slow-3G interactive
   time down to 3.3s (61% faster). Site-wide fix, not just `/titles` - the lazy-load/paginate
   question doesn't need revisiting unless a future measurement still shows a problem. 636 tests
   green (3 new).
8. **Admin dashboard: extend the on/off urgency dot** from 2 of ~12 rows to all of them, split out
   the rows that explicitly "won't reach 0" into their own group (`3bdeab9`) - the eighth and last
   item, completing the backlog. No mockup needed (small, unambiguous extension of an existing
   pattern) - built directly, verified with a real admin-login screenshot against live local data
   (throwaway login created and deleted after). Every row in "Awaiting your review," "Missing
   data" and "Possible errors to check" now carries the same `.admin-dot-on`/`.admin-dot-off`
   marker the first two rows already had (11 rows total). "Award records with no society match" -
   already documented in its own hint text as structurally permanent, mostly genuinely defunct
   societies - moved into a new, deliberately dot-less "Won't reach zero" group: a permanent amber
   dot there would be a standing false alarm, the same shape "Active societies missing a default
   venue" had before being fixed earlier the same session. 639 tests green (3 new; 2 existing
   tests fixed for a real bug the dot rollout exposed - a `<td>Label</td>` regex assumed a label
   only ever appears once, which breaks when that row also gets featured in the "quick win"
   banner, since the label text then appears twice on the page).

**Bonus fix, same session, not part of the ordered list:** "Active societies missing a default
venue" (admin dashboard count + `/admin/venues`) used to count every active society with no
`default_venue`, including ones with zero shows recording a venue at all - nothing a moderator
could act on. Darragh flagged it as counterproductive to mix those in. Both the dashboard count
and `/admin/venues` now only count/list societies with at least one show of their own recording a
venue; the rest sit in a separate, collapsed "no venue history on record yet" section, still
fillable but out of the main list and out of the count.

**Verified deployed 2026-08-24, same day**, by checking the live site directly rather than
assuming a push means a deploy: `whatson-poster is-placeholder` renders on the homepage,
`.detail-hero`/`.society-hero`/`.review-card`/`.filter-chip`/`.back-to-top`/`.admin-row-label` all
present in the live `style.css`, `/reviews` paginates ("Page 1 of 12"), `/titles` responses come
back `Content-Encoding: gzip` through Cloudflare, and a real admin-login check showed all 11
urgency dots plus the "Won't reach zero" group (540 unmatched award records) rendering correctly
against live production data (540 checked, not guessed). The DEPLOY QUEUE section that used to sit
at the top of `ROADMAP.md` - `enrich_venues.py`/`backfill_default_venues.py` run against
production, the homepage "What's on" rebuild, `/reviews` pagination, the historical-society "No
region" option, venue map directions - is also confirmed live the same way: Town Hall Theatre,
Galway reads 21 productions with a 400-seat capacity and a "Get directions" link, 124 of 143
active societies now carry a `default_venue` (up from 39/194 before this backlog started).

**Follow-up, same night: `/season` page weight measured, no further work needed.** The roadmap's
next open item asked whether `/season` needed anything beyond the compression fix above (item 7),
since it was flagged in the same 2026-08-23 UX audit as `/reviews` (123KB, no pagination) but only
`/reviews` got a fix that session. Measured the same way as `/titles` (Playwright + CDP network
throttling, mobile viewport, local dev server): `/season` is 16,276px tall, 66.7KB over the wire
(compression already covers it site-wide, same as every other route), 2.7s interactive on a
genuine Slow 3G profile - in the same range as `/titles`'s own post-fix numbers (79KB, 3.3s).
Closed without a code change; removed from `ROADMAP.md`'s open-items list.

## Google Maps integration proposal - sections 1-2 adopted, verified live; section 3 still open

Gemini-generated, three sections, assessed 2026-08-24. Section 1 (Google Maps directions) shipped
earliest. Section 2 (`default_venue` for 140 societies) cross-checked against this repo's own
archive first - 90 of 112 judgeable claims agreed (80%), and most of the 22 disagreements turned
out to be this repo's own data being wrong (bare county names like "Roscommon" instead of a real
venue) rather than the proposal. Applied via `backfill_default_venues.py` +
`backfill_default_venues_round2.py` (own-data cross-check for the names Gemini had nothing to say
about) - active-society `default_venue` coverage went from 39/194 to 124/143 (86.7%), with the
remaining gap split into "genuinely has venue history to act on" (tracked live on `/admin/venues`)
and "no data on record at all yet" (its own collapsed section there, out of the actionable count).

**Section 3, the 109-venue `DATA` dict, is still open** - the venue list itself is valuable (54 of
109 named venues have no record here at all - Barbican Drogheda, Hawk's Well, Lime Tree, Everyman,
Millennium Forum, An Grianán...), but the coordinates need verifying before they go in: of the 83
new (non-duplicate) ones, 76 are rounded to ≤4 decimal places on both axes (against 1 of 28 in the
OSM/Wikipedia-sourced set already in the database), and spot-checks found real drift (the
proposal's "The Abbey Clane" is 170m from Clane's actual town centre, "Temperance Hall, Loughrea"
85m off). The adoption path is mechanical, not manual: geocode each proposed venue against OSM,
accept where the two agree within a couple of hundred metres, flag where they don't - and drop the
proposal's `region` key, since `venues.region` is derived from staged productions and moderator-
corrected, not a field to set from an external list.

## Working agreements (from the 2026-08-03 process review)
- `/clear` (or a fresh session) between genuinely distinct workstreams -
  don't chain unrelated incidents/features/audits in one long thread.
- Mockup-first for anything visual - already working well, keep doing it.
- For a sweep touching many files (like Phase 0's audit), write the plan
  and get sign-off before editing, rather than fixing things as found.
- Lessons that matter beyond one session go in `docs/`, not just chat -
  already the habit for this repo, keep it up.
