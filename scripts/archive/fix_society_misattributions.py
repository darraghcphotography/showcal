"""One-time fix for a real, confirmed extractor bug: dozens of ShowTimes
reviews were filed under the wrong society entirely (not just a citation-
label typo - the review's own text names a completely different society
than the one its show page lives on). Same root cause as the Sister Act/
Kilkenny, Merry Widow/Gorey, and Little Shop of Horrors/Carnew fixes from
the 2026-08-19/20 session (see ROADMAP.md Round 35) - this is the rest of
that same bug, found by cross-referencing every society_gate_suggestions.json
suggestion against the real database and reading each flagged review's own
text for corroborating place names, venue names, and self-references, rather
than trusting the suggestion blindly (the extractor-gate branch itself has a
confirmed remaining gap - see ROADMAP's "Newcastle Glees vs Newcastlewest" -
so several of its 80 suggestions were checked and rejected here, not applied).

Three kinds of fix, all confirmed by reading the review's own text:

1. REPOINTS - the skeleton show already has the right title/season/tier,
   just the wrong society_id. A single-column UPDATE, no new row needed.
2. DUPLICATE_DELETES - the exact same ShowTimes review got extracted twice
   (>99.8% identical text, same issue), once landing on the correct show and
   once on a wrong one. Delete the wrong copy, same pattern as Round 35's
   ShowTimes duplicate cleanup.
3. NEW_SOCIETY_REPOINTS - the review names a real society that has no
   record in `societies` yet. Creates it (region/section inferred from the
   review's own venue references and its own tier - flagged inline where
   that inference is less certain), then repoints.

Deliberately NOT included - a further ~13 suggestions from the same JSON file
that could not be confirmed one way or the other from the review's own text,
or whose correct society's identity/region is still ambiguous (see
NEEDS_DECISION below, printed but never applied) - these need Darragh's own
judgement, not a guess baked into a script.

Also inserts 5 rows into dismissed_society_corrections for suggestions that
were checked and found to be WRONG (the review's own text confirms the
society it's already filed under is correct) - so they stop reappearing on
/admin/society-corrections as if still undecided.

Safe to re-run: every write is guarded by an assertion of the expected
current state, and already-applied rows are skipped (get_db() calls check
before writing). Defaults to a dry run - pass --apply to actually commit.

Usage:
    py fix_society_misattributions.py [--db aims.db]
    py fix_society_misattributions.py --db aims.db --apply

In Docker: docker exec <container> python fix_society_misattributions.py --db /data/aims.db --apply
"""
import argparse
import sqlite3
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

# name -> (region, section, tier_evidence). Section is inferred from the
# tier printed on the review(s) that surfaced this society - not confirmed
# against AIMS's own current section list the way a real member's would be,
# since these societies aren't on that list at all yet. Worth a sanity check
# against AIMS's own records before treating as final.
NEW_SOCIETIES = {
    "Belfast Music and Drama Society": ("Northern", "Gilbert"),
    "Belfast School of Performing Arts": ("Northern", "Sullivan"),
    "Encore Theatre Company": ("Western", "Gilbert"),
    "New Lyric Operatic Company, Belfast": ("Northern", "Gilbert"),
    "Meath Youth Musical Society": ("Eastern", "Sullivan"),
    "Patrician Musical Society": ("Eastern", "Gilbert"),
    "Headford Musical Society": ("Western", "Sullivan"),
}

