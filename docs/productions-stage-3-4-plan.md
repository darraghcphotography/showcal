# Productions-table migration, stages 3 and 4

Written 2026-08-23 as a handoff. Stages 1 (`/stats`) and 2 (admin counts) are live and
have been since 2026-08-22 - see `ROADMAP_ARCHIVE.md`, "Productions-table migration,
stages 1-2". This plan covers the last two stages: cutting the public show/society
pages over to `productions`, and answering the open architecture question about whether
that table should become authored rather than derived.

Read `docs/data-model.md`'s "Productions (the shared definition of 'a staging')"
section first if you haven't. Read `CLAUDE.md`. This plan assumes both.

---

## 1. Context: why this work, and what it closes

`productions` exists because the site had no shared definition of "a staging". Every
page that needed to count or list productions re-derived its own by unioning `shows`
with `historical_results` and anti-joining the skeleton rows - and they disagreed with
each other. That cost 371 productions on `/stats`, then a further 823.

Stages 1 and 2 fixed the two surfaces where the disagreement had already been *caught*.
Stage 3 fixes the surfaces where it hasn't been - which turn out to be worse, not
better, than the ones already fixed.

**The headline problem stage 3 closes.** `historical_results` holds one row per award
*nomination*, not one row per production. `titles_list()` in `app/blueprints/public.py`
counts those rows as if each were a staging:

```sql
SELECT show, COUNT(*) AS n FROM (
    SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical'
    UNION ALL
    SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
)
GROUP BY show
```

A production nominated in five categories counts five times. **Measured 2026-08-23
against current production data (1,385 shows / 4,879 award records / archive from 1912):**

| Title | Shows A-Z says | Real productions |
|---|---|---|
| Jesus Christ Superstar | 152 | 78 |
| Fiddler on the Roof | 143 | 81 |
| Oliver! | 95 | 66 |
| West Side Story | 100 | 48 |
| Les Miserables | 22 | 14 |

Summed across the whole A-Z, the "Times performed" column adds up to **4,677 against
2,802 real productions** - the page overstates the circuit by roughly **1.67x**, and the
same query backs the "Shows" section of `/search`.

Re-measure anyway before you ship (§7.1) - production moves daily. The script that
produced these numbers is worth re-running rather than rewriting; it lives in the
session scratchpad as `replan_numbers.py` and is reproduced by §7.1a/b.

The same page's own detail view already gets it right: `title_detail()`'s archive table
does `SELECT DISTINCT year, society_name`, so `/titles/Jesus Christ Superstar` lists 57
archive rows under a heading that the A-Z says is 148. The two pages have been
contradicting each other in public.

**Three more real defects in the same surfaces, all confirmed against the code:**

- **Society pages list recent productions twice.** `society_detail()`'s archive query
  has no year filter at all, despite the template heading reading "Show history
  (pre-23/24 archive)". Any 2024+ award record appears both in the "Show history" table
  (from `shows`) and again in the archive timeline below it. On the stale local copy
  that's 198 (year, show, society) combinations from 2024 on, 178 of which also have a
  `shows` row.
- **Some real productions have no page at all.** `title_detail()` 404s when there's
  neither a `shows` row nor a pre-2024 award record. A title first staged in 24/25 or
  later that reached the site only through the awards archive therefore 404s - invisible
  on the A-Z, absent from the sitemap. **16 titles as of 2026-08-23**, splitting into two
  kinds - and the distinction matters when you show Darragh the list:
  - **Genuinely missing** (9): `Michael Collins` (2 productions), `Songs For A New World`
    (2), `Miss Saigon (School Edition)` (2), `Bad Girls`, `Cinderella`, `Disco Inferno`,
    `Miracle on 34th Street`, `She Loves Me`, `Summer Holiday`.
  - **Spelling variants of a title already on the A-Z** (7): `Annie - The Musical`,
    `Big The Musical`, `Elf - The Musical`, `Fame: The Musical`, `Shrek`,
    `Peter Pan, A Musical Adventure`, `Sugar The Musical - Some Like It Hot`. These are
    real `/admin/duplicate-titles` work, not a bug in this cutover. **Decided 2026-08-23:
    ship the cutover and clean these up separately** - do not block the migration behind a
    manual title-merge pass, and do not fold the merges into this work. Hand Darragh the
    list at merge time (§7.1b) so the new rows are expected rather than discovered.
- **`show_detail()`'s award history carries a century bug.** It matches award records
  via `historical_results_year(show["season"])`, the helper whose own docstring says it
  "cannot express an award year before 2001". Latent today (the `shows` table holds
  09/10 onward), live the moment anyone bulk-creates an older `shows` row.

**What "done" looks like.** Every public surface that answers "how many productions" or
"which productions" reads `productions`; the surfaces that answer "which award, which
category, who won" still read `historical_results` unfiltered, because that's a
different question (see §5). `SHOWS_COVERAGE_START_YEAR` and `historical_results_year`
are no longer imported by `public.py` at all - not deleted from the codebase, just no
longer needed by the pages this plan touches. `/stats`'s numbers are unchanged (they're
already right; if stage 3 moves them, stage 3 is wrong). And a written decision on
stage 4, recorded where it will be found again.

