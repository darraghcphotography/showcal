"""(Re)build the productions table from shows, historical_results and
historical_reviews - see schema.sql's own notes on why that table exists.

The productions table is derived, not authored: this module is the only thing
that writes to it, and it's safe to re-run any time. It upserts on the natural
key (see app/productions.py), so a production keeps its id across rebuilds -
which is what makes the production_id foreign keys on the three source tables
stable enough to build pages on.

Every run ends with a verification pass that re-derives the same totals
independently and raises rather than trusting the write it just made.

Lives inside the app package (rather than as a root-level script like
import_csv.py) because the app itself runs it: on every startup, and lazily
whenever the source data has moved since the last build. `build_productions.py`
at the repo root is the command-line half - the same split as
add_changelog.py / app/changelog_sync.py.
"""
from .productions import key_from_award_record, key_from_show, season_for_key
from .similarity import normalize_title


# ---------------------------------------------------------------- collecting

def collect(db):
    """Group every source row by production natural key.

    Returns (productions, unkeyed) where productions maps key -> a dict of the
    rows that make it up, and unkeyed counts the rows that name no production
    at all (a shows placeholder with no title yet, an award record with a blank
    show column) - those are a real, expected state, not a failure.
    """
    productions = {}
    unkeyed = {"shows": 0, "awards": 0}

    def slot(key):
        p = productions.get(key)
        if p is None:
            p = productions[key] = {"shows": [], "awards": [], "reviews": []}
        return p

    for row in db.execute(
        "SELECT id, society_id, season, show, region, source FROM shows"
    ):
        key = key_from_show(row)
        if key is None:
            unkeyed["shows"] += 1
            continue
        slot(key)["shows"].append(row)

    for row in db.execute(
        "SELECT id, year, show, society_name, society_id FROM historical_results"
    ):
        key = key_from_award_record(row)
        if key is None:
            unkeyed["awards"] += 1
            continue
        slot(key)["awards"].append(row)

    # A review reaches its production through the show it's attached to -
    # historical_reviews has its own free-text show_raw/society_raw, but those
    # are the parser's reading of the page, not a matched identity, and
    # re-matching them here would invent a second, weaker matching rule
    # alongside the moderator's own. A review with no show_id simply has no
    # production yet, exactly as it has no show yet.
    show_to_key = {}
    for key, p in productions.items():
        for row in p["shows"]:
            show_to_key[row["id"]] = key
    for row in db.execute("SELECT id, show_id FROM historical_reviews WHERE show_id IS NOT NULL"):
        key = show_to_key.get(row["show_id"])
        if key is not None:
            productions[key]["reviews"].append(row)

    return productions, unkeyed


# ---------------------------------------------------------------- display values

def lookups(db):
    """The two reference tables display resolution needs, read once. Both are
    small and every production consults them - looking them up per row instead
    turned an O(n) rebuild into an O(n x m) one the last time that pattern got
    into an admin page (see ROADMAP, 19 Aug: it caused a live 524)."""
    return (
        {r["id"]: r for r in db.execute("SELECT id, name, region FROM societies")},
        {
            r["society_name"]: r["confirmed_region"]
            for r in db.execute(
                "SELECT society_name, confirmed_region FROM historical_society_regions "
                "WHERE confirmed_region IS NOT NULL"
            )
        },
    )


def resolve_display(societies, region_guesses, key, rows):
    """Pick the season/society/title/region a production is shown under.

    Titles and society names differ in spelling between sources (that's the
    whole reason the key is normalized), so one has to win. A shows row wins
    over an award record: it's the moderated, editable record a person has
    actually looked at, and it's what the show's own page already displays.
    """
    show_rows = rows["shows"]
    award_rows = rows["awards"]

    if show_rows:
        title = show_rows[0]["show"]
    else:
        title = award_rows[0]["show"]

    society_id = None
    society_name = None
    if show_rows:
        society_id = show_rows[0]["society_id"]
    elif award_rows:
        society_id = award_rows[0]["society_id"]
        society_name = award_rows[0]["society_name"]
    if society_id and society_id in societies:
        society_name = societies[society_id]["name"]
    if not society_name:
        # Only reachable for an award record with neither a matched society
        # nor a society_name - the key would then be 'name:', which is a
        # single bucket, so it's labelled honestly rather than left blank.
        society_name = "Unknown society"

    # Region, resolved once: the production's own snapshot first (shows.region
    # records the society's tier/region *at the time*, which is the accurate
    # historical value), then the society's current region, then a moderator-
    # confirmed guess for a defunct society. NULL when none of those exist.
    region = None
    if show_rows:
        region = show_rows[0]["region"]
    if not region and society_id and society_id in societies:
        region = societies[society_id]["region"]
    if not region:
        for award in award_rows:
            guess = region_guesses.get(award["society_name"])
            if guess:
                region = guess
                break

    return {
        "season_start_year": key[1],
        "society_key": key[0],
        "title_key": key[2],
        "season": season_for_key(key),
        "society_id": society_id,
        "society_name": society_name,
        "title": title,
        "region": region,
    }


