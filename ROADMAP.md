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

## START HERE - an audit, and the off-site backup was broken for three weeks (2026-09-23)

> **1304 tests green.** `main` clean at the wrap-up commit. 0 foreign key violations, counted live.
>
> - **The off-site backup had been failing silently since the 2026-08-28 SSD move** - HBS3's job
>   pointed at an emptied path. Fixed (`0a789d4`): `aims-backup` mirrors into
>   `Data/aims-web-offsite`, HBS3 uploads that nightly, verified landing in Google Drive. See the
>   CLAUDE.md NAS section. **Still to do: a test restore from Drive.**
> - **A full-codebase audit** (Opus 5.5, 2026-09-22). Verdict: security basics are sound (every
>   admin/society route gated, SQL parameterised, CSP, hashed tokens); the weaknesses are
>   operational. Findings are parked by Darragh under **Technical debt item 4** below, in priority
>   order - red CI still deploys; one failed derived-table rebuild takes the whole site down;
>   `mark_stale()` is remember-to-call.
> - **The 2026-09-20 session wrote no handover.** From its commits: Athenry Musical Society created
>   and live (`71a2c59`, `c6c6385`); the Wayback harvest finished and does not name the other three
>   collapsed partners (`307a349`); `/admin/collapsed-societies` got bulk accept, productions that
>   move with their award records, and a "can't tell" state (`dd09909`, `19e9088`, `754970b`);
>   apostrophe/"St." name-matching faults fixed (`d90cadb`). Live now: **Athenry holds 10 award
>   rows; 37 collapsed-society suggestions, 15 decisions.**
> - **Waiting on Darragh:** reply to Jack Rawlings (suggestion #9 - his Athenry report, now fixed)
>   and triage Cillian Fahy's sponsor-directory idea (#8); both still `New`.
> - Most of this session went on Darragh's NAS media stack, not AIMS - see `HANDBACK.md`. None of
>   it touched `aims.db`.

## Superseded: START HERE - two of the seven collapsed societies are now answered (2026-09-18)

> **1274 tests green** (was 1201). `main` clean at `cb737ea`. 0 foreign key violations, counted
> against the live database.
>
> ### The harvester got built, and it answered the question
>
> `scripts/harvest_aims_archive.py` pulls the pre-Wix aims.ie out of the Internet Archive;
> `scripts/match_awards_to_archive.py` reads it back against our award rows.
> **Read `docs/collapsed-societies.md`** - it holds the evidence, the sources and what is proven
> versus suspected. The short version:
>
> - **Athlone is collapsed with Athenry.** Every Gilbert row is Athlone's, every Sullivan row is
>   Athenry's. All six disputed years are now sourced from the official AIMS lists - 2001 and 2003
>   were the ones outstanding - **plus 2008, which the detector could never have found**.
> - **Clara is collapsed with Clane Musical & Dramatic Society** - one letter apart, which is
>   presumably how it happened. Clane already exists as society id 25, so this is a reassignment,
>   not a society that has to be created. Gilbert side is Clane's, Sullivan side is Clara's, in
>   every sourced year.
> - **Tralee, Avonmore and Kilcock** come back as themselves on their own section with nothing
>   consistent opposite. **UCC and Twin Productions** have no nominee-bearing rows in range.
> - **Nothing has been written to the database.** Two societies being identified does not make a
>   bulk update the right next move; the agreed shape is an admin queue.
>
> ### The finding that changes how the problem is counted
>
> **"100 award rows, ~2% of the archive" is a floor, not a total.** The two-tier test only sees a
> year where *both* collapsed societies were nominated. In 2008 only Athenry was, so there was no
> conflict to detect - and two rows sit under Athlone anyway, confirmed against the official page,
> on which the word "Athlone" does not appear at all. Quote the figure as a minimum.
>
> ### Two corrections to what this file used to say
>
> - **The 2003 nominations PDF is not a 2003 list, and not a scan.** It is the 2001/2002 leaflet at
>   a `/seminar/` path; it holds text streams and no image filter at all; and the archived copy is
>   truncated to its outer panels, with no page tree, which is why PyMuPDF opens it to zero pages.
>   Only one capture exists. **OCR was never the way in** - the salvageable text is in
>   `archive_harvest/noms2003/noms2003.salvaged.txt`.
> - **The archive is far bigger than "~7,220 URLs".** The CDX index returns **21,427 captures**,
>   **13,724** of them documents, because the old site carried a show database, a review section and
>   a busy discussion forum on top of the awards pages.
>
> ### What the harvester is, so nobody rebuilds it
>
> Resumable and polite by design: an append-only manifest, a re-run that skips what is already
> there, a 404 treated as a real answer about one URL, and a run of consecutive failures stopping
> the whole thing rather than hammering an Archive that is having a bad day. `--match`/`--exclude`
> run the useful part first, and **a pattern miss is deliberately not recorded as done**, so a
> later, wider run still sees those pages. Output lands in `archive_harvest/`, gitignored like
> `enrichment/`; every extracted file carries its source URL and capture date in its own header.
>
> **Accented URLs need cp1252, not UTF-8** (found 2026-09-18, `b2cbdb8`). The old awards pages carry
> one URL per person and Irish names are full of fadas. Wayback keys on the bytes the original site
> served, and a 2004 ASP site served cp1252, so `director=%C1ine+Gilmore` returns the page and
> `%C3%81ine` returns 404. Measured against the Archive, not reasoned about. Two related traps:
> `urllib` refuses a non-ASCII URL with an ascii codec error that reads exactly like a network
> fault, and printing one to a cp1252 console killed a run of 1,885 fetched pages outright.
>
> **`--retry-failed` exists because of that.** Failures are recorded so a missing page stays
> visible, but a plain re-run skips anything the manifest holds - so a bug on our side would have
> buried 152 real pages permanently. If you change anything about how URLs are fetched, re-run with
> that flag.
>
> `match_awards_to_archive.py` **offers both neighbouring societies rather than choosing between
> them**, because the pages disagree on column order - the 2001 nominations read nominee, show,
> society; the 2003 results print the society first. Picking by distance produced confident wrong
> answers while it was being built. Repetition across rows, seasons and pages is what settles it.
>
> ### The queue is built and loaded (later the same day)
>
> `/admin/collapsed-societies`, at `cb737ea`. **1274 tests green.** The unit is a season and a
> section, not a row. Propose-don't-apply: `scripts/import_collapsed_suggestions.py` writes
> proposals carrying the capture date and URL they were read off, the page links back to the source,
> and moving anything is a human decision that is undoable from the same page.
>
> **39 suggestions are loaded in production** (2026-09-18, after a backup - `aims-20260918-133122.db`).
> **No award record was moved**, and none should be until Darragh works the queue:
>
> - **Clara -> Clane, 8 seasons, ready to apply.** Clane is society id 25, so the button works.
> - **Athlone -> Athenry, 5 seasons, blocked.** Athenry has no `societies` row, so the page shows
>   "not on our list" rather than a dead button. **Darragh is creating Athenry himself** (his call,
>   asked and answered 2026-09-18) - the region and lifecycle are his to set.
> - The rest are one-off hits and are flagged **"one season only"** on the page. They are shown, not
>   hidden: the queue reports, it does not decide.
>
> Three things worth not re-deriving:
>
> - **The dashboard counter is counted from suggestions, not conflicts**, so it can reach zero. A
>   conflicted season with no evidence behind it is not work anybody can do.
> - **A moved season used to vanish from the page**, taking its Undo with it, because it no longer
>   had rows under the old society. `groups_for` now unions in decided groups and reads their rows
>   from wherever they went. A test caught it.
> - **The page was 616KB** with seven societies on it - one form per button, per suggestion, per
>   season. One form per group with `formaction` buttons, and hiding the seasons with neither a
>   conflict nor a source, took it to 266KB / 20KB gzipped. `?all=1` brings the quiet ones back, and
>   it has to: that is where 2008 was.
>
> **`docs/collapsed_suggestions.json` is committed on purpose.** The harvest is gitignored and local
> to one machine, so without that file nobody could populate the queue or check the findings without
> re-running a multi-hour harvest. Note `data/` in `.gitignore` matches `docs/data/` too, which is
> why it sits directly in `docs/`.
>
> ### Open, in the order I would take them
>
> 0. **Work the queue** - Clara/Clane is ready; Athenry needs its society row creating first.
> 1. **Finish the harvest.** About 13,000 documents are still unfetched - the old ASP show database
>    and the review section especially, which is where the partners for Tralee, Avonmore and
>    Kilcock would be. Same command; it resumes.
> 2. **Decide with Darragh how a reassignment gets applied**, then build it - the propose-don't-
>    apply admin queue, in the pattern the venue and people queues use. Athlone/Athenry and
>    Clara/Clane are ready to be its first two cases.
> 3. **Go back to Jack with confirmation rather than a question**, and raise it with AIMS so it is
>    fixed at source - that fixes aims.ie and every future import too.
> 4. **Create Athenry Musical Society** as a defunct society once its years are settled. Clane
>    needs no creation; it is already id 25.
>
> ### Still open from before this stretch
>
> 13 poster chases, 20 never-expiring invite codes, 8 duplicate venue clusters, 13 lifecycle calls,
> 36 person clusters, the pantomime scope call, the `/titles` genre taxonomy, and the `/titles`
> page-weight note (316 cards, ~500KB of HTML; it gzips to 38KB, so this is render cost on a phone,
> **not** a bandwidth problem - compression already resolved that once).

## START HERE - the traffic data is now trustworthy, and two empty pages left the nav (2026-09-06)

> Darragh asked for recommendations on any topic. I gave four, ranked, each checked against the
> live site or the database rather than the tracking docs. He took the top two. **1142 tests green**
> (was 1117).
>
> ### 1. The traffic data could not support the decisions being made from it
>
> The session earlier today read `page_views` and changed a product call off it ("the homepage is
> 47.8% of traffic, show pages are a sitemap sweep"). Good call - but `page_views` has three
> columns: `path`, `views`, `last_viewed`. One running counter per path since 2026-08-03. It cannot
> say whether traffic is **growing**, what happened **this week**, or how much of the total is
> **Googlebot**. The headline 24,363 is inflated by an unknown amount, and it is the number
> decisions are now being made from.
>
> `page_views_daily (path, day, is_bot, views)` now records alongside it. `page_views` is
> deliberately unchanged and still counts everything, so figures quoted before today stay
> comparable - **do not "fix" it to exclude bots.**
>
> **The bot test is a user-agent heuristic and the page says so.** It catches every crawler that
> identifies itself (which the 955-paths-at-exactly-two-views signature says is most of ours) and
> nothing that poses as a browser. A missing UA counts as a bot. Read "people" as the total with
> the obvious rubbish removed, not a verified human count.
>
> **It starts empty.** The split cannot be backfilled - nothing recorded a date or a user agent
> before now. `/admin/traffic` says which date it can speak for, so the first fortnight does not
> read as a collapse.
>
> Two things worth not re-deriving:
> - **The chart colours were validated, not chosen.** `--accent` against `--muted` was the obvious
>   pairing and sits at normal-vision delta-E 10.8 - genuinely hard to tell apart with full colour
>   vision. `--accent` against `--gold` is 31 (dark) / 38 (light). Screenshotted in both themes and
>   at 390px before shipping.
> - **A real bug fell out of writing the tests:** `purge_excluded_pageviews` read paths from
>   `page_views` only, so a daily row whose twin had been pruned was never cleaned.
>
> ### 2. An empty page was linked from the homepage - one, not the two I claimed
>
> **Correction, and it is the useful part of this section.** I told Darragh that `/exchange` and
> `/faq` were both empty and recommended hiding both. **`/faq` is genuinely empty (0 entries).
> `/exchange` is not** - it has a real listing, Castlebar Musical & Dramatic Society's *We Will Rock
> You* whole-cast costumes, added 2026-08-30.
>
> I got there by fetching the page and grepping its HTML for `empty`, matching something in the CSS,
> and reading that as an empty state without ever looking at what the page rendered. The local
> `aims.db` said 0 items and I let it agree with me. One `sed`-strip of the tags showed the listing
> immediately. **Local `aims.db` diverges from production on exactly this kind of field, and a grep
> for a word is not a check** - render the page or query production.
>
> The gate itself is unaffected and behaves correctly: the FAQ link is hidden, and the exchange link
> stays because there is something behind it. But the reasoning I gave was half wrong, and the
> changelog entry was corrected before it published.
>
> **Five links, not the two I first found.** The header dropdown and two footer columns were
> obvious. The other three were not: **both entries on `/more`**, which is the entire menu on a
> phone - gating `base.html` alone would have left them reachable for exactly the visitors who see
> them most - and the **"Staging X? Check the Exchange" banner** on a title page, which appears
> precisely when that title has nothing listed. (The society- and title-page cross-links were
> already inside `{% if wardrobe_items %}` and needed nothing.)
>
> Links hidden, routes kept: each page returns on its own the moment there is content. Each
> condition mirrors what its page actually lists (published FAQ entries; non-delisted items from
> non-hidden societies), so a draft answer or a delisted costume cannot put the empty page back.
> `/venues`' constant-query-budget test went 8 -> 9; the bound being constant is what it protects.
>
> ### 3. The ticket-link research task is prepared, not sent
>
> **61 of 67 upcoming shows have no ticket link** (counted against production; the 43-of-48 figure
> quoted earlier in the session came from the stale local copy). The site's core job is telling
> someone what's on so they can go, and right now they land on the homepage and hit a dead end.
> This is the biggest product gap open, and it is data, not code.
>
> `build_ticket_worklist.py` (repo root, tested) generates the worklist; the brief is
> `enrichment/TICKET_LINKS_BRIEF.md` (untracked, like every other brief). **The worklist itself is
> deliberately not generated yet** - it must be built in the container, because the upcoming set
> turns over weekly and a local `aims.db` has none of the society website/Facebook values the
> researcher starts from.
>
> The brief is built around one failure: **a link that resolves but sells a different show.** That
> is not hypothetical here - 32 of the 102 `rights_url` values published in August served a
> different show, every one returning HTTP 200, because "the URL resolves" was all that was
> checked. So every filled row must carry the title, society and dates **as printed on the page**,
> which we then check mechanically against what we hold.
>
> ### Checked and deliberately NOT done
>
> - **`/titles` renders 316 cards, ~500KB of HTML.** It gzips to 38KB, so this is DOM/render cost
>   on a mid-range phone, not bandwidth. `/titles` gets 187 views against the homepage's 1,370.
>   Filed, not fixed - and note the page-weight backlog item was already resolved once by adding
>   compression, so don't re-open it as a bandwidth problem.
> - **SSH to the NAS timed out all session** (`dc-qnap-2` port 22). Everything above was verified
>   against the public site over HTTPS instead. Nothing needed a container command; the ticket
>   worklist does, and that is why it is not generated.
>
> ### 4. Then, from the open list: the society edit audit log
>
> Darragh said "you pick from what's open". Most of that list is his judgement calls, not code.
> The audit log was the strongest actual build item and had been **mocked up on 2026-09-04 and not
> selected** - I re-picked it on merit, which is worth flagging since he had passed on it once.
>
> The argument: societies edit their own history live, with no moderation queue, and a committee
> shares one login code. So a wrong edit to a decades-old production was **silent, unattributable
> and unrecoverable**, on a site whose whole value is being a record of what really happened. That
> is the same class of failure as the FK violation and the `rights_url` incident - a wrong change
> nobody notices.
>
> Built at the cut scope already agreed (append-only, no revert UI) and wired into **all ten**
> write paths rather than a subset, because a log that misses one reads as "nothing happened"
> there. Creations log one line; deletions log every field - a created row is recoverable from
> itself minus later updates, a deleted one is not. Contact fields record that they changed
> without quoting the value.
>
> **I broke `record()` on purpose to check the tests were watching**: 8 of 13 failed. Worth doing
> whenever a new test file passes first time.
>
> ### Still open from this
>
> - ~~**Generate and send the ticket worklist**~~ **DONE 2026-09-06** - 61 rows researched by
>   Antigravity (`enrichment/ticket_worklist_filled.json`). 9 verified live booking links, 52 off-sale.
> - ~~**An importer for the returned ticket file**~~ **DONE 2026-09-06** -
>   `scripts/backfills/import_ticket_links.py` built and tested (9 unit tests in
>   `tests/test_import_ticket_links.py`, **1166 tests green**). Validates 3-point page proof (title,
>   society, dates) against the database before updating `ticket_url`. Dry-run verified against
>   production: ready for Darragh's approval to apply.
> - **11 FAQ drafts are in the live database, unpublished.** Written 2026-09-06 at Darragh's
>   request. The public page and its nav link stay hidden until he publishes at least one. Two
>   need his eye in particular: "Is this an official AIMS website?" (it speaks for his Council
>   role) and "How do I get our upcoming show listed?" (it says "ask us" without naming a channel,
>   because none could be verified).
> - **The FAQ is the cheaper of the two empty pages to fill.** Six real entries sit in
>   `feature_suggestions`, and Darragh answers the same committee questions repeatedly. That is the
>   FAQ, already written, just not typed in.

## START HERE - what the traffic says, and an accessibility pass (2026-09-06, earlier)

> Darragh asked for a stance on the UX. I had one and it was inference, so I looked at `page_views`
> first - nobody ever had. **1117 tests green.**
>
> ### Read the traffic with its caveats attached
>
> 24,363 views over 2,625 paths since 2026-08-03. **`app/analytics.py` does no bot filtering**, and
> it is a cumulative counter - no sessions, uniques or referrers. These are requests, not people.
>
> - **The homepage is 47.8% of all views.** Next real destinations: `/season` 604, `/stats` 566,
>   `/societies` 538, `/awards` 380, `/titles` 251.
> - **The long tail tells you which is crawl and which is human**, and this is the part worth
>   keeping: `/shows/<id>` has 1,803 paths at a **median of 2 views** (955 of them at exactly two -
>   a sitemap sweep), while `/societies/<id>` has 167 paths at a median of 5, with only 2 pages on
>   a single view.
>
>   **People land on the homepage and mostly do not click through to a show.** The homepage is the
>   product. Weigh that before putting more work into show-detail pages - a good deal of recent
>   effort went there.
> - `/society/` + `/society/login` at 402 combined: the committee-facing side gets real use.
> - `/calendar.ics` fetched 175 times - the subscription feed defended on principle on 2026-09-04
>   is genuinely used.
>
> ### Accessibility is better than this file has been claiming
>
> **axe-core over the 10 highest-traffic pages: zero WCAG A/AA violations.** Confirmed axe actually
> ran rather than trusting an empty result. The "accessibility is only markup-deep" line that has
> sat in this file since 2026-08-29 was too harsh about the automated layer, and is withdrawn.
>
> Keyboard driving found two things axe structurally cannot (`33a860f`, both verified live): **no
> skip link** - axe passes bypass-blocks on the `<main>` landmark alone, which does nothing for
> someone tabbing - and **Escape not closing the calendar menu**.
>
> **Checked and deliberately not changed, so nobody re-derives them:** the dark-mode focus ring is
> genuinely visible (`outline: auto` paints Chromium's own ring, whatever the computed colour says -
> screenshotted, not assumed); `alt=""` on card posters is correct because the poster is a second
> link to the same place as the title beside it; 320px reflow is clean; the site stays readable with
> images blocked.
>
> **Still unproven: a real screen reader.** Nothing has been driven with NVDA or VoiceOver and
> Claude cannot do it from here. Narrowed rather than closed in `docs/spikes.md`.

---

## START HERE - calendar + social card shipped, repertoire finder unblocked (2026-09-04, later)

> Darragh reviewed a proposals mockup
> (https://claude.ai/code/artifact/6b2c3233-689f-4fa1-88f7-42bf2dfb23d9, built in the site's own
> tokens) and picked two to build. **1108 tests green.**
>
> ### Add to calendar (`41582d0`)
>
> He asked for Add-to-Google-Calendar *instead of* the .ics. Both halves of that were wrong and the
> corrections are worth keeping:
>
> - **The Google link already existed** - a 13px text link inside the Dates row, which is why he had
>   never seen it. The gap was presentation, not capability.
> - **Dropping the .ics would have made mobile worse.** Apple Calendar has no pre-filled-event URL
>   of any kind, so the .ics is the *only* route to it, and on an iPhone opening one is the native
>   path. A Google-only control excludes a large share of an Irish committee.
>
> Now one **Add to calendar** control offering Google, Apple, Outlook and a plain download.
> New `/shows/<id>/calendar.ics` shares `_vevent()` with the feed, so the same show added by hand
> and arriving via a subscription carries the same UID and merges instead of duplicating.
> **The subscribable `/calendar.ics` feed is untouched and must stay that way** - it answers "keep
> me updated with all of these", which per-show links cannot.
>
> ### The social card (`41582d0`, `app/social_card.py`)
>
> **Not the link preview.** `og-card.png` is what a scraper renders when someone pastes a link and
> already worked; this is an image a society *downloads and posts* to its own Instagram. Three
> shapes (post/square/story) because each platform crops a wrong ratio differently. A society with
> no poster still gets a real card via the typeset playbill, with the upload ask attached once -
> which is the point, since 175 of 194 have never uploaded one and every previous approach asked
> them for something rather than giving them something.
>
> `/shows/<id>/card.png?size=` is public on purpose (a society has to be able to paste the URL into
> a committee WhatsApp group); `/society/shows/<id>/card` is their own page for it.
>
> **Two layout faults were caught by rendering the image and looking at it, not by tests passing.**
> Both now have tests, and both are the kind that a "did a PNG come back?" check sails past:
> the playbill clipped `EVERYBODY'S` to `VERYBODY'` (the shrink loop checked line *count* but not
> line *width*, against centred text), and the story shape keyed every size to canvas height, so at
> 1920 tall the countdown was drawn on top of the venue line. **Render it and look at it.**
>
> New runtime dependency: `segno` (pure Python, no compiled deps) for the QR, plus the two Archivo
> weights committed as `.ttf` - Pillow cannot read woff2 and `fonttools` is deliberately not a
> runtime dependency. The card degrades to no-QR rather than 500ing if segno ever goes missing.
>
> ### The repertoire finder is unblocked, and it is a casting tool
>
> Darragh answered the question that had parked it: *"committees like to find shows based on cast
> size, number of male/female parts, supporting characters, etc."* It is a **can-we-cast-this**
> tool, not a taste tool - my earlier guess (rights status, regional gaps, recent stagings) had the
> emphasis wrong.
>
> The data does not exist. `enrichment/REPERTOIRE_DATA_BRIEF.md` and
> `enrichment/repertoire_worklist.json` (299 titles, most-staged first) are written and ready for
> Antigravity. **This is the good shape of delegated task** - 221 rows already name the licensing
> house's own page, so it is transcription from a source we can check, not research. The brief
> carries hidden controls, two canaries and batch-discard scoring, because this project has been
> burned three times by plausible values wearing invented citations.
>
> **Do not build the filters before the data lands.** A cast-size filter over mostly-blank rows
> hides titles rather than admitting it does not know.

---

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

- **Poster outreach.** 60 posters across 19 of 194 societies. **13 shows are chaseable** (opening
  inside `POSTER_CHASE_DAYS` = 93 and with no poster), down from 17 on 2026-09-02 because shows
  have since opened, not because posters arrived - the total is unchanged at 60. Every chaseable
  society has an active login code and a Copy message button on `/admin/missing-posters`.
  **Nothing is blocked on code.** 50 upcoming shows have no poster, but only 13 are worth asking
  about - do not quote the 50.
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
- ~~**What committees actually asked for in a repertoire finder.**~~ **ANSWERED 2026-09-04.**
  Darragh: *"committees like to find shows based on cast size, number of male/female parts,
  supporting characters, etc - the more filters and info we have for them to select and filter on
  the better."* So the finder is a **casting-constraint** tool, not a taste tool. A society with
  nine strong women and four men cannot stage *Guys and Dolls*, and finding that out in November
  after choosing in September is an expensive mistake. My earlier guess at the shape (rights
  status + regional gap + recent stagings) was wrong in emphasis - those are secondary to "can we
  cast it?". **The data does not exist yet; see the build item below.**

### Build items

- ~~**Social card generator**~~ **SHIPPED 2026-09-04** (`41582d0`), along with a proper
  add-to-calendar control - both chosen by Darragh off the proposals mockup
  (https://claude.ai/code/artifact/6b2c3233-689f-4fa1-88f7-42bf2dfb23d9). See `app/social_card.py`
  and the START HERE block above.
- **The repertoire finder - now a real, scoped job.** Darragh has answered the question that was
  blocking it (see above): committees filter on **casting constraints**. Two halves:
  1. **The data, which still does not exist.** Antigravity returned a filled worklist on
     2026-09-05. **Do not import `enrichment/repertoire_worklist_filled.json`** - 32 of its Concord
     rows describe the wrong shows. **The cause was ours, not its:** our stored Concord URLs
     carried wrong product IDs, and Concord's `/p/<id>/<slug>` treats the ID as authoritative, so
     it was sent to the wrong pages and faithfully recorded where it landed. Claude first read that
     as fabricated citations and **was wrong**; the correction is in `HANDBACK.md` and is worth
     reading, because the mistake was reaching for a known failure mode instead of testing it.
     The 92 MTI/TRW/ALW rows are a candidate but unverified - a matching slug proves the URL names
     the right show, not that the numbers on it are what was recorded.
     **The bad URLs are now fixed** (`b2b7885`+, 102 cleared), so re-running the Concord half is a
     clean task - but it needs fresh, working URLs first, which we do not have.
     `scripts/enrichment/build_repertoire_worklist.py` regenerates the worklist.
  2. **The schema and the UI**, once data comes back and is verified. Columns go on `show_info` via
     `COLUMN_MIGRATIONS` in `app/db.py` - the field list is in the brief.
  **Do not build the filters before the data lands.** A cast-size filter over mostly-blank rows is
  worse than no filter, because it silently hides titles rather than admitting it does not know.
- ~~**Society edit audit log.**~~ **SHIPPED 2026-09-06** (`7245986`), at the cut scope agreed on
  2026-09-04: append-only log, no revert UI. `app/society_audit.py` + `society_edit_log`, wired
  into **all ten** society write paths rather than a subset, and readable at
  `/admin/society-edits`. Three limits are stated on the page itself: it identifies a **login, not
  a person** (a committee shares one code), it does **not** cover moderator edits made in
  `/admin`, and there is no revert. It starts empty and cannot be backfilled. A society still
  cannot delete a show, so the show archive can only grow or be corrected.

### Parked for the future, with a trigger

- **Poster / programme museum.** Wanted, genuinely gated on poster count, and **Darragh's call
  2026-09-04 was to park it rather than lower the bar** - "put it in one for the future". At 60
  posters against a ~100 trigger (a number Claude proposed, and he has not disputed). It unblocks
  itself if the social card does its job, since that is the thing designed to get posters uploaded.
  **Re-raise it when the poster count passes 100**, not before.

### Data work

- **A backfill that deletes rows should run `PRAGMA foreign_key_check` in its own dry-run.**
  Learned 2026-09-05: `merge_song_dundalk.py` guarded every table referencing the *society* it
  deleted and none referencing the **shows it deleted itself**, so a real adjudicator review sat
  pointing at a deleted show for two days. Nothing on the site was watching - it surfaced from
  `verify_backup.py` while testing something unrelated. Fixed
  (`scripts/backfills/fix_orphaned_song_review.py`), and the hole is now commented in the merge
  script, which is the template the next merge will copy.
- **54 orphaned `historical_reviews` rows.** Recounted live 2026-09-06 - it read 55 the day
  before, 54 before that, and "~112" in this file for weeks. **The number genuinely moves, so
  recount before acting on it.** Still not deleted, because "it looks unmatched" is not a test -
  see `docs/spikes.md`.
- **297 `historical_results` rows with `category_name IS NULL`**, 274 of them pre-2001. Needs real
  archival research into AIMS awards programmes; no query resolves this.
- **~10 unmapped historical societies** with no `societies` row (Bangor Operatic, De La Salle
  Waterford, others). Creating historical society records is a structural decision, not a bugfix.
- **28 orphaned Inactive societies** with zero shows and zero awards - retain or remove is a
  judgment call with no urgency signal.
- ~~**Dead `show_info.rights_url` values**~~ **FIXED 2026-09-05** - 102 cleared, not the 57 first
  reported: 57 redirected to the licensing house's homepage, **32 served a different show
  entirely**, 13 were hard 404s. Cleared rather than replaced, because a link to the wrong show is
  worse than no link - a committee could research or license the wrong title off it.
  `licensing_house` is untouched, so the page still says who licenses it.
  **119 URLs remain and 28 of those are unverified** - 24 on `guidetomusicaltheatre.com` and 4 MTI
  pages could not be reached from Claude's environment, *which also could not reach
  `example.com`*, so those failures say nothing about the sites and nothing was cleared on that
  basis. Re-check them from a normal network before touching them.
- **29 `rights_url` values are not licensing pages at all** - 24 point at `guidetomusicaltheatre.com`
  and 5 at Wikipedia, while the page labels all of them "Licensing page". Separate from the dead-link
  problem and still open.
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

## Technical debt

1. **`productions_build.py` and `venues_build.py` duplicate the same freshness machinery** -
   `FINGERPRINT_SQL`, `fingerprint()`, `mark_stale()`, `ensure_current()` and a one-row `*_build_state`
   table, written twice. Less pressing now that `ensure_current()` itself has one caller for both
   (a shared `before_request`) rather than sixteen scattered call sites - the duplication left is
   two near-identical private helpers, not a rule spread over six modules.
2. **FTS indexes rebuild on every startup.** Known, deliberate, documented in `db.py` - the obvious
   `COUNT(*)` guard doesn't work on an external-content FTS5 table. Left alone on purpose.
3. **`page_views` is keyed on path only**, so no query-string question can ever be answered from it.
   Still true, and still fine - it is a popularity counter. **The two questions that actually
   mattered are now answered elsewhere**: `page_views_daily` (2026-09-06) adds the date and a
   people-vs-bot split, so "is it growing" and "how much is a crawler" no longer need this table
   to change. Query strings remain unanswerable and nobody has asked.

4. **From the 2026-09-22 audit - parked by Darragh ("back burner"), in priority order:**
   - **A red CI build still deploys.** Portainer polls `main`, not the workflow's result. Fix: CI
     fast-forwards a `production` branch on green; point Portainer stack 8 at that branch.
   - **One failed derived-table rebuild takes the whole site down.** `verify()` raises
     `VerificationError` inside the `before_request` rebuild (500 on every page, retried every
     request) and at startup (container crash-loop). Should log loudly and keep serving the last
     good tables.
   - **Freshness depends on remembering `mark_stale()`** for any edit the count/`updated_at`
     fingerprint can't see. A trigger-maintained change counter would make it automatic - same
     argument that removed the sixteen per-route calls.
   - **Oversized units:** `public.py` 2,444 lines; `create_app` 382, `stats()` 354,
     `society_detail` 273. Split opportunistically when next touched, not as a project.
   - Nits: `submit.photo` leaves earlier files on disk when a later one in the batch fails;
     admin login only hashes when the username exists (timing reveals valid usernames);
     `CF-Connecting-IP` is forgeable from the LAN via published port 8000.
   - **Test restore from Google Drive** (HBS3 → Restore to a scratch folder) - see the backup
     entry below.

## Housekeeping, low priority, no urgency signal

- Audit other societies for similarly stale/presumptive data (same shape as the venue-data fixes already
  done).
- A formal `LAUNCH.md` spec, written up retroactively (the site launched organically instead).
- **Off-site backup was silently broken 2026-08-28 → 2026-09-22 (not housekeeping).** HBS3 job
  "AWB" (nightly 04:00, to Google Drive `AIMS WEB Backup/AWB.qdff`) still pointed at
  `Data/config/aims-web` on volume 1, which the SSD move emptied: "Total files: 0", Error, every
  night. HBS3 can only pick registered shared folders and the SSD volume's `Data/` isn't one, so
  `aims-backup` now mirrors the newest 3 backups + `uploads/` into
  `/share/CACHEDEV1_DATA/Data/aims-web-offsite` and the job's source is re-pointed there.
  Confirmed 2026-09-22: job green, ~77 MB of new chunks landed in Drive at 20:04.
  **Still to do:** a test restore from Drive (HBS3 → Restore, to a scratch folder), then open the
  restored `.db` - a backup nobody has restored is a hope.
  Do NOT point HBS3 at `Data/config.old-premove-20260828` - frozen pre-move copy.

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
