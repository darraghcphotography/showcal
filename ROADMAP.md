## Morning queue, 2026-08-24 - worked through same day

Full plan and reasoning: https://claude.ai/code/artifact/c85710e6-d535-46d1-8041-5e4bad7c5115

**Done and verified live on production** (queue items 1-3, 5-6): the Fame/Fame: The Musical bug
(Leixlip's six award nominations now show on its own page), Annie/Shrek/Elf title merges, and the
11 published-no-link reviews cleared back to "None". Item 4 (default_venue backfill) landed 3 of
the targeted 5-10 - re-checked against this repo's own data (the Gemini list is exhausted), and
68 of the remaining 71 societies genuinely don't have enough venue history on record to back a
confident call; deliberately not forced further (see `backfill_default_venues_round2.py`).

**Built, tested (612 tests pass), verified against local data - pushed, not yet deployed**
(queue items 9-10, said "go" on this morning): the society page now links every venue in its show
history and highlights the next announced show; the show page shows venue capacity/town, an
"About the society" blurb with social links, and a one-line circuit summary; the homepage has a
"Near me" toggle (browser geolocation, distance-sorted, honest about the ~third of venues that
have a map pin so far - no fake map graphic, just the list, matching the site's existing
"link out to Google Maps" convention rather than adding a new mapping dependency). Same redeploy
step as the rest of this file's deploy queue below.

**Also built, same status (mockup approved 2026-08-24, then built for real the same day):** the
week-by-week season calendar moved off `/season` onto its own page, `/season/calendar` - `/season`
now holds only the past/upcoming productions list plus a link to the calendar. An empty Gilbert or
Sullivan column reads as an actual blank card (dashed border, "Nothing opening this week") instead
of italic muted text. Nav, footer, More page, the homepage's "week by week" link, and the sitemap
all point at the new route; the mobile bottom tab bar's "Seasons" tab was deliberately left
pointed at `/season` (no spare tab slot, no "week by week" wording there to redirect).

**Still open from that plan:**
- Item 8 (FAQ page mockup) - parked until the six questions are settled.
- Peter Pan and Sugar/Some Like It Hot title pairs - left unmerged, no confident call either way.
- Queue items 11-14 (next venue-backfill batch, venue long tail, unmapped historical societies
  schema question, outreach track) - not started this session.

**Item 7 resolved, then taken further.** The 14 Cancelled shows weren't a "some are wrong, flag
which ones" cleanup - Darragh's call was that the field itself isn't reliably used, so the flag
was cleared everywhere (local + production) rather than corrected row by row. Digging into why
turned up the actual root cause: `import_csv.py` reads a `status` column straight from the source
spreadsheet and upserts it unconditionally on every import, with none of the protection
`review_status` gets - so the next routine re-import would have silently resurrected wrong
Cancelled flags. The feature (schema column, admin/society checkboxes, tag rendering, the CSV read
path) is being removed entirely, not just the data cleared, so this can't recur.

**Second thread started today: a UI-polish plan** (Fable's read on "the site feels dated," plan at
`C:\Users\Darragh\.claude\plans\hello-1-are-sunny-hippo.md`, executing phase by phase). **Phase 0
done, pushed, not yet deployed:** colour was already tokenised in `style.css` but spacing/radius
weren't - added `--space-*`/`--radius-*` tokens and consolidated five near-identical card
components (venue/resident/adj/lb/stat) and three "hero" gradient cards (explorer/trends-callout/
era-card) that were each independently re-declaring the same border/background/shadow, plus ~11
duplicate `border-radius: 999px` pill declarations. Every substitution is value-identical to what
it replaced - zero rendered-output change, 612 tests green, safe to redeploy whenever convenient
(no rush, purely cosmetic-neutral). Phases 1-3 (bare-page consistency pass, a motion/icon pass,
typography/colour experiment) still to come.

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

## DEPLOY QUEUE (2026-08-24) - everything below is pushed, none of it is live

Suite 607 green. Redeploy through Portainer, then run **two** scripts in the container -
the code deploy alone changes no data:

```bash
docker exec aims-web python enrich_venues.py --db /data/aims.db
docker exec aims-web python backfill_default_venues.py --db /data/aims.db
```
(`docker compose exec` needs the compose directory; `docker exec` works from anywhere.)

Both are idempotent, and `enrich_venues.py` has already run once against prod - the second
run adds 15 venues and one merge. Then check: the homepage leads with "What's on" grouped by
month, `/reviews` is a page at a time with a pager, an upcoming show page no longer shows the
adjudication cut-off to a logged-out visitor, and a venue page offers "Get directions".

Shipped in this batch: the homepage rebuild (audit bet 1 + findings 02/04), the adjudication
cut-off audience fix (finding 07), `/reviews` pagination and full-text search (finding 12),
the "No region" option for historical societies, Google Maps directions on venue pages, and
the Gemini venue-mapping adoption (84 default venues, 15 more venues enriched).

---

**Two earlier things, also waiting on the same redeploy.** Suite 589 green at the time.

1. **Venue content pass** - `enrich_venues.py` fills town/county/capacity/website/tech-spec/map pin for
   the 30 venues with 5+ productions (~70% of venue-attributed shows), folds away 6 duplicate
   spellings, and corrects 6 shows filed under a bare "Town Hall Theatre" that was really four
   buildings. **The script has NOT been run against production yet** - deploying the code changes
   nothing on its own. After the redeploy, run:
   `docker compose exec aims-web python enrich_venues.py --db /data/aims.db`
   Then check `/venues/town-hall-theatre-galway` reads 19 productions (it reads 11 and 6 on two pages
   today) and shows its capacity, website and map link. Verified locally against a production copy: 145
   venues become 138, 17 gain a capacity, 28 gain a pin, and a rebuild preserves all of it.
2. **Admin "Shows missing a date"** counter/page mismatch (30 vs 812), fixed via a shared
   `MISSING_DATES_WHERE` in `admin/_shared.py`. Moderator-only; nothing public waits on it.

Everything before those is deployed and verified live - see below.

Darragh answered the venue questions on 2026-08-24 and all of them are applied: Twin Productions are
Galway-based (so their Town Hall Theatre is Galway's), Kilcock perform at Kilcock GAA (so that merge
went ahead after all), and the Grand Opera House and the Lyric are two different Belfast venues (so
that slash-joined record stays unmerged, as does glór/Shannon).

**Productions-table migration stages 3-4 - DEPLOYED and verified live 2026-08-23 evening.** All four
public surfaces now count real stagings; stage 4 was decided against (the table stays derived, with the
reasoning and the trigger conditions in `schema.sql` and `docs/data-model.md`). Verified on the live
site, not assumed: `/stats` still reads **2,709** (the invariant that proves stage 1's numbers didn't
move), `/titles/Fame:%20The%20Musical` returns 200 where it used to 404, the A-Z's most-performed
column reads real production counts (Oklahoma! 83, Fiddler 81, JCS 78 - it said 152 for JCS before),
and `review_author` exists in the production schema, confirming the byline shipped in the same deploy.
Full detail and numbers in `ROADMAP_ARCHIVE.md` under "Productions-table migration, stages 3-4".

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

## `GOOGLE_MAPS_INTEGRATION_PROPOSAL.md` - assessed 2026-08-24, mostly adopt

Gemini-generated, three sections. **Section 1 (Google Maps directions) is shipped.** Sections 2
and 3 are worth adopting, but field by field rather than pasted whole - the two carry very
different confidence, and the measurements below say which is which.

**Section 2, `default_venue` for 140 societies - strong, adopt after the auto-check.**
Cross-checked every claim against the venue our own archive says that society most often plays:
**90 of the 112 judgeable claims agree (80%)** - 61 exact, 29 the same venue under a different
spelling. Only 22 genuinely differ, and **on inspection most of those are our data being wrong,
not the proposal**: our archive has Boyle Musical Society at "Roscommon", Ennistymon Choral at
"Clare", Ballyshannon at "Donegal", Castlebar at "Castelbar", Trim at "40th Anniversary (March
run)". Those are exactly the `looks_unresolved()` junk entries (53 of them) the merge queue
flags and can't fix by itself. **This list is the missing half of that problem** - it names the
real building behind the bare county. It also gives the correct spelling for venues we hold
under a typo ("Pavillion Theatre" -> Pavilion Theatre, Dún Laoghaire).