# ---------------------------------------------------------------- writing

def write(db, productions):
    """Upsert every production and point the source rows at it. Returns
    (inserted, updated, deleted)."""
    societies, region_guesses = lookups(db)
    existing = {}
    for r in db.execute(
        "SELECT id, society_key, season_start_year, title_key, season, society_id, society_name, "
        "title, region FROM productions"
    ):
        existing[(r["society_key"], r["season_start_year"], r["title_key"])] = r

    # Sorted into two batches and written with executemany rather than a
    # statement per production: at this data's size that's a ~1.0s rebuild
    # against a ~0.2s one, and the rebuild runs on every app start.
    key_to_id = {}
    to_insert = []
    to_update = []
    for key, rows in productions.items():
        values = resolve_display(societies, region_guesses, key, rows)
        row = existing.get(key)
        if row is None:
            to_insert.append(values)
            continue
        key_to_id[key] = row["id"]
        if any(row[column] != value for column, value in values.items()):
            to_update.append(dict(values, id=row["id"]))

    if to_insert:
        db.executemany(
            """
            INSERT INTO productions
                (season_start_year, society_key, title_key, season, society_id,
                 society_name, title, region)
            VALUES (:season_start_year, :society_key, :title_key, :season, :society_id,
                    :society_name, :title, :region)
            """,
            to_insert,
        )
        # executemany gives no per-row lastrowid, so the new ids are read back
        # by natural key - the same key they were just written under.
        fresh = {
            (r["society_key"], r["season_start_year"], r["title_key"]): r["id"]
            for r in db.execute("SELECT id, society_key, season_start_year, title_key FROM productions")
        }
        for values in to_insert:
            key = (values["society_key"], values["season_start_year"], values["title_key"])
            key_to_id[key] = fresh[key]
    if to_update:
        db.executemany(
            """
            UPDATE productions
               SET season = :season, society_id = :society_id, society_name = :society_name,
                   title = :title, region = :region, updated_at = datetime('now')
             WHERE id = :id
            """,
            to_update,
        )
    inserted, updated = len(to_insert), len(to_update)

    # Point every source row at its production, and blank the link on any row
    # that no longer resolves to one (a title cleared back to TBA, say) so a
    # stale link can never outlive the fact behind it. The `wanted` map is
    # complete for every table, so a row missing from it wants NULL.
    wanted = {"shows": {}, "historical_results": {}, "historical_reviews": {}}
    for key, rows in productions.items():
        production_id = key_to_id[key]
        for table, source_rows in (
            ("shows", rows["shows"]),
            ("historical_results", rows["awards"]),
            ("historical_reviews", rows["reviews"]),
        ):
            for row in source_rows:
                wanted[table][row["id"]] = production_id

    for table, links in wanted.items():
        # Only rows whose link actually changes get written. Blanking the
        # column and rewriting every row instead would be simpler, but
        # historical_results and historical_reviews both carry FTS5 update
        # triggers - every touched row re-indexes its full text, including
        # whole review bodies - which turned a re-run into a ~1.2s rebuild
        # doing no real work. A steady-state rebuild now writes nothing here.
        current = {r["id"]: r["production_id"] for r in db.execute(f"SELECT id, production_id FROM {table}")}
        changed = [(links.get(row_id), row_id) for row_id, existing_link in current.items()
                   if links.get(row_id) != existing_link]
        if changed:
            db.executemany(f"UPDATE {table} SET production_id = ? WHERE id = ?", changed)

    # A production whose last source row is gone (an award record corrected, a
    # skeleton show merged away) stops being a production. Deleted rather than
    # left orphaned - nothing points at it any more by definition, since the
    # link columns were just rewritten from scratch above.
    stale = [row["id"] for key, row in existing.items() if key not in key_to_id]
    if stale:
        db.executemany("DELETE FROM productions WHERE id = ?", [(pid,) for pid in stale])

    return inserted, updated, len(stale)


