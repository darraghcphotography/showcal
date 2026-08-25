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

**759 tests green, no known bugs. FOUR commits are NOT yet confirmed live - a redeploy is needed
before any of this is real for a visitor:** `3f35355` (season calendar), `87b7b3d` (titles filters),
`f3e8561` (society next-show highlight fix), `b1ddceb` (venues card redesign + map, `cdd44c4`'s
TRUSTED-list code change too, though that one's DB write already landed). Checked directly against
the running container earlier tonight for the first two - confirmed absent. Re-verify all four the
same way after the next Portainer redeploy, don't assume.

The 2026-08-25 session, in order: interrogated the backlog; built the three ready backlog items
(`f07bd11`); scored Gemini's two remaining deliverables and rejected both (see the delegation
section); fixed two real security findings - unsafe rate-limit key behind Cloudflare Tunnel, an open
redirect on the 413 handler (`2a11272`) - confirmed deployed and live; then a fresh round from
Darragh's own screenshots of the live site:
- **Season calendar** - a week with openings on only one tier no longer shows an empty "Nothing
  opening this week" placeholder for the other side (`3f35355`).
- ~~**Venues page**~~ - **DONE, built and pushed (`b1ddceb`), NOT yet confirmed deployed.** Card
  redesign (centered, pin indicator, real mapped-count line) plus a real `/venues/map` route -
  actual Leaflet map, real pinned venues, not the 9 fabricated ones the old parked prototype used.
  Needed a scoped CSP relaxation (unpkg.com + basemaps.cartocdn.com, only on that one route) to
  actually load - flagged in the commit message since it's a real security-boundary change, not a
  routine one. Along the way, fixed a genuine bug in the pre-existing (never-rendered-until-now)
  `mapped_count`: it was computed after the list was already paginated, silently undercounting.
- ~~**Society next-show highlight**~~ - **DONE, built and pushed (`f3e8561`).** The "Future
  announced show" callout was season-based, not date-based, so a show dated later in the *current*
  season (the common case) never got it. Now date-based. See its own section below for the full note.
- **Titles page** - rights-availability and licensing-house filters shipped (`87b7b3d`), extending
  the exact existing onstage/revival/gems chip pattern. Genre filtering was scoped but deliberately
  **not built** - it needs a new schema column, a taxonomy decision, and a Gemini task under the
  calibration protocol; see the delegation section.

**The redo came back and was scored (2026-08-25) - genuinely mixed, not the clean pass Gemini's own
"all tasks completed and verified" summary implied.** Two real, distinct results:

**The citation fixes are both genuine.** Leixlip now cites `lmvg.ie/about-lmvg/` with the quote
*"Established in Leixlip in 1980..."* - independently fetched and confirmed word-for-word, page
loads (no 404, unlike the invented `/about-us` last time). Baldoyle was also quietly redone (not
asked for) and landed on the answer already independently found - 1973, `/pages/history`. Both
fabrications from earlier today are now fixed with real, checkable sources.

**The archive reachability half genuinely improved - no more templated non-answer.** All 14 rows now
carry distinct, specific notes instead of one copy-pasted line: real HTTP/SSL/DNS error strings for
the 4 still genuinely dead (`SSLV3_ALERT_HANDSHAKE_FAILURE` for Ennis, `UNEXPECTED_EOF_WHILE_READING`
for Dun Laoghaire - though `www.dmds.ie` itself is reachable, worth a manual look - TLS mismatch +
DNS failure for Kilcock, plain DNS failure for Pop-Up Sligo), and real transcriptions/facts for the
other 10, including Ballywillan (no production list - the "past productions" subpage turned out to
be an image gallery, not transcribable text - but its narrative page confirms the 1952 founding and
1996 first musical (Oliver!), consistent with what this file already believed).

**But "HTTP-verified" is not the same test as "the content is right," and running the actual overlap
cross-check on the newly-transcribed data - the same check that caught Carnew - found real problems
in it:**

| Society | Overlap years | Matched | Verdict |
|---|---|---|---|
| Killarney Musical Society | 7 | 7 | **100% - clean pass** |
| Castlebar Musical & Dramatic Society | 5 | 5 | **100% - clean pass** |
| Fortwilliam Musical Society | 31 | 17 | 55% - too mixed to trust |
| Glencullen Dundrum MDS | 17 | 8 | 47% - too mixed to trust |
| Harolds Cross Tallaght Musical Society | 5 | 0 | **0% - same red flag as Carnew** |
| Muse Productions | 3 | 0 | **0% - same red flag as Carnew** (small sample) |
| Kilmacud, Boyle, Waterford | 0 | - | no overlapping years - **unverifiable by this method**, not passed |