Worth verifying individually before applying: `Mandela Hall, Belfast` closed in 2018 and the
building was demolished in January 2020 (the name was reused in the new QUB student centre, so
it's ambiguous rather than simply wrong). `default_venue` prefills the venue on a society's own
submission, so a wrong one mis-tags future shows quietly. 39 of 194 societies have one today.

**Section 3, the 109-venue `DATA` dict - the venue list is valuable, the coordinates need
verifying first.** 54 of the 109 name venues we have no record of at all (Barbican Drogheda,
Hawk's Well, Lime Tree, Everyman, Millennium Forum, An Grianán...) - a genuinely useful
to-research list for the long tail. But the coordinates can't go in unchecked: 26 are
byte-identical to `enrich_venues.py`, and of the 83 new ones **76 are rounded to ≤4 decimal
places on both axes, against 1 of 28 in the OSM/Wikipedia-sourced set**. Spot-checking the three
venues this repo deliberately left unpinned because every candidate was a town-centre point: the
proposal's "The Abbey Clane" is **170m from Clane's town centre**, its "Temperance Hall,
Loughrea" **85m from Loughrea's**. Same for capacities on buildings that publish none (300, 300,
180, 400...).

**The adoption path for section 3 is mechanical, not manual:** geocode each proposed venue
against OSM and accept the coordinates where the two agree within a couple of hundred metres,
flag where they don't. That turns the list into verified data instead of discarding it. Also
drop its `region` key - `venues.region` is derived from the productions staged there and
moderator-corrected, so it isn't a field to set from a list.

## Next feasible things, roughly in order

- **`/reviews` + `/season` page weight** - 362KB/123KB, no pagination. Flagged in the UX audit as the
  one remaining quick win too big/risky to bundle into the two batches already shipped.
- **Show/title enrichment, Source C follow-ups** - Source C (circuit intelligence) shipped 2026-08-23.
  Source A (Wikidata) has a real bug in its proposed query (`wdt:P58` should be `wdt:P87`) and only
  reliably resolves 48 of 306 titles without fuzzy title-matching, which this repo avoids - fix the
  query before building. Source B (licensing-house specs) isn't a pipeline, it's manual data entry.
- **Venue research, the long tail** - the 30 venues with 5+ productions were done 2026-08-23
  (`enrich_venues.py`); ~110 venues with 1-4 productions still have nothing. Same script, extend its
  `DATA` table. Lower value per venue, so only worth doing if the first pass proves itself. Six of the
  30 also still have no map pin: **St. Mary's College Arklow, The Abbey Clane and Loughrea Temperance
  Hall**. All three venues are confirmed - OpenStreetMap simply has no entry for them findable by name,
  and Eircodes don't help (Nominatim doesn't index them and fuzzy-matches to unrelated addresses). They
  need a different source, not another search.