---

## 2. Ground rules carried over from the original brief

These were Darragh's own calls when the migration was scoped (`ROADMAP_ARCHIVE.md`,
"Scoping brief for the productions-table session"). They still hold.

1. **Work in an isolated worktree.** The blast radius crosses most of the public query
   surface. Use the `EnterWorktree` capability (stages 1-2 were built in
   `worktree-productions-table`); merge to `main` only when the suite is green and the
   real-data comparison in §6 has been run and read.
2. **Additive only.** Nothing gets dropped or renamed. `SHOWS_COVERAGE_START_YEAR` stays
   in `app/constants.py` - `info.py` still uses it legitimately for the /stats season
   banding, and `app/blueprints/admin/historical_reviews.py` references it in comments.
   Only `public.py`'s and `feeds.py`'s *uses* of it go away.
3. **Verify against real production data before trusting anything**, using a read-only
   snapshot pulled from the NAS. Never edit that copy.
4. **Any rebuild still ends with a verification pass that re-derives from the database**,
   not from the dict it just built. This plan adds no new writer, so that discipline is
   preserved by not touching it - see stage 4.
5. **The full suite stays green.** `py -m pytest`, 541 passing at commit `0517963`,
   ~45s with xdist.

**No schema change is needed for stage 3.** No new columns, so no `COLUMN_MIGRATIONS`
entry in `app/db.py`. If you find yourself wanting to add a column to an existing table,
stop - that's CLAUDE.md's hard rule and it means the plan has drifted.

---

## 3. State check before you start

Confirm these are still true; the plan is wrong if any has moved.

- `app/blueprints/public.py` imports `productions_build` already (line 9) - no new
  import needed there.
- `title_detail()` already calls `productions_build.ensure_current(db)`. **No other
  public route does.** `titles_list()`, `search()`, `society_detail()` and
  `show_detail()` do not - they must, before they read `production_id` or `productions`,
  or they silently under-report (ROADMAP tech-debt item 1).
- `app/circuit_intelligence.py`'s `production_ids_for_title()` already reads
  `productions` by `title_key` - the panel on `/titles/<title>` is already cut over. The
  count and the tables above it are not, which is why they disagree.
- `productions_build.collect()` reads `SELECT id, society_id, season, show, region,
  source FROM shows` with **no `moderation_status` filter**. A pending or rejected
  submission has a production row. This is the single most important fact in this plan
  - see §4.0 and §8.

---

## 4. Stage 3: exactly what changes

### 4.0 One shared definition of "publicly on record" (do this first)

Every surface below needs the same filter, and if each writes its own we've rebuilt the
original problem one level up. Add a single SQL fragment next to the key derivation, in
`app/productions.py` - the module whose whole stated purpose is "so the definition can't
drift between callers":

```python
# A production the public site may count or list. The productions table is built
# from every shows row regardless of moderation_status (see productions_build.
# collect), so a pending or rejected submission has a production row too -
# filtering that out is the caller's job, and every public surface has to do it
# the same way or they will disagree again, which is the whole reason this table
# exists.
#
# An award record needs no status check: historical_results has no moderation
# gate, and a row only exists because AIMS published the result.
#
# "On record", not "has already happened". /titles has always counted an
# announced future show, and info.py's own happened_production predicate asks
# the narrower question (it takes a :today parameter). Deliberately two
# predicates, not one - don't merge them.
#
# Callers must refer to the table as `productions` (not an alias).
ON_RECORD_PRODUCTION = """
    (EXISTS (SELECT 1 FROM shows
              WHERE shows.production_id = productions.id
                AND shows.moderation_status = 'approved')
     OR EXISTS (SELECT 1 FROM historical_results
                 WHERE historical_results.production_id = productions.id))
"""
```

Also in this step, add `productions_build.ensure_current(db)` as the first database call
in `titles_list()`, `search()`, `society_detail()` and `show_detail()`. `show_detail()`
already calls `venues_build.ensure_current(db)`; put the productions one beside it.

This step changes no behaviour and the suite must stay green with zero test edits.
That's the point: it's a safe, separately committable foundation.

*Cost note:* `ensure_current()` is ~50ms when nothing has changed, and `show_detail()`
is the highest-traffic page on the site. That's the accepted price of the derived model
(and `/stats` serves in ~180ms on the NAS with it). Replacing the scattered call sites
with a `before_request` is ROADMAP tech-debt item 1 and is explicitly **out of scope**
here - don't bundle a refactor into a cutover.

### 4.1 Shows A-Z, search, and the sitemap - the count that's wrong

Three places share one query shape. Fix the definition once; apply it three times.

**`titles_list()`** (`app/blueprints/public.py`, ~line 1091). Replace the union query
and the `last_performed` lookup:

```sql
SELECT title_key, MIN(title) AS show, COUNT(*) AS n, MAX(season_start_year) AS last_year
  FROM productions
 WHERE {ON_RECORD_PRODUCTION}
   [AND title LIKE ? ESCAPE '\']
 GROUP BY title_key
 ORDER BY {TITLES_SORT_OPTIONS[...]}
```

