# Handoff — running this project while Claude is unavailable

**Written 2026-08-29 by Claude (Opus 5), for Gemini Antigravity, at Darragh's request.
Kept current at the end of every Claude session — see "Current state" at the bottom for the
date it was last refreshed.**

This is a **standing** handover, not a one-week note. Darragh's Claude usage resets
periodically, and whenever it does you are the one driving this repo, the live site, and git —
not a research delegate handing outputs back, which is the role you have had here before. If the
"Current state" date at the bottom is more than a few days old, trust `ROADMAP.md`'s START HERE
block and `HANDBACK.md`'s last entry over this file's specifics.

This file is the handover. It does **not** restate `CLAUDE.md`; that file is accurate and
current, and two copies of the same instructions drift apart within a week.

---

## 1. Read these first, in this order

1. **`CLAUDE.md`** — the stack, every command you will need, and the repo's own rules. Assume
   everything in it applies to you exactly as written.
2. **`ROADMAP.md`**, the START HERE block — where things stand and what is genuinely open.
   Update it when the phase changes; that is what makes a session survive a context reset.
3. **`docs/`** — `user-guide.md`, `moderator-guide.md`, `deployment.md`, `data-model.md`.
   Most "how does X work" and "why is Y like this" questions are already answered there.
4. **`HANDBACK.md`** — the log you write to. See §7.

`ROADMAP_ARCHIVE.md` is history, not a to-do list. Read it only when you need the reasoning
behind a past decision. It is **append-only** — never rewrite or prune it.

## 2. What this is, and who it is for

A Flask + SQLite site tracking Irish amateur musical societies: their upcoming productions,
their history, and the AIMS awards archive going back decades. It is used by society
committees and their members, and it is replacing a hand-maintained spreadsheet.

Two consequences that shape almost every judgement call:

- **The archive is a record of what really happened.** Societies check it against their own
  programmes. Guessing, inferring or "tidying" data without evidence is the one thing that
  destroys its value. Where the repo makes a guess it says so in the code — see
  `scripts/backfills/guess_society_lifecycle.py` for the pattern.
- **The audience is volunteers, not developers.** Copy on the site should sound like a person
  talking to a committee secretary. `/admin` copy should say what will happen when a button is
  pressed.

## 3. The deploy rule — read this before your first commit

**A push to `main` is a deploy.** Portainer polls this repository every ~5 minutes and ships
`main` to the live site on its own. There is no review step, no approval, and no undo. CI
(`.github/workflows/test.yml`) runs on every push but **does not block the deploy** — it tells
you loudly that `main` is broken, after it is already live.

Darragh's decision for this week:

| Straight to `main` | Branch `ag/<topic>` + PR, for Darragh to merge |
|---|---|
| Bug fixes | Schema changes (new tables/columns/constraints) |
| Data corrections and backfills | New routes or pages |
| Copy and wording changes | Anything that changes what a public visitor sees |
| Tests | Dependency changes |
| Docs, `ROADMAP.md`, `HANDBACK.md` | Anything touching auth, CSP, sessions or rate limiting |

**When unsure, branch.** A branch costs Darragh one merge click. A bad deploy costs a broken
public site with nothing standing in front of it.

Before any push to `main`: `py -m pytest` must be green. **1034 tests pass as of `0a8c8ae`**
(2026-09-02).

**One addition Darragh made on 2026-09-02**, which sits on top of the table above rather than
replacing it: anything a visitor or committee member can *see* gets **described to him before
the push**, even when the table says it could go straight to `main`. Fixes, data work, tests and
docs still flow. He wants the last look on visible change, and it has already caught a real
deviation — a button built in the wrong colour against an approved mockup.

## 4. Production access, and the one hard rule

You have the same access Claude had. The NAS is a QNAP; the app runs in a container called
`aims-web`.

```bash
# SSH (key-only, no password anywhere)
ssh -i ~/.ssh/claudeshowcal_ed25519 claudeshowcal@dc-qnap-2

# docker is NOT on that account's PATH - use the full path, every time
/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker exec aims-web <cmd>

# Verify what is actually deployed (Portainer Stack 8's own git checkout)
/share/CACHEDEV2_DATA/Data/config/portainer/compose/8/
```

To answer "is production running my code?", compare a file there against your local copy.
Because this working tree is CRLF and the checkout is not, compare normalised:
`sed 's/\r$//' <file> | md5sum` on both sides. A raw `md5sum` disagrees purely on line endings.

### The hard rule