# ---------------------------------------------------------------- verification

class VerificationError(AssertionError):
    pass


def verify(db, productions, unkeyed):
    """Re-derive the same facts straight from the database and refuse the run
    if anything disagrees. Deliberately written against the written table
    rather than the in-memory dict wherever possible - checking the dict
    against itself would prove nothing about what actually landed."""
    problems = []

    def check(label, got, want):
        if got != want:
            problems.append(f"{label}: got {got}, expected {want}")

    check(
        "productions row count",
        db.execute("SELECT COUNT(*) FROM productions").fetchone()[0],
        len(productions),
    )

    # Every source row that names a production has a link; every one that
    # can't name one has none.
    keyed_shows = sum(len(p["shows"]) for p in productions.values())
    check(
        "shows rows linked",
        db.execute("SELECT COUNT(*) FROM shows WHERE production_id IS NOT NULL").fetchone()[0],
        keyed_shows,
    )
    check(
        "shows rows total",
        db.execute("SELECT COUNT(*) FROM shows").fetchone()[0],
        keyed_shows + unkeyed["shows"],
    )
    keyed_awards = sum(len(p["awards"]) for p in productions.values())
    check(
        "historical_results rows linked",
        db.execute("SELECT COUNT(*) FROM historical_results WHERE production_id IS NOT NULL").fetchone()[0],
        keyed_awards,
    )
    check(
        "historical_results rows total",
        db.execute("SELECT COUNT(*) FROM historical_results").fetchone()[0],
        keyed_awards + unkeyed["awards"],
    )
    check(
        "historical_reviews rows linked",
        db.execute("SELECT COUNT(*) FROM historical_reviews WHERE production_id IS NOT NULL").fetchone()[0],
        db.execute(
            "SELECT COUNT(*) FROM historical_reviews hr JOIN shows s ON s.id = hr.show_id "
            "WHERE s.production_id IS NOT NULL"
        ).fetchone()[0],
    )

    # No production may hold two shows rows: shows is one row per staging, so
    # two of them under one key would mean the key is merging real, distinct
    # productions - the single most damaging way this could be wrong.
    dupes = db.execute(
        "SELECT production_id, COUNT(*) n FROM shows WHERE production_id IS NOT NULL "
        "GROUP BY production_id HAVING n > 1"
    ).fetchall()
    if dupes:
        problems.append(f"{len(dupes)} productions have more than one shows row (ids: "
                        f"{[r['production_id'] for r in dupes][:5]})")

    # Nothing may be linked to a production that doesn't exist.
    for table in ("shows", "historical_results", "historical_reviews"):
        orphans = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE production_id IS NOT NULL AND production_id NOT IN "
            "(SELECT id FROM productions)"
        ).fetchone()[0]
        check(f"{table} rows pointing at a missing production", orphans, 0)

    # Every production must have at least one source row behind it.
    empty = db.execute(
        """
        SELECT COUNT(*) FROM productions p
         WHERE NOT EXISTS (SELECT 1 FROM shows WHERE production_id = p.id)
           AND NOT EXISTS (SELECT 1 FROM historical_results WHERE production_id = p.id)
        """
    ).fetchone()[0]
    check("productions with no source row", empty, 0)

    # Identity columns must actually agree with the display columns they were
    # derived from - a mismatch would mean the natural key and what the page
    # shows have drifted apart.
    bad_title_key = db.execute("SELECT id, title, title_key FROM productions").fetchall()
    mismatched = [r["id"] for r in bad_title_key if normalize_title(r["title"]) != r["title_key"]]
    check("productions whose title_key doesn't match their title", len(mismatched), 0)
    bad_society_key = db.execute(
        "SELECT COUNT(*) FROM productions WHERE society_id IS NOT NULL "
        "AND society_key != 'id:' || society_id"
    ).fetchone()[0]
    check("productions whose society_key doesn't match their society_id", bad_society_key, 0)

    # The whole point of the table: an award year maps to its real season,
    # in every century. Checked as a join over every linked record rather
    # than as a spot check on the oldest one, because the old 'yy/yy'
    # round-trip was wrong for 75 separate years, not just the extremes.
    misdated_awards = db.execute(
        "SELECT COUNT(*) FROM historical_results h JOIN productions p ON p.id = h.production_id "
        "WHERE p.season_start_year != h.year - 1"
    ).fetchone()[0]
    check("award records filed under the wrong season", misdated_awards, 0)
    misdated_shows = db.execute(
        "SELECT COUNT(*) FROM shows s JOIN productions p ON p.id = s.production_id "
        "WHERE p.season != s.season"
    ).fetchone()[0]
    check("shows rows filed under the wrong season", misdated_shows, 0)

    if problems:
        raise VerificationError("productions rebuild failed verification:\n  - " + "\n  - ".join(problems))


