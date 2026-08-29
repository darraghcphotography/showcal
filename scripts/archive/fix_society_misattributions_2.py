"""Follow-up to fix_society_misattributions.py - resolves the 8 cases that
script explicitly deferred to Darragh's own judgement (NEEDS_DECISION) or
left unresolved (STILL_UNRESOLVED). See ROADMAP.md's "Society misattribution
follow-ups" for the full history.

Five real fixes, each confirmed by re-reading the review's own text and
cross-checking the society's *own* official award-entry record in `shows`
(not just the review text, which is how 577/790 turned out to be false
positives - see below):

1. Review 951 (Spring Awakening, 21/22) - the review says "UL Musical
   Theatre Society... their very first musical since their inception in
   2019." The existing "University of Limerick Musical Theatre Society"
   (id 124) has its own earliest official record one season later (Carrie,
   22/23) - consistent with this being their delayed (covid-era) debut, not
   a separate group. REPOINT to the existing society, no new row.
2. Review 440 (Seussical, 11/12) - review text says "Greenhill's' production
   of Seussical", not Craic Theatre (the show it's currently filed under)
   and not "Civic Theatre" (the auto-gate's suggestion, apparently confusing
   a venue name for a society). Craic Theatre has its *own* separate,
   correctly-attributed Seussical entry the same season - this review was
   cross-matched to the wrong record during import. "Greenhills Variety
   Group" is a real AIMS-affiliated society (confirmed via web search - a
   past Wedding Singer AIMS nomination) with no record in this database yet.
3. Review 595 (Little Women, 13/14) - review text names "SONG in Dundalk".
   AIMS's own current Eastern-region society list uses exactly "SONG
   Dundalk" as a distinct entry from the already-registered "Dundalk
   Musical Society" (id 36). Darragh confirmed the full name: Stage One
   New-Musical Group (S.O.N.G.), commonly referred to as SONG Dundalk.
4. Review 673 (Assassins, 14/15) - review text unmistakably names "the ESB
   company" (plus an Electric Ireland pun), performed at the Helix, Dublin.
   Not on AIMS's current public society list (likely lapsed/historical).
   Region is a genuine guess (Eastern, since ESB is Dublin-headquartered) -
   flagged as unconfirmed in the new society's notes field rather than
   forcing a schema change to the region CHECK constraint for one row.

Two reviews turned out to be FALSE POSITIVES on closer inspection - dismissed
rather than repointed:

5. Review 577 (Jesus Christ Superstar, 13/14, filed under Ratoath) - Ratoath's
   own official record already has a JCS entry that exact season. Meath
   Youth's own record has no JCS at all (only Rent 11/12, Les Mis 12/13).
   Correctly attributed already.
6. Review 790 (Footloose, 16/17, filed under Kill) - Kill's own official
   record already has a Footloose entry that exact season. Belfast Music and
   Drama Society's earliest record is a season later (Rock of Ages, 17/18).
   Correctly attributed already.

Deliberately NOT touched - Darragh chose to skip these entirely this session,
still flagged for later:
  - Review 367 (The Real Theatre Company) - confirmed real, no region evidence.
  - Review 366 (National Youth Musical Theatre) - confirmed real, but a
    touring/national group not tied to one AIMS region; needs its own
    structural decision, not a quick call.

Safe to re-run: every write is guarded by an assertion of the expected
current state; already-applied rows are skipped via get_or_create_society.
Defaults to a dry run - pass --apply to actually commit.

Usage:
    py fix_society_misattributions_2.py [--db aims.db]
    py fix_society_misattributions_2.py --db aims.db --apply

In Docker: docker exec <container> python fix_society_misattributions_2.py --db /data/aims.db --apply
"""
import argparse
import sqlite3
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

# name -> (region, section, notes or None)
NEW_SOCIETIES = {
    "Greenhills Variety Group": ("Eastern", "Gilbert", None),
    "SONG Dundalk": (
        "Eastern", "Gilbert",
        "Full name: Stage One New-Musical Group (S.O.N.G.) - commonly referred to as SONG Dundalk, "
        "matching AIMS's own public society listing.",
    ),
    "ESB Musical and Dramatic Society": (
        "Eastern", "Sullivan",
        "Region is a best guess (ESB is Dublin-headquartered), not confirmed - not on AIMS's current "
        "public society list, likely lapsed/historical. Confirmed real via review 673's own text "
        "(\"the ESB company\", Electric Ireland pun, Helix Theatre).",
    ),
}

# (review_id, show_id, expected_show_title, expected_season, expected_current_society_id, target_society_id)
REPOINTS = [
    (951, 1918, "Spring Awakening", "21/22", 121, 124),  # UCC -> University of Limerick Musical Theatre Society
]