> **Every write to the production database is a committed script under `scripts/backfills/`
> with a `--dry-run` mode. Run it dry first. Record the output in `HANDBACK.md`.
> Never run an ad-hoc `UPDATE`, `INSERT` or `DELETE` against `/data/aims.db`.**

This is not bureaucracy. An ad-hoc statement is invisible to Darragh, unreviewable by the next
agent, and impossible to repeat or reverse. A script is a diff he can read, a dry run he can
check, and something that still explains itself in six months. `guess_society_lifecycle.py`
(written 2026-08-29) is the worked example: a pure, separately-tested `classify()` function, a
`--dry-run` that rolls back, only ever filling blanks so a re-run never overwrites a human
decision, and a docstring arguing for its own thresholds.

Reading production is unrestricted — query it freely, and prefer it over the local database for
anything you are going to report as fact.

## 5. Traps — every one of these has already cost someone a session

**Mixed line endings.** The working tree is mostly CRLF, but **not universally, and not
predictably per file** (`tests/test_startup_guard.py` and several templates are LF). A
search/replace written with `\n` patterns silently matches *nothing* against a CRLF file and
reports success. Detect per file before editing:
`'\r\n' if '\r\n' in text else '\n'`.

**A database copy that looks right and isn't.** The live database is
`/share/CACHEDEV2_DATA/Data/config/aims-web/aims.db`. For a day after the volume move in August a
complete, entirely plausible copy also sat at the old `CACHEDEV1` path — real data, its own
`backups/`, just frozen — and reading it instead of the live one was a silent, convincing
failure: correct data, merely out of date, with nothing signalling anything was wrong. It cost
most of a session. **That specific copy is gone (verified 2026-08-29, the whole
`/share/CACHEDEV1_DATA/Data/config/` path no longer exists) and `CLAUDE.md`'s warning about it
has been corrected** — but the habit is the point: check the mtime before trusting any database
copy you pull down, and don't assume a path is live because it looks right.

**Local `aims.db` is not production.** It is a dev copy and drifts. Any number you are going to
state as fact — a count, a gap, an audit finding — comes from the live database.

**`url_for(..., _external=True)` and `request.url` report `http://` in production, and they are
not wrong.** The Cloudflare Tunnel terminates TLS and hands the origin a plain request with no
`X-Forwarded-Proto`, so `ProxyFix(x_proto=1)` has nothing to promote. This is invisible for links a
browser follows and very visible in Open Graph tags - it shipped an `http://` `og:url` and
`og:image` on an https site. **Use the `absolute_url()` Jinja global** (built from `SITE_URL`, the
same way `notify.link` does it) for anything that has to be absolute. A test fails if
`content="http://` reappears in the page head.

**Cloudflare re-encodes images and will composite away an alpha channel.** An RGBA PNG served over
https came back RGB with its transparency flattened against crimson, which is how every WhatsApp
preview ended up a gold "M" on a red field. Brand assets under `app/static/` are flat RGB
deliberately; `scripts/build_brand_images.py` regenerates them and a test fails if the share card
regains an alpha channel. Do not "restore transparency" on those files.

**Some bugs are only visible in a browser.** Playwright is installed here (1.62.0, **Chromium
only** - `--device="iPhone 13"` fails because it defaults to WebKit; use `--browser chromium` with
device emulation). Two things this session found that no server-side test could: four layout faults
that made the site scroll sideways on a phone, caught by comparing `document.scrollWidth` to the
viewport across 18 routes at 320/390px; and a CSP violation that silently blocked an image preview.
Both were invisible in screenshots and in pytest.

**`--db /data/aims.db` is not optional in the container.** Every management script defaults to
a bare `aims.db` relative to `/app`. Omit the flag and the script silently creates a fresh
empty database inside the container's writable layer, does its work against *that*, and reports
success. Nothing changes on the live site and nothing tells you.

**Script paths depend on directory depth.** One-off scripts live under
`scripts/{backfills,enrichment,maintenance}/` and compute `ROOT = Path(__file__).resolve()
.parents[2]`. Copy one to `/app` and it raises `IndexError` at import. Run them by full path:
`docker exec aims-web python /app/scripts/backfills/<name>.py --db /data/aims.db`.

**Jinja wraps lines.** A test asserting a sentence that spans a template line break will fail.
Put the sentence on one line in the template rather than weakening the test.

**`SECRET_KEY` now fails fast in production.** As of `056c752`, `create_app` raises rather than
starting with the insecure default when `AIMS_DB_PATH` is set. `stack.env` holds a real 64-char
key. Do not remove that guard and do not unset the variable — the container will refuse to
start, which is the point.

