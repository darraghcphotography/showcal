"""(Re)build the productions table from shows, historical_results and
historical_reviews - see schema.sql's own notes on why that table exists.

The productions table is derived, not authored: this script is the only thing
that writes to it, and it's safe to re-run any time. It upserts on the natural
key (see app/productions.py), so a production keeps its id across rebuilds -
which is what makes the production_id foreign keys on the three source tables
stable enough to build pages on.

Every run ends with a verification pass that re-derives the same totals
independently and refuses to commit if they disagree, rather than trusting the
write it just made. --dry-run does all of it and rolls back.

Usage:
    py build_productions.py [--db aims.db] [--dry-run] [--quiet]

    docker compose exec aims-web python build_productions.py --db /data/aims.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.productions import key_from_award_record, key_from_show, season_for_key  # noqa: E402
from app.similarity import normalize_title  # noqa: E402

ROOT = Path(__file__).parent


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
    existing = {
        (r["society_key"], r["season_start_year"], r["title_key"]): r["id"]
        for r in db.execute("SELECT id, society_key, season_start_year, title_key FROM productions")
    }

    inserted = updated = 0
    key_to_id = {}
    for key, rows in productions.items():
        values = resolve_display(societies, region_guesses, key, rows)
        production_id = existing.get(key)
        if production_id is None:
            production_id = db.execute(
                """
                INSERT INTO productions
                    (season_start_year, society_key, title_key, season, society_id,
                     society_name, title, region)
                VALUES (:season_start_year, :society_key, :title_key, :season, :society_id,
                        :society_name, :title, :region)
                """,
                values,
            ).lastrowid
            inserted += 1
        else:
            db.execute(
                """
                UPDATE productions
                   SET season = :season, society_id = :society_id, society_name = :society_name,
                       title = :title, region = :region, updated_at = datetime('now')
                 WHERE id = :id
                """,
                dict(values, id=production_id),
            )
            updated += 1
        key_to_id[key] = production_id

    # Point every source row at its production, and blank the link on any row
    # that no longer resolves to one (a title cleared back to TBA, say) so a
    # stale link can never outlive the fact behind it.
    db.execute("UPDATE shows SET production_id = NULL")
    db.execute("UPDATE historical_results SET production_id = NULL")
    db.execute("UPDATE historical_reviews SET production_id = NULL")
    for key, rows in productions.items():
        production_id = key_to_id[key]
        for table, source_rows in (
            ("shows", rows["shows"]),
            ("historical_results", rows["awards"]),
            ("historical_reviews", rows["reviews"]),
        ):
            if not source_rows:
                continue
            db.executemany(
                f"UPDATE {table} SET production_id = ? WHERE id = ?",
                [(production_id, r["id"]) for r in source_rows],
            )

    # A production whose last source row is gone (an award record corrected, a
    # skeleton show merged away) stops being a production. Deleted rather than
    # left orphaned - nothing points at it any more by definition, since the
    # link columns were just rewritten from scratch above.
    stale = [pid for key, pid in existing.items() if key not in key_to_id]
    for pid in stale:
        db.execute("DELETE FROM productions WHERE id = ?", (pid,))

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


# ---------------------------------------------------------------- entry point

def build(db, quiet=False):
    productions, unkeyed = collect(db)
    inserted, updated, deleted = write(db, productions)
    verify(db, productions, unkeyed)
    if not quiet:
        with_shows = sum(1 for p in productions.values() if p["shows"])
        with_awards = sum(1 for p in productions.values() if p["awards"])
        both = sum(1 for p in productions.values() if p["shows"] and p["awards"])
        with_reviews = sum(1 for p in productions.values() if p["reviews"])
        print(f"{len(productions)} productions ({inserted} new, {updated} updated, {deleted} removed)")
        print(f"  {with_shows} have a shows row, {with_awards} an award record, {both} both")
        print(f"  {with_reviews} have at least one ShowTimes review attached")
        print(f"  skipped {unkeyed['shows']} shows rows and {unkeyed['awards']} award records "
              f"with no usable title")
    return productions


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="build and verify, then roll back without writing")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        build(db, quiet=args.quiet)
    except VerificationError as exc:
        db.rollback()
        print(exc, file=sys.stderr)
        return 1
    if args.dry_run:
        db.rollback()
        if not args.quiet:
            print("--dry-run: rolled back, nothing written.")
    else:
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