- `MIN(title)`, not a bare `title`: with `GROUP BY title_key`, a bare column picks an
  arbitrary row's spelling. `MIN` is deterministic. (Aliasing it `show` keeps
  `TITLES_SORT_OPTIONS` - `"show COLLATE NOCASE"`, `"n DESC, show COLLATE NOCASE"` -
  working unchanged, and keeps `titles_list.html` untouched.)
- `last_year` folds into the same query. The separate `last_performed` query goes away
  entirely; so does its `CAST(substr(opening_date, 1, 4) AS INTEGER)`.
- `manual_links` and `has_info` still key on the raw display title (`show_links` and
  `show_info` are keyed on exact text). Keep them as they are - see the trap in §8.9.
- The row dicts keep every key the template already uses (`title`, `count`,
  `last_year`, `url`, `is_manual`, `has_info`, `search_url`). **No template change.**

**`search()`** (~line 248): the `titles` query becomes the same shape, minus the sort,
plus `LIMIT ?`. `search.html` reads `t['show']` and `t['n']`, so aliasing `MIN(title) AS
show` means **no template change** there either.

**`sitemap_xml()`** (`app/blueprints/feeds.py`, ~line 199): same replacement. Add `from
.. import productions_build` and call `ensure_current(db)`. This matters beyond tidiness
- today the sitemap mirrors `titles_list()`'s definition exactly, so every title page
that the A-Z can't see (the `Rocky Horror Show` class) is also missing from the sitemap.
Drop the now-unused `SHOWS_COVERAGE_START_YEAR` import from `feeds.py`.

**One deliberate display change.** "Last performed" today is `MAX` over two different
conventions: a calendar year from `shows.opening_date`, and `historical_results.year`,
which is the season's *ending* year. After the change it's `season_start_year` - the
year the season opened - for everything. Archive-derived values therefore drop by one
(2014 becomes 2013). That's a fix to an inconsistency, not a regression, but it is
visible, it's the only cosmetic change in stage 3, and Darragh should be told before it
ships. The "Longest since performed" sort is unaffected (relative order is identical).

### 4.2 `/titles/<title>` - the detail page

`title_detail()` (~line 1163). Three changes; the route already calls `ensure_current`.

**Join the "full detail" table through productions**, so it groups by identity rather
than raw string and sorts by a real year:

```sql
SELECT shows.*, societies.name AS society_name
  FROM shows
  JOIN societies ON societies.id = shows.society_id
  JOIN productions ON productions.id = shows.production_id
 WHERE productions.title_key = ? AND shows.moderation_status = 'approved'
 ORDER BY productions.season_start_year DESC, societies.name
```

This also retires a latent trap: the current `ORDER BY shows.season DESC` is a text sort
on a `'yy/yy'` string.

**Replace the archive table** with the productions that have no `shows` row, rather than
with "everything before 2024":

```sql
SELECT productions.season_start_year + 1 AS year, productions.society_name, productions.society_id
  FROM productions
 WHERE productions.title_key = ? AND {ON_RECORD_PRODUCTION}
   AND NOT EXISTS (SELECT 1 FROM shows
                    WHERE shows.production_id = productions.id
                      AND shows.moderation_status = 'approved')
 ORDER BY productions.season_start_year DESC
```

`season_start_year + 1` reproduces `historical_results.year` exactly - the rebuild's own
verification pass asserts `p.season_start_year = h.year - 1` for every linked award
record, so this is exact by construction, not an approximation. Displaying it that way
means the only visible difference on this page is which rows appear, never a number
quietly shifting. `title_detail.html` reads `row['year']` and `row['society_name']`:
**no template change to the table body.**

**The two headings are now wrong and must change.** "Since 23/24 (full detail)" and
"Earlier history (AIMS awards archive)" become a split on *whether there's a show page
to link to*, not on era - a skeleton `shows` row from 12/13 belongs in the top table
because it has a real page. Suggested: "Productions with full detail" and "Also on
record (awards archive)". Keep the two-table shape: merging them into one unified
timeline is a visual redesign, and this repo is mockup-first for anything visual
(ROADMAP working agreements). Note it as a follow-up; don't do it here.

**Also fix `production_ids_for_title()`** in `app/circuit_intelligence.py` to apply
`ON_RECORD_PRODUCTION`. It currently returns every production with that `title_key`,
including one backed only by a pending or rejected submission, which inflates the
regional-distribution chips and the revival panel's `production_count`. Small, cheap,
and it makes the panel agree with the count directly above it.

`debut_label` and the 404 condition follow from the productions rows (earliest
`season_start_year + 1`; 404 when there are none), which also retires the
`min(s['season'] for s in shows)` lexical comparison.

### 4.3 `/societies/<id>` - stop listing the same production twice

`society_detail()` (~line 819).

**The archive timeline.** Replace the `historical_rows` query and its Python grouping
with two queries:

