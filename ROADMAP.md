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

## START HERE - audit of computed figures (2026-09-02, latest)

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

## Security audit of the Antigravity stint (2026-09-01)

> Claude audited the 63-commit Antigravity stint by reading the code and querying the live
> database, not by reading its log. **985 tests green at `e7fa1ea`+.** The engineering was solid -
> ownership is enforced on every vault mutation, uploads reuse `save_poster`'s Pillow validation,
> no `|safe` in any new template, CSP nonces intact, and the `season_for_date` change is
> advisory-only. Two things were wrong, one badly.
>
> ### FIXED, shipped and verified
>
> - **The Costumes & Props Exchange was publishing volunteers' contact details.**
>   `/exchange/<id>` rendered `contact_name` and `contact_phone` - a named person and a personal
>   mobile, as a `tel:` link - on a page `robots.txt` lets crawlers index, from a form that never
>   said so. **This was live, not hypothetical**: the one real listing carried a committee
>   secretary's name and working mobile. Cleared from production
>   (`scripts/backfills/clear_exchange_personal_contacts.py`), then fixed in code: stripped in the
>   *route* not the template (a template guard still ships the number in the HTML), form no longer
>   collects either field, `vault_edit` NULLs both on save. Darragh's decision: details visible
>   only to a signed-in society, society address only.
>   **Antigravity's own test asserted `"Mary Kelly" in html`** - it encoded the exposure as
>   intended behaviour. Inverted, with the reason recorded beside it.
>
> - **Society invite codes could be guessed in about eight minutes.** `adjective-noun` from two
>   40-word lists = 1,600 codes; with ~21 live that is 1 valid code per 76 guesses, at a 10/min
>   limit. `invite_words.py` justified 1,600 as "comfortable headroom", which is a *collision*
>   argument - nobody had asked the *guessing* question. And a society code is not read-only: it
>   edits that society's shows and uploads posters. Now `adjective-noun-NNNN` (~16 million) plus an
>   hourly cap on `/society/login`. Old two-word codes still work deliberately - see below.
>
> ### OPEN - ranked, none urgent
>
> **Items 2, 3 and 4 were all closed on 2026-09-02 - see the block above.** Only item 1 remains,
> and it is outreach rather than code.
>
> 1. **17 of 21 active invite codes never expire.** The only 4 with an expiry are the ones the
>    magic-link flow minted itself. Widening the generator does nothing for codes already issued.
>    Retire the 17 by moving those societies onto magic links.
> 2. ~~Magic-link tokens are stored in plaintext.~~ **Hashed 2026-09-02.**
> 3. ~~`/society/request-access` has no email validation and no honeypot.~~ **Done 2026-09-02**,
>    along with surfacing `notify.send` failures to the moderator.
> 4. ~~Decision pending on exchange contact details.~~ **Decided and shipped 2026-09-02:** restored
>    behind the society login, no WhatsApp link.
>
> ### Direction agreed on society access
>
> Magic links are the front door; codes stay as the deliberate fallback for a committee meeting
> where nobody has email to hand. They are **not rivals** - approving a magic link mints an invite
> code and the link just opens a session keyed to it, so "replace codes with links" would mean
> rewriting the session model for no gain. What needed to die was the weak permanent code, not the
> concept.
>
> ### Two errors of Claude's own, corrected
>
> - `AGENTS.md` told Antigravity the rate-limiting finding was unfixed. It was already fixed -
>   `app/rate_limit.py` keys on `CF-Connecting-IP`. Claude had grepped `ProxyFix` and never opened
>   that file.
> - `AGENTS.md` and this file both claimed the society-links queue would "release 529 award rows".
>   That module's own docstring says most names never match. 8 are linked against ~9 predicted, so
>   Antigravity hit the expected number while reporting against a target that never existed.
>
> ### On trusting the handback log
>
> It is well kept - dry-run-then-apply on every backfill, PRs for the risky work - but it
> **overstates**. "unlinked awards 499 -> 0" describes an outcome that did not occur; that number is
> unchanged at 529 (the queue emptied via `no_match`, which is correct). Its tests are thorough but
> lock in whatever the code did, so they confirm behaviour rather than question it. Verify claims
> against the database, not the log.

---

