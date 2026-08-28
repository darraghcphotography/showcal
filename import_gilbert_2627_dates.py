"""One-off import of the official 26/27 Gilbert schedule (48 productions with
real dates), from `gilbert_2627_schedule.csv` in the repo root.

Darragh was sent the schedule on 2026-08-27; the CSV is the machine-readable
transcription of it and is tracked in git. It holds up well against what we
already had - 16 rows agree exactly on both dates with no help from this
script at all, which is good evidence the list itself is accurate.

WHAT THIS SCRIPT DOES, AND THE FIVE THINGS THAT AREN'T MECHANICAL
-----------------------------------------------------------------

1. TWO-WEEKEND RUNS COLLAPSE INTO ONE ROW. Athlone's "The Wedding Singer"
   (26-28 Feb *and* 3-6 Mar) and Newcastle Glees' "Sweeney Todd" (19-21 Nov
   *and* 25-28 Nov) each appear on the list twice. `ux_shows_natural_key`
   allows only one row per society+season+show, so they're stored as the full
   span: opening = the earliest date, closing = the latest. A naive loop would
   let the second entry silently overwrite the first and record only the
   second weekend - hence the explicit collapse before anything is written.

2. THE NEW LIST WINS EVERY DATE CONFLICT. Darragh's call. Seven rows disagree
   with what we hold, some substantially - Trim's "Sweet Charity" is three
   weeks out (ours 23-27 Mar, the list says 1-6 Mar) and Portlaoise a full
   week. All seven are overwritten.

3. SOCIETY NAMES ARE MAPPED EXPLICITLY, NEVER FUZZY-MATCHED. Seventeen of the
   list's names differ from ours, and several are genuinely ambiguous against
   the societies table - "Newcastle Glees" is one character of context away
   from "Newcastlewest Musical Society", "Castlebar Musical and Dramatic
   Society" from "Castlebar Pantomime", "Belfast Operatic" from four other
   Belfast societies. Every one is resolved by hand in NAME_TO_SOCIETY_ID
   below, with the id pinned, so a rename can never silently re-point a row.

4. CLANE: WE HELD THE WRONG SHOW. We had "Sweeney Todd" for Clane 26/27; the
   list says "Jekyll and Hyde". Darragh confirms Jekyll is correct and Sweeney
   is wrong, so the title is corrected as well as the dates being added.

5. ST. AGNES IS A DUPLICATE SOCIETY, AND WE USE THE POPULATED ONE.
   "St. Agnes Choral Society" (id 101) holds Shrek for 26/27; "St. Agnes'
   Musical Society" (id 169, section 'Inactive') is empty and is the name the
   list actually uses. Darragh's call: add the dates to the existing row on
   101 and create nothing on 169. Note we keep our own fuller title, "Shrek
   the Musical", rather than overwriting it with the list's "Shrek".
   Society 169 remains a merge candidate for a later cleanup pass - this
   script deliberately does not merge it.

Also handled: two placeholder rows (`show IS NULL`, "society slotted for this
season, title TBA") get their title and dates filled in rather than a second
row inserted - Newcastle Glees (id 81) and Castlebar M&DS (id 22). And SONG
Dundalk (id 10014) has no 26/27 row at all, so one is created for "Elf".

Usage:
    py import_gilbert_2627_dates.py [--db aims.db] [--csv gilbert_2627_schedule.csv] [--dry-run]

    docker exec aims-web python import_gilbert_2627_dates.py --db /data/aims.db \
        --csv /data/gilbert_2627_schedule.csv --dry-run
"""
import argparse
import csv
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from app.similarity import normalize_title  # noqa: E402

SEASON = "26/27"

