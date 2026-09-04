# Roadmap

Tracks the current phase of work and genuinely open items, so a new session (after `/clear` or a fresh
start) can pick up without re-deriving context. Update this file - don't just say the plan out loud in
chat - whenever the phase changes.

**Pruned four times now** (2026-08-20, 2026-08-23, 2026-08-24, 2026-09-04) - each time because it had
grown into a chronological session log of mostly-shipped work, and CLAUDE.md's own rule says to read it
at the start of every session. Full history (every Round, every Phase, every session's blow-by-blow) is
preserved verbatim in `ROADMAP_ARCHIVE.md` - nothing was ever deleted, just moved out of the file that
gets read every session. This file holds only: the current phase, and a flat list of items that are
genuinely still open (not started, explicitly parked, or blocked on something). When a session fully
resolves an open item, move its entry to `ROADMAP_ARCHIVE.md` rather than letting resolved items
accumulate here again.

**The fourth prune (2026-09-04) found the deeper problem.** The previous three pruned for *length* -
the file was a session log. This one pruned for *accuracy*: of the 13 items its numbered backlog still
listed as open, **seven had already been built**, some for over a week. Length was the symptom; the
cause is entering an item here and never re-checking it against the code. **Before listing anything as
open, grep for it.** The file has now been wrong in both directions - claiming work was outstanding
when it had shipped, and claiming a security finding was unfixed when it had been fixed.

## START HERE - fresh site review, two fixes shipped and verified live (2026-09-04)

> Darragh asked for a fresh full-site review (not a rehash of the backlog) and to fix whatever
> turned up. Two real findings, both fixed, both deployed and confirmed live. **1075 tests green.**
>
> - **`sitemap.xml` / `robots.txt` / `calendar.ics` all advertised `http://`** (`6197908`). Same
>   root cause as the `og:` tags fix (2026-09-02, see the block below): the Cloudflare Tunnel gives
>   the origin no `X-Forwarded-Proto`, so `url_for(_external=True)` honestly reports http. This is
>   the same bug in three more places `absolute_url()`/`notify.link()` hadn't reached yet - all 19
>   call sites in `app/blueprints/feeds.py` swapped over. Two existing tests had themselves codified
>   the bug as correct (one literally asserted the http fallback was right) - rewritten, not just
>   the source. Verified live: `curl https://darraghc.ie/showcal/sitemap.xml` and `/robots.txt` both
>   show `https://` now (the one remaining `http://` in the sitemap is the XML namespace URI, which
>   is supposed to be that).
> - **Venue detail pages scrolled sideways on a phone** (`b8d9d39`). 4 of 15 sampled venues
>   overflowed 3-38px - `.detail-list`'s grid track was a bare `1fr` (really `minmax(auto, 1fr)`),
>   so a long value (a website URL) could force the page wider than the screen. Fixed with
>   `minmax(0, 1fr)` + `overflow-wrap: break-word`, same overflow class as the `.run` grid bug fixed
>   2026-09-02. Verified against a full crawl of every venue detail page at 320px/390px, not just
>   the 3 named venues. Confirmed live via the actual versioned CSS URL the site serves (an
>   unversioned fetch showed Cloudflare's edge cache, which is expected and harmless - the versioned
>   URL every page actually links to already serves the fix).
>
> **One more overflow found, not fixed:** a single venue with an unusually long name overflows at
> 320px via its `<h1>`, not `.detail-list` - a different bug, out of scope for this pass. Worth
> queuing.

---

## START HERE - share previews, and a scheme bug worth knowing about (2026-09-03)

> Darragh sent a photo of a WhatsApp preview showing a gold "M" on a **crimson** field. Three faults
> stacked, all live on every shared link, all fixed in `a016554`.
>
> 1. **It was the old logo.** The header switched to a DC monogram on 2026-08-30; `favicon.svg` and
>    every PNG under `static/icons/` kept the previous "M" for three days.
> 2. **Cloudflare was mangling it.** `icon-512.png` was RGBA. Over **https** Cloudflare's image
>    optimisation re-encodes it to RGB and composites the transparency against crimson - corner pixel
>    `(11,15,20)` becomes `(200,16,46)`. Over http you get the correct file. Every share scraper uses
>    https. **All brand assets are flat RGB now**; a test fails if the card regains an alpha channel.
> 3. **Every absolute URL on the site says `http://`.** This is the one worth remembering. The
>    Cloudflare Tunnel terminates TLS and hands the origin a plain request with **no
>    `X-Forwarded-Proto`**, so `ProxyFix(x_proto=1)` has nothing to promote and
>    `url_for(_external=True)` / `request.url` honestly report http. Harmless for a link a browser
>    follows; not harmless for `og:url` and `og:image`. Use the new **`absolute_url()`** Jinja global
>    (built from `SITE_URL`, same as `notify.link`) for anything that must be absolute. A test fails
>    if `content="http://` reappears in the head.
>
> `scripts/build_brand_images.py` regenerates the card and all four icons from the header SVG's own
> geometry, so the mark cannot drift from the logo again. Needs `fonttools` (deliberately not in
> requirements.txt - one-off asset build).
>
> **WhatsApp caches previews hard.** After a change, share the link with `?x=1` appended to see it.
>
> ### Also shipped 2026-09-03: the society checklist reworked (`a43228e`)
>
> Every cell used to be its own form, so a tick or a status change reloaded all 195 rows - and the
> grid re-sorts as gaps close, so the row you were about to click had moved. It is one form with a
> sticky Save bar now, plus filters for tier, missing-field, progress, upcoming-show and name.
>
> **The correctness question is partial saves.** An unticked checkbox is indistinguishable from one
> that was never rendered, so a save made while filtered would otherwise read as "nothing is ticked
> anywhere" and wipe every society not on screen. Hidden `rows` and `editable` markers name what was
> actually rendered, and only those are reconciled. There is a test for exactly that.

---

## Posters are a lead-time problem, not a coverage problem (2026-09-02)

> **This corrects the framing used all through the sessions below, including by Claude.** Darragh:
> *"we shouldn't worry too much about posters - normally they're not designed until closer to
> showtime - we should always prioritise posters for the next 2/3 months."*
>
> **The live data agrees emphatically.** Of 68 upcoming productions on 2026-09-02:
>
> | Opening | Upcoming | No poster |
> |---|---|---|
> | within 1 month | 7 | **0** |
> | 1-2 months | 7 | 7 |
> | 2-3 months | 13 | 10 |
> | 3-6 months | 14 | 12 |
> | 6+ months | 27 | 25 |
>
> **Every show opening within a month already has its poster.** The process works. "54 missing
> posters" - repeated in this file, in `HANDBACK.md`, in `AGENTS.md` and by Claude all session as
> *the single most valuable thing left* - was mostly counting the calendar. The real job is the ~17
> in the one-to-three-month band, and **15 of those 17 societies have no active login code**, which
> is the actual bottleneck: you cannot ask for a poster from someone who cannot upload one.
>
> `POSTER_CHASE_DAYS = 93` in `app/blueprints/admin/_shared.py` now scopes the dashboard counter and
> `/admin/missing-posters`. Anything further out is listed for reference, not as work. This is the
> `permanent-vs-fixable-queues` rule at the other end - a counter including a show 18 months away can
> never reach zero.
>
> ### The login-code bottleneck is CLEARED - the ball is with Darragh
>
> 15 of the 17 chaseable societies had no active login code, so they could not upload a poster even
> if they had one. All 15 were minted on 2026-09-02 via
> `scripts/backfills/generate_poster_chase_codes.py` (dry-run then applied). **All 17 chaseable rows
> now show a code on `/admin/missing-posters`, each with a Copy message button.** Every one of the
> 15 societies is reachable - all have Facebook and Instagram on record, 8 also a website.
>
> **Nothing further is blocked on code.** The next step is Darragh sending 15 messages.
>
> **Paste-to-upload shipped the same day** (`b36d39a`), which is what makes those messages worth
> sending: a committee member copies their poster off their own Facebook page and presses Ctrl+V on
> the form. Live on both show forms, both logo forms and the new-show form. See
> `app/templates/_paste_upload.html` for why it is single-file only and why there is no
> drag-and-drop.
>
> **One thing to not undo:** the preview builds a `data:` URL via FileReader rather than
> `URL.createObjectURL`. The CSP is `img-src 'self' data:` and does **not** allow `blob:` - an
> object URL renders as a broken image and logs a violation. That was invisible to the unit tests
> and only turned up when a real browser was driven. Do not "simplify" it back to an object URL,
> and do not widen the CSP for a thumbnail.
>
> These codes **expire 2027-05-31** (end of the 26/27 season), unlike the ones
> `admin.generate_society_code` mints. Active society codes now stand at 17 never-expiring - still
> the open audit item, unchanged - and 19 with an expiry. **Do not "fix" the new ones to match the
> old ones**; the old ones are the defect.
>
> **Not applied to logos.** 174 of 195 societies have no logo and that has no seasonal timing; it is
> a real, chaseable gap all year round.
>
> **Do not quote a raw "N missing posters" total as a deficiency again.** Say how many are chaseable.

---

## Audit of computed figures (2026-09-02)

> Prompted by the show-page circuit line turning out to be wrong on the live site for months with
> nothing catching it. **Method: recompute each public figure independently from the live database
> and compare, rather than reading the code.** The audit scripts are in scratch; the method is the
> part worth keeping.
>
> ### Checked and CLEAN - verified, not assumed
>
> `historical_results.year = season_start_year + 1` (**0 mismatches in 4,847** linked rows, so the
> comment in `title_detail` claiming that relationship is trustworthy) · production season vs its
> show's opening date (0 disagreements) · society production count, index card vs society page
> (exact) · homepage upcoming count · revival "quiet since" · "rare gem - staged once" · wins never
> exceeding total award records · no reversed opening/closing dates · no orphaned productions ·
> **every one of 523 venue strings maps to a venue page** · title spellings (1 trivial case).
>
> **Two `season_start_year + 1` sites were suspected and turned out correct** - both are scoped to
> archive-only productions (`NOT EXISTS ... shows`), where the award year is the only year there is.
> Do not "fix" them.
>
> ### Found and fixed
>
> - **The circuit line on every show page was wrong twice over** (`9861e90`). `+1` labelled autumn
>   productions with the following year; "most recently" ordered by season alone so it could name a
>   production that had not happened yet. Now a span of seasons, and only ever a show that has
>   opened.
> - **`/stats` promised a cancelled filter that no longer exists** (`df147f4`). `shows.status` was
>   dropped in August as unreliable; the copy still claimed the guarantee.
> - **A decade leaderboard named a society by whichever variant SQLite picked** (`bccc8f8`). Three
>   societies carry two archive names.
> - **One production deleted from production data** (`b9cbf32`, dry-run then applied): "A Chorus
>   Line (Cancelled)", Maynooth, May 2020 - a COVID casualty recorded by putting the cancellation in
>   the title, and counted as a real staging. Productions on record 2942 -> 2941. Darragh's call.
>
> ### Round three found no new defects - it confirmed three claims the docs make
>
> Diminishing returns reached, which is the signal to stop rather than keep digging.
>
> - **The award-category merges are right.** "Best Chorus" (1977-2025) -> "Best Choral Singing"
>   (2026 only) and "Adjudicator's Special Award" -> "Spirit of AIMS" each have **zero overlapping
>   years**, which is what a clean rename looks like. "Best Choreography" and "Best Choreographer"
>   ran in parallel in **six** years (2019, 2020, 2022-2025), so keeping them separate is right too.
>   The August note claiming both of these was "confirmed year-by-year" is trustworthy.
> - **Adjudicator data is clean.** One season+tier carries two adjudicators (13/14 Gilbert, Richie
>   Ryan / Damien Murray) - the real mid-season change the table was rebuilt to allow. **0 of 876**
>   reviews are attributed to an adjudicator not assigned that season.
> - **Orphaned reviews are 54, not ~112.** This file's older figure is out of date; correcting it
>   here rather than leaving a stale number to be re-derived. Still open, still awaiting a better
>   verification method than "it looks unmatched".
>
> ### Known latent, deliberately not changed
>
> `/stats/trends` groups "most-staged shows" on the raw `historical_results.show` string rather than
> a normalized key. Exactly one title in the whole archive is recorded under two spellings
> (Honk / Honk!) and the 2010s top five is identical either way. Fragility, not a defect. It becomes
> real if a bulk import ever introduces spelling variants.
>
> ### The thing worth carrying forward
>
> **Two of my own checks were wrong before the code was.** A revival query used `MAX(season)` on a
> string, so `'99/00'` beat `'18/19'`; two tests used year 2098 as "the future" and the productions
> rebuild resolved `98/99` back to 1998 through `season_start_year()`'s 50-pivot. Check the check
> before believing the finding.

---

## UX sweep (2026-09-02, earlier)

> Full write-up published as an artifact: **ShowCal Polish Pass**
> (https://claude.ai/code/artifact/2837b038-6e88-4737-b011-08a249211ca2) - five ranked proposals,
> each with a before/after rendered in the app's own tokens, plus two charts built from live data.
> Read that rather than re-deriving it.
>
> ### Method, because it changes what the findings are worth
>
> 18 public routes rendered at 320/390/1280px against **the live site**, with
> `document.scrollWidth` measured against the viewport on every one - not a screenshot review.
> **Every page returned 200.** Three of the four faults found are invisible by eye because the
> overflow reads as padding. The probe is at `scratchpad/overflow_audit.py` if it is worth keeping;
> it is ~90 lines and would work as a CI check.
>
> ### Fixed and deployed (`0804ec6`)
>
> Four real mobile layout faults - the site scrolled sideways on a phone. `/awards` on **every**
> phone (an uncapped `<select>` sized to a long award-category name); `.society-hero`'s mobile
> collapse **never applied at any width** (equal specificity, later in the file than
> `.detail-hero`'s media query); `.meta-chips span` nowrap on chips holding venue names; `.run`'s
> mobile grid using `1fr` where desktop correctly used `minmax(0, 1fr)`. Also set
> `overflow-wrap: break-word` on `body` - **nothing in 99KB of CSS set it at all**.
> Re-measured after: 36 of 36 page x width combinations scroll vertically only.
>
> ### DECIDED with Darragh, 2026-09-02. Two of four shipped (`59d4061`).
>
> **The governing call, and it outranks any mockup:** *"this is an amateur organisation, the awards
> are secondary not something that they should be flaunting openly."* Award counts are never a
> flagship number. Activity (productions, years active, next show) can lead; ranking (wins,
> placings) goes lower and never in a grid comparing societies. See the `awards-are-secondary`
> memory.
>
> | # | Job | State |
> |---|---|---|
> | 1 | Society page: awards below the fold, header = Productions + Active-since | **SHIPPED** |
> | 2 | Playbill placeholder + homepage/season card restack | **SHIPPED** |
> | 3 | Societies index rebuild - **no award number on the card at all** | **SHIPPED** |
> | 4 | /stats charts - productions by decade + shows by region | **SHIPPED** |
>
> **All four are done.** 1020 tests green.
>
> **Job 3, as built.** Two aggregate queries for the whole page, run *after* pagination so they
> only cover the ~50 rows being drawn. A test renders 40 societies and fails above 30 queries - an
> absolute ceiling, not a comparison, because a ceiling is what actually protects the page. New
> `society_monogram` filter (WLOS, TMS); `initials()` stays at two characters for the poster boxes
> it was written for.
>
> **Job 4, and a correction to what this file said.** The warning here that `productions` stores a
> two-digit season, so a decade chart would confuse 1912 with 2012, was **wrong** - checked against
> the live database rather than assumed. `productions.season_start_year` is a real four-digit
> INTEGER spanning 1911-2027; the ambiguity was resolved when the table was built. (The trap is
> real for `season_start_year()` the *function*, whose 50-pivot cannot tell 1911/12 from 2011/12 -
> that is what its own docstring warns about, and it is not what this column is.) Left here rather
> than deleted so a future session does not re-derive the same wrong caution.
>
> Neither chart needed a new query: both fold out of rows `stats()` already computed for its season
> table and its chip strip, so a chart cannot drift from the total printed above it. Hand-rolled
> SVG, no library, no CSP change.
>
> **Deploy policy, agreed same day.** GitOps auto-deploy stays for fixes, data work and internal
> changes. Anything a visitor or committee member can *see* gets described to Darragh before the
> push. First applied to `59d4061`.
>
> **One deviation worth remembering:** the mockup showed a solid gold Tickets button and Darragh
> approved it; built green instead and flagged it, because gold on the button costs the run dates
> their exclusive claim on gold. He kept green. Flag deviations, don't absorb them.
>
> **A flaw the mockup hid.** The first playbill carried title, society *and* dates. Correct in
> isolation, wrong in place: the card body repeats the society and dates directly below, so every
> card said everything twice - the exact fault being fixed on the society page in the same commit.
> A component drawn standalone will not show you what it does next to its neighbours.
>
> ### The five proposals, as originally ranked
>
> 1. **Duplicate pills on the society page.** 4 stat tiles then 5 pills, 3 of which repeat a tile
>    verbatim. ~20 min. Do this first because it costs nothing.
> 2. **The playbill placeholder.** 55 of 67 upcoming shows have no poster, 176 of 194 societies no
>    logo - **the blank card is the normal card**, five in a row on the October homepage. Replace
>    the flat initials box with a designed playbill (title in Archivo, society, dates, rule) that
>    carries an "Add your poster" ask. Biggest visible win, and the only proposal that also chips
>    at the data gap.
> 3. **Homepage card hierarchy.** Five facts at one weight; the dates - the thing people came for -
>    are buried mid-sentence. CSS-only.
> 4. **The societies index.** The weakest page and a common search landing point. 143 societies,
>    3 underlined links each, and a gold initial badge that is **meaningless** (alphabetical sort,
>    so column 1 reads A, A, A). Needs production/win counts carried into the list query - they are
>    already computed for the coverage checklist. Watch for the N+1.
> 5. **Charts on /stats.** 2,857 productions, 5,019 award records, 114 years, **zero charts**. Two
>    single-hue SVG charts would carry most of the value; no library, no CSP change. The artifact
>    has both built with live numbers.
>
> ### Verdict on the question "should we slow down"
>
> **Slow the deployments; don't stop the polish** - two different questions. The feature surface is
> already ahead of the user base (an exchange with one live listing, a bulk-credits workbench, a
> watchlist, a date-anomaly auditor). GitOps puts a push in production in ~5 minutes with no human
> checkpoint, which was fine with no audience and is a different proposition now. All five
> proposals above are deliberately **not scope** - same pages, rendered better. None adds a table,
> a route or a queue.

---

## START HERE - security follow-ups closed (2026-09-02)

> **995 tests green.** Three of the four items left open by the 2026-09-01 audit are done; the
> fourth is Darragh's outreach, not code.
>
> - **Magic-link tokens are hashed at rest.** `society_access_requests` was rebuilt around a
>   `token_hash` column (SHA-256; the plaintext column is gone, not merely renamed, and a test
>   dumps the file to prove it). **Links already in societies' inboxes still work** - the URL
>   carries the plaintext and lookup hashes it. The token is now also minted at *approval* rather
>   than at request time, so a pending or rejected request has never held a usable credential.
>   `used_at`/`use_count` were added for a moderator's visibility.
>
>   **Links stay reusable for their 30 days, deliberately.** Single-use would break on an email
>   scanner's prefetch and buys nothing: the link is an alias for the 30-day invite code it
>   activates, so anyone who could replay one already has the other. Plaintext at rest was the
>   real finding; that is what got fixed.
>
> - **`/society/request-access` hardened.** Email shape check, honeypot (it emails Darragh on
>   every POST), and `notify.send` now *reports* whether it sent. The approval screen tells the
>   moderator when an email failed and hands them the link to pass on by hand - previously a lost
>   email and a delivered one looked identical.
>
> - **Exchange contact details are back, behind the login** (Darragh's call, 2026-09-02). A
>   listing can name a coordinator and a phone again; the route still strips all three for
>   anonymous viewers, and the form now states where they appear. No WhatsApp link - `wa.me` puts
>   the number in the URL, so it is UX with no privacy benefit; raise it separately if wanted.
>
> - **A time-bomb test was fixed, not the code.** `test_season_page_lists_shows_soonest_first`
>   hardcoded two September 2026 dates; on 2026-09-02 the earlier became the past and the test went
>   red on a clean `main` for a reason unrelated to sort order. It now derives its dates from today
>   and steps around the season boundary. **`main` was red before this session started** - the
>   "985 tests green" claim in the block below was 984.
>
> ### Still open from the audit
>
> 1. **17 of 21 active invite codes never expire.** Widening the generator did nothing for codes
>    already issued. Retire them by moving those societies onto magic links - **outreach, needs
>    Darragh**.
> 2. Whether to say anything to Castlebar MDS about the contact details having been removed from
>    their listing. Now that a coordinator name is collectable again behind the login, this is a
>    smaller conversation than it was.

---

## What is actually open (verified 2026-09-04)

**Everything here was checked against the code or the live database on 2026-09-04**, not carried
forward from the lists this replaces. That mattered: of the 13 items the old numbered backlog
still listed as open, **seven had already shipped** - the costumes/props exchange, the share
button, the poster lightbox, the checklist grid, person identity resolution, the filter chips and
the `match_show_for_edit` fix. They are in `ROADMAP_ARCHIVE.md` now. This is the fourth time this
file has grown a backlog of things that were already done; the fix is to check the code before
listing something as open, every time.

### Needs Darragh - not a coding task

- **Poster outreach.** 60 posters across 19 societies, recounted live (this file said 44 across 12,
  from 2026-08-25). All 17 chaseable societies have an active login code and a Copy message button
  on `/admin/missing-posters`. **Nothing is blocked on code** - this is 15 messages.
- **17 invite codes that never expire.** Retire them by moving those societies onto magic links.
  The 15 minted for the poster chase *do* expire (2027-05-31); the old ones are the defect, so do
  not "fix" the new ones to match.
- **13 lifecycle judgement calls** - the 10 societies marked `Closed` (all last produced 2011-2017)
  and the 3 marked `Unverified` (Armagh Creative Theatre Group, KATS, Seven Woods Productions).
  Several rows classed from production history are arguably *Out of scope* by nature instead.
  Propose, don't apply.
- **8 duplicate venue clusters.** The tooling shipped - `/admin/venue-directory` with a dashboard
  counter and a "Different venue" dismissal - but **the queue is untouched**: 0 dismissals
  recorded, still 118 venues. This is clicking, not research.
- **3 venue coordinates awaiting confirmation before import** - St. Mary's College Arklow, The
  Abbey Clane, Loughrea Temperance Hall. All three are street-accurate but none is confirmed at
  building level, and the Arklow pin's plausible failure mode is a different school 100m away.
  9 venues still have no coordinates, 4 of which are not buildings at all.
- **FAQ is live and empty** (`/admin/faq`, 0 entries). Needs his voice, not invented AIMS policy.
- **A pantomime category** - a scope decision about what the site is, not a build item.
- **The genre taxonomy for `/titles`** - blocked on his call on the taxonomy itself. No genre data
  exists in the schema; this is real new work, and the delegated half needs the full calibration
  protocol (hidden controls, canaries, citation per tag).
- **What committees actually asked for in a repertoire finder.** He confirmed they raise it with
  him directly; the shape (rights status + regional gap + recent stagings) is still a guess.

### Build items - verified not started

- **Social card generator** (per show: poster + society logo + opening countdown + QR). Confirmed
  absent from the codebase. The one backlog item that *gives* societies something rather than
  asking them for something, which is plausibly the lever that gets posters uploaded. Needs a
  mockup first.
- **Society edit audit log.** Confirmed absent. Societies share one login code, so there is
  currently no way to tell who made an edit or to undo it. Scope was already cut to the cheap 80%:
  build the append-only log, drop the revert UI.
- **Poster / programme museum.** Wanted, and genuinely gated on poster count rather than on the
  withdrawn content-supply argument. **Trigger was ~100 posters; we are at 60.** Confirm the
  number with Darragh - it was Claude's proposal, not his.

### Data work

- **55 orphaned `historical_reviews` rows.** Recounted live 2026-09-04. This file carried "~112"
  for weeks and 54 more recently; the count drifts, so **recount before acting**. Still not
  deleted, because "it looks unmatched" is not a test - see `docs/spikes.md`.
- **297 `historical_results` rows with `category_name IS NULL`**, 274 of them pre-2001. Needs real
  archival research into AIMS awards programmes; no query resolves this.
- **~10 unmapped historical societies** with no `societies` row (Bangor Operatic, De La Salle
  Waterford, others). Creating historical society records is a structural decision, not a bugfix.
- **28 orphaned Inactive societies** with zero shows and zero awards - retain or remove is a
  judgment call with no urgency signal.
- **4 place-name artifacts** - `Cork`, `Wexford`, `Cork run`, `40th Anniversary (March run)` are
  `shows.venue` text naming no building. Excluded from every venue worklist and never classified,
  but the underlying show rows still carry them.
- **Society founding years: still 6 of 194.** Low remaining yield - a crude scrape of the 74
  societies with a website found only 4 genuine founding statements. The method, if revisited:
  accept only a year the society's own site states explicitly *and* that does not contradict our
  earliest award record for them.
- **Remaining society production archives.** 9 were confirmed reachable with substantial year data;
  Killarney and Castlebar were transcribed and imported. Do this in-house with WebFetch, never
  delegated - and read the delegation findings in `ROADMAP_ARCHIVE.md` first, especially that the
  overlap cross-check only validates years we already hold, which is precisely the years an import
  adds nothing for. Oyster Lane passed that check and its new rows were still wrong.

### Found during this cleanup, not yet fixed

- **Four `url_for(..., _external=True)` call sites still emit `http://` in production.** Same
  Cloudflare Tunnel bug fixed in `feeds.py` on 2026-09-04 - these were simply not reached:
  `admin/access_requests.py:117` and `:199` (**the magic-link URL emailed to a society**),
  `public.py:1430` (the Add-to-Google-Calendar event details), and `show_detail.html:28` (the
  share button's `data-url`, so a cast sharing its own show to WhatsApp shares an http link).
  The fix is `notify.link(url_for(...))` or the `absolute_url()` Jinja global, exactly as used
  elsewhere. The two magic-link ones matter most: an emailed plain-http link looks wrong to a
  committee member and some scanners rewrite or strip it.

---

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
  off-box copy (QNAP HBS3 pointed at `/share/CACHEDEV2_DATA/Data/config/aims-web`) is the missing
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