~~**Action: add Killarney and Castlebar to TRUSTED and import them**~~ - **DONE, 2026-08-25
(`cdd44c4`).** Ran against production after a dry-run confirmed exactly 11 new rows with no
surprises (6 Killarney, 5 Castlebar); verified live afterward - all 11 present, 58 total rows now
carry this import's reason tag. Everything else stays untrusted. Kilmacud/Boyle/Waterford aren't
rejected, just unverifiable this way - would need a different check (e.g. Darragh's own knowledge
of a specific claimed production) before being trusted on faith.

**Deploy check, 2026-08-25 later that evening: two more commits confirmed NOT live.** Grepped the
running container directly (not just its restart timestamp) - `3f35355` (season calendar collapse)
and `87b7b3d` (titles rights/licensing filters) are both absent from `/app` inside the container,
and confirmed absent on the live site too (`Rights available` doesn't appear on
`darraghc.ie/showcal/titles`). **A redeploy via Portainer is needed** before either is real for a
visitor. The historical_results import (Killarney/Castlebar, `cdd44c4`) does NOT need a redeploy -
that was a direct DB write via SSH, already live regardless of container state.

~~**A real gap found while checking the society page**~~ - **FIXED same session, `f3e8561`.** The
"Future announced show" highlight only fired for a show in a season *after* the current one, so a
show dated months from now but still within the *current* season - the common case - got no
highlight and blended into plain history. Confirmed live on Jack Cunningham Productions before the
fix. Now date-based (`opening_date >= today`, with a fallback for a future-season show that's
announced but has no date yet - a pure date check alone can't catch that case).

**Logo discovery handed to Gemini/Antigravity, 2026-08-25 - not yet returned, check `enrichment/`
next session.** Only 7 of 192 societies have a logo on file; 71 have a website and no logo.
`enrichment/LOGO_SCRAPE_BRIEF.md` + `enrichment/logo_worklist.json` (both gitignored) sent - find a
direct image URL per society, `found: false` is a fine answer for a text-only site, Darragh reviews
and approves/rejects each `logo_url` himself. Deliberately **a discovery worklist, not an import** -
no bulk-logo-import script exists (today's uploads are all one-at-a-time via `/admin/societies`,
through `save_poster()`'s decode/resize path) - build the real import path once we see how many
candidates actually survive review.

**Two decisions recorded for later, from a final round of questions before Darragh headed out
(2026-08-25):**
- **Society checklist grid, when built: status starts pre-filled with the heuristic's best guess,
  Darragh confirms/corrects each one** - not blank. His call, traded a little accuracy risk (a wrong
  guess rubber-stamped) for speed across 194 rows. Not built yet - still needs its own session.
- **Costume/prop listings, if built: per show, not per society** - matches the original request's
  literal wording ("a section for each show"), overriding the earlier triage note that had assumed
  per-society. Not built yet - still the biggest lift on the whole backlog (new data model, new
  admin UI, a matching concept), this only settles the shape, not the schedule.

**Three jobs are genuinely ready to start** - pick by appetite:
the archive transcription immediately below (data work, well-understood, high certainty of value -
now also queued with Gemini, see above); **item 1, the society coverage checklist grid** (Darragh's
own request, needs a plan + mockups first); or item 2, internal-only person identity resolution (the
item with measured harm that grows while untouched).

~~One security gap worth knowing about~~ - **FIXED and pushed 2026-08-25 (`fc3fbb2`).** Photo
submissions are now decoded before being written, so a file named `.jpg` that is really HTML or SVG
is rejected instead of being served into the admin queue. Full suite 722 passing.

### Session continuation (Sonnet, 2026-08-25) - step 1 of the handoff done

~~1. Build the three ready items~~ - **DONE, pushed `f07bd11`.** Filter chips on `/reviews` (same
pattern as `/awards`), `?society=`/`?season=` on `/calendar.ics` (combinable with the existing
`?section=`/`?region=`, invalid values fall back to unfiltered), and the `match_show_for_edit`
normalisation fix (society+season-scoped, not fuzzy - `Frozen`/`Frozen Jr.` still don't match, tested
explicitly). 17 new tests, each verified to fail without its fix. **Full suite 722 -> 739 passing.**

~~2. Score Gemini's other two deliverables~~ - **DONE, scored 2026-08-25. Neither is clean; do not
import either without further work. Full findings below**, replacing the "mechanical, no judgement
needed" framing - it needed judgement, and caught two real problems.

3. **Leave the checklist grid (item 1) for a flagship session** - its two open questions are real
   judgement calls, especially the privacy pass on storing named volunteers' contact details.

Production data as of now:

| | |
|---|---|
| Societies | 194 (6 with a founding year) |
| Venues | 118 (113 typed, 72 with box office contact) |
| Show titles with info | 300 (all 300 now credit composer/lyricist/book/licensing house) |
| historical_results rows | 5,010 (was 4,999; +11 from Killarney/Castlebar archives, 2026-08-25) |
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
`known_productions_for_cross_check` so the overlap test runs the same way.

**The "genuinely unreachable" five are now in doubt** (2026-08-25). Ballywillan, Ennis, Dun Laoghaire,
Kilcock and Pop-Up Theatre Sligo were recorded as timeout/DNS failures - but a later attempt to
HTTP-test all 69 society websites from Claude's sandbox returned "could not resolve host" for **all
69**, including sites confirmed live minutes earlier, and could not resolve `example.com` either.
That is a restricted-DNS artifact of the environment, not evidence about the sites. So the original
five may well be alive. **Claude cannot settle this from here** - it's in the calibration brief as a
task for Antigravity (`enrichment/CALIBRATION_BRIEF.md`, Task 3), or Darragh can just open them in a
browser. Ballywillan matters most: 1952-2025 is the largest single prize outstanding, musicals only
(their first 35+ years are pantomime, out of scope).

Note the irony worth remembering: this is the same "falsely reported unreachable" failure that got
Antigravity's last round rejected, and Claude nearly filed 69 live societies as dead the same way.
**Never record a reachability finding without checking that the environment can reach anything.**

### Waiting on Darragh, nothing Claude can do

- **FAQ content.** `/admin/faq` is built and live (add / edit / reorder / draft / publish). It has
  zero entries. Needs his voice, not invented AIMS policy.
- **`/admin/historical-society-links`.** 69 printed names awaiting a decision. Deployed and unused.
  Expect ~9 to have any suggestion and most to be "no current society", which is bulk-selectable -
  probably 10 minutes of clicking. Worth him doing before the next awards re-import.
- **Posters.** 44 against ~200 current-era shows - and concentrated in **12 societies of 194**, so
  the gap is who has been asked, not who is willing. Gates any poster-led design work.

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

**This third accusation is now in serious doubt (2026-08-25) and should not be repeated until
re-tested.** The calibration round returned `[Errno 11001] getaddrinfo failed` for 11 of 20 rows -
a *Windows* DNS error, meaning Antigravity runs locally on Darragh's machine and hits **the same
restricted DNS that Claude's sandbox hits** (which could not resolve `example.com`, never mind 69
society domains). So "falsely reported unreachable" may have been an honest environmental failure
the whole time. Claude nearly filed 69 live societies as dead the same way on the same day. Settle
this from a normal network before the roadmap keeps asserting bad faith.

**A fourth round changed the picture substantially (2026-08-25, the calibration batch).** Scored
against five hidden controls and two canaries: **zero wrong years** (3 correct, 2 blank with the
right year correctly labelled "unverified recall"), both canaries passed, and **3 of 4 quotes
independently verified verbatim** by fetching the cited URL - against 0 of 34 last round. The
Leixlip control is the telling one: it returned blank with "HTTP 200, no founding year on the
homepage, unverified recall 1980", which matches exactly what an independent WebFetch found.
**Conclusion: the measurable task design works.** Giving recall a legitimate labelled home appears
to remove the pressure to disguise it as a citation. Net gain: Rathmines & Rathgar 1913, verified.

**But scoring the other two deliverables (2026-08-25, same day) found the calibration result did not
generalise, and caught a live repeat of the exact failure it was designed to prevent.**

**`society_archives_worklist.json` - the 14 "reachable" archives came back with a lazy templated
non-answer, again.** All 14 blank rows (Waterford, Fortwilliam, Kilmacud, Boyle, Killarney, Ennis,
Dun Laoghaire, Kilcock, Harolds Cross Tallaght, Glencullen, Muse, Castlebar, Ballywillan, Pop-Up
Sligo) carry the **word-for-word identical** note: *"Archive page unreachable or contains narrative
history rather than a full tabular past productions list."* No per-page HTTP status, no
`source_url` - both explicitly required by the calibration brief for this exact task. That's not 14
independently-diagnosed failures, it's a template - and it directly contradicts this file's own
earlier direct verification that at least 9 of these load fine with substantial year data (see "The
single best next technical job" above). This is the **third** occurrence of the same lazy-default
pattern within the delegation's history, on the task that was specifically instrumented to catch it.
**Do not treat any of these 14 as checked.** Claude's sandbox has the same DNS restriction and cannot
independently verify or refute them either - this needs Darragh on a normal network, or a re-run
with the "unreachable is not acceptable" instruction repeated even more forcefully.

The 5 populated rows (Carnew 48, Baldoyle 49, Oyster Lane 31, Limerick 19, 9 Arch 13 - 160 total)
scored **identically to already-known results already documented in `import_society_archives.py`'s
own docstring** (Carnew 0/16, Baldoyle 96%, Limerick 93%, 9 Arch 25%, Oyster Lane 9/13 exact
matches). These are not new information regardless of whether they're a stale carryover from before
this round or a genuine faithful re-scrape - either way nothing here changes the existing `TRUSTED`
list (Baldoyle, Limerick, Oyster Lane only). Carnew stays rejected; 9 Arch stays too low to trust.

**`society_founding_years_v2.json` - real fabrication found on direct check, 2 of a small sample.**
Independently verifying `source_url` + `evidence_quote` for a handful of the 34 filled rows (same
method as the calibration round): **Boyle and Rathmines & Rathgar verified genuine, word-for-word.**
But **Baldoyle and Leixlip (LMVG) are fabricated** in the exact pattern the original founding-years
failure was defined by - a plausible-to-correct year wearing an invented citation:
- Baldoyle: claimed *"formed in late 1972"* at `baldoylemusicalsociety.ie/about` - that URL 404s;
  the real page (`/pages/history`, found by asking the site for its own nav) says *"In 1973 a group
  of people met and decided to establish..."* - a different year and a completely different quote.
- Leixlip: claimed *"LMVG was formed in 1980"* at `lmvg.ie/about-us` - also 404s. The year happens to
  be correct (it's one of the five hidden calibration controls), which is the concerning part: this
  is recall dressed as a citation, indistinguishable from a genuine one until the URL is opened.

Both fabricated rows have a **plausible year and an invented URL** - exactly last round's pattern,
now proven to still be present in Gemini's actual delivered work, not just eliminated by the
calibration protocol. **Conclusion: the calibration format itself is not sufficient protection** -
performing well on a scored, controlled batch does not mean the same standard holds on an
unscored, real deliverable. **Nothing from this file should be imported without opening every
single `source_url` first**, per the standing rule already in this document - that rule has now
paid for itself twice over in one day.

**Rule of thumb:** delegate transcription with a built-in cross-check against data we already hold.
Do citation-dependent work in-house. Never accept a `source_url` without opening it.

### The backlog interrogation - DONE 2026-08-25

The planned interrogation of the UX-audit slivers and the Parked list **was carried out** (see "The
backlog interrogation" section below for the full verdicts and reasoning). Darragh's rule for it:
"no one has asked for this" was **not** enough on its own to close an item - each was argued on
merit. **Then Darragh was re-questioned on everything closed on inferred demand, and five of seven
verdicts were overturned** - costume listings, the share button and the `.ics` export all reinstated,
the repertoire finder validated, the poster museum confirmed wanted-but-gated. Only "On This Day" and
the embeddable widget survived as closures. The live backlog is now that section's numbered list of
12, headed by Darragh's own checklist-grid request.

**One verdict was reversed the same day** (costume/prop listings - now item 3), and the interrogation's
own headline finding was withdrawn, both for the same reason: it argued about user demand without
consulting the demand record. Read the corrected section below, not the original claims.

Three things came out of it that outlast the individual verdicts:

- **Ask about demand, don't infer it.** `feature_suggestions` holds real user requests with a triage
  lane; Darragh's own conversations with committees and adjudicators leave no trace in this repo at
  all. Claude closed an item the PM had personally marked **Planned**. Query the table and ask him.
- **Poster supply is an outreach gap, not unwillingness** - production has 44 posters across just
  **12 societies of 194**. 182 have never engaged at all. This does not support blocking features on
  "societies won't maintain data"; it supports item 9 (society profile completion).
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

- **3 venues with no map pin - coordinates now supplied by Antigravity and partially verified
  (2026-08-25).** Delegated deliberately because coordinates self-verify, and the check was run:

  | Venue | Supplied | Reverse-geocodes to | Verdict |
  |---|---|---|---|
  | St. Mary's College Arklow | 52.79582, -6.15852 | St Michaels GNS, Collins Street, **Arklow** | Right town, nearest feature is a *different school* - weakest of the three |
  | The Abbey, Clane | 53.29252, -6.68722 | Serenity Hair Salon, **Main Street, Clane** | Right town + right street, lands on a salon |
  | Loughrea Temperance Hall | 53.19748, -8.56864 | **Barrack Street, Loughrea** | Right town + right street, no conflicting building - cleanest |

  Both cited websites return **HTTP 200** (`stmarysarklow.ie`, `clanecommunity.ie`) - a real
  improvement on the founding-years run where 19 of 34 domains didn't resolve, and evidence the
  self-verifying task design works. **But none is confirmed at building level.** That's partly
  expected: these three are unpinnable precisely *because* OSM has no entry for them, so "nearest
  mapped feature is a hair salon" shows the building is absent from OSM, not that the coordinate is
  wrong. Street-level accuracy is likely good enough - `venue_detail.html` uses the pin only for the
  optional "See the exact spot" link, while "Get directions" is name+town based either way.
  **Before importing: Darragh should confirm the Arklow pin** (a different school 100m away is the
  plausible failure mode) **and confirm "The Abbey Clane" really means The Abbey Community Centre on
  Main Street** - that identification was Antigravity's interpretation of an ambiguous name, not
  something it read off a page. The named "verification sources" (CEIST, community directories) came
  without URLs and should not be treated as checked.

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
argued for and against. Every "already delivered" verdict below was checked against the actual code,
not against this file's own summary of it.

**Then Darragh was re-questioned on every item that had been closed on inferred demand, and the
inferences lost badly.** Of the items where Claude guessed at demand rather than asking:

| Item | Claude's verdict | Darragh's answer |
|---|---|---|
| Costume / prop listings | closed | **reversed** - a real user asked, he'd triaged it Planned |
| Share button on show pages | closed | **reversed** - real backing |
| Season watchlist / `.ics` export | closed | **reversed** - real backing |
| Repertoire finder | kept, unvalidated | **promoted** - committees have raised it to him |
| Poster / programme museum | closed (blocked) | **wanted**, genuinely gated on poster count |
| "On This Day" widget | closed | closure confirmed |
| Embeddable widget / JSON feed | closed | closure confirmed |

Five of seven wrong. The lesson is not "be more generous when triaging" - it's that **Claude has no
visibility into the demand channel that matters** (Darragh's conversations with committees,
adjudicators and AIMS), so inferring demand is guessing dressed as analysis. Ask.

**The finding that reorganises the rest - CORRECTED 2026-08-25, read the correction not the original.**
The original claim was that the binding constraint is society-supplied content, evidenced by the
poster count, and that this justified blocking several items. Checked against **production** rather
than the stale local copy, the numbers are **44 posters across just 12 societies of 194**. That is
the opposite of what was argued: it isn't 194 societies declining to supply content, it's 12 who
were asked or who found it, and 182 who have never engaged at all. That's an **outreach gap, not
evidence of unwillingness** - so it cannot carry the weight of blocking a feature. Item 8 (society
profile completion) is the real work here; the blocking argument is withdrawn.

**Second finding, and the important one: demand data existed and was never consulted.** The whole
interrogation argued about what users want without querying `feature_suggestions` - a table of real
submissions from the live site, with a triage lane Darragh maintains. Six rows, and one of them is
a direct request for costume/prop listings that he had already marked **Planned**. It was closed
anyway. **Before arguing demand for anything, query that table** (and ask Darragh, whose own
conversations with committees and adjudicators are a demand channel that leaves no trace in the
repo at all). "No evidence in the artifacts I can see" is not "no one asked".

Third finding, process rather than product: **rejected ideas were being laundered back in.** The
watchlist / Leaflet map / "On This Day" / embeddable-JSON group was ruled skip on 2026-08-20 with
reasons. All four returned to Parked on 2026-08-24 labelled "genuinely new, unclaimed", because they
arrived inside a *different* audit doc. Any future audit doc gets diffed against prior rulings before
its suggestions are entered here.

### Kept - the live backlog, in priority order

1. **Society coverage checklist grid + lifecycle status (admin).** **Darragh's own request,
   2026-08-25** - highest-confidence origin on this list, and it unblocks his own data work rather
   than adding a public feature. Two parts, one page:
   - **A checklist grid over all 194 societies**, one row per society, columns for the things we
     gather (production history backfilled? upcoming season entered? profile/about? logo? poster?
     contact/socials? venue set? founding year?), tickable so he can work through them and see
     coverage at a glance. Most columns can be **derived** from data we already hold rather than
     hand-ticked - the tick is only needed where "we checked and there is genuinely nothing".
   - **A lifecycle status per society** - Active / Dormant-Hiatus / Closed. Today `societies` has
     only `section` and a `hidden` flag, which conflates "gone" with "hide from the public list".
     Many historical societies no longer exist but still carry real history that must stay visible;
     others are on hiatus and may return. Needs a real column (`COLUMN_MIGRATIONS` in `app/db.py`,
     per CLAUDE.md) plus a decision on how each state renders publicly.

   **Mockup built 2026-08-25: `mockups/society_checklist_grid.html`** - all 192 visible societies,
   real production data, status chips that filter, gap-count sort. Three findings from measuring the
   data first, which shaped it:

   - **Every column is derivable; nothing needs hand-ticking.** Coverage today: region 100%, socials
     71%, about 70%, default venue 65%, website 38%, poster 6%, logo 4%, founded year 3%. So the grid
     is a *view*, not a new data-entry surface. The only state worth storing per cell is
     **"checked, and there is genuinely nothing to get"** - which is what stops a permanent gap from
     nagging forever. That's the one new concept the feature actually introduces.
   - **Active/Dormant/Closed is not enough - five states are needed.** Of the 37 societies with zero
     shows, **5 are pantomime companies** (Arklow Panto Creations, Ballinasloe Panto Company,
     Castlebar Pantomime, Renmore Pantomime Society, Rush Panto Society) which will never have shows
     because panto is out of scope, 6 are youth/education groups, and of the remaining 26, **20 have
     no shows *and* no awards** - almost certainly the 28 orphaned Inactive societies on the
     data-accuracy list. "Gone", "out of scope" and "we never gathered it" are three different
     things and one status field must not conflate them. Suggested: Active / Dormant / Closed /
     Out of scope / **Unverified** (the default, meaning nobody has looked yet).
   - **The chase list is smaller than it looks.** On the mockup's heuristic: 128 active, 27 dormant
     (have shows but nothing for 2025/26), 26 unverified, 6 closed, 5 out of scope. The 27 dormant
     are the actionable ones for a season-entry push.

   **Second purpose, confirmed by Darragh 2026-08-25: this is a society call-out tool**, not just a
   coverage view. That changes the scope, and measuring first found the real bottleneck:

   - **There is no email field on `societies` at all** - contact is only `website_url` /
     `facebook_url` / `instagram_url` / `tiktok_url`. Of the 27 priority call-out targets (history on
     record, nothing entered for 2025/26): **11 have a social, 3 have a website, 16 have neither**.
     We cannot currently reach 16 of the 27 from data we hold.
   - **Only 14 invite codes exist across 194 societies**, so "let them fill it in themselves" is not
     yet a route for ~180 of them.

   Darragh's decisions:
   - **Add proper contact fields** (committee email, named contact) - **admin-only, never public**,
     via `COLUMN_MIGRATIONS` in `app/db.py`. **Flag when scoping:** these are named volunteers'
     personal details, not organisational data, and the same privacy instinct that parked public
     person pages applies. Decide retention and who can see them *before* building the field.
   - **A call-out issues an invite code** as part of the action, so the ask becomes "here's your
     code, fill in your own page" rather than "send me your info". Self-service scales; keying in
     194 societies by hand does not.
   - **No call-out tracking table** - he'll track that himself. Worth noting he gets most of it free
     anyway: `invite_codes` already stores `created_at`, `created_by` and `label`, so "which
     societies have I chased, and when" is derivable from code issuance without a new column.
   - Contact routes are **his own email contacts, Facebook/Instagram DM, and in person at events** -
     not AIMS centrally. The in-person route means **the grid must work on a phone**: a filtered list
     he can pull up at a festival to know who to corner and what to ask them for.

   **Decided 2026-08-25: status starts pre-filled with the heuristic's guess, Darragh confirms each
   one** (not blank) - see the note near the top of this file for the full reasoning. **Still open
   before code:** whether status needs an "as of" year like `section_as_of`; and whether
   Closed/Out-of-scope rows drop off the grid or just sort last.
2. **Person identity resolution, internal only.** The only parked item with *measured* harm rather
   than a hypothesis: 1,730 distinct award nominee names, 746 credit names, **217 credit names are
   also an award nominee by exact match alone**, and `/admin/backfill-credits` is actively adding
   more free-text names, so it grows while untouched. Darragh's privacy objection was to *public
   person pages*, which stays honoured - the agreed path is canonical names + aliases, moderator-
   reviewed, reusing `dedupe.find_candidates`, **no new public surface**. Top of the list.
3. **Costume / prop / set listings for sale or rent.** The **only item on this list with a written,
   attributable origin from a real user**, and it was wrongly closed on 2026-08-25 before that was
   checked. `feature_suggestions` row 4 (2026-08-04): *"Perhaps a section for each show for societies
   to list for costumes/ props/ sets for sale or rent?"* - triaged **Planned** by Darragh on
   2026-08-23 with the note *"Will revisit this in future - could be good to add ot society pages!"*.
   The archive had also flagged it as "a live demand signal". It is still the biggest lift on the
   list (new data model, new admin UI, a matching concept) so it wants its own scoping session - but
   "societies won't maintain it" was an assumption, contradicted by the fact that the request came
   from someone volunteering to list things. **Scope settled 2026-08-25: per show**, per Darragh -
   the requester's literal wording wins over the earlier triage note that had assumed per-society.
   Still not built - this only settles the shape, not the schedule.
4. **Share affordance on show pages.** **Reinstated 2026-08-25 after Darragh confirmed real
   backing** - closed that morning on Claude's inference, which was the weakest closure of the day
   ("the URL is the share mechanism"). Ignored that a one-tap share to WhatsApp or Instagram is how
   a cast actually spreads its own show - and that is the same audience the social card generator
   (item 5) serves, so **scope the two together**. Still open.

   ~~and a season `.ics` export~~ - **DONE, pushed `f07bd11`** (same session). Turned out to be
   mostly already built: `/calendar.ics` (`app/blueprints/feeds.py:54`) already existed, filterable
   by `?section=`/`?region=`; added `?society=` and `?season=`, combinable with the existing params,
   invalid values falling back to unfiltered per the feed's own convention. This was the **fourth**
   item found already shipped while this file still listed it as open - alongside milestone badges,
   show-page cross-links and the design audit's nav restructure. Check the code before scoping
   anything on this list.
5. **Social card generator** (per show: poster + society logo + opening countdown + QR). Promoted
   from a throwaway line to a real candidate because it's the one item that *gives* societies
   something instead of asking them for something - plausibly the lever that gets posters uploaded
   ("upload your poster, get a card you can post"). Pillow landed 2026-08-24 for the poster pipeline,
   so the rendering dependency already exists. Needs a mockup pass before any build.
6. ~~**`match_show_for_edit` exact-match bug.**~~ **DONE, pushed `f07bd11`.** Now also tries a
   normalization-insensitive match (society+season-scoped) when the exact match misses - not fuzzy
   matching, `Frozen`/`Frozen Jr.` still don't match, tested explicitly.
7. **Society edit audit log - scope cut to the cheap 80%.** Kept because the hole is real and
   structural, not a feature wish: societies share one login code, so there is no way to tell who
   made an edit or to undo it. Cut: build the append-only log (who/when/field/old/new), **drop the
   revert UI** - that's the expensive half, and a moderator can restore by hand from the log.
8. **Repertoire finder** (the "what show should we do next" hub) - the single survivor of *both*
   deleted audit docs, and the only feature idea either produced with a real audience: volunteer
   committees genuinely do spend months choosing a title. Builds on columns that already exist
   (amateur rights status, licensing house on `show_info`). Its "which other societies staged this
   recently" sub-idea also fits the collaborative ethos the design audit itself insisted on.
   **Validated 2026-08-25: Darragh confirms committees have raised this to him directly**, which
   moves it from a plausible bet to one of only three items here with a real attributable origin.
   **Before scoping, get from him what committees actually asked for** - Claude's version (rights
   status + regional gap + recent stagings) is a guess at the shape, and the real ask may be
   narrower or completely different.
9. **Society profile completion** - merges the old "empty vs. filled society page" sliver with the
   whole outreach/onboarding track, because they're one problem: a nudge on a thin profile, 2-3
   exemplar societies filled in completely as a reference, a draft message to a committee, a "claim
   your page" route. Mostly Darragh's lever, not a coding task.
10. **Poster lightbox/zoom** - kept but explicitly *not standalone*: bundle it into the next piece of
   poster work. At 44 posters (12 societies) it currently affects few pages.
11. ~~**Removable filter chips - redirected.**~~ **DONE, pushed `f07bd11`.** Built on `/reviews`
   (the page that actually earned it, with four filters: free-text `q`, season, tier, adjudicator),
   same pattern as `/awards`, reusing its existing CSS.
12. **A pantomime category** - not a build item and never was. Pantomimes were ruled out of scope
   (AIMS musical-theatre circuit specifically) with "may get their own category in the future".
   It's a scope decision about what the site *is*, and only Darragh can make it.
13. **Genre filtering on `/titles`** - added 2026-08-25, part of the same "no one goes alphabetically"
   conversation that shipped rights/licensing filters (item text above, `87b7b3d`). No genre data
   exists anywhere in the schema - this is real new work, not a quick add. Needed before any build:
   a `show_info.genre` column via `COLUMN_MIGRATIONS` (`app/db.py`, per CLAUDE.md); a small **fixed
   taxonomy**, not free text - Darragh's own call, likely based on what MTI/Concord/TRW themselves
   use on their own listing pages, not invented here; and a Gemini task under the **same calibration
   protocol** used for founding years today (hidden controls, two canaries, batch-discard scoring,
   citation required per tag). Do not skip the controls - the founding-years v2 file proved today
   that skipping them lets fabrication back in even after a clean calibration run.

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

- **Embeddable per-society JSON feed / widget.** **Closure confirmed by Darragh 2026-08-25** - no society has asked. Real merit: a society embedding "our upcoming shows"
  on its own site is useful and drives adoption. Against: a new unauthenticated public surface with
  no rate-limiting built for it, on a single-moderator site, for zero requests. The 2026-08-20 ruling
  survives the re-argument. **Trigger to reopen: one named society asks to embed something.**
- ~~**Fuller interactive Leaflet/OSM pin map.**~~ **TRIGGER FIRED 2026-08-25 - closure reversed.**
  Merit: a map genuinely beats a list for 118 venues. Against: it would be the first JS-library
  dependency on a deliberately no-build-step site, and the existing Near-me list already answers the
  question a map would. **Trigger: pin coverage near complete AND a request.** Both fired: 108/118
  venues (91%) have coordinates, and Darragh directly asked for map ideas on `/venues`. A real
  mockup was built and sent (`mockups/venues_map.html`, real data, keyless CartoDB tiles) - the "new
  JS dependency" cost is real and still worth weighing, but it's no longer blocked on data-readiness.
  Awaiting Darragh's reaction before building it into the app.
- ~~**"My Season Watchlist".**~~ **PARTLY REVERSED 2026-08-25 - the `.ics` export is now item 4.**
  Darragh confirmed real backing. The reasoning below was right about which half is valuable and
  wrong to close the whole thing. Merit: the `.ics` export half is a real hook. Against: the watchlist
  wrapper is invisible to Darragh (no login means no data, no signal), evaporates when a browser is
  cleared, and duplicates bookmarks for a site people visit a few times a season. **Killed, but the
  `.ics` half is salvageable on its own** - a season/society calendar export is small and standalone.
- **"On This Day in AIMS History" widget.** **Closure confirmed by Darragh 2026-08-25.** Merit, and better than the earlier ruling credited: with
  4,879 `historical_results` rows it would have real content most days, which is an asset most sites
  don't have. Against: homepage real estate for a novelty, aimed at a daily-returning audience this
  site doesn't have. Killed as a homepage widget; the underlying data is better spent feeding the
  social cards (item 2).
- ~~**Costume/prop rental listings.**~~ **CLOSURE REVERSED same day - see the Kept list, item 2.**
  It was closed on an inference about societies not maintaining data, in ignorance of the fact that
  a real user asked for it and Darragh had already triaged it Planned. Left here as a record of the
  mistake, not as a verdict.
- **Historical-posters gallery + programme-cover museum.** Two entries for one idea. **Darragh
  confirms it is wanted** (2026-08-25) but genuinely gated on having enough posters - so this is a
  real blocker, not the withdrawn content-supply argument it was originally closed on. Currently 44
  posters from 12 societies. **Trigger: ~100 posters - Claude's proposed number, not Darragh's;
  confirm it.** Getting there is items 5 and 9 (social cards as the carrot, profile completion as
  the outreach). Also still open: plain gallery vs. the designer-credited archive framing - different
  builds, decide when it unblocks.
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
- ~~**Show-page share affordance.**~~ **REVERSED 2026-08-25 - now item 4.** Darragh confirmed real
  backing. The original reasoning ("no case beyond 'sites have one' - the URL is the share mechanism,
  and OG tags are already in `base.html`") was the weakest call of the day: it treated a technical
  capability as if it were an affordance, and ignored that a cast sharing its own show to WhatsApp or
  Instagram is the site's most natural growth loop.

## Waiting on Darragh, not a coding task

- **Posters** - 44 exist against ~200 current-era shows, from 12 societies. Gates the whole visual redesign (type/palette
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
- **Check the demand record before arguing demand** (added 2026-08-25, learned the hard way).
  `feature_suggestions` in the live DB holds real user submissions with a triage lane Darragh
  maintains; the archive also records origins for some ideas ("a live demand signal", "an
  adjudicator's actual complaint"). An entire backlog interrogation ran without consulting either,
  and closed an item the PM had personally triaged **Planned**. Claude's view of demand is limited
  to what's written down - Darragh's conversations with committees, adjudicators and AIMS itself
  are a real channel that leaves no trace in this repo. **Ask, don't infer.**
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