# Every society name on the list that is not an exact match for ours, resolved
# by hand against the societies table on 2026-08-28 and pinned by id. Ids are
# included so a later society rename cannot silently re-point one of these.
NAME_TO_SOCIETY_ID = {
    "The Odd Company": (112, "The Odd Theatre Company"),
    "Aghada MS": (3, "Aghada Centre Theatre Group"),
    "Kilcock Musical Society": (56, "Kilcock Musical & Dramatic Society"),
    "Newbridge Musical Theatre": (80, "Newbridge Musical Society"),
    "Leixlip Musical and Dramatic Society": (63, "Leixlip Musical & Variety Group"),
    "Clane Musical and Dramatic Society": (25, "Clane Musical & Dramatic Society"),
    "Malahide Musical and Dramatic Society": (None, "Malahide Musical & Dramatic Society"),
    "Castlebar Musical and Dramatic Society": (22, "Castlebar Musical & Dramatic Society"),
    "Dun Laoghaire Musical and Dramatic Society": (None, "Dun Laoghaire Musical & Dramatic Society"),
    # Ambiguous against a similarly-named society - pinned deliberately.
    "Newcastle Glees": (81, "Newcastle Glees Musical Society"),          # not Newcastlewest (82)
    "Belfast Operatic": (None, "Belfast Operatic Company"),              # not the 3 other Belfast societies
    "Ulster Operatic": (None, "Ulster Operatic Company"),
    "MUSE": (None, "Muse Productions"),
    "Oyster Lane": (87, "Oyster Lane Theatre Group"),
    "Bellvue": (None, "Bellvue Academy of Performing Arts"),
    "Entr'acte": (None, "Entr'acte Musical Theatre Society"),
    "St. Mel's Musical Society": (105, "St. Mel's Musical Society, Longford"),
    "St. Mary's Musical Society, Navan": (None, "St. Marys Musical Society, Navan"),
    "St. Mary's Choral Society Clonmel": (103, "St. Mary's Choral Society, Clonmel"),
    "SONG, Dundalk": (10014, "SONG Dundalk"),
    # See point 5 in the docstring - the list's name matches the EMPTY duplicate
    # (169); we deliberately target the populated society instead.
    "St. Agnes' Musical Society": (101, "St. Agnes Choral Society"),
}

# The list's title differs from ours and OURS WINS (we hold the fuller/canonical
# name). Keyed by society id. Anything not in here matches on normalize_title.
#
# These have to be explicit because `normalize_title` does NOT strip a leading
# article - it lowercases and drops punctuation, nothing more. So "Prince of
# Egypt" does not match our "The Prince of Egypt", and on the first run of this
# script that miss fell through to the "no 26/27 row at all" branch and inserted
# a duplicate row (id 2003) beside the real one (id 415, which already held the
# correct dates). Caught on verification the same evening and deleted. Stripping
# articles inside `normalize_title` would be a wider behaviour change than this
# import should make - listing the handful by hand is the safer fix, and matches
# how society names are resolved above.
KEEP_OUR_TITLE = {
    101: "Shrek the Musical",     # list says just "Shrek"
    87: "The Prince of Egypt",    # list says just "Prince of Egypt"
}

# We hold the wrong show outright - correct the title. Keyed by society id:
# (the title we currently hold, the title it should be).
CORRECT_TITLE = {
    25: ("Sweeney Todd", "Jekyll and Hyde"),   # Clane, confirmed by Darragh
}


def resolve_society(db, listed_name):
    """Return (society_id, society_name), or (None, None). Explicit map first,
    then an exact name match. Never fuzzy - see docstring point 3."""
    if listed_name in NAME_TO_SOCIETY_ID:
        pinned_id, our_name = NAME_TO_SOCIETY_ID[listed_name]
        if pinned_id is not None:
            row = db.execute("SELECT id, name FROM societies WHERE id = ?", (pinned_id,)).fetchone()
            if row is None:
                return None, None
            if row["name"] != our_name:
                print(f"  !! society {pinned_id} is now named {row['name']!r}, "
                      f"expected {our_name!r} - skipping, re-check the mapping")
                return None, None
            return row["id"], row["name"]
        listed_name = our_name
    row = db.execute("SELECT id, name FROM societies WHERE name = ?", (listed_name,)).fetchone()
    return (row["id"], row["name"]) if row else (None, None)