## START HERE - where things stand (2026-08-29, end of session)

> ### The code side is in good shape. What is left is mostly not code.
>
> **20 commits** since `6230357`, all deployed and verified live. **901 tests green** (from 776).
> **CI now runs on every push** (`.github/workflows/test.yml`) - it does *not* gate the deploy,
> because GitOps polls the branch and not the workflow, but a red `main` is now loud.
>
> #### The single most valuable thing left is not a feature
>
> **55 of 67 upcoming productions have no poster. 176 of 194 societies have no logo.** The site is
> now poster-led on the homepage, `/season` and society pages, so every one of those renders as a
> blank card next to real artwork. The tooling to close this all exists and is finished:
>
> - `/admin/missing-posters` - the chasing list, soonest first, with a one-click **Copy message**
>   or inline login-code generation per row.
> - `/admin/society-checklist` - one row per society showing every gap, with **checked, nothing to
>   get** so it can be finished.
> - Each society's own dashboard flags its missing posters from their side.
>
> Nobody has worked the list yet. **This is an outreach job, and it is the biggest visible
> improvement still available.**
>
> #### Other things only Darragh can do
>
> - **3 pending photo submissions** at `/admin/photo-submissions` - Carnew x2 and St. Mary's Choral
>   Society Clonmel. Real society history waiting to be transcribed.
> - ~~**Ask Brandon at Oyster Lane for 1998-2010.**~~ **Closed 2026-08-29 - Darragh's call, the
>   history is there.** Confirmed against the live database: Oyster Lane holds 18 seasons running
>   from 06/07 to 27/28. Do not re-open this from the multi-upload bug story - that bug is fixed and
>   the gap it caused has since been filled by other means.
> - **`/admin/historical-society-links`** - 64 printed names undecided, ~10 minutes, unlocks 265
>   nominated productions that are missing only because their `society_id` is null.
> - **FAQ is live and empty** (`/admin/faq`, 0 entries). Needs Darragh's voice.
> - **1 open feature suggestion** at `/admin/suggestions`.
>
> #### Open dev work, ranked
>
> **4b and R6 shipped 2026-08-29** - both moved to `ROADMAP_ARCHIVE.md`. What is left:
>
> 1. **Item 3 - re-match unmatched ShowTimes reviews.** 52 still pending; only about 3 will clear.
>    Low value, be honest about that before spending a session on it.
> 2. **R8 - `public.py` is ~1,930 lines.** A judgment call, not a defect. Do not let it jump the
>    queue.
>
> #### Lifecycle status is now set for all 194 societies (2026-08-29)
>
> It had been NULL on every row since the field shipped, so the coverage checklist could not tell a
> live society from a panto company with no records at all.
> `scripts/backfills/guess_society_lifecycle.py` filled every NULL from one signal - the last year we
> have any record of that society producing anything - giving **Active 141, Out of scope 28, Dormant
> 12, Closed 10, Unverified 3**. Chaseable societies dropped from 194 to 156.
>
> **These are guesses and are labelled as such.** The thresholds sit deliberately on the generous
> side (a wrong "Active" costs one email; a wrong "Closed" quietly drops a living society), and
> `classify()` is pure and separately tested so the lines can be argued with. Only NULLs are filled,
> so a moderator's decision always wins and a re-run never overwrites one.
>
> **Two small piles want a human glance**, and only Darragh can give it:
> the **10 marked Closed** (all last produced 2011-2017), and the **3 marked Unverified** - Armagh
> Creative Theatre Group, KATS and Seven Woods Productions, which sit in the Sullivan tier yet have
> no production on record at all. Also worth knowing: several rows classed by production history are
> arguably *Out of scope* by nature (Belfast School of Performing Arts, Currid School of Performing
> Arts, Phoenix Performing Arts College, two youth theatres) - they produced, so the data called them
> Closed or Dormant, but a human would likely call them out of scope instead.
>

