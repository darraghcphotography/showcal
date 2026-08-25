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

## START HERE - where things stand (2026-08-25, end of session)

**Everything is built, deployed, verified live and committed. 718 tests green, no known bugs.** The
ready-to-build backlog was closed out on 2026-08-24; the 2026-08-25 session then **interrogated the
remaining backlog** rather than building (no code changed - the only edit was this file). There is no
half-finished work to pick up: the next session starts from a clean base and picks from the numbered
live backlog below.

**Two jobs are genuinely ready to start**, and they're different in kind - pick by appetite:
the archive transcription immediately below (data work, well-understood, high certainty of value),
or item 1 of the interrogated backlog (internal-only person identity resolution - the item with
measured harm that grows while untouched).

One security gap worth knowing about before either: **unvalidated photo-submission uploads** (see
"Next feasible things") - small fix, one function.

Production data as of now:

| | |
|---|---|
| Societies | 194 (6 with a founding year) |
| Venues | 118 (113 typed, 72 with box office contact) |
| Show titles with info | 300 (all 300 now credit composer/lyricist/book/licensing house) |
| historical_results rows | 4,999 |
| Award rows with no society match | 539 across 69 distinct names, 0 decisions made yet |
| Photo submissions pending | 0 |
| FAQ entries | 0 published, 0 draft |

### The single best next technical job

**Transcribe the 9 society production archives that are demonstrably reachable.** Antigravity
returned 14 of 19 as "archive page unreachable" - checked directly on 2026-08-25 and **9 of those 14
load fine**, with substantial year data in the page:

| Society | Page | We hold |
|---|---|---|
| Waterford Musical Society | 292KB, 40 distinct years | 9 productions |
| Fortwilliam Musical Society | 84KB, 38 years | 24 |
| Muse Productions | 185KB, 20 years | 5 |
| Boyle Musical Society | 292KB, 17 years | 8 |
| Kilmacud Musical Society | 99KB, 15 years | **2** |
| Castlebar Musical & Dramatic Society | 292KB, 10 years | 5 |
| Harolds Cross Tallaght Musical Society | 292KB, 9 years | 22 |
| Killarney Musical Society | 175KB, 7 years | 13 |
| Glencullen Dundrum MDS | 19KB, 6 years | 15 |

Do this **in-house with WebFetch**, not by delegating - it's transcription from a named page, and the
tooling to validate it already exists: `import_society_archives.py` has the `TRUSTED` list, the
SHOW_RENAMES canonicalisation and the +/-1 year duplicate guard, and the worklist carries
`known_productions_for_cross_check` so the overlap test runs the same way. Genuinely unreachable on
the same check: Ballywillan (timeout - retry, it may be transient and it is the biggest prize at
1952-2025), Ennis, Dun Laoghaire, Kilcock (DNS), Pop-Up Theatre Sligo (domain gone).

### Waiting on Darragh, nothing Claude can do

- **FAQ content.** `/admin/faq` is built and live (add / edit / reorder / draft / publish). It has
  zero entries. Needs his voice, not invented AIMS policy.
- **`/admin/historical-society-links`.** 69 printed names awaiting a decision. Deployed and unused.
  Expect ~9 to have any suggestion and most to be "no current society", which is bulk-selectable -
  probably 10 minutes of clicking. Worth him doing before the next awards re-import.
- **Posters.** Still 41 against ~200 current-era shows. Gates any poster-led design work.

### The delegation finding - read before handing Antigravity anything again

Standing rules live in `enrichment/RULES.md` (gitignored, sent 2026-08-25). Three rounds of evidence
now, and the pattern is consistent:

**What works:** transcription from a page we name, where verification does not depend on the worker
being truthful. The archives task succeeded *because* each row carried our own existing records as a
built-in overlap check - Baldoyle scored 96%, Limerick 93%, Oyster Lane matched "All 4 One" (2008),
an obscure original nobody guesses. Carnew scored **0% across 16 overlapping years** and was rejected
on the spot. The check did its job with no human reading required.