**Portainer UI config edits are overwritten.** GitOps rewrites the stack on its next poll.
Anything that must persist belongs in `docker-compose.yml` in git. Real environment values live
in `stack.env` beside the Stack 8 checkout.

**Per-row expensive work in a list view.** An O(n²) helper called once per row in an admin list
took the site down (a 524) on 2026-08-19. Batch it once outside the loop. `app/people.py` shows
the other half of the lesson: block the candidate set first — a naive sweep of 2,267 names is
2.5M comparisons, bucketing by surname makes it 0.04s.

**Portainer's API (port 9000) is unreachable even from the NAS itself** — investigated once,
firewall, not solved. Anything needing the Portainer UI goes to Darragh.

## 6. What is on this machine but not in git

You are working in `d:\showdb`, so you can see these. None of them get committed
(`.gitignore` covers them, deliberately):

- **`enrichment/`** — delegated-research briefs and their JSON outputs, including your own
  earlier passes. `logo_worklist.json` has been fully imported; see `ROADMAP.md`.
- **`uploads/`** — real posters and logos, so local dev renders images.
- **`aims.db`** — the local dev database. See the trap above.
- **`mockups/`** — local HTML mockup drafts. Mockups are normally shown to Darragh as a
  published page rather than committed.
- **`~/.ssh/claudeshowcal_ed25519`** — the NAS key.

Root-level `*.docx`, `*.pdf` and several named proposal docs are also ignored: they are
*inputs*, and what came out of each is recorded in `ROADMAP.md` and the commits that acted on
it.

## 7. `HANDBACK.md` — how this comes back to Claude on Friday

Append one entry per working session, in the shape the file already shows. It is the difference
between Darragh resuming in ten minutes and reconstructing a week from memory.

Also, so `git log` alone answers "who did this":

- End commit messages with `Co-Authored-By: Gemini Antigravity <noreply@google.com>` (Claude's
  commits carry its own trailer, so authorship stays legible without reading anything).
- Prefix branches `ag/` — open branches then identify themselves on Friday.
- Leave the working tree **clean** at the end of every session. No stashes, no half-applied
  edits, no uncommitted experiments.
- On your **last session before the handback**, write a "state of play" entry: what is deployed,
  what is sitting on a branch, what production data you touched, and what you would do next.

## 8. Conventions worth keeping

- **Diffs, not rewrites.** Minimal targeted edits. `Write` is for genuinely new files.
- **Comments explain *why*, not what.** This repo's comments carry the reasoning and the bugs
  that motivated the code. That is deliberate and it is why a cold session can pick it up. Match
  it.
- **A test names the bug it exists for.** See `tests/test_person_identity.py` for the house
  style — the docstring says what would break and why it matters.
- **`CHANGELOG.md` in the same commit** for anything user-visible. It self-publishes to the
  public `/suggestions` Roadmap page on the next deploy — no command needed. One line per
  bullet, blocks separated by `---`, newest at the top. Internal/moderator-only changes do
  **not** get an entry.
- **Verify before you claim, and check the check.** Repeatedly now, a statement in `ROADMAP.md`
  or in *this file* has turned out to be wrong when tested against the live database — the logo
  import "had never been run" (it had), the rate-limiting finding "still unfixed" (it was fixed),
  "529 award rows" (a number that never existed). Check code and data, not the tracking doc.

  And check your own query before you believe its answer. On 2026-09-02 two audit checks were
  wrong before the code was: one compared seasons as strings, where `'99/00'` beats `'18/19'`;
  two tests used year 2098 as "the future" and the productions rebuild resolved `98/99` back to
  **1998** through `season_start_year()`'s 50-pivot, so a test passed on a false premise. A
  finding you have not sanity-checked is a guess with a number attached.
- **Adding a column** to an existing table needs an entry in `app/db.py`'s `COLUMN_MIGRATIONS`;
  `CREATE TABLE IF NOT EXISTS` never adds a column to a table that already exists. Changing a
  `CHECK` constraint needs a table rebuild — `_migrate_photo_submission_kinds` and
  `_migrate_shows_source_check` in the same file are the pattern.
- **Clean up test data.** Any admin login or test row you create in a real database goes away
  when you are done.

## 9. Never

- Force-push, or rewrite history on `main`.
- Commit secrets, `aims.db`, or anything under `uploads/` or `enrichment/`.
- Delete rows from the dismissal tables (`dismissed_person_pairs`, `dismissed_venue_pairs`,
  `dismissed_duplicate_pairs`, `society_field_checked`). They are what let admin counters reach
  zero; without them a queue looks permanently unfinished and stops being used.