```sql
-- the productions (one row per staging, no shows row of its own)
SELECT productions.id, productions.season_start_year + 1 AS year, productions.title AS show,
       (SELECT tier FROM historical_results
         WHERE production_id = productions.id AND tier IS NOT NULL LIMIT 1) AS tier
  FROM productions
 WHERE productions.society_id = ? AND {ON_RECORD_PRODUCTION}
   AND NOT EXISTS (SELECT 1 FROM shows
                    WHERE shows.production_id = productions.id
                      AND shows.moderation_status = 'approved')
 ORDER BY year DESC, show

-- the award records to hang off them
SELECT production_id, year, tier, category_name, result, show, nominee_name, role, reason
  FROM historical_results
 WHERE society_id = ? AND production_id IS NOT NULL
```

Group the second by `production_id` in Python and attach as `awards`, exactly as the
current code attaches by `(year, show)`. The template's contract - `prod['year']`,
`prod['tier']`, `prod['show']`, `prod['awards']` - is unchanged, so
`tests/test_society_historical_show_split.py` should stay green as written. Rows with no
category and no result still produce an empty `awards` list and render "No award record".

`person_awards` (award records with `show IS NULL` - the Mary Kelly/Unsung Hero class)
becomes its own small query rather than a Python filter over the old row set:
`WHERE society_id = ? AND show IS NULL ORDER BY year DESC`. Those records have no
production by definition (`production_key()` returns `None` for a blank title), so they
can't come through the productions path.

**Rename the heading.** "Show history (pre-23/24 archive)" is now "productions with no
show page of their own", not an era. Something like "Earlier productions (awards
archive)".

**Keep the award badges - decided 2026-08-23, do not re-open.** A production that has
both a `shows` row and award records currently shows its award badges in the archive
table. Deduping would leave it only in the "Show history" table, which has no awards
column, so those badges would stop rendering. Darragh's call was to **build the awards
column in this same step** rather than accept a temporary regression: no society page
should lose information at any point in the cutover.

So step 4 also adds, to the "Show history" table: one query keyed on
`shows.production_id` returning that production's award records, and one extra cell in
`society_detail.html` rendering the same badge markup the archive table already uses.
Reuse the existing markup rather than inventing a second badge style - a society page
must not show one production's awards one way and another's a different way.

**Badges** (`_society_badges()`, ~line 699):