# (review_id, show_id, expected_show_title, expected_season, expected_current_society_id, target_society_id)
# target_society_id resolved against the *real* societies table, not a fuzzy
# guess - see the investigation this script came from for how each one was
# checked (either an exact/near-exact name match, or the review's own text
# read directly).
REPOINTS = [
    (843, 1825, "Calamity Jane", "17/18", 19, 25),           # Carnew -> Clane (the one that started this)
    (409, 1426, "Hello, Dolly!", "10/11", 19, 25),            # Carnew -> Clane
    (517, 1523, "Sweeney Todd", "12/13", 19, 25),             # Carnew -> Clane
    (875, 1849, "9 To 5", "18/19", 147, 105),                 # Kells -> St. Mel's, Longford
    (623, 1622, "Oliver!", "13/14", 147, 105),                # Kells -> St. Mel's, Longford
    (874, 1848, "Little Shop of Horrors", "18/19", 49, 73),   # Galway University -> Maynooth University
    (954, 1921, "Jesus Christ Superstar", "21/22", 49, 73),   # Galway University -> Maynooth University
    (476, 1486, "Rent", "11/12", 94, 73),                     # Ratoath -> Maynooth University (Aula Maxima venue)
    (369, 1388, "Jesus Christ Superstar", "10/11", 58, 147),  # Kill -> Kells
    (396, 1413, "The New Pirates of Penzance", "10/11", 6, 70),  # Baldoyle -> Malahide
    (475, 1485, "Sweeney Todd", "11/12", 6, 70),              # Baldoyle -> Malahide
    (542, 1546, "Crazy For You", "12/13", 6, 70),             # Baldoyle -> Malahide
    (426, 1443, "Nunsense", "10/11", 76, 104),                # Naas -> St. Marys, Navan
    (435, 1450, "Jesus Christ Superstar", "10/11", 162, 163), # Portarlington -> Portmarnock
    (581, 1584, "Rent", "13/14", 162, 163),                   # Portarlington -> Portmarnock
    (437, 1452, "The Pajama Game", "10/11", 2, 51),           # Achill -> Glencullen Dundrum MDS
    (457, 1468, "Hello, Dolly!", "11/12", 26, 24),            # Clara -> Cecilian, Limerick
    (534, 1539, "West Side Story", "12/13", 26, 24),          # Clara -> Cecilian, Limerick
    (591, 1592, "Copacabana", "13/14", 26, 24),               # Clara -> Cecilian, Limerick
    (531, 1536, "All Shook Up", "12/13", 85, 149),            # North East MDS -> Loughrea
    (524, 1529, "The Wizard of Oz", "12/13", 101, 103),       # St. Agnes Choral -> St. Mary's, Clonmel
    (575, 1578, "Jekyll & Hyde", "12/13", 101, 103),          # St. Agnes Choral -> St. Mary's, Clonmel
    (608, 1607, "Jesus Christ Superstar", "13/14", 98, 167),  # Shannon -> Sheevawn
    (429, 1445, "Our House", "10/11", 16, 63),                # Boyle -> Leixlip
    (842, 1824, "Les Miserables", "17/18", 9, 10),            # Ballyshannon -> Ballywillan
]

# (review_id, wrong_show_id, correct_show_id) - the same ShowTimes review
# extracted twice, one copy already correctly placed. Delete the review and
# skeleton show on the wrong one; the correct copy is untouched.
DUPLICATE_DELETES = [
    (846, 1828, 1959),  # Sister Act 17/18: wrong copy on Kells, correct one already on St. Mel's Longford
    (833, 1817, 1964),  # The Hired Man 17/18: wrong copy on MTU, correct one already on Harolds Cross Tallaght
]

# review 441 is a double bug: its show_raw ("RENT (School Edition)") doesn't
# even match the skeleton show's own title ("Miss Saigon (School Edition)") -
# the review text is unambiguously about Rent. One UPDATE fixes both the
# title and the society together, since only this one review points at the show.
RENT_FIX_REVIEW_ID = 441
RENT_FIX_SHOW_ID = 1455
RENT_FIX_EXPECTED_TITLE = "Miss Saigon (School Edition)"
RENT_FIX_EXPECTED_SEASON = "11/12"
RENT_FIX_EXPECTED_SOCIETY_ID = 94  # Ratoath
RENT_FIX_NEW_TITLE = "Rent"
RENT_FIX_NEW_SOCIETY = "Meath Youth Musical Society"

# (review_id, show_id, expected_show_title, expected_season, expected_current_society_id, new_society_name)
NEW_SOCIETY_REPOINTS = [
    (825, 1810, "Rock of Ages", "17/18", 85, "Belfast Music and Drama Society"),
    (850, 1832, "The Producers", "18/19", 85, "Belfast Music and Drama Society"),
    (871, 1846, "Footloose", "18/19", 85, "Belfast Music and Drama Society"),
    (650, 1648, "Miss Saigon (School Edition)", "13/14", 136, "Belfast School of Performing Arts"),
    (494, 1504, "Clown", "11/12", 47, "Encore Theatre Company"),
    (430, 1446, "West Side Story", "10/11", 83, "New Lyric Operatic Company, Belfast"),
    (520, 1526, "Les Miserables", "12/13", 94, "Meath Youth Musical Society"),
    (402, 1419, "Fiddler on the Roof", "10/11", 117, "Patrician Musical Society"),
    (484, 1494, "Show Boat", "11/12", 117, "Patrician Musical Society"),
    (380, 1399, "Calamity Jane", "10/11", 125, "Headford Musical Society"),
]