**What fails:** anything where a *citation* must be produced. The founding-years re-run followed every
behavioural rule (109 of 143 blank, zero bound violations, no Facebook sourcing) and still fabricated
its evidence wholesale - **19 of 34 cited domains do not resolve, 8 more 404, and 0 of 34 quotes
appear on the page cited**. One quote was attributed to a page about a different organisation's choir.
The years were probably mostly right; they were accurate recall wearing invented citations.

**A third failure mode appeared this round:** falsely reporting a page as unreachable. Because a blank
is the "safe" answer under the rules, it became the lazy default - hence the 9 reachable archives
above sitting unread.

**Rule of thumb:** delegate transcription with a built-in cross-check against data we already hold.
Do citation-dependent work in-house. Never accept a `source_url` without opening it.

### The backlog interrogation - DONE 2026-08-25

The planned interrogation of the UX-audit slivers and the Parked list **was carried out** (see "The
backlog interrogation" section below for the full verdicts and reasoning). Darragh's rule for it:
"no one has asked for this" was **not** enough on its own to close an item - each was argued on
merit. 22 items in, 9 kept, 13 closed. The live backlog is now that section's numbered list of 9,
in priority order, headed by internal-only person identity resolution.

Two things came out of it that outlast the individual verdicts:

- **The binding constraint is society-supplied content, not engineering time** (41 posters against
  ~200 current-era shows, after months). A third of the backlog was blocked behind that same
  assumption. Judge new feature ideas by whether they move that number rather than depend on it.
- **Rejected ideas were being laundered back in** via new audit docs - the watchlist / map /
  "On This Day" / embeddable-JSON group was ruled skip on 2026-08-20 and re-entered as "genuinely
  new, unclaimed" on 2026-08-24. **Diff any future audit doc against prior rulings before entering
  its suggestions here.**

### The untracked root proposal docs - all now checked

Three large untracked `.md` proposals sit in the repo root. Two are confirmed superseded and are
**safe to delete whenever Darragh wants** - both verdicts are recorded here, so nothing is lost:

- `DESIGN_AUDIT_AND_PROPOSALS.md` (158 lines) - superseded, see the interrogation section below.
- `GOOGLE_MAPS_INTEGRATION_PROPOSAL.md` (828 lines) - **already implemented; its premise is wrong.**
  It argues the site uses OpenStreetMap links and should switch to keyless Google Maps universal
  URLs. The site already does exactly that (`maps_directions_url` / `maps_search_url`), already
  hands off to the native GPS app on mobile, and `venue_detail.html:37-46` documents the same
  reasoning the proposal makes the case for. Nothing to build.
- `VENUE_CATEGORIZATION_PROPOSAL.md` (226 lines) and
  `DATA_ENRICHMENT_AND_SCRAPING_OPPORTUNITIES.md` (140 lines) - **not yet checked.** Venue typing
  (113 of 118 typed) and the enrichment work both shipped, so expect the same superseded verdict,
  but that hasn't been verified line by line.

## Next feasible things, roughly in order

- **Transcribe the 9 reachable society production archives** - the single best-value job. See
  START HERE for the list, the evidence they're reachable, and why to do it in-house.

- **Merge the duplicate venue rows.** Five clusters, all via `/admin/venue-directory`, no research
  needed: `Scout's Hall, Nenagh` / `Scouts' Hall, Nenagh`; `Tullyvin Community Centre` /
  `Tullyvin Community Centre, Cavan`; `Siamsa Tire, Tralee` / `Siamsa Tire Theatre, Tralee`;
  `Island Arts Centre, Lisburn` / `Island Arts Centre (Lagan Valley Island), Lisburn`; and a
  four-way DCU St Patrick's cluster (`St. Pat's DCU` 3 shows, `St. Patricks College DCU` 8,
  `DCU St Patrick's College, Drumcondra` 1, `DCU St. Patrick's Campus Auditorium / The Helix` 1).

- **Image-content validation on uploads - half already done, and now pinned to one function.**
  Checked properly 2026-08-25: **posters are already validated.** `save_poster()` routes through
  `_resized_webp_bytes()`, which decodes with Pillow, resizes and re-encodes as WebP - a file whose
  extension lies cannot survive that, and it already raises "That file doesn't look like a valid
  image". The gap is **`save_photo_submission()` only**: it calls `_viewable_bytes()`
  (`app/uploads.py:63`), which for any non-HEIC extension does a bare `fileobj.read()` and writes the
  bytes straight to disk **with no decode at all**. So a `.jpg` that is really HTML, an SVG or an
  archive is stored unexamined and later served into the admin queue for a moderator to open. Fix is
  a few lines in that one passthrough branch (decode to verify, rewind, then pass through unchanged -
  keeping the deliberate no-resize behaviour that branch exists for).

- **The 4 place-name artifacts still need a source-level fix** - `Cork`, `Wexford`, `Cork run`,
  `40th Anniversary (March run)` are `shows.venue` text that names no building. They're excluded
  from every venue worklist and deliberately never classified, but the underlying show rows still
  carry them.

- **3 venues with no map pin: St. Mary's College Arklow, The Abbey Clane, Loughrea Temperance Hall.**
  All confirmed real; OpenStreetMap simply has no entry findable by name, and Eircodes don't help
  (Nominatim doesn't index them and fuzzy-matches to unrelated addresses). Needs a different source,
  not another search.

- **Society founding years beyond the 6 confirmed.** The column, admin field and public display all
  shipped; 6 of 194 are set, each verified against a real source. A crude scrape of the 74 societies
  whose website we hold found only 4 genuine founding statements, so the remaining yield is low. The
  working method, if revisited: accept only a year a society's own site states explicitly *and* that
  doesn't contradict our earliest award record for them - that contradiction check is cheap, already
  written, and is a genuine floor (a society with a 1912 award record was founded on or before 1912).

## Data-accuracy follow-ups (from the 2026-08-23 report check), need Darragh's input or real research

- **297 `historical_results` rows with `category_name IS NULL`, 274 of them pre-2001** - needs real
  historical AIMS awards-programme research; a Gemini report only sampled 6 of them.
- **~10 unmapped historical societies with no existing `societies` row** (Bangor Operatic Society, De La
  Salle Musical Society Waterford, others) - creating new historical society records is a structural
  decision, not a data-quality bugfix.
- **28 orphaned Inactive societies with zero shows/awards** - retain or remove is a judgment call, no
  urgency signal.
- **Society production archives** - 3 imported 2026-08-25 (Baldoyle, Limerick, Oyster Lane;
  47 productions). 9 more are reachable and untranscribed - see START HERE, it's the top job.
  5 are genuinely dead (Ballywillan timed out and is worth a retry; Ennis, Dun Laoghaire and
  Kilcock fail DNS; Pop-Up Theatre Sligo's domain is gone).
- **~112 stale orphaned `historical_reviews` rows** - cross-referenced as real, but explicitly not
  deleted pending a more rigorous verification method than what was used to find them.

## The backlog interrogation (2026-08-25) - what survived and why

The UX-audit slivers and the Parked list were interrogated item by item, on Darragh's explicit rule
that **"no one has asked for this" is not on its own enough to close an item** - each got a real case
argued for and against. 22 items in, 9 out. Every "already delivered" verdict below was checked
against the actual code, not against this file's own summary of it.

**The finding that reorganises the rest:** the site's binding constraint is not engineering capacity,
it's **society-supplied content**. Posters are the live experiment - 41 against ~200 current-era shows
after months. Roughly a third of the backlog was either blocked behind that same unproven assumption
(societies will fill things in) or was an attempt to work around it. So the useful question isn't
"which feature next", it's "does anything move the content-supply number" - and exactly one backlog
item attacks it head-on rather than depending on it (the social card generator, below).

Second finding, process rather than product: **rejected ideas were being laundered back in.** The
watchlist / Leaflet map / "On This Day" / embeddable-JSON group was ruled skip on 2026-08-20 with
reasons. All four returned to Parked on 2026-08-24 labelled "genuinely new, unclaimed", because they
arrived inside a *different* audit doc. Any future audit doc gets diffed against prior rulings before
its suggestions are entered here.

### Kept - the live backlog, in priority order

1. **Person identity resolution, internal only.** The only parked item with *measured* harm rather
   than a hypothesis: 1,730 distinct award nominee names, 746 credit names, **217 credit names are
   also an award nominee by exact match alone**, and `/admin/backfill-credits` is actively adding
   more free-text names, so it grows while untouched. Darragh's privacy objection was to *public
   person pages*, which stays honoured - the agreed path is canonical names + aliases, moderator-
   reviewed, reusing `dedupe.find_candidates`, **no new public surface**. Top of the list.
2. **Social card generator** (per show: poster + society logo + opening countdown + QR). Promoted
   from a throwaway line to a real candidate because it's the one item that *gives* societies
   something instead of asking them for something - plausibly the lever that gets posters uploaded
   ("upload your poster, get a card you can post"). Pillow landed 2026-08-24 for the poster pipeline,
   so the rendering dependency already exists. Needs a mockup pass before any build.
3. **`match_show_for_edit` exact-match bug.** Verified real: `app/blueprints/admin/historical_reviews.py:650`
   matches `society_id + season + show` on an exact string. Systemic version of a title-mismatch bug
   already fixed once for a specific case. Small, contained, already bit us.
4. **Society edit audit log - scope cut to the cheap 80%.** Kept because the hole is real and
   structural, not a feature wish: societies share one login code, so there is no way to tell who
   made an edit or to undo it. Cut: build the append-only log (who/when/field/old/new), **drop the
   revert UI** - that's the expensive half, and a moderator can restore by hand from the log.
5. **Repertoire finder** (the "what show should we do next" hub) - the single survivor of *both*
   deleted audit docs, and the only feature idea either produced with a real audience: volunteer
   committees genuinely do spend months choosing a title. Builds on columns that already exist
   (amateur rights status, licensing house on `show_info`). Its "which other societies staged this
   recently" sub-idea also fits the collaborative ethos the design audit itself insisted on. Still
   needs Darragh to confirm it solves a problem a committee has actually raised to him.
6. **Society profile completion** - merges the old "empty vs. filled society page" sliver with the
   whole outreach/onboarding track, because they're one problem: a nudge on a thin profile, 2-3
   exemplar societies filled in completely as a reference, a draft message to a committee, a "claim
   your page" route. Mostly Darragh's lever, not a coding task.
7. **Poster lightbox/zoom** - kept but explicitly *not standalone*: bundle it into the next piece of
   poster work. At 41 posters it currently affects few pages.
8. **Removable filter chips - redirected.** The idea shipped on `/awards`; the roadmap kept it open
   for `/season`/`/stats`, but the page that now actually earns it is **`/reviews`**, which carries
   four filters (free-text `q`, season, tier, adjudicator). Retarget if picked up.
9. **A pantomime category** - not a build item and never was. Pantomimes were ruled out of scope
   (AIMS musical-theatre circuit specifically) with "may get their own category in the future".
   It's a scope decision about what the site *is*, and only Darragh can make it.

### Closed - already delivered (verified in code, this file was simply stale)

- **Society milestone badges.** Shipped 2026-08-20. `_society_badges()` at
  `app/blueprints/public.py:797`, 7 badges live, rendered on `/societies/<id>`. Was still listed as a
  "genuinely new, unclaimed idea".
- **Show-page cross-links to other societies staging the same show.** Already there:
  `show_detail.html:14` renders the circuit summary ("staged N times since Y, most recently by X"),
  and `show_detail.html:20` links "See every AIMS production of this show →" to `title_detail`.
  Worth knowing the scale it serves: **123 of 182 distinct titles have been staged by more than one
  society**, so this was load-bearing and it's covered.
- **`DESIGN_AUDIT_AND_PROPOSALS.md` - read in full, now closable.** Its headline complaint (10 nav
  links crammed into one wrapping row) is already solved: `base.html:80` uses grouped
  `<details class="nav-group">` dropdowns plus a mobile tab bar. Its design-system section is
  superseded by the Rehearsal Room theme (shipped site-wide 2026-08-24). Three of its four feature
  proposals are the already-ruled watchlist / map / "On This Day". Only the repertoire finder
  survived, and it's item 5 above. **The file can be deleted** - nothing in it is unrepresented.

### Closed - argued on merit and lost

- **Embeddable per-society JSON feed / widget.** Real merit: a society embedding "our upcoming shows"
  on its own site is useful and drives adoption. Against: a new unauthenticated public surface with
  no rate-limiting built for it, on a single-moderator site, for zero requests. The 2026-08-20 ruling
  survives the re-argument. **Trigger to reopen: one named society asks to embed something.**
- **Fuller interactive Leaflet/OSM pin map.** Merit: a map genuinely beats a list for 118 venues.
  Against: it would be the first JS-library dependency on a deliberately no-build-step site, and the
  existing Near-me list already answers the question a map would. **Trigger: pin coverage near
  complete AND a request.**
- **"My Season Watchlist".** Merit: the `.ics` export half is a real hook. Against: the watchlist
  wrapper is invisible to Darragh (no login means no data, no signal), evaporates when a browser is
  cleared, and duplicates bookmarks for a site people visit a few times a season. **Killed, but the
  `.ics` half is salvageable on its own** - a season/society calendar export is small and standalone.
- **"On This Day in AIMS History" widget.** Merit, and better than the earlier ruling credited: with
  4,879 `historical_results` rows it would have real content most days, which is an asset most sites
  don't have. Against: homepage real estate for a novelty, aimed at a daily-returning audience this
  site doesn't have. Killed as a homepage widget; the underlying data is better spent feeding the
  social cards (item 2).
- **Costume/prop rental listings.** Merit: societies really do lend to each other - this is genuine
  amateur-theatre behaviour, not an invented need. Against: it's the biggest lift on the whole list
  (new data model, new admin UI, a matching concept) and it lives or dies on societies maintaining
  it - the exact thing 41 posters says they don't yet do. **Blocked behind the content-supply
  finding, not on merit.** Revisit if profile completion moves.
- **Historical-posters gallery + programme-cover museum.** Two entries for one idea; merged and
  closed for now on the same content-supply argument. **Trigger: ~100 posters.**
- **Staging/test environment.** Merit: a bad change can hit the live site. Against: 718 tests already
  run against a fresh temp DB, and Portainer's git-backed stack gives a rollback path. More to the
  point, the failure mode this project has *actually* suffered is data damage (a management script
  run without `--db /data/aims.db`), which a staging environment wouldn't have caught. **Redirected:
  the off-box backup in Housekeeping is the mitigation this item was really reaching for.**
- **`/admin/duplicate-titles` UX redesign.** Asked for once, then called "not really an issue" *after*
  a real mockup existed - that's a decision, not a deferral. The mockup is in `mockups/` if wanted.
- **Reviews page: show dropdown instead of season grouping.** Closed as posed - stale framing. The
  page already has a free-text search plus season, tier and adjudicator dropdowns; season grouping is
  only the *default browse view*. The genuine remaining question is whether that default landing view
  should be grouped-by-season at all, which is a one-line change to decide by looking at the page.
- **Show-page share affordance.** No case for it beyond "sites have one" - the URL is the share
  mechanism, and OG tags for link previews are already in `base.html`.

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
- **Diff any new audit/proposal doc against prior rulings and against the actual code before
  entering its suggestions in this file** (added 2026-08-25). Three separate generated audit docs
  have now been found to re-propose things that were either already shipped or already argued down
  with reasons - milestone badges, the nav restructure, the Google Maps switch, and the whole
  watchlist/map/"On This Day" group. Filing them unchecked is how a backlog grows without anything
  actually being open.
- **When closing a backlog item, record the argument, not just the verdict** (added 2026-08-25) - and
  where a closure is conditional, write the explicit trigger that reopens it ("one named society asks
  to embed something", "~100 posters"). A bare "skip" gets re-litigated by the next doc that suggests
  it; a recorded reason plus a trigger does not.