- **FAQ page** - real questions already gathered (what is AIMS, how do I join, which societies are near
  me). Smallest self-contained new page on the list.
- **Merge duplicate/near-duplicate titles the A-Z now shows** (`/admin/duplicate-titles`) - 7 spelling
  variants of titles already on the list became visible when the productions cutover stopped hiding
  them: `Annie - The Musical`, `Big The Musical`, `Elf - The Musical`, `Fame: The Musical`, `Shrek`,
  `Peter Pan, A Musical Adventure`, `Sugar The Musical - Some Like It Hot`. Real merge work, deliberately
  kept out of the cutover (Darragh's call 2026-08-23) so the migration wasn't blocked behind a manual
  title pass. The other 9 new titles are genuinely distinct shows and want no action.

## Data-accuracy follow-ups (from the 2026-08-23 report check), need Darragh's input or real research

- **297 `historical_results` rows with `category_name IS NULL`, 274 of them pre-2001** (re-measured
  2026-08-24 against the fuller archive now loaded - the earlier "154, 1983-2000" figure undercounted)
  - needs real historical AIMS awards-programme research; a Gemini report only sampled 6 of them.
- **~10 unmapped historical societies with no existing `societies` row** (Bangor Operatic Society, De La
  Salle Musical Society Waterford, others) - creating new historical society records is a structural
  decision, not a data-quality bugfix.
- **28 orphaned Inactive societies with zero shows/awards** - retain or remove is a judgment call, no
  urgency signal.
- **19 of 23 researched societies' online production archives not yet backfilled** (research inventory
  exists, only 4 done so far).
- **~112 stale orphaned `historical_reviews` rows** - cross-referenced as real, but explicitly not
  deleted pending a more rigorous verification method than what was used to find them.

## UX-audit bigger bets and outreach track (not started, need Darragh's design input)

- **Homepage reorder** - lead with what's on, group by month, add poster thumbnails inline.
- **Society page, empty vs. filled** - venue links + next-show callout shipped 2026-08-24 (pending
  redeploy); still open: the mockup's fuller "empty vs. filled" pitch beyond that.