# Suggestions from society_gate_suggestions.json that were checked against
# the review's own text and found WRONG - the review confirms its current
# society is correct. Dismissed so they stop showing as undecided.
# (source_issue, show_raw, adjudicator)
DISMISSALS = [
    ("Issue 100, December 2014", "A Slice Of Saturday Night", "John Grayden"),   # genuinely "the Venue in Ratoath"
    ("Issue 114, June 2016", "Some Like It Hot", "Greg Currid"),                  # "St Mary's Musical Society" == the Navan one already attached
    ("Issue 130, May 2018", "Oliver!", "Peter Kennedy"),                          # Dun Laoghaire, accent/abbreviation variant of the same society
    ("Issue 79, Summer 2012", "Little Shop Of Horrors", "Andrea Rea"),            # same Navan false match
    ("Issue 95, May 2014", "South Pacific", "John Grayden"),                      # same Navan false match
]

# Not applied by this script - printed for visibility only. Each needs a
# real decision from Darragh, not a guess:
#  - ESB Musical and Dramatic Society (review 673, Assassins 14/15,
#    currently North East MDS) - real society name, region unconfirmed.
#  - "SONG" (review 595, Little Women 13/14, currently Shannon) - review
#    text names it "SONG in Dundalk" - full name/expansion unknown.
#  - The Real Theatre Company (review 367, Les Miserables 09/10, currently
#    The Odd Theatre Company) - confirmed real via text, no location found.
#  - National Youth Musical Theatre (review 366, Spring Awakening 09/10,
#    currently Donegal Youth Musical Theatre) - confirmed via "NYMT"
#    acronym in text, but it's a touring/national group, not tied to one
#    AIMS region.
#  - UL Musical Theatre Society (review 951, Spring Awakening 21/22,
#    currently UCC Musical Theatre Society) - confirmed via text ("UL
#    Musical Theatre Society, a relatively newly formed Society..."), but
#    unclear whether this is the same entity as the already-registered
#    "University of Limerick Musical Theatre Society" (id 124) or a
#    genuinely separate group - needs a judgement call, not a merge assumed
#    by a script.
NEEDS_DECISION = [673, 595, 367, 366, 951]

# Left completely alone - couldn't be confirmed either way from the review's
# own text, or (790) plausible but not textually confirmed:
#  - review 577 (Jesus Christ Superstar 13/14, Ratoath) - part of the same
#    Ratoath/Meath Youth pattern as 441/520, but this review's own text
#    never names either society.
#  - review 440 (Seussical 11/12, Craic Theatre vs suggested Civic Theatre)
#    - "Civic Theatre" may be the venue, not the society; text doesn't
#    settle it.
#  - review 790 (Footloose 16/17, Kill vs suggested Belfast Music and Drama
#    Society) - staged at the Waterfront Hall, Belfast (consistent with the
#    now-real Belfast Music and Drama Society), but the review's own text
#    never names the society directly the way 825/850/871 do.
STILL_UNRESOLVED = [577, 440, 790]