> #### Design work that needs Darragh's eye, not mine
>
> Both came out of the 2026-08-29 site audit. Both are visual calls, and the last one of these went
> much better as a mockup than as a direct edit:
>
> - **Stat tiles are the clearest summary pattern on the site and only `/venues/<slug>` uses them.**
>   Society pages carry the same information as beige tag pills, which scan far worse. The coverage
>   checklist already computes the numbers.
> - **Society logo placeholders.** With 176 of 194 missing, the flat initials box is the *normal*
>   case, and it sits directly above a colourful poster wall on the societies that have one.
>
> `/venues/<slug>` and `/stats/trends` (Decades) came out of that audit as the two best-structured
> pages on the site - useful models for either of the above.
>
> #### Loose ends worth knowing
>
> - **Accessibility is only markup-deep.** `aria-label` on pagination, `role="status"` on flashes,
>   `aria-pressed` on the theme toggle. Never tested with a screen reader, at 320px, or with images
>   disabled - and the site leans much harder on imagery than it did yesterday.
> - **Gemini's review** (`enrichment/feedback_gemini.md`) is fully triaged. Its `.replace()` count
>   query, healthcheck and log rotation all shipped; its `before_request` suggestion was **wrong as
>   written** (it proposed exempting every `feeds.*` endpoint, but `/sitemap.xml` reads both derived
>   tables) and was implemented narrowly instead. Its root-scripts point is done. Only "split
>   public.py" remains, which is R8.
> - **Two mockups exist and are local-only** (`mockups/` is gitignored):
>   `society_and_home_redesign.html` (built, shipped) and `society_checklist_grid.html` (built,
>   shipped). The checklist mockup carries **no contact fields**, so the privacy caveat this file
>   used to attach to that item never applied.
> - **A stale `aims.db` copy still sits at the old `CACHEDEV1` path** - see CLAUDE.md's warning.
>   Check the mtime before trusting any copy pulled down.
>
> #### Working notes for a fresh session
>
> - The repo checks out **CRLF**. A LF-pattern search/replace silently matches nothing. Read
>   universal, write back with `newline="\r\n"`.
> - **Verifying a deploy:** compare `sed 's/\r$//' <file> | md5sum` against the same command on the
>   NAS's GitOps checkout at `/share/CACHEDEV2_DATA/Data/config/portainer/compose/8/`. A raw
>   `md5sum` disagrees purely on line endings.
> - `mockups/`, `uploads/` and `enrichment/` are all gitignored. The 87 production posters were
>   pulled into local `uploads/` so local dev renders images.
> - Jinja wraps long lines; a test asserting a sentence that spans a template line break will fail.
>   Put the sentence on one line in the template rather than weakening the test.
> - Scripts moved (2026-08-29): one-offs live under `scripts/{backfills,enrichment,maintenance}/`
>   and compute the repo root as `Path(__file__).resolve().parents[2]`. The documented operational
>   entry points stayed at the root. See CLAUDE.md.

---

## What shipped on 2026-08-29

Kept short deliberately; the commits carry the detail.