- **Show page as the shared front door** - venue capacity/town, an about-the-society blurb, and a
  one-line circuit summary shipped 2026-08-24 (pending redeploy); still open: cross-links to other
  societies who've staged this show, a share affordance.
- **"What's on near me"** - shipped 2026-08-24 as a homepage toggle (pending redeploy), honest about
  the ~third of venues pinned so far rather than waiting for full coverage.
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

1. ~~`ensure_current()` is a call site you have to remember.~~ **Done 2026-08-24** - a
   `before_request` in `app/__init__.py` does it for every request; the sixteen per-route calls are
   gone. Affordable because the no-op case is one fingerprint query, measured at 0.26ms (the stage
   3-4 plan's "~50ms" was pessimistic). Guarded by `tests/test_derived_tables_stay_current.py`.
2. **`productions_build.py` and `venues_build.py` duplicate the same freshness machinery** -
   `FINGERPRINT_SQL`, `fingerprint()`, `mark_stale()`, `ensure_current()` and a one-row `*_build_state`
   table, written twice. Still open, but much less pressing now item 1 has one caller for both: the
   duplication is now two near-identical private helpers rather than a rule spread over six modules.
3. **FTS indexes rebuild on every startup.** Known, deliberate, documented in `db.py` - the obvious
   `COUNT(*)` guard doesn't work on an external-content FTS5 table. Left alone on purpose.
4. **`page_views` is keyed on path only**, so no query-string question can ever be answered from it.
   Fine as a popularity counter, useless as analytics. Only worth changing if a real question needs it.
5. ~~Untracked `.md` files sit in the repo root.~~ **Done 2026-08-24** - gitignored by name, following
   the convention already set for `AUDIT_AND_RECOMMENDATIONS.md`. They're inputs; what came out of
   each is in `ROADMAP.md` and the commits that acted on it. Listed individually rather than by
   wildcard so a genuinely new repo document isn't silently ignored. `git status` is clean.

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
- From an untracked `FEATURE_IDEAS.md` (deleted 2026-08-24, everything else in it either already shipped
  or already tracked above) - three genuinely new, unclaimed ideas: a 1-click Instagram/Facebook social
  card generator per show (poster + logo + opening countdown + QR code); automated society milestone
  badges (e.g. "100+ productions", "3+ Best Overall Show wins"); a browsable programme-cover/poster
  museum page (overlaps the posters-gallery idea above, but framed as a designer-credited visual archive
  rather than a plain gallery).
- From an untracked `AUDIT_AND_RECOMMENDATIONS.md` (deleted 2026-08-24 - its case-insensitive-index,
  WAL-mode/busy-timeout, and admin.py-split recommendations were all already independently done) - five
  genuinely new, unclaimed ideas: removable filter "chips" above `/season`/`/awards`/`/stats` tables; a
  poster lightbox/zoom on show pages; a zero-login "My Season Watchlist" (localStorage bookmarks + a
  personal .ics export); an "On This Day in AIMS History" homepage widget; an embeddable per-society
  JSON feed/widget for a society's own website. Also worth a note: a fuller interactive Leaflet/OSM pin
  map (colour-coded by region, filterable by tier) as a richer successor to the list-based Near-me
  toggle that shipped 2026-08-24, once venue pin coverage is higher.

## Housekeeping, low priority, no urgency signal

- Audit other societies for similarly stale/presumptive data (same shape as the venue-data fixes already
  done).
- A formal `LAUNCH.md` spec, written up retroactively (the site launched organically instead).
- Real image-content validation on poster uploads (would need Pillow, not built).
- ~~Periodically verify the nightly backup actually restores cleanly.~~ **Done 2026-08-24.**
  `verify_backup.py` restores a backup to a scratch copy and runs `integrity_check`,
  `foreign_key_check`, a table-count comparison against live, and a full rebuild of the derived
  tables (whose own verification raises rather than committing on disagreement). It runs
  automatically after every backup - see `docker-compose.yml` - so a bad backup shows up in
  `docker logs aims-backup` rather than at the moment you need it. Verified against the real
  production backup: integrity ok, zero FK violations, both rebuilds passed, 2,818 productions.
  Retention was also fixed: "keep the newest 14 files" covered only 3.5 days in practice, because
  a backup is taken on every container start and this session's own redeploys spent ten slots.
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