# ---------------------------------------------------------------- staying current

# What the last successful build saw. The table is derived, so a page reading
# it has to know whether the source data has moved since - a moderator
# approving a show shouldn't have to wait for the next deploy to see it
# counted. Cheap enough (four aggregates, no scan of any large text column) to
# check on a page request; the rebuild it guards only runs when it differs,
# and a rebuild with nothing to do takes ~50ms at this data's size.
#
# MAX(updated_at) on shows catches an in-place edit; COUNT/MAX(id) catch
# inserts and deletes; TOTAL(show_id) catches a review being repointed at a
# different show. It does NOT catch an in-place edit to a historical_results
# row (that table has no updated_at) - the admin routes that do that call
# mark_stale() explicitly instead.
FINGERPRINT_SQL = """
    SELECT (SELECT COUNT(*) FROM shows) || ':' ||
           (SELECT COALESCE(MAX(id), 0) FROM shows) || ':' ||
           (SELECT COALESCE(MAX(updated_at), '') FROM shows) || ':' ||
           (SELECT COUNT(*) FROM historical_results) || ':' ||
           (SELECT COALESCE(MAX(id), 0) FROM historical_results) || ':' ||
           (SELECT COUNT(*) FROM historical_reviews) || ':' ||
           (SELECT COALESCE(MAX(id), 0) FROM historical_reviews) || ':' ||
           (SELECT COALESCE(TOTAL(show_id), 0) FROM historical_reviews)
"""


def fingerprint(db):
    return db.execute(FINGERPRINT_SQL).fetchone()[0]


def mark_stale(db):
    """Force the next ensure_current() to rebuild. For a change the
    fingerprint can't see - an award record edited in place, a title
    corrected across tables by a merge."""
    db.execute("DELETE FROM productions_build_state")


def ensure_current(db):
    """Rebuild only if the source data has moved since the last build.
    Returns True if a rebuild happened."""
    stored = db.execute("SELECT fingerprint FROM productions_build_state WHERE id = 1").fetchone()
    if stored is not None and stored["fingerprint"] == fingerprint(db):
        return False
    build(db)
    db.commit()
    return True


# ---------------------------------------------------------------- entry point

def build(db, report=None):
    """Rebuild the table and verify the result. `report` is called with each
    summary line when the caller wants output (the CLI passes print; the app
    passes nothing)."""
    productions, unkeyed = collect(db)
    inserted, updated, deleted = write(db, productions)
    verify(db, productions, unkeyed)
    db.execute("DELETE FROM productions_build_state")
    db.execute(
        "INSERT INTO productions_build_state (id, fingerprint) VALUES (1, ?)", (fingerprint(db),)
    )
    if report:
        with_shows = sum(1 for p in productions.values() if p["shows"])
        with_awards = sum(1 for p in productions.values() if p["awards"])
        both = sum(1 for p in productions.values() if p["shows"] and p["awards"])
        with_reviews = sum(1 for p in productions.values() if p["reviews"])
        unchanged = len(productions) - inserted - updated
        report(f"{len(productions)} productions ({inserted} new, {updated} changed, {deleted} removed, "
               f"{unchanged} unchanged)")
        report(f"  {with_shows} have a shows row, {with_awards} an award record, {both} both")
        report(f"  {with_reviews} have at least one ShowTimes review attached")
        report(f"  skipped {unkeyed['shows']} shows rows and {unkeyed['awards']} award records "
               f"with no usable title")
    return productions
