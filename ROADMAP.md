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

**Everything is built, deployed, verified live and committed. 718 tests green, nothing uncommitted,
nothing unpushed, no known bugs.** This session closed the last of the ready-to-build backlog. There
is no half-finished work to pick up - the next session starts from a clean base and chooses what to
do, rather than finishing something.

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

### The agreed plan for the next session

Darragh's call, 2026-08-25: **interrogate the UX-audit slivers and the Parked list properly, and plan
them methodically** - rather than picking off whichever is nearest to hand. Both lists below have sat
untouched for a while and neither has been pressure-tested: the Parked items in particular are mostly
unsolicited suggestions from deleted audit docs, with no evidence anyone wants them (`ROADMAP_ARCHIVE`
already ruled that way once on the watchlist / map / "On This Day" trio). Expect that a proper
interrogation kills several outright, which is a good outcome and worth doing explicitly rather than
leaving them to accumulate.

Worth deciding up front: whether "no one has asked for this" is enough on its own to close an item,
or whether each still gets argued on merit. That single choice determines how long the exercise takes.

## Next feasible things, roughly in order

- **Transcribe the 9 reachable society production archives** - the single best-value job. See
  START HERE for the list, the evidence they're reachable, and why to do it in-house.

- **Merge the duplicate venue rows.** Five clusters, all via `/admin/venue-directory`, no research
  needed: `Scout's Hall, Nenagh` / `Scouts' Hall, Nenagh`; `Tullyvin Community Centre` /
  `Tullyvin Community Centre, Cavan`; `Siamsa Tire, Tralee` / `Siamsa Tire Theatre, Tralee`;
  `Island Arts Centre, Lisburn` / `Island Arts Centre (Lagan Valley Island), Lisburn`; and a
  four-way DCU St Patrick's cluster (`St. Pat's DCU` 3 shows, `St. Patricks College DCU` 8,
  `DCU St Patrick's College, Drumcondra` 1, `DCU St. Patrick's Campus Auditorium / The Helix` 1).

- **Image-content validation on uploads - newly unblocked.** This sat in Housekeeping for months as
  "would need Pillow, not built". Pillow was added 2026-08-24 for the poster pipeline, so it's now a
  small job: verify an upload really is the image type its extension claims, in `app/uploads.py`
  where the resize already decodes it.

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