- Add a public person page or any public surface listing individuals. This was asked and
  answered **no** on privacy grounds. The identity work in `app/people.py` is internal-only and
  a test asserts `/people` returns 404. Keep it that way.
- Publish anything that presents itself as coming from AIMS centrally. This is Darragh's
  unofficial project; `README.md` and the About page are careful about that and so should you
  be.
- Rewrite `historical_results` or the `shows` credit columns to "normalise" a name. The archive
  says what the programme said. Identity is a join, not an edit.

## 10. What to work on

Ranked, with the argument, so you can re-order it on merit rather than following it blindly.
Darragh is doing the poster outreach himself this week and does not need help with the
pre-Christmas shows.

1. **Keep `main` green, and fix what Darragh reports.** CI does not gate the deploy, so a red
   `main` is a live-site risk, not just an untidy badge. This outranks everything below.

2. **Data and outreach support** — high value, small blast radius:
   - ~~`/admin/historical-society-links` — 64 printed names releasing 529 award rows~~
     **Both wrong, and both cleared.** The queue is at **0 undecided** (checked against the live
     database 2026-09-02); it emptied largely via `no_match` decisions, which is the correct
     outcome — the module's own docstring predicted only ~9 of 69 would ever link, and 8 did.
     **The "529 award rows" figure was never real.** It sat in this file and in `ROADMAP.md` for
     a week and neither was checked. Do not resurrect it.
   - ~~`/admin/photo-submissions` — 3 unread~~ **Cleared, 0 pending** (verified 2026-09-02).
   - **13 lifecycle judgement calls to sanity-check** (see `ROADMAP.md`, 2026-08-29). The 10
     marked `Closed` and the 3 marked `Unverified` — Armagh Creative Theatre Group, KATS, Seven
     Woods Productions. Several rows classed from production history (Belfast School of
     Performing Arts, Currid School of Performing Arts, Phoenix Performing Arts College, two
     youth theatres) are arguably *Out of scope* by nature instead. **That is Darragh's call,
     not yours** — propose, don't apply.

3. **Off-box backup.** Backups currently sit in the same directory, on the same volume, as the
   database. It is the only open item whose downside is losing everything. `CACHEDEV1` has
   ~339GB free but is a 96%-full ageing array; a genuinely off-box destination is a decision
   about Darragh's hardware and accounts. **Investigate and propose options with trade-offs;
   do not pick one.** `backup_db.py` and `verify_backup.py` already exist — read them first.

4. ~~**The rate-limiting finding** — still unfixed.~~ **This was wrong when it was written and
   it is still wrong. It was already fixed.** `app/rate_limit.py` keys on Cloudflare's own
   `CF-Connecting-IP` header, which their edge sets and a client cannot forge, precisely so that
   `ProxyFix(x_proto=1)` never has to be widened to trust forged `X-Forwarded-For` hops. Claude
   wrote this item by grepping for `ProxyFix` without opening `rate_limit.py`, noticed the error
   on 2026-09-01, recorded the correction in `ROADMAP.md` — **and never applied it here**, so it
   sat wrong for another day. Left visible rather than deleted, because the failure mode it
   demonstrates (fixing the tracking doc and not the handover) is worth more than the item was.

   Still genuinely open in that same document: **off-box backup** — see item 3.

5. **Costumes / props / sets listings, per show.** The only backlog item with a written,
   attributable request from a real member (`feature_suggestions` row 4, triaged *Planned* by
   Darragh). Scope is settled as per-show. It is also the biggest lift on the board — new data
   model, new admin UI, a matching concept — so it wants its own scoping pass and a written
   proposal before any code.

6. ~~**The two design items**~~ — **both shipped 2026-09-02**, along with a full design pass.
   Society pages now lead with stat tiles; the missing-poster placeholder is a typeset playbill
   rather than an initials box; the societies index, the homepage cards and `/stats` were all
   rebuilt. See `ROADMAP.md`.

   **Two working agreements came out of that, and they outrank any mockup:**

   - **Award counts are never a headline number.** Darragh's steer: *"this is an amateur
     organisation, the awards are secondary not something that they should be flaunting
     openly."* No award figure appears on `/societies` at all and a test asserts that absence; a
     society's own page leads with productions and years active, with awards in their own
     section further down. When a design surfaces a count, ask whether it describes **activity**
     (productions, years, next show) or **ranking** (wins, placings). Activity can lead; ranking
     goes lower, never gold, never in a grid comparing societies.
   - **Build a mockup first and show it to him** — still true, and with one caveat learned the
     hard way: a component drawn standalone will not show you what it does beside its
     neighbours. The first playbill carried title, society and dates, which read perfectly in
     isolation and badly in place, because the card body repeats two of the three directly
     below it.