| Commit | What |
|---|---|
| `579beb2` | The 16-item small queue (M1, V1-V5, T1-T5, F1-F4, C1-C4) |
| `53b6ef9` `0aa181b` | Two Thurles bugs: decades-old shows listed as upcoming, and blank placeholder rows |
| `c608085` | **The design pass** - container 900 to 1240px, a type scale, society history rebuilt, poster-led homepage |
| `5b3aa4a` | **Real bug** - a CSRF failure returned an unhandled 500 whose error page also failed |
| `f8c61b4` `8fd6467` | Poster-coverage workflow + inline login-code generation |
| `e42f55e` `e4c5bfb` | CI, which immediately caught a test that only passed because PyMuPDF happened to be installed locally |
| `fffaf91` | Show detail page restructured around the show's own facts |
| `c6f3d43` | Derived-table freshness check narrowed (correctly, unlike the review's suggestion) |
| `3aec2d7` | **Society coverage checklist + lifecycle status** (plan item 7, the biggest item on the board) |
| `1f671a7` | `datetime.utcnow()` replaced across 15 call sites, format preserved byte-for-byte |
| `76e882c` | A society's posters as a wall on its own page |
| `bdd3f6e` | Root scripts reorganised; `society_names.py` moved into the app |
| `512b1d7` | Audit fixes - `/season` gets the homepage's cards, narrow container for prose pages |

**Verified on a real device:** multi-upload (five distinct images, one submission) and the mobile
awards table. Both were the things pytest structurally could not reach.
---

## 📌 OUTSTANDING TO-DO

Everything genuinely open that isn't already covered in the START HERE block above.

Rejected on the 2026-08-28 code-review diff, do not re-add: the `search.py` f-string (callers pass
hardcoded table names, so there is no injection risk), and a numbered migration framework (42
startup PRAGMAs cost nothing; this is a preference, not a bug). Opus's `updated_at` trigger point
does stand — all 9 triggers in `schema.sql` are FTS sync triggers, none touch `updated_at`.

### Still open from the older backlog (not in the plan, deliberately)

~~Person identity resolution~~ (**built 2026-08-29**, see below); costume/prop listings (per show —
scope settled, needs a data-model session); social card generator (needs a mockup); society edit
audit log (ready to build, just not selected); repertoire finder (blocked until Darragh says what
committees actually asked for); genre filtering on `/titles` (blocked on a taxonomy decision);
pantomime category (his scope call); the 60-society logo redo still out with Gemini.

**One of these connects to the poster/logo gap in START HERE, which raises its value:**

- ~~`import_logo_candidates.py` has never been run against production~~ - **checked against the live
  database 2026-08-29 and this was wrong.** All 11 `found: true` rows were imported: 10 approved and
  applied, 1 still pending. The only one left is Rathmines & Rathgar, whose logo is an **SVG**, which
  `fetch_logo_candidate` (Pillow) cannot decode - it needs a raster URL, not a re-run. Societies with
  a logo now stands at 18 of 194.
- **Venue duplicates are 8 clusters, not 5** (16 venue rows), and they are now surfaced with a
  dashboard counter and a **Different venue** dismissal, so the queue can actually be cleared. See
  `/admin/venue-directory`.

### Known-unfinished from earlier sessions, still true

- **The 4 place-name artifacts** (`Cork`, `Wexford`, `Cork run`, `40th Anniversary (March run)`) are
  `shows.venue` text naming no building.
- **54 stale orphaned `historical_reviews` rows** (was recorded here as ~112; re-counted against
  the live database 2026-09-02). Real, but not deleted pending a better verification method.
- **297 `historical_results` rows with `category_name IS NULL`**, 274 pre-2001 — needs real archival
  research, not a scrape.
- **Off-box backup** — backups still sit on the same volume as the database. A NAS config job.

---

**825 tests green (as of `579beb2`, 2026-08-28), no known bugs.** (Everything below this line predates
that commit and is kept only for the historical detail it still carries — see START HERE above for
current state.)

**Deploy state, checked directly against the running container 2026-08-28:** `8b120ad` (map dark
mode + filters) and `37c7e61` (the logo-candidate review queue) **are now live** - GitOps picked
them up on its own, which is what the old "not yet deployed, needs a Portainer click" note here was
waiting for. That note is now resolved and has been removed.

**Tonight's two commits (`658eb0a`, `7ef4b06`) had NOT deployed yet** when last checked ~20 minutes
after the push - `/app/CHANGELOG.md` in the container still showed the previous top entry. Nothing
is wrong: the data changes were direct DB writes and are already live regardless, and only the
*changelog entries* are waiting on the container picking up the new files (`changelog_sync` runs on
startup). **First thing next session: confirm the two new changelog entries are actually published
on `/suggestions`** - the Oyster Lane correction is a public trust statement and should not sit
unpublished.

~~**The logo review queue still needs one more step.**~~ **Resolved - it had already been done.**
Verified against the live database on 2026-08-29: `logo_candidates` holds all 11 rows, 10 approved.
See the corrected entry above. Kept here only to stop a future session re-deriving the same wrong
conclusion from this file.

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

**Logo discovery came back and was scored, 2026-08-25 - 11 verified good, 60 sent back for a redo.**
Only 7 of 192 societies had a logo on file; 71 have a website and no logo, so that was the target
list. Result: 11 `found: true`, 60 `found: false`.

**All 11 found logos independently verified** - every `logo_url` fetched directly (not taken on
Gemini's word), every one a real image with a matching content-type: Baldoyle, Belfast Operatic,
Belfast School of Performing Arts, Boyle, Fortwilliam, Killarney, Leixlip (LMVG), Malahide,
Rathmines & Rathgar, St. Agnes Choral, St. Michael's Theatre. **Ready for Darragh to review and
approve/reject each one via `/admin/societies`** - no bulk-logo-import script exists (today's
uploads are all one-at-a-time, through `save_poster()`'s decode/resize path), so approving one
means uploading it there by hand for now; a real import path is worth building once we see how many
survive review across a bigger batch.

**The 60 "not found" rows all carried the identical templated line** - "Site has no distinct logo,
header is text-only or site is unreachable," word for word, all 60. Same shape of problem as two
other tasks today (the 14 archive pages, the founding-years file) - reads as a default, not 60
independently-checked results. Worth noting the severity is lower here than those two: a false
negative (missed logo) is recoverable, not fabrication. Tried to spot-check reachability directly
and hit the same DNS-restricted-sandbox limitation flagged earlier today, so couldn't independently
confirm which of the 60 are genuine misses. **Sent back for a redo**:
`enrichment/LOGO_REDO_BRIEF_2026-08-25.md` + `enrichment/logo_worklist_redo.json` (both gitignored,
the same 60 rows reset to blank) - same firmer instruction as the archive redo, no bare
"unreachable," a real per-site observation or a real HTTP status required. **Not yet returned -
check `enrichment/` next session.**

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
| historical_results rows | 4,989 (was 5,010; -21 in the Oyster Lane rollback + duplicate cleanup, 2026-08-28) |
| 26/27 productions with real dates | 73 of 117 rows (46 set from the official Gilbert schedule, 2026-08-28) |
| Award rows with no society match | 539 across 69 distinct names, 0 decisions made yet |
| Photo submissions pending | **3** (ids 5, 6, 7 - see START HERE; #6/#7 are duplicates of one image) |
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
tooling to validate it already exists: `scripts/backfills/import_society_archives.py` has the `TRUSTED` list, the
SHOW_RENAMES canonicalisation and the +/-1 year duplicate guard, and the worklist carries
`known_productions_for_cross_check` so the overlap test runs the same way.

**Scope Rule (Crucial for transcription & imports)**: Exclude straight plays (e.g. *Sive*, *The Field*,
*The Plough and the Stars*, *The Weir*, *Steel Magnolias*, *A Few Good Men*, *Stones in his Pockets*,
*One Act Nights*, pantomimes, non-musical concerts) from society production histories. AIMS tracker
is strictly focused on musical theatre productions. Societies with "Musical & Dramatic" in their name
often list both; only musical theatre productions should be kept.


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
scored **identically to already-known results already documented in `scripts/backfills/import_society_archives.py`'s
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

**The rule above is not enough, and Oyster Lane proved it (2026-08-28).** The overlap cross-check
this whole section rests on **only validates years we already hold data for - precisely the years
the import is adding nothing for.** Every row that actually contributes new information is, by
construction, in a year with nothing to compare against, so it is never checked. Oyster Lane passed
into `TRUSTED` on the strength of matching the checkable years and its *new* rows were still wrong
(titles attached to the wrong years); a society reported it, and all 18 rows have been rolled back.
Two corollaries, both learned the hard way:
- **A score below the pack is a signal in itself.** Oyster Lane scored 69% when every other trusted
  society scored 93-100%. That was printed at the time and moved past. It should have pulled it out.
- **The check tells you the transcriber read the page, not that the data is right.** Those are
  different claims. Treat a pass as "worth a human look", never as "safe to import unattended".

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
2. ~~**Person identity resolution, internal only.**~~ **BUILT 2026-08-29** - `app/people.py`,
   `/admin/people`, `people` + `person_aliases` + `dismissed_person_pairs`, 22 tests. The matcher
   blocks on surname and only scores the given name, which is both faster (84 candidates from 2,267
   real names in 0.04s, versus 2.5M naive pairs) and more accurate - "Alan McClarty"/"Alan McCarthy"
   score 87% on a whole-string ratio and are two different people. Validated against the real
   production name list before any UI was written; that pass caught two defects, a father/son pair
   ("Sean Costello" vs "Sean Costello Senior") being merged at full confidence, and "/" not being
   treated as a multi-person separator. **No public surface, and the archive is never rewritten** -
   a merge writes only to the alias tables, so every award row and credit keeps its original text
   and any merge is undoable. Original justification kept below.

   The only parked item with *measured* harm rather
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