- Century Club: the two-query `pre_2024_productions + recent_productions` sum collapses
  to `SELECT COUNT(*) FROM productions WHERE society_id = ? AND {ON_RECORD_PRODUCTION}`.
  The function's own comment admits today's version is deliberately imprecise ("skips
  that logic's skeleton-show reconciliation... low-stakes for a decorative badge") -
  that caveat can go, because the precise answer is now one query. Expect a few
  societies to cross or fall back over the 100 threshold.
- Golden Jubilee streak: `SELECT DISTINCT season_start_year FROM productions WHERE
  society_id = ? AND {ON_RECORD_PRODUCTION}`, dropping the `historical_results_year(...)`
  call on `shows.season`. Today's set mixes award years with `historical_results_year()`
  output; both are the season's *ending* year, so moving to `season_start_year` shifts
  every element by exactly -1 and streak lengths are unchanged.
- The other five badges (Triple Crown, Clean Sweep, Dual Tier, All-Rounder, Debut
  Delight) stay on `historical_results` - see §5.

**`active_since`.** The current code is:

```python
award_totals = db.execute(
    "SELECT COUNT(*), SUM(CASE WHEN category_name = 'Best Overall Show' THEN 1 ELSE 0 END), MIN(year) "
    "FROM historical_results WHERE society_id = ? AND result = 'Winner'", ...)
...
active_since = earliest_award_year or (2000 + int(earliest_season[:2]) if earliest_season else None)
```

That `MIN(year)` is scoped to `result = 'Winner'`, so "Active since" is currently the
year of a society's **first win**, not the first year they're on record - the comment
above it claims otherwise. (The very next query in the file already spotted this exact
scoping trap for a different column and worked around it; this one was missed.) The
fallback also hard-codes a 2000 pivot, which is the same century bug that cost this
migration two rounds already.

Replace with `SELECT MIN(season_start_year) + 1 FROM productions WHERE society_id = ?
AND {ON_RECORD_PRODUCTION}`. **This will move "Active since" earlier on many society
pages** - correctly, but visibly. Flag it to Darragh alongside the "Last performed"
change; both are fixes, and both will be noticed.

Leave the `future_shows` / `shows` split (`s["season"] > current`) alone. It's a text
comparison on season strings and it is a latent trap (§8.4), but it operates on `shows`
rows only, `shows` holds 09/10 onward, and changing it is not what this migration is
for.

### 4.4 `/shows/<id>` - award history by identity, not by arithmetic

`show_detail()` (~line 1046). The whole `award_history` block - the
`historical_results_year(show["season"])` lookup plus the Python
`normalize_title` re-match - collapses to:

```sql
SELECT show, tier, category_name, result, nominee_name, role, reason
  FROM historical_results
 WHERE production_id = ?
   AND (category_name IS NOT NULL OR result IS NOT NULL)
```

with `show["production_id"]` (already available - the route selects `shows.*`), guarded
by `if show["production_id"]:` since a titleless placeholder row has none. Requires the
`ensure_current` call added in §4.0.

This is the cleanest win in stage 3: it deletes a hand-rolled join on (society, decoded
year, normalized title) in favour of the foreign key that exists precisely to express
it, and it takes the century bug with it. The `(category_name IS NOT NULL OR result IS
NOT NULL)` filter is kept deliberately - it's what excludes a bare "this production
happened" row (from `admin.bulk_historical_productions`) from rendering as if it were an
award.

Nothing else on this page changes. In particular `historical_review` stays keyed on
`show_id`: it's *this show's* review, not the production's, and it drives an anchor link
to text on this page.

### 4.5 Imports to drop at the end

Once §4.1-4.4 are done, `public.py` should no longer use `SHOWS_COVERAGE_START_YEAR` or
`historical_results_year`. Remove both from its import lines (lines 16 and 20) - but
leave the constant in `constants.py` and the helper in `season.py`, which other modules
still use legitimately.

---

## 5. What must NOT change

This matters as much as the list above. The pattern is easy to over-apply, and applying
it to these would be a real regression.

**Anything that shows award-*category* detail rather than a staging count** is
deliberately not subject to the double-count filter, and must keep reading
`historical_results` unfiltered - `docs/data-model.md` says so explicitly, and it's
right: an award record is a fact about a category, and there's nothing in `shows` to
double-count it against.

- `/awards` (`info.py`'s `awards()`) - the whole browse table, its year/category
  dropdowns, its FTS search. Untouched.
- `/stats/trends` (`stats_trends()`) - the decade view. Its `top_shows` query already
  does its own `DISTINCT show, year, soc_key` dedupe and explains in a comment why
  `top_societies` deliberately does *not*. Leave both.
- `society_detail()`'s `award_totals`, `best_show_second` / `best_show_third`, and
  `person_awards`.
- `_society_badges()`'s Triple Crown, Clean Sweep, Dual Tier Champions, The All-Rounder
  and Debut Delight.
- `/stats`'s award leaderboard, `wins_by_region`, and the `hist_join` /
  `hist_region_clause` helpers that serve them. **Stage 1 deliberately left these on the
  old tables.** If stage 3 changes any number on `/stats`, stage 3 has a bug.
- `search()`'s award-nominee section and its review search.

**Review lists, which count reviews and not productions:**

- `reviews_index()`, `adjudicators_list()`, `adjudicator_detail()`. ROADMAP.md points at
  `reviews_index()` as "the best worked example in the codebase of the problem the table
  solves" - and as an *illustration* that's fair: it unions two eras and justifies the
  absence of dedup with a prose argument ("Structurally can't overlap - the archive ends
  before the link-out era begins"). But it is honest today, it lists reviews rather than
  stagings, and rewriting its row shape would be a visual change on a 362KB page that
  ROADMAP already has queued for pagination work. Leave it. The latent flaw in its
  argument is recorded in §8.5 with a one-line check.

**Write paths and admin tools:**

- `app/similarity.py`'s `find_award_record_match()` (the society submission form's
  double-count warning). It asks "does an award record already exist for this
  society/season/title *before* I insert a row" - there is no production to key on yet.
- `admin.bulk_historical_productions()`'s existing-row check, for the same reason.
- Everything under `app/blueprints/admin/` - stage 2 already did what it needed.

**`export_csv.py` / `export_awards.py`** - the scoping brief listed them as places to
inventory. They are table dumps and inverses of the importers; they must keep matching
the tables they round-trip. Not part of this.

---

## 6. Sequencing

Each step is independently verifiable and independently committable. Stop safely
between any two.

**Step 0 - set up.** `EnterWorktree`. Confirm a clean tree and a green baseline
(`py -m pytest`, expect 541).

**On which database to measure against.** The repo-root `aims.db` was replaced with a
current production copy on 2026-08-23 (1,385 shows, archive from 1912, `productions`
already built), so unlike previous sessions it is a valid basis for the §7.1 comparison.
Check that it still is before relying on it - `SELECT COUNT(*) FROM shows` should be in
the high 1,300s and `SELECT MIN(year) FROM historical_results` should be 1912, not 1977.
If it has drifted, or if you want a guaranteed-untouched basis, pull a read-only snapshot
into the scratch directory instead (never into the repo):

```bash
scp -i ~/.ssh/claudeshowcal_ed25519 \
  claudeshowcal@dc-qnap-2:/share/CACHEDEV1_DATA/Data/config/aims-web/aims.db \
  "$SCRATCH/prod-check.db"
```

Either way, open it read-only for measurement (`?mode=ro`) - the local copy is now a
working dev database that the app writes to, and a comparison run must not be the thing
that changes it.

Then confirm the snapshot's derived table is current before you compare anything to it:

```bash
py build_productions.py --db "$SCRATCH/prod-2026-08-24.db" --dry-run
```

It must pass verification and report roughly "N productions (0 new, 0 changed, 0
removed)". If it reports work to do, production's table was stale when you pulled it and
your before/after comparison would be measuring the wrong thing.

**Step 1 - the shared definition and the `ensure_current` calls** (§4.0). No behaviour
change; suite green with no test edits. Commit.

**Step 2 - Shows A-Z, search, sitemap** (§4.1). This is the step that moves the big
numbers. Run the §7 comparison before committing. New tests in
`tests/test_public_productions_cutover.py` (naming follows
`test_stats_productions_cutover.py` / `test_admin_productions_cutover.py`): a title with
several award categories in one year counts once; a title known only from a 2024+ award
record appears; a pending submission does not. Commit.

**Step 3 - `/titles/<title>`** (§4.2), including `production_ids_for_title()`. Tests: a
production with both a skeleton `shows` row and an award record appears once, not twice;
the `Rocky Horror Show` case (award-record-only, 2024+) renders instead of 404ing.
Commit.

**Step 4 - `/societies/<id>`** (§4.3). Tests: a 2024+ award record for a society that
also has a `shows` row appears once; the badge count and `active_since` come from
productions. Watch `tests/test_society_historical_show_split.py` and
`tests/test_society_badges.py` - they should pass unedited; if one fails, understand why
before changing it. Commit.

**Step 5 - `/shows/<id>`** (§4.4). Test: award history resolves for a show whose season
predates 2001, which the old arithmetic could not express. Commit.

**Step 6 - (folded into step 4).** The society "Show history" awards column was
originally sequenced here as an optional follow-up; Darragh decided on 2026-08-23 to
build it as part of step 4 instead, so nothing regresses mid-cutover. Nothing to do here.

**Step 7 - paperwork.** Drop the dead imports (§4.5). Update `docs/data-model.md`: the
line "Cutover is staged, one surface at a time: `/stats` first (done), then the admin
dashboard counts, then the public show/society pages" is now history - say all four
surfaces are cut over, and say which queries deliberately still read the old tables
(§5), because that's the part a future session will otherwise get wrong. Record the
stage 4 decision in `schema.sql`'s `productions` comment (it currently says "DERIVED,
NOT AUTHORED (first pass)" and "Making it authored... is a later step"). Add a
`CHANGELOG.md` entry - it publishes itself on redeploy. Move the ROADMAP.md item
"Productions-table migration, stages 3-4" into `ROADMAP_ARCHIVE.md` with what actually
shipped and what was verified.

**Step 8 - merge, deploy, verify live** (§7).

---

## 7. Verification

### 7.1 Before/after on the real snapshot

Run both the old and the new SQL against the same read-only snapshot and diff them.
Read the output; don't just check it ran. Open the snapshot with
`sqlite3.connect("file:...?mode=ro", uri=True)` so you cannot accidentally write to it.

**a. Shows A-Z counts.** Old query (the union in §1) vs
`SELECT MIN(title), COUNT(*) FROM productions WHERE <ON_RECORD> GROUP BY title_key`.
Print: the number of titles either side, the sum of the count column either side, and
the 20 largest movers. Expect large downward moves on the most-nominated titles (JCS,
Fiddler, West Side Story) and a small set of new titles. **A title whose count goes *up*
by more than a handful deserves an explanation before you ship.**

**b. New titles.** List every `title_key` in the new set that isn't in the old. Expect
**16**, split 9 genuinely-missing / 7 spelling variants - the §1 list names both kinds,
so a material difference from that list means something moved and is worth understanding.
The variants are real `/admin/duplicate-titles` work, not a bug in this cutover, but
**hand Darragh the list before shipping**, because the A-Z visibly gaining near-duplicate
rows will otherwise look like a regression.

**c. Society double-listing.** Count `(year, show, society_id)` combinations in
`historical_results` with `year >= 2024` that also have a `shows` row - that's the number
of duplicate lines this removes from society pages. **195 on current production data.**

**d. `/stats` invariant.** Run the season-by-season query from `info.py`'s `stats()`
against the snapshot before and after. **It must be byte-identical.** Stage 3 must not
move stage 1's numbers.

**e. Title-spelling collisions.** For every `show` in `show_links` and `show_info`,
check whether `normalize_title(show)` maps to more than one raw spelling in the data. 0
on the stale copy; `app/productions.py`'s docstring says exactly one pair merges in the
real archive ("Ghost the Musical" / "Ghost: The Musical"). If a `show_links` row is
affected, its Wikipedia link will stop rendering when the displayed spelling flips - see
§8.9.

**f. The latent-overlap checks from §8**, run once each so we know whether they're
theoretical or live:
```sql
-- reviews_index double-listing (expect 0)
SELECT COUNT(*) FROM shows s
 WHERE s.review_status = 'Published' AND s.review_url IS NOT NULL AND s.review_url != ''
   AND EXISTS (SELECT 1 FROM historical_reviews h
                WHERE h.show_id = s.id AND h.moderation_status = 'approved');
-- shows rows season.season_start_year cannot decode safely (expect 0)
SELECT DISTINCT season FROM shows ORDER BY season;
-- duplicate season labels from season_range() (expect: check MIN(year))
SELECT MIN(year) FROM historical_results;
```

### 7.2 Tests

`py -m pytest` after every step. 541 passing before; expect roughly 555-565 after, with
the new files named in §6. If an existing test fails, the default assumption is that the
code is wrong, not the test - stages 1 and 2 both left tests that encode real,
hard-won behaviour.

### 7.3 Live, after deploy

Redeploy through Portainer (the API is unreachable, see CLAUDE.md - this is Darragh's
step or the UI). Then check the real pages, not just that the container came up:

- `/titles?sort=most` - the top of the list should now be plausible production counts
  (tens, not hundreds), and the first page's numbers should match the snapshot
  comparison from §7.1a.
- `/titles/Jesus%20Christ%20Superstar` - the count in the opening line and the number of
  table rows must agree with each other and with the A-Z. They don't today.
- `/titles/<a title from §7.1b>` - the page that used to 404.
- `/societies/<id>` for a society with a 2024+ award record - each production appears
  once. Pick a specific id from §7.1c and note it here when you run it.
- `/shows/<id>` for a show that has award records - award history still renders.
- `/stats` - the headline "Productions on record" number is **unchanged** from before
  the deploy. Note it down before you deploy so you can compare.
- `/sitemap.xml` - contains the newly-visible title pages.

---

## 8. Known traps

This migration has already surfaced two century bugs (`historical_results_year()`
couldn't express a year before 2001; `season_start_year()`'s pivot at 50 assumed a 1977
start when the archive begins 1912). These are the same shape, found in or next to the
stage 3-4 surfaces.

1. **`productions` contains rows for unmoderated shows.** `collect()` reads `shows` with
   no `moderation_status` filter. Any public query that reads `productions` without
   `ON_RECORD_PRODUCTION` will leak a pending or rejected submission onto a public page.
   This is the single most likely way to break something user-visible in stage 3.
   **Measured on current production data: 0 such productions exist today**, so neither
   the real data nor an accidental test will catch a missing filter - the bug would sit
   latent until the next pending submission and then leak it onto a public page. Write a
   test that seeds a pending show explicitly, and treat that test as the guard.
2. **`historical_results_year()` in `public.py`.** Two call sites (`_society_badges()`,
   `show_detail()`), both removed by this plan. It returns `2000 + yy + 1`: `'99/00'`
   gives 2100, `'87/88'` gives 2088. Safe only on a `shows.season` value from this
   century. Don't reintroduce it.
3. **`active_since`'s `2000 + int(earliest_season[:2])`** in `society_detail()` - a
   hard-coded century pivot, exactly the shape of bug this migration exists to make
   impossible. Removed by §4.3.
4. **Season strings compared as text.** `s["season"] > current` (the future/past split in
   `society_detail()`), `ORDER BY season DESC` in the same route's shows query,
   `min(s['season'] for s in shows)` in `title_detail()`. `'76/77'` sorts after `'09/10'`
   as text - the Round 25 bug. Two of these get fixed for free by ordering on
   `productions.season_start_year`; the future/past split doesn't and is left alone
   deliberately. Safe only while `shows` holds 2000s seasons, which it does today.
5. **`reviews_index()`'s no-overlap argument is a comment, not a constraint.** It unions
   link-out reviews (`shows.review_url`) with archive reviews (`historical_reviews`) and
   argues the two eras can't overlap. But `historical_reviews.source = 'manual'` exists
   precisely so a moderator can type in a review that was never in the PDF archive - on
   any show, including a modern one. If that ever happens on a show that also has a
   `review_url`, the show appears twice in the list and twice in the stats above it.
   0 on the stale copy. Check (§7.1f), don't fix.
6. **`season_range()` (`app/season.py`) emits duplicate season labels.** It builds
   labels from `MIN(historical_results.year) - 1` forward. Production's archive starts in
   1912, so it generates `'12/13'` for 1912 *and* for 2012 - duplicate `<option>` values
   in `reviews_index()`'s season dropdown, where selection is string equality. Harmless
   in practice today (`historical_reviews` only spans 09/10-22/23), and out of scope, but
   it is the archive's century ambiguity leaking into a UI control.
7. **`app/productions_build.py` ends with dead code.** Lines 448-449 are
   `if __name__ == "__main__": sys.exit(main())`, but the module imports no `sys` and
   defines no `main` - a leftover from before the CLI half moved to
   `build_productions.py`. Harmless (nothing runs the module directly) and it would
   `NameError` if anyone tried. A two-line delete if you want it; not required.
8. **The A-Z will gain near-duplicate titles** (`Shrek` and `Shrek: The Musical`) that
   the old year filter was hiding. That's the data telling the truth, not the cutover
   misbehaving - but it needs to be expected, not discovered live.
9. **`show_links` / `show_info` are keyed on exact title text.** If `MIN(title)` picks a
   different spelling than the one a moderator saved a link under, the confirmed
   Wikipedia link silently reverts to a search link. One known pair in the real archive;
   check §7.1e and re-save the link if it bites.

---

## 9. Stage 4: recommendation

**Recommendation: keep `productions` derived. Do not build the authored version now.
Record the decision, record what would change our minds, and stop.**

### What stage 4 was asking

`productions` is derived-only: `app/productions_build.py` is the sole writer, the three
source tables stay where data is entered, and the table is rebuilt from scratch on every
app start and whenever a fingerprint says the sources moved. Stage 4 asks whether a
moderator should be able to edit a production directly - merge two rows the natural key
wrongly split, split one it wrongly merged, or create one that no source row implies.

### Why not

**1. The problem it would solve is a source-data problem, and the source has better
tools.** Every way a production can be wrong today traces to a source row being wrong:
a title spelled two ways, a society name that never matched a `societies` row, an award
year mis-entered. Each of those has an existing editing surface (`/admin/awards`, the
duplicate-title merge, Edit Show), each already calls `productions_build.mark_stale()`
where the fingerprint can't see the change, and fixing the source fixes both the
production *and* the page where the data actually lives. Editing the production instead
would fix the index and leave the source wrong - which is the exact disagreement between
surfaces that this table was built to end.

**2. It would cost the property that makes the table trustworthy.** The rebuild is
safe to run at any time precisely because it's a pure function of the sources: it
upserts on the natural key, blanks links that no longer resolve, deletes productions
whose last source row is gone, and then re-derives every total from the database and
raises rather than committing on disagreement. Authored rows break all of that. You'd
need an override layer the rebuild must respect, a merge/alias table the link-rewriting
pass must consult, and a verification pass that can tell "a human said so" from "the
data changed underneath you". That is a substantial amount of new machinery in the one
component whose entire value is that it can be thrown away and rebuilt - and constraint
4 of the original brief ("every rebuild ends with a verification pass that re-derives
totals from the database") gets materially harder to honour, not easier.

**3. There is no evidence of the need.** The derived model has been live across `/stats`
and the admin counts since 2026-08-22. In that time the rebuild's verification has
passed on every start, no production has been found holding two `shows` rows (the single
most damaging failure mode, and the one it checks for explicitly), and title
normalization merges exactly one pair of raw spellings in the whole archive - a pair
that is genuinely the same show. Building an editing layer against zero observed
failures is speculative work on the highest-risk component in the system.

**4. The one real gap has a cheaper fix that's already on the roadmap.** The natural
key's weakest point is `society_key`: 71 society names in the awards archive have never
matched a `societies` row, so they key on `name:<normalized name>`, and one defunct
society recorded under two spellings becomes two productions of one real staging.
Authoring would let a moderator merge them one at a time, forever. Matching the names
instead fixes every affected production at once, permanently, and ROADMAP.md already
carries the work item ("~10 unmapped historical societies with no existing `societies`
row"). `society_key()` reads through `society_id` the moment it's set - no code change
needed. That's strictly better value than a merge UI.

**5. The honest counter-argument, stated.** Derived means a moderator who spots a wrong
production has no way to fix it *there* - they have to work out which source row caused
it. That's a real ergonomic cost, and it falls on Darragh rather than on the code. The
mitigation is that the productions table is small, the natural key is three columns, and
the source row is always findable from it. If that stops being true - if Darragh is
regularly staring at a wrong production and can't tell why - the calculus changes.

### What would change the answer

Revisit stage 4 if any of these becomes true, and say so in `docs/data-model.md` so a
future session knows the trigger rather than re-litigating from scratch:

- A correction is needed that **cannot** be expressed as an edit to `shows`,
  `historical_results` or `historical_reviews`. (None has come up yet.)
- The rebuild's verification pass starts failing on real data, or two genuinely distinct
  stagings are found merged under one key.
- Unmatched historical society names are worked down and productions *still* split
  wrongly - i.e. the cheap fix was tried and wasn't enough.
- A moderator-facing need appears for a production that no source row implies (a staging
  that was never adjudicated, never reviewed, and never entered as a show). Today that's
  what `admin.bulk_historical_productions` is for: it writes a bare `historical_results`
  row, and the production follows.

### What to do instead, now

Nothing structural. Write the decision down in three places - `schema.sql`'s
`productions` comment (which currently promises "Making it authored... is a later step"),
`docs/data-model.md`, and the ROADMAP archive entry for this session - with the reasoning
above and the trigger conditions. The queries in §7.1f double as the evidence-gathering
for the next time the question comes up: if they stay at zero, the answer stays "leave
it derived".

---

## 10. Definition of done

- Steps 1-5 committed in the worktree, suite green after each.
- The §7.1 comparison run against a fresh production snapshot, output read, and the
  new-titles list (§7.1b) plus the two visible display changes ("Last performed",
  "Active since") shown to Darragh before merge.
- `/stats` numbers provably unchanged.
- Merged to `main`, deployed, and the §7.3 live checks done against the real site - not
  assumed from a green build.
- `docs/data-model.md`, `schema.sql`'s productions comment, `CHANGELOG.md` and
  `ROADMAP.md` updated; the stages 3-4 item moved into `ROADMAP_ARCHIVE.md` with the
  real numbers this session produced.
- `ExitWorktree`.
