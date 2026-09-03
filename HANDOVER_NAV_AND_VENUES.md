# Handover — navigation, the venues hub, and /titles

**Written 2026-09-03 by Claude (Opus 5) for Gemini Flash 3.8, at Darragh's request.**

You are implementing `mockups/ux_audit_and_nav_venues_proposal.html` — the three-part proposal
covering the nav restructure, the unified venues hub, and the `/titles` awards realignment.

Read `CLAUDE.md` first, then `AGENTS.md` — especially §3 (the deploy rule) and §5 (traps). This
file does not restate either.

**The proposal is good and its diagnosis is correct.** I checked each finding against the running
code and the live database rather than taking it on trust; results in §1. What follows is the
context it cannot carry: what is already true, what will bite, and the rules that outrank it.

---

## 1. Its findings, checked

| Claim | Verdict |
|---|---|
| "Explore" holds 8 disparate items | **True** — All Shows, Costumes & Props, Seasons, Season Calendar, Societies, Venues, Reviews, Adjudicators |
| "All Shows" is misleading — goes to the script catalogue | **True** — `public.titles_list`, a repertoire A–Z, not upcoming shows |
| "Seasons" vs "Season Calendar" sit adjacent and sound identical | **True** |
| Reviews sits in Explore while Awards sits in History | **True** — they are split across two menus |
| `/venues` and `/venues/map` are disconnected pages | **True** — separate routes, no cross-link beyond a text line |
| `/titles` still shows a gold trophy nomination count on every row | **True**, all 315 titles |

One more the proposal did not catch, and which its restructure would fix anyway:

- **Venues appears in the desktop nav twice** — inside the Explore dropdown *and* as a top-level
  link (`base.html`, two `venues_index` references in the header). Whichever way the nav lands,
  it should appear once.

### Numbers in the mockup are illustrative — do not hard-code them

It says "All Theatres (182)" and "195 active and historical societies". The live figures are
**118 venues** and **194 societies**, of which **58 venues have an upcoming show**. `/titles`
carries **315** titles, not 316. Read counts from the database, as the current pages do.

The venue examples are largely real, though — National Opera House at 855 seats matches the record
exactly. Capacity is on 106 of 118 venues; a venue card that assumes one will render a hole for the
other 12.

---

## 2. The two things most likely to go wrong

### The CSP, when you merge the map into the directory

`app/__init__.py` relaxes the Content Security Policy **only on `public.venues_map`**:
`script-src`/`style-src` gain `https://unpkg.com` (Leaflet, SRI-pinned) and `img-src` gains
`https://*.basemaps.cartocdn.com` (tiles).

A unified hub means Leaflet loads on the main venues route, so **that exception has to widen to
cover it**. That is a deliberate security-boundary change: say so out loud in the commit rather
than letting it ride along. If you forget it entirely, the map silently renders nothing — a CSP
violation logs to the console and the page looks merely empty. This has bitten twice: once here,
once on an image preview that used a `blob:` URL the CSP does not allow.

Keep the relaxation as narrow as the routes that need it. Do not move it to the global policy.

### Per-row queries in a list view

`/venues` renders 118 rows. "What's Playing Here Next" per venue is exactly the shape that took
the site down with a 524 on 2026-08-19: an O(n) helper called once per row.

Aggregate once, outside the loop. `_society_card_facts` in `app/blueprints/public.py` is the
worked example — two grouped queries for the whole page, run *after* pagination — and
`tests/test_societies_index_cards.py` has a query-count ceiling test you can copy directly. Do
that before it is slow, not after.

---

## 3. Rules that outrank the proposal

