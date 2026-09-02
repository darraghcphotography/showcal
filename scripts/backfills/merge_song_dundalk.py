"""Merges the duplicate "SONG Dundalk" record into Stage One New-Musical Group.

Darragh spotted Elf listed twice on the homepage for November 2026. They are one
society recorded twice:

    id   108  Stage One New-Musical Group (S.O.N.G.)   19 shows, 20 award rows,
                                                       logo, Facebook, venue
    id 10014  SONG Dundalk                             2 shows, 0 awards,
                                                       website, about text

The duplicate's own About text reads "Stage One New-Musical Group (S.O.N.G.) is
an award-winning youth musical theatre company based in Dundalk, Co. Louth",
which settles it.

BOTH of 10014's shows already exist on 108, and 108's copies are the better
record in each case:

    13/14  Little Women   108 has a date and a poster; 10014 has neither
    26/27  Elf            108 has the venue and the poster; 10014 has neither

So the shows are deleted rather than reassigned - reassigning would leave the
duplicate pair Darragh reported, just both under one society.

WHAT THE DUPLICATE CONTRIBUTES. It is not worthless: it holds a website_url and
an about text that 108 has never had, and both render on the public society
page. Those are copied across, but ONLY where 108 is blank - a merge that
overwrites the surviving record's own data is a merge that loses information.

It also holds an active login code, minted by generate_poster_chase_codes.py on
2026-09-02 for the very Elf listing being deleted here - so the poster chase was
about to ask a society that does not exist for a poster that already exists. The
code is deleted, and Darragh's distribution list drops from 15 societies to 14.

There is no general society-merge tool (there are ones for titles, people and
venues). Writing one for a single case would be inventing a workflow before
anyone has needed it twice - a sweep of the whole database for the same fault
found no other genuine instance, so this stays a one-off script.

Usage:
    py scripts/backfills/merge_song_dundalk.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python \\
        scripts/backfills/merge_song_dundalk.py --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
from pathlib import Path

DUPLICATE_ID = 10014
DUPLICATE_NAME = "SONG Dundalk"
KEEPER_ID = 108
KEEPER_NAME = "Stage One New-Musical Group (S.O.N.G.)"

# Fields worth rescuing off the duplicate, copied only into a blank on the
# keeper. Anything not listed here is discarded with the row.
CARRY_OVER = ("website_url", "about")

# Every table that points at a society (grepped from schema.sql). The script
# refuses to delete while any of them still references the duplicate, so a
# table added later cannot be silently orphaned.
REFERENCING = (
    ("shows", "society_id"),
    ("productions", "society_id"),
    ("historical_results", "society_id"),
    ("historical_reviews", "society_id"),
    ("historical_society_links", "society_id"),
    ("invite_codes", "society_id"),
    ("logo_candidates", "society_id"),
    ("society_access_requests", "society_id"),
    ("society_field_checked", "society_id"),
    ("wardrobe_items", "society_id"),
)


def _default_db():
    if __file__ in ("<stdin>", "-"):
        return "aims.db"
    return str(Path(__file__).resolve().parents[2] / "aims.db")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=_default_db())
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    dup = db.execute("SELECT * FROM societies WHERE id = ? AND name = ?",
                     (DUPLICATE_ID, DUPLICATE_NAME)).fetchone()
    keeper = db.execute("SELECT * FROM societies WHERE id = ?", (KEEPER_ID,)).fetchone()

    if dup is None:
        print(f"No society {DUPLICATE_ID} named {DUPLICATE_NAME!r} - already merged, nothing to do.")
        db.close()
        return
    if keeper is None:
        raise SystemExit(f"Society {KEEPER_ID} ({KEEPER_NAME}) is missing - refusing to merge into nothing.")

    print(f"Merging [{DUPLICATE_ID}] {dup['name']}  ->  [{KEEPER_ID}] {keeper['name']}\n")

    # --- 1. rescue anything the keeper is missing --------------------------
    for field in CARRY_OVER:
        value = dup[field]
        if not value:
            continue
        if keeper[field]:
            print(f"  keep {field}: the keeper already has one, the duplicate's is discarded")
            continue
        db.execute(f"UPDATE societies SET {field} = ? WHERE id = ?", (value, KEEPER_ID))
        shown = value if len(str(value)) < 60 else str(value)[:57] + "..."
        print(f"  copy {field}: {shown}")

    # --- 2. the duplicated shows ------------------------------------------
    print()
    for row in db.execute(
        "SELECT id, season, show, opening_date FROM shows WHERE society_id = ? ORDER BY season",
        (DUPLICATE_ID,),
    ).fetchall():
        twin = db.execute(
            "SELECT id, opening_date, poster_filename, venue FROM shows "
            "WHERE society_id = ? AND season = ? AND LOWER(TRIM(show)) = LOWER(TRIM(?))",
            (KEEPER_ID, row["season"], row["show"]),
        ).fetchone()
        if twin is None:
            # Not a duplicate after all - move it rather than lose it.
            db.execute("UPDATE shows SET society_id = ? WHERE id = ?", (KEEPER_ID, row["id"]))
            print(f"  move show {row['id']} ({row['season']} {row['show']}) - the keeper does not have it")
            continue
        print(f"  drop show {row['id']} ({row['season']} {row['show']}) - "
              f"keeper's show {twin['id']} has date={twin['opening_date']} "
              f"poster={'yes' if twin['poster_filename'] else 'no'} venue={twin['venue'] or '-'}")
        db.execute("DELETE FROM shows WHERE id = ?", (row["id"],))

    # --- 3. the login code -------------------------------------------------
    #
    # Deleted, not deactivated. A deactivated row would still point at a society
    # that is about to stop existing, which is a dangling reference kept only
    # for the look of an audit trail - and there is nothing to audit: the code
    # was minted yesterday by generate_poster_chase_codes.py for the very
    # listing being removed here, and has not been sent to anyone. The keeper
    # already has its own working code.
    print()
    for code in db.execute(
        "SELECT id, code, created_by FROM invite_codes WHERE society_id = ?", (DUPLICATE_ID,)
    ).fetchall():
        db.execute("DELETE FROM invite_codes WHERE id = ?", (code["id"],))
        print(f"  delete code {code['code']} (minted by {code['created_by']}) - "
              f"it unlocked a society that will not exist")

    # --- 4. anything else still pointing at the duplicate ------------------
    print()
    leftovers = []
    for table, column in REFERENCING:
        if not db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                          (table,)).fetchone()[0]:
            continue
        n = db.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (DUPLICATE_ID,)).fetchone()[0]
        if n and table == "productions":
            # Derived, and rebuilt wholesale on the app's next start - but
            # cleared here rather than left dangling, so nothing between now and
            # that rebuild can read a production whose society no longer exists.
            db.execute("DELETE FROM productions WHERE society_id = ?", (DUPLICATE_ID,))
            print(f"  clear {n} derived productions row(s) - rebuilt on the app's next start")
            continue
        if n:
            leftovers.append(f"{table}={n}")
    if leftovers:
        raise SystemExit(f"Refusing to delete: still referenced by {', '.join(leftovers)}")

    db.execute("DELETE FROM societies WHERE id = ?", (DUPLICATE_ID,))
    print(f"\n  delete society {DUPLICATE_ID}")

    remaining = db.execute(
        "SELECT COUNT(*) FROM shows WHERE LOWER(TRIM(show)) = 'elf' AND season = '26/27'"
    ).fetchone()[0]
    print(f"\n26/27 Elf listings now on record: {remaining} (should be 1)")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nWritten.")
    db.close()


if __name__ == "__main__":
    main()
