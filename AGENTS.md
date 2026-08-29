# Handoff — running this project while Claude is unavailable

**Written 2026-08-29 by Claude (Opus 5), for Gemini Antigravity, at Darragh's request.**
Darragh's Claude usage resets on **Friday 5 September 2026**. Until then you are the one
driving this repo, the live site, and git — not a research delegate handing outputs back, which
is the role you have had here before.

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

Before any push to `main`: `py -m pytest` must be green. **945 tests pass as of `d0b591e`.**

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
- **Verify before you claim.** Twice this session a `ROADMAP.md` statement turned out to be
  wrong when checked against the live database (the logo import "had never been run" — it had,
  and 10 candidates were already approved). Check code and data, not the tracking doc.
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
   - `/admin/historical-society-links` — **64 printed names** awaiting a decision, releasing
     **529 award rows** that are missing for no other reason. Roughly ten minutes of clicking,
     and the single best value-per-effort item on the board.
   - `/admin/photo-submissions` — **3 unread**, from 28 August (Carnew ×2, St. Mary's Choral
     Society Clonmel). Real society history waiting to be transcribed by hand.
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

4. **The rate-limiting finding** — `docs/SECURITY_AND_ARCHITECTURE_OBSERVATIONS.md` §1, still
   unfixed. `ProxyFix` is configured `x_proto=1` with no `x_for`, so behind the Cloudflare
   Tunnel every visitor shares one rate-limit bucket and ten failed logins can 429 real users.
   **The naive fix is dangerous**: trusting more forwarded hops than actually exist lets a
   client spoof its own IP and evade the limits entirely. The hop count must match the real
   tunnel path, verified, not assumed. **Branch, not `main`.**

5. **Costumes / props / sets listings, per show.** The only backlog item with a written,
   attributable request from a real member (`feature_suggestions` row 4, triaged *Planned* by
   Darragh). Scope is settled as per-show. It is also the biggest lift on the board — new data
   model, new admin UI, a matching concept — so it wants its own scoping pass and a written
   proposal before any code.

6. **The two design items**, both of which need Darragh's eye:
   - Stat tiles on society pages. `/venues/<slug>` uses the clearest summary pattern on the
     site and is the only page that does; society pages carry the same information as beige tag
     pills, which scan far worse. The coverage checklist already computes the numbers.
   - Society logo placeholders. With 176 of 194 societies missing a logo, the flat initials box
     is the *normal* case, and it sits directly above a colourful poster wall on the societies
     that have one.

   **Build a mockup first and show it to him.** The last design item of this kind went far
   better as a mockup than as a direct edit, and that is recorded as a working agreement.

Explicitly **not** worth a session, per the roadmap's own argument: re-matching the 52 unmatched
ShowTimes reviews (only about 3 will clear), and splitting `public.py` (~1,930 lines — a
judgement call, not a defect; do not let it jump the queue).

---

## Current state, 2026-08-29

- **HEAD `d0b591e`**, deployed and verified live. **945 tests green.**
- Shipped today: `SECRET_KEY` fail-fast; photo submissions split into four kinds; show edits
  return you to the page you came from; lifecycle status guessed for all 194 societies; person
  identity resolution (internal only).
- **54 of 67 upcoming productions have no poster; 176 of 194 societies have no logo.** Darragh
  is working the poster list by hand. Only 5 of those 54 societies have an active login code —
  generating one is the first step of any outreach, and `/admin/missing-posters` does it inline.
- Open queues right now: 64 society-link decisions, 3 photo submissions, 1 logo candidate
  (Rathmines & Rathgar — an SVG the image fetcher cannot decode; it needs a PNG or JPG address,
  not another import run), 1 feature suggestion.

Anything unclear, or any judgement that is really Darragh's: ask him rather than guessing. He is
the product owner, not a developer, so explain trade-offs in plain terms and make the technical
call yourself once he has decided the direction.