def collapse_runs(rows):
    """Fold the deliberate duplicate rows (real two-weekend runs) into one entry
    spanning both weekends. See docstring point 1."""
    runs = OrderedDict()
    for row in rows:
        key = (row["society_as_listed"], row["show"])
        if key in runs:
            existing = runs[key]
            existing["opening_date"] = min(existing["opening_date"], row["opening_date"])
            existing["closing_date"] = max(existing["closing_date"], row["closing_date"])
            existing["weekends"] += 1
        else:
            runs[key] = dict(row, weekends=1)
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--csv", default=str(ROOT / "gilbert_2627_schedule.csv"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    with open(args.csv, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    runs = collapse_runs(rows)
    print(f"{len(rows)} CSV rows -> {len(runs)} productions "
          f"({sum(1 for r in runs.values() if r['weekends'] > 1)} two-weekend runs collapsed)")
    for (listed, show), run in runs.items():
        if run["weekends"] > 1:
            print(f"  two weekends: {listed} - {show} -> "
                  f"{run['opening_date']} .. {run['closing_date']}")

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    unchanged = dated = overwritten = retitled = filled = created = 0
    problems = []

    for (listed_name, listed_show), run in runs.items():
        society_id, society_name = resolve_society(db, listed_name)
        if society_id is None:
            problems.append(f"UNRESOLVED SOCIETY: {listed_name!r} ({listed_show})")
            continue

        opening, closing = run["opening_date"], run["closing_date"]
        want_title = KEEP_OUR_TITLE.get(society_id, listed_show)

        existing = db.execute(
            "SELECT id, show, opening_date, closing_date FROM shows "
            " WHERE society_id = ? AND season = ?",
            (society_id, SEASON),
        ).fetchall()

        target, note = None, ""

        # 1. A row whose title matches (normalised, never fuzzy).
        for row in existing:
            if row["show"] and normalize_title(row["show"]) == normalize_title(want_title):
                target, note = row, ""
                break

        # 2. We hold the wrong show for this society - correct it.
        if target is None and society_id in CORRECT_TITLE:
            wrong, right = CORRECT_TITLE[society_id]
            if normalize_title(right) == normalize_title(listed_show):
                for row in existing:
                    if row["show"] and normalize_title(row["show"]) == normalize_title(wrong):
                        target = row
                        note = f"corrected title {row['show']!r} -> {right!r}"
                        db.execute("UPDATE shows SET show = ?, updated_at = datetime('now') "
                                   " WHERE id = ?", (right, row["id"]))
                        retitled += 1
                        break

        # 3. A "society slotted, title TBA" placeholder - fill it in, don't
        #    insert a second row beside it.
        if target is None:
            for row in existing:
                if not row["show"]:
                    target = row
                    note = f"filled placeholder with {want_title!r}"
                    db.execute("UPDATE shows SET show = ?, updated_at = datetime('now') "
                               " WHERE id = ?", (want_title, row["id"]))
                    filled += 1
                    break

        # 4. No 26/27 row at all - create one.
        if target is None:
            society = db.execute("SELECT region, section FROM societies WHERE id = ?",
                                 (society_id,)).fetchone()
            db.execute(
                "INSERT INTO shows (society_id, season, region, section, show, "
                "                   opening_date, closing_date, source, moderation_status) "
                "VALUES (?, ?, ?, 'Gilbert', ?, ?, ?, 'import', 'approved')",
                (society_id, SEASON, society["region"], want_title, opening, closing),
            )
            print(f"  CREATE  {society_name}: {want_title!r} {opening}..{closing}")
            created += 1
            continue

        if target["opening_date"] == opening and target["closing_date"] == closing and not note:
            unchanged += 1
            continue

        was = f"{target['opening_date']}..{target['closing_date']}"
        if target["opening_date"] is None and target["closing_date"] is None:
            dated += 1
            verb = "DATED   "
        else:
            overwritten += 1
            verb = "OVERWROTE"
        db.execute(
            "UPDATE shows SET opening_date = ?, closing_date = ?, updated_at = datetime('now') "
            " WHERE id = ?",
            (opening, closing, target["id"]),
        )
        extra = f"  [{note}]" if note else ""
        print(f"  {verb} {society_name}: {want_title!r} {was} -> {opening}..{closing}{extra}")

    print(f"\n{unchanged} already correct, {dated} gained dates, {overwritten} dates overwritten, "
          f"{retitled} titles corrected, {filled} placeholders filled, {created} rows created")
    if problems:
        print("\nPROBLEMS:")
        for problem in problems:
            print(f"  {problem}")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("Committed.")
    db.close()


if __name__ == "__main__":
    main()