- **Award counts are never a headline number.** Darragh, 2026-09-02: *"this is an amateur
  organisation, the awards are secondary not something that they should be flaunting openly."*
  Section 3 of the proposal is applying that principle to `/titles`, correctly. Note the same test
  when you design anything else: does this number describe **activity** (stagings, regions, years,
  what's on next) or **ranking** (wins, nominations, placings)? Activity can lead. Ranking goes
  lower, never gold, never in a grid comparing societies against each other.
  `tests/test_societies_index_cards.py` asserts no award figure appears on `/societies` at all.
- **Describe visible changes to Darragh before pushing.** Fixes, data work, tests and docs go
  straight to `main`; anything a visitor or committee member can *see* gets described to him
  first. This sits on top of `AGENTS.md` §3's table.
- **He is the product owner, not a developer.** Explain trade-offs in plain terms and make the
  technical call yourself once he has picked a direction.
- **Nothing that ranks societies against each other.** A "versus" concept was explicitly rejected;
  AIMS is collaborative.

---

## 4. What already exists — do not rebuild it

The map is **not** the prototype. `mockups/ireland_theatre_map.html` used **9 fabricated venues**;
`public.venues_map` pins every venue with real coordinates — **109 of 118**. Reuse it; the
proposal's split view is a re-housing of working code, not a rewrite.

Also already built, in case a nav label tempts you to recreate one: `/season/calendar`, `/titles`
with rights status, `/stats/trends` (Decades), `/watchlist` with `.ics` export, the header search,
the mobile 5-tab bar, `venue_type` badges and filter, and passwordless society magic links.

`VENUE_TYPES` in `app/constants.py` is the source of truth for the badge set — the `venues` table
has no `CHECK` on `venue_type` (SQLite cannot add one after the fact), so the application layer is
the only gate.

**8 of 118 venues have no type and 9 have no coordinates**, and four of those nine are not
buildings at all — `Cork`, `Wexford`, `Cork run`, `40th Anniversary (March run)` are free-text
artefacts from the spreadsheet import. They must never get a pin. Design the empty states for
these rather than assuming every venue has everything.

---

## 5. Tests you will have to update, deliberately

The nav is in `base.html`, so it renders on every page and several tests assert its contents:

- `tests/test_homepage_split.py::test_nav_matches_new_arrangement`
- `tests/test_reviews_index.py::test_nav_links_to_reviews`
- plus nav assertions in `test_hidden_societies.py` and `test_stats_and_season_filters.py`

Update them to the new arrangement — that is correct, the nav is changing. What is **not**
acceptable is weakening an assertion until it passes. A test here should still fail if a
destination becomes unreachable. The house style is that a test names the bug it exists for; see
`tests/test_person_identity.py`.

---

## 6. Do not "tidy" these — each looks like an improvement and is a regression

- The paste-upload preview builds a **`data:` URL**, not `URL.createObjectURL`: the CSP is
  `img-src 'self' data:` and does not allow `blob:`.
- Brand images under `app/static/` are **flat RGB with no alpha**. Cloudflare's image optimisation
  composites transparency against crimson — that is how every WhatsApp preview became a gold "M"
  on a red field.
- Use the **`absolute_url()`** Jinja global for absolute URLs. `url_for(..., _external=True)`
  reports `http://` in production because the Cloudflare Tunnel gives the origin no
  `X-Forwarded-Proto`. A test fails if `content="http://` reappears in the page head.
- The society checklist's hidden `rows` / `editable` markers are what make a **filtered** save
  safe. Remove them and a save wipes every society not on screen.
- Society login codes minted by scripts **expire**. The admin button's do not, and that is the
  open finding rather than the model to copy.

---

## 7. How to know you have not broken anything

```bash
py -m pytest        # 1067 green as of 03b83a5. Must be green before any push.
```

For anything visual, check it in a real browser at **320px and 390px** and confirm the page does
not scroll sideways. Four real mobile layout faults shipped unnoticed because screenshots hide
them — they were only found by comparing `document.scrollWidth` to the viewport across 18 routes.
Measure; do not eyeball.

After pushing, verify what actually deployed:

```bash
sed 's/\r$//' <file> | md5sum
# compare with the same command on the NAS at
# /share/CACHEDEV2_DATA/Data/config/portainer/compose/8/<file>
```

GitOps polls roughly every 5 minutes and has taken 10+ today; a MISMATCH checked too early is not a
failed deploy. Re-check before concluding.

Log what you did in `HANDBACK.md`, in the shape the file already shows. End commit messages with
`Co-Authored-By: Gemini Flash <noreply@google.com>` so `git log` alone answers who did what, and
prefix branches `gf/`.

---

## 8. One judgement call to put back to Darragh

The proposal renames **"All Shows" → "Repertoire"**. The diagnosis is right — "All Shows" reads as
*upcoming* shows and delivers a 315-title script catalogue. But "Repertoire" is industry language,
and the audience is volunteer committee members and theatre-goers, not producers. "Shows A–Z" or
"Every Musical" may land better with them.

Worth one question rather than a silent decision, since the whole point of the rename is that the
current word confuses the people using it.
