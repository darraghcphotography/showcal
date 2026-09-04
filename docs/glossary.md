# Glossary

Canonical terms for this project. **Every other doc, commit message and code comment should use
the term in bold here**, not one of its aliases.

This exists because the domain has several concepts that sound identical in English and are not:
a *show*, a *production* and a *title* are three different things stored in three different
places, and using the wrong one in a query is a silent bug rather than an error. The circuit's own
vocabulary (section, tier, region, season) also collides with ordinary English, and some UI labels
deliberately differ from the database term behind them.

Where a term has a known trap, the trap is recorded with it. Where a claim was checked against the
live database rather than assumed, it says so.

---

## The organisation and the circuit

**AIMS** — the Association of Irish Musical Societies. The amateur musical theatre body this site
tracks. Not a client, not a customer: the site is a record *of* the circuit, kept by Darragh.

**The circuit** — the whole body of AIMS societies producing musicals in a given era. Used when
talking about aggregate activity ("28-37 productions a season"). Deliberately distinguished from
the archive's earliest years: everything before **1976** (`ARCHIVE_CIRCUIT_START_YEAR`) is 98
productions across 51 seasons from exactly three societies backfilling their own histories, so a
row saying "1954: 2 productions" would read as a fact about AIMS when it is a fact about how far
three societies' records go.

**Society** — an amateur musical society. The primary actor: it stages shows, holds a logo, a
region and a section, and can be given a login. 194 on record (counted live 2026-09-04).

**Gilbert** / **Sullivan** — the two AIMS competition tiers a society (or an individual show)
competes in. **These are tiers, not genres, and not a reference to Gilbert & Sullivan operettas** —
a society in the Gilbert tier is not producing G&S. There is a separate award category, *Best
Gilbert & Sullivan/Pre 1935 Show/Modern Opera*, which genuinely does mean the repertoire; the
collision is unfortunate and is exactly why this entry exists.

---

## The three record types that sound the same

This is the most important section in the file. All three are "a musical" in English.

**Show** — one row in `shows`. One society staging one title in one season, as tracked for the
*current era*. This is the operational record: it carries dates, a venue, a poster, a moderation
status, and can be edited by the society itself. `shows.show` is the title text; `shows.season` is
the season string.

**Production** — one row in `productions`. **Derived, never edited by hand.** Rebuilt from
`shows` + `historical_results` + `historical_reviews` on app startup and whenever the source
tables move, so it is the one place that answers "every staging ever recorded, current and
historical, one row each". Keyed by `(season_start_year, society_key, title_key)`. Use this for
counting and listing stagings; use `shows` when you need something only the live record has (a
poster, a moderation state, an editable field).

> **The trap it was built to fix:** `historical_results` holds one row per award *category*, so
> counting stagings from it overstated the circuit by roughly 1.67x — a production nominated five
> times counted five times. If you find yourself counting `historical_results` rows as
> productions, you have the bug `productions` exists to prevent.

**Title** — a musical as a *work*, independent of who staged it. Surfaced at `/titles`. There is
no `titles` table: a title is a `GROUP BY title_key` over `productions`, where `title_key` is
`app.similarity.normalize_title(title)`. 315 on record.

**Show info** — one row in `show_info`, keyed by title text. Facts about the **work**, not about
any staging: composer, lyricist, book author, licensing house, rights status, world premiere.
Despite the name it has nothing to do with the `shows` table, and its `show` column is a title,
not a foreign key. Named before the show/title distinction was drawn; renaming it is a schema
migration nobody has needed enough to do.

**Staging** — plain-English word for "a society producing a title in a season". Use it in prose
when the reader does not need to know which table you mean. In code, say **production**.

---

## Time

**Season** — `'yy/yy'`, e.g. `'26/27'`. The AIMS season runs **mid-June of year N to early May of
year N+1**, concluding with the June National Awards. A show opening in June-December belongs to
that starting year's season; one opening January-early May belongs to the concluding season. The
cutoff is 15 May (`app/season.py::season_for_date`).

**`season_start_year` (the column)** — a real four-digit INTEGER on `productions`, spanning
1911-2027. Unambiguous. Safe to group a decade chart on.

**`season_start_year()` (the function)** — decodes a `'yy/yy'` string with a **pivot at 50**, so
`'11/12'` resolves to 2011. Correct for `shows.season` (whose real range is 05/06 to 27/28) and
correct until 2050. **Not a general decoder for the awards archive**, which starts in 1912, where
`'11/12'` is genuinely ambiguous.

> These two are different things with the same name and different guarantees. A note in ROADMAP.md
> once warned that a decade chart would confuse 1912 with 2012 — that warning was about the
> *function* and was wrong about the *column*, which had already resolved the ambiguity. Checked
> against the live database before the charts shipped.