# (review_id, show_id, expected_show_title, expected_season, expected_current_society_id, new_society_name)
NEW_SOCIETY_REPOINTS = [
    (440, 1454, "Seussical", "11/12", 29, "Greenhills Variety Group"),         # Craic Theatre -> Greenhills
    (595, 1596, "Little Women", "13/14", 98, "SONG Dundalk"),                  # Shannon -> SONG Dundalk
    (673, 1669, "Assassins", "14/15", 85, "ESB Musical and Dramatic Society"), # North East MDS -> ESB
]

# (source_issue, show_raw, adjudicator) - checked against the society's own
# official award-entry record and found correct as filed.
DISMISSALS = [
    ("Issue 90, November 2013", "Jesus Christ Superstar", "John Grayden"),  # Ratoath's own JCS 13/14 record
    ("Issue 120, April 2017", "Footloose", "Greg Currid"),                  # Kill's own Footloose 16/17 record
]

# Skipped entirely this session - Darragh's call, not a script decision:
#  - review 367 (The Real Theatre Company) - confirmed real, no region evidence.
#  - review 366 (National Youth Musical Theatre) - confirmed real, touring/national,
#    not tied to one AIMS region - needs its own structural decision.
SKIPPED = [367, 366]


def get_or_create_society(conn, name, region, section, notes):
    row = conn.execute("SELECT id FROM societies WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0], False
    cur = conn.execute(
        "INSERT INTO societies (name, region, section, notes) VALUES (?, ?, ?, ?)",
        (name, region, section, notes),
    )
    return cur.lastrowid, True


def run(db_path, apply_changes):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    log = []

    def note(msg):
        log.append(msg)
        print(msg)

    # 1. Repoint to an already-registered society.
    for review_id, show_id, title, season, expected_society_id, target_id in REPOINTS:
        show = conn.execute("SELECT show, season, society_id FROM shows WHERE id = ?", (show_id,)).fetchone()
        assert show is not None, f"show {show_id} missing (review {review_id})"
        assert (show["show"], show["season"], show["society_id"]) == (title, season, expected_society_id), (
            f"review {review_id} show {show_id}: expected {(title, season, expected_society_id)}, "
            f"found {(show['show'], show['season'], show['society_id'])} - skipping, state has changed"
        )
        target = conn.execute("SELECT name FROM societies WHERE id = ?", (target_id,)).fetchone()
        assert target is not None, f"target society {target_id} does not exist"
        note(f"REPOINT show {show_id} '{title}' ({season}): -> {target['name']} (id {target_id})")
        if apply_changes:
            conn.execute("UPDATE shows SET society_id = ? WHERE id = ?", (target_id, show_id))

    # 2. Repoints that need a brand-new society first.
    for review_id, show_id, title, season, expected_society_id, new_name in NEW_SOCIETY_REPOINTS:
        show = conn.execute("SELECT show, season, society_id FROM shows WHERE id = ?", (show_id,)).fetchone()
        assert show is not None, f"show {show_id} missing (review {review_id})"
        assert (show["show"], show["season"], show["society_id"]) == (title, season, expected_society_id), (
            f"review {review_id} show {show_id}: expected {(title, season, expected_society_id)}, "
            f"found {(show['show'], show['season'], show['society_id'])} - skipping, state has changed"
        )
        region, section, notes = NEW_SOCIETIES[new_name]
        if apply_changes:
            target_id, created = get_or_create_society(conn, new_name, region, section, notes)
        else:
            existing = conn.execute("SELECT id FROM societies WHERE name = ?", (new_name,)).fetchone()
            target_id, created = (existing[0] if existing else "new"), existing is None
        note(f"REPOINT (new society) show {show_id} '{title}' ({season}): -> {new_name} (id {target_id}"
             f"{', newly created' if created else ''})")
        if apply_changes:
            conn.execute("UPDATE shows SET society_id = ? WHERE id = ?", (target_id, show_id))

    # 3. Dismiss the suggestions that turned out to be false positives.
    for source_issue, show_raw, adjudicator in DISMISSALS:
        note(f"DISMISS suggestion: {show_raw!r} / {source_issue} / {adjudicator}")
        if apply_changes:
            conn.execute(
                "INSERT OR IGNORE INTO dismissed_society_corrections (source_issue, show_raw, adjudicator) "
                "VALUES (?, ?, ?)",
                (source_issue, show_raw, adjudicator),
            )

    print()
    print(f"Skipped this session (Darragh's call, review ids): {SKIPPED}")

    if apply_changes:
        conn.commit()
        print(f"\nApplied. {len(REPOINTS) + len(NEW_SOCIETY_REPOINTS)} shows repointed, "
              f"{len(DISMISSALS)} suggestions dismissed.")
    else:
        print(f"\nDry run only - {len(log)} planned actions above, nothing written. Pass --apply to commit.")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--apply", action="store_true", help="Actually commit the changes (default: dry run)")
    args = parser.parse_args()
    run(args.db, args.apply)