def get_or_create_society(conn, name, region, section):
    row = conn.execute("SELECT id FROM societies WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0], False
    cur = conn.execute(
        "INSERT INTO societies (name, region, section) VALUES (?, ?, ?)",
        (name, region, section),
    )
    return cur.lastrowid, True


def run(db_path, apply_changes):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    log = []

    def note(msg):
        log.append(msg)
        print(msg)

    # 1. Repoints to an already-registered society.
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

    # 2. Duplicate reviews - delete the wrong copy, correct one untouched.
    for review_id, wrong_show_id, correct_show_id in DUPLICATE_DELETES:
        wrong = conn.execute("SELECT show, season FROM shows WHERE id = ?", (wrong_show_id,)).fetchone()
        correct = conn.execute("SELECT id FROM shows WHERE id = ?", (correct_show_id,)).fetchone()
        assert wrong is not None and correct is not None, f"show {wrong_show_id}/{correct_show_id} missing"
        review = conn.execute("SELECT show_id FROM historical_reviews WHERE id = ?", (review_id,)).fetchone()
        assert review is not None and review["show_id"] == wrong_show_id, (
            f"review {review_id}: expected show_id {wrong_show_id}, found {review['show_id'] if review else None}"
        )
        other_reviews = conn.execute(
            "SELECT COUNT(*) FROM historical_reviews WHERE show_id = ? AND id != ?", (wrong_show_id, review_id)
        ).fetchone()[0]
        assert other_reviews == 0, f"show {wrong_show_id} has other reviews attached - not safe to delete"
        note(f"DUPLICATE: delete review {review_id} and show {wrong_show_id} '{wrong['show']}' "
             f"({wrong['season']}) - correct copy already on show {correct_show_id}")
        if apply_changes:
            conn.execute("DELETE FROM historical_reviews WHERE id = ?", (review_id,))
            conn.execute("DELETE FROM shows WHERE id = ?", (wrong_show_id,))

    # 3. The Rent/Miss Saigon title-and-society fix.
    show = conn.execute("SELECT show, season, society_id FROM shows WHERE id = ?", (RENT_FIX_SHOW_ID,)).fetchone()
    assert show is not None
    assert (show["show"], show["season"], show["society_id"]) == (
        RENT_FIX_EXPECTED_TITLE, RENT_FIX_EXPECTED_SEASON, RENT_FIX_EXPECTED_SOCIETY_ID
    ), f"show {RENT_FIX_SHOW_ID} state changed since this was written - skipping"
    review = conn.execute("SELECT show_id FROM historical_reviews WHERE id = ?", (RENT_FIX_REVIEW_ID,)).fetchone()
    assert review is not None and review["show_id"] == RENT_FIX_SHOW_ID
    region, section = NEW_SOCIETIES[RENT_FIX_NEW_SOCIETY]
    if apply_changes:
        new_society_id, created = get_or_create_society(conn, RENT_FIX_NEW_SOCIETY, region, section)
    else:
        existing = conn.execute("SELECT id FROM societies WHERE name = ?", (RENT_FIX_NEW_SOCIETY,)).fetchone()
        new_society_id, created = (existing[0] if existing else "new"), existing is None
    note(f"TITLE+SOCIETY FIX: show {RENT_FIX_SHOW_ID} '{RENT_FIX_EXPECTED_TITLE}' -> "
         f"'{RENT_FIX_NEW_TITLE}', {RENT_FIX_NEW_SOCIETY} (id {new_society_id}"
         f"{', newly created' if created else ''})")
    if apply_changes:
        conn.execute(
            "UPDATE shows SET show = ?, society_id = ? WHERE id = ?",
            (RENT_FIX_NEW_TITLE, new_society_id, RENT_FIX_SHOW_ID),
        )

    # 4. Repoints that need a brand-new society first.
    for review_id, show_id, title, season, expected_society_id, new_name in NEW_SOCIETY_REPOINTS:
        show = conn.execute("SELECT show, season, society_id FROM shows WHERE id = ?", (show_id,)).fetchone()
        assert show is not None, f"show {show_id} missing (review {review_id})"
        assert (show["show"], show["season"], show["society_id"]) == (title, season, expected_society_id), (
            f"review {review_id} show {show_id}: expected {(title, season, expected_society_id)}, "
            f"found {(show['show'], show['season'], show['society_id'])} - skipping, state has changed"
        )
        region, section = NEW_SOCIETIES[new_name]
        if apply_changes:
            target_id, created = get_or_create_society(conn, new_name, region, section)
        else:
            existing = conn.execute("SELECT id FROM societies WHERE name = ?", (new_name,)).fetchone()
            target_id, created = (existing[0] if existing else "new"), existing is None
        note(f"REPOINT (new society) show {show_id} '{title}' ({season}): -> {new_name} (id {target_id}"
             f"{', newly created' if created else ''})")
        if apply_changes:
            conn.execute("UPDATE shows SET society_id = ? WHERE id = ?", (target_id, show_id))

    # 5. Dismiss the suggestions that were checked and found wrong.
    for source_issue, show_raw, adjudicator in DISMISSALS:
        note(f"DISMISS suggestion: {show_raw!r} / {source_issue} / {adjudicator}")
        if apply_changes:
            conn.execute(
                "INSERT OR IGNORE INTO dismissed_society_corrections (source_issue, show_raw, adjudicator) "
                "VALUES (?, ?, ?)",
                (source_issue, show_raw, adjudicator),
            )

    print()
    print(f"NOT applied - needs a real decision (review ids): {NEEDS_DECISION}")
    print(f"NOT applied - still unresolved from the review text alone (review ids): {STILL_UNRESOLVED}")

    if apply_changes:
        conn.commit()
        print(f"\nApplied. {len(REPOINTS) + len(NEW_SOCIETY_REPOINTS) + 1} shows repointed/retitled, "
              f"{len(DUPLICATE_DELETES)} duplicate reviews removed, {len(DISMISSALS)} suggestions dismissed.")
    else:
        print(f"\nDry run only - {len(log)} planned actions above, nothing written. Pass --apply to commit.")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--apply", action="store_true", help="Actually commit the changes (default: dry run)")
    args = parser.parse_args()
    run(args.db, args.apply)