**Year** (in `historical_results.year`) — the awards year, which is **`season_start_year + 1`**.
The 26/27 season's awards are year 2027. Verified: **0 mismatches in 4,847** linked rows
(2026-09-02), so the relationship is safe to rely on.

**`SHOWS_COVERAGE_START_YEAR` = 2024** — the awards year at which `shows.csv`'s own coverage
begins. Any query treating a `historical_results` row as equivalent to a `shows` row must stay
*below* this year or it double-counts.

---

## Classifying a society

Three separate axes that all get loosely called "status" in conversation. They are independent.

**Region** — one of six geographic areas: Eastern, Western, Northern, South-West, South-East,
Midlands. Enforced by CHECK constraint; mirrored in `app/constants.py::REGIONS`.

**Section** — the AIMS competition tier: `Gilbert`, `Sullivan`, `Non-AIMS`, or `Inactive`. A
*show* can only be the first three (a society is never "Inactive" *as a show*). Says which
competition category, **not** whether the society is alive.

**Lifecycle status** — whether the society still exists and is in scope: `Active`, `Dormant`,
`Closed`, `Out of scope`, `Unverified`. Deliberately distinct from `section = 'Inactive'`. Every
row was filled once from a heuristic (last year of any recorded production) and **these are
guesses labelled as such** — a moderator's own decision always wins and a re-run never overwrites
one.

---

## Records on a show

**Source** — `import` (from the CSV), `submission` (member-submitted), or `historical`.
`import_csv.py` only ever updates `source='import'` rows, and never regresses a populated field to
blank, so a value set in the app survives a re-import.

**Moderation status** — whether a submitted show is visible publicly. Separate from **review
status** (`Published`, `Scheduled`, `Not adjudicated`, `None`), which is about *adjudication*, not
moderation. Two different words for two different queues.

**Venue** — a building, one row in `venues` (118 on record), with a slug, a type and usually
coordinates. Distinct from **`shows.venue`**, a free-text string. Every one of 523 venue strings
maps to a venue page (verified 2026-09-02), but four are not buildings at all — `Cork`,
`Wexford`, `Cork run`, `40th Anniversary (March run)` are spreadsheet artefacts and must never get
a map pin.

**Venue type** — what kind of building (`Theatre`, `Arts Centre`, `School or College`,
`Community or Parish Hall`, `Other`). The `venues` table has **no CHECK constraint** on it —
SQLite cannot add one after the fact — so `VENUE_TYPES` in `app/constants.py` is the only gate.
`NULL` means nobody has classified it yet, which is a real state.

---

## Awards

**Award category** — e.g. *Best Overall Show*. Some are **society-level** and some are
**person-level**; `AWARD_CATEGORIES` in `app/constants.py` records which, **checked against real
data rather than inferred from the column name**.

**Nominee** — `historical_results.nominee_name`. **For society-level categories this column holds
a society name, not a person.** Best Technical, Best Visual, Best Programme and Best House
Management all do this. The `/awards` table hides the Nominee column for those rows because it
would just duplicate the Society column.

**Result** — `Winner`, `Second Place`, `Third Place`, `Nominee`.

**Adjudicator** — the AIMS-appointed judge for a season and tier. One season+tier legitimately
carries two (13/14 Gilbert), which is a real mid-season change, not a data fault.

> **Awards are secondary.** A standing product rule, not a data note: award counts are never a
> flagship number anywhere on the site. When a design surfaces a count, ask whether it describes
> **activity** (productions, years active, next show) or **ranking** (wins, placings). Activity can
> lead; ranking goes lower, never gold, never in a grid comparing societies against each other.

---

## Access

**Invite code** — the shared `adjective-noun-NNNN` code that unlocks a society's own editing
dashboard. Also called a **login code** in user-facing copy and in Darragh's outreach messages;
`invite_codes` is the table. Both names are current — prefer *login code* when writing to a
society, *invite code* when writing about the table.

**Magic link** — the passwordless email flow (`society_access_requests`). It is **not a rival to
invite codes**: approving a magic link *mints* an invite code, and the link opens a session keyed
to it. Tokens are hashed at rest; the plaintext lives only in the emailed URL.

---

## UI labels that differ from the database term

Keep both in mind — the label is what Darragh and societies say, the term is what the code says.

| UI label | Database / code term |
|---|---|
| Musicals Repertoire | `titles` (`public.titles_list`) — renamed from "All Shows", which read as *upcoming* shows and delivered a 315-title catalogue |
| Costumes & Props Exchange | `wardrobe_items`, `wardrobe_photos` |
| Login code | `invite_codes` |
| Adjudication / review status | `shows.review_status` (not `moderation_status`) |
| Tier | `section` |