Explicitly **not** worth a session, per the roadmap's own argument: re-matching the 52 unmatched
ShowTimes reviews (only about 3 will clear), and splitting `public.py` (~1,930 lines — a
judgement call, not a defect; do not let it jump the queue).

---

## Current state, 2026-09-02

Every figure here was counted against the **live** database on that date, not carried forward.

- **HEAD `0a8c8ae`**, deployed and verified live by md5 against the Stack 8 checkout.
  **1034 tests green.**
- **`main` had been red since 2026-09-02 before that session noticed** — a test hardcoded two
  September 2026 dates and the earlier one silently became the past. The previous handback entry
  claiming 985 green was 984. CI does not gate the deploy, so check it rather than trusting a
  count you were handed.
- Shipped 2026-09-01/02, in three groups:
  - **Security:** magic-link tokens hashed at rest (a copy of `aims.db` no longer yields working
    society logins); `/society/request-access` given an email check and a honeypot;
    `notify.send` now reports failure so a lost approval email is visible; exchange contact
    details restricted to signed-in societies.
  - **Layout:** four measured faults — the site scrolled sideways on a phone. Found by comparing
    `document.scrollWidth` to the viewport across 18 routes at 320/390px, not by eye; three of
    the four are invisible in a screenshot.
  - **Design and correctness:** the playbill placeholder, homepage card hierarchy, societies
    index rebuild, first two charts on `/stats`, and four wrong figures (see `ROADMAP.md`'s
    audit block).
- **Posters are a lead-time problem, not a coverage problem** (Darragh, 2026-09-02 - this
  corrects what earlier entries in this file and `HANDBACK.md` said). A society does not
  commission its poster until the run is close. Of 68 upcoming productions, **every one opening
  within a month already has its artwork**; the shows without one are almost all months away and
  have no poster to ask for yet. The chaseable set is the ~17 opening in the next 93 days, which
  is what `POSTER_CHASE_DAYS` in `app/blueprints/admin/_shared.py` now scopes the dashboard
  counter and `/admin/missing-posters` to. **Never quote a raw "54 missing posters" as a
  deficiency** - say how many are chaseable.
- ~~**The real bottleneck is login codes, not posters.**~~ **Cleared 2026-09-02.** 15 of the 17
  chaseable societies had no active code - they physically could not upload a poster. All 15 were
  minted via `scripts/backfills/generate_poster_chase_codes.py` (dry-run then applied), so **all
  17 chaseable rows on `/admin/missing-posters` now show a code and a Copy message button.**
  Nothing is blocked on code any more; the outreach itself is Darragh's.

  **Those 15 expire 2027-05-31**, unlike the ones `admin.generate_society_code` mints, which have
  no expiry at all - that is the open never-expiring-codes finding, and it would have gone from 17
  to 32 if this script had copied the button's behaviour. **Do not "fix" the new codes to match the
  old ones.** If you mint society codes, give them an expiry.
- **Paste-to-upload is live** (`b36d39a`) on both show forms, both logo forms and the new-show form:
  copy an image, press Ctrl+V on the page, it attaches with a preview. See
  `app/templates/_paste_upload.html` for why it is single-file only and has no drag-and-drop.
  **Do not replace the preview's `data:` URL with `URL.createObjectURL`** - the CSP is
  `img-src 'self' data:` and does not allow `blob:`, so an object URL is a broken image plus a
  console violation. It looks like a simplification and is a regression.
- **174 of 195 societies have no logo**, and that *is* a genuine year-round gap - a logo has no
  seasonal timing, so the poster reasoning above does not apply to it.
- **Open queues are empty**: 0 undecided society links, 0 pending photo submissions. The one
  remaining logo candidate is Rathmines & Rathgar — an SVG the image fetcher cannot decode; it
  needs a PNG or JPG address, not another import run.
- **Still open from the security audit:** 17 of 21 active invite codes never expire. Retiring
  them means moving those societies onto magic links, which is outreach rather than code.
- **One design question raised and not decided:** `/titles` puts a gold trophy and a nomination
  count on every one of 316 rows — the same comparison-grid shape Darragh rejected for
  societies. It is per title rather than per society, so it may be a different thing. His call.

Anything unclear, or any judgement that is really Darragh's: ask him rather than guessing. He is
the product owner, not a developer, so explain trade-offs in plain terms and make the technical
call yourself once he has decided the direction.
