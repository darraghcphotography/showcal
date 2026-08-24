"""Apply the 2026-08-24 venue-name research: 53 venue records that were just
a bare town/county name ("Belfast", "Antrim", "Tipperary"...) instead of a
real building, so a visitor couldn't tell "we don't know the venue" from
"here's a real theatre" - see ROADMAP.md's "Second Act backlog" item 1 for
the full story. Researched via three parallel Haiku agents cross-referencing
the untracked GOOGLE_MAPS_INTEGRATION_PROPOSAL.md and, where that didn't
cover it, a live web search.

Mechanism: corrects shows.venue (the free-text field, per society) rather
than touching the venues table directly - the same pattern enrich_venues.py
already uses in its own VENUE_CORRECTIONS list, and for the same reason: a
bare placeholder can quietly mean several different real buildings for
different societies (see the Antrim/Newcastle entries below, three
societies, three different real counties), so the fix has to happen at the
level of "what did this society actually type," with venues_build.build()
left to resolve each corrected spelling to the right venue - existing or
new - entirely on its own. A venue nothing points at any more is cleaned up
automatically by that same rebuild.

Deliberately NOT included:
  * Venues 120 ("Cork run") and 130 ("40th Anniversary (March run)") - not
    real places, malformed data-entry artifacts. Need a source-level fix
    (find where the bad text came from), not a venue correction.
  * Enniscorthy Musical Society ("Wexford") and UCC Musical Theatre Society
    ("Cork") - the only candidate answers found were slash-joined
    ("Coláiste Bríde / IFA Centre", "Cork Arts Theatre / Devere Hall UCC"),
    which enrich_venues.py's own documented policy treats as naming two
    buildings, not one - see its "Not merged, on purpose" note. Needs
    per-show research (which building for which specific production), not
    a blanket correction.
  * "Mandela Hall, Belfast" (Queen's Musical Theatre Society, was under
    "Antrim") is applied below, but ROADMAP.md flags it as ambiguous - the
    building closed and was demolished 2018-2020, so this may be right for
    an older production and wrong for a recent one. Worth a second look,
    not blocking.

Applied against production 2026-08-24: 71 of 71 (placeholder, society)
pairs matched, 73 show rows corrected, 118 venues from 144 normalized
spellings (30 new, 49 removed). Re-ran enrich_venues.py immediately after -
several of these corrected names (The Dean Crowe Theatre, Town Hall Theatre
Galway, Grand Opera House Belfast, Lime Tree Theatre, and others) already
had capacity/coordinates sitting in its DATA dict, waiting for a venue to
exist under that exact spelling.

Safe to re-run: every UPDATE is conditional on the row not already reading
the corrected text, so a second run reports "already correct" and changes
nothing.

Usage:
    py apply_venue_research.py [--db aims.db] [--dry-run]

    docker exec aims-web python apply_venue_research.py --db /data/aims.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import venues_build  # noqa: E402
from app.venues import normalize_venue  # noqa: E402

ROOT = Path(__file__).parent

# (placeholder venue text as currently typed, society, real venue name)
CORRECTIONS = [
    ("Aghada", "Aghada Centre Theatre Group", "Aghada Community Centre"),
    ("Athlone", "Athlone Musical Society", "The Dean Crowe Theatre"),
    ("Baldoyle", "Baldoyle Musical Society", "St. Mary's Secondary School Hall, Baldoyle"),
    ("Ballinrobe", "Ballinrobe Musical Society", "Ballinrobe Community School"),
    ("Ballinsaloe", "Ballinasloe Musical Society", "Town Hall Theatre, Ballinasloe"),
    ("Down", "Ballywillan Drama Group", "Riverside Theatre, Coleraine"),
    ("Down", "Lisnagarvey Operatic and Dramatic Society", "Island Arts Centre, Lisburn"),
    ("Tipperary", "Bellvue Academy of Performing Arts", "The Everyman, Cork"),
    ("Tipperary", "Nenagh Choral Society Ltd", "Scouts' Hall, Nenagh"),
    ("Tipperary", "Nenagh Choral Society Youth Academy", "Scouts' Hall, Nenagh"),
    ("Tipperary", "Roscrea Musical Society", "Abbey Hall, Roscrea"),
    ("Tipperary", "Tipperary Musical Society", "Tipperary Excel Arts Centre"),
    ("Birr", "Birr Stage Guild", "Birr Theatre & Arts Centre"),
    ("Newry", "Bosco Drama Group", "Newry Town Hall"),
    ("Newry", "Newry Musical Society", "Newry Town Hall"),
    ("Newry", "Newry Youth Performing Arts", "Newry Town Hall"),
    ("Roscommon", "Boyle Musical Society", "St. Joseph's Hall, Boyle"),
    ("Bray", "Bray Musical Society", "Mermaid Arts Centre, Bray"),
    ("Carnew", "Carnew Musical Society", "St. Brigid's Hall, Carnew"),
    ("Castelbar", "Castlebar Musical & Dramatic Society", "TF Royal Theatre Castlebar"),
    ("Limerick", "Cecilian Musical Society, Limerick", "Lime Tree Theatre, Limerick"),
    ("Limerick", "Limerick Musical Society", "University Concert Hall (UCH), Limerick"),
    ("Limerick", "Mary I Dramatic Arts Society", "Lime Tree Theatre, Limerick"),
    ("Limerick", "University of Limerick Musical Theatre Society", "University Concert Hall (UCH), Limerick"),
    ("Belfast", "Craic Theatre", "Craic Theatre, Coalisland"),
    ("Belfast", "Belfast Operatic Company", "Grand Opera House, Belfast"),
    ("Belfast", "St. Agnes Choral Society", "Grand Opera House, Belfast"),
    ("Belfast", "Ulster Operatic Company", "Grand Opera House, Belfast"),
    ("Dunboyne", "Dunboyne Musical Society", "Dunboyne GAA Hall"),
    ("Dundalk", "Dundalk Musical Society", "An Táin Arts Centre"),
    ("Strabane", "Encore Performing Arts Academy", "The Alley Theatre, Strabane"),
    ("Ennis", "Ennis Musical Society", "glór, Ennis"),
    ("Fermanagh", "Fermanagh Musical Theatre", "Ardhowen Theatre, Enniskillen"),
    ("Fortwilliam", "Fortwilliam Musical Society", "Courtyard Theatre, Newtownabbey"),
    ("Rathmines", "Rathmines & Rathgar Musical Society", "National Concert Hall (NCH), Dublin"),
    ("Galway", "Galway University Musical Society", "Town Hall Theatre, Galway"),
    ("Kilcock", "Kilcock Musical & Dramatic Society", "Kilcock GAA"),
    ("Kilkenny", "Kilkenny Musical Society", "Watergate Theatre, Kilkenny"),
    ("Killarney", "Killarney Musical Society", "Gleneagle Arena, Killarney"),
    ("Donegal", "Letterkenny Music & Drama Group", "An Grianán Theatre, Letterkenny"),
    ("Donegal", "Ballyshannon Musical Society", "Abbey Arts Centre, Ballyshannon"),
    ("Letterkenny", "Letterkenny Musical Society", "An Grianán Theatre, Letterkenny"),
    ("Londonderry", "Londonderry Musical Society", "Millennium Forum, Derry"),
    ("Tralee", "Light Opera Society of Tralee (LOST)", "Siamsa Tíre Theatre, Tralee"),
    ("Tralee", "Tralee Musical Society", "Siamsa Tíre Theatre, Tralee"),
    ("Dublin", "Malahide Musical & Dramatic Society", "Malahide Community School"),
    ("Dublin", "Trinity Musical Theatre Society", "O'Reilly Theatre Belvedere"),
    ("Dublin", "Ennistymon Choral Society", "Ennistymon Community Centre"),
    ("Mitchelstown", "Mitchelstown Musical Society", "CBS Secondary School Hall, Mitchelstown"),
    ("Meath", "Maynooth University Musical and Dramatics Society", "Aula Maxima, Maynooth University"),
    ("Meath", "Trim Musical Society", "Swift Cultural Centre, Trim"),
    ("Clare", "Ennistymon Choral Society", "Ennistymon Community Centre"),
    ("Glenamaddy", "Glenamaddy Musical Society", "Glenamaddy Town Hall Theatre"),
    ("Kilrush", "Kilrush Choral Society", "Kilrush Community School Hall"),
    ("Monaghan", "North East Musical and Dramatic Society", "Íontas Arts Centre, Castleblayney"),
    ("Newbridge", "Newbridge Musical Society", "The Riverbank"),
    ("Newbridge", "The Odd Theatre Company", "Moat Theatre, Naas"),
    ("Antrim", "Newcastle Glees Musical Society", "Annesley Hall, Newcastle"),
    ("Antrim", "Newcastlewest Musical Society", "Newcastle West Community Centre"),
    ("Antrim", "Queen's Musical Theatre Society", "Mandela Hall, Belfast"),
    ("Newcastle", "Newcastle Glees Musical Society", "Annesley Hall, Newcastle"),
    ("Portlaoise", "Portlaoise Musical Society", "Dunamaise Arts Centre, Portlaoise"),
    ("Rush", "Rush Musical Society", "Millbank Theatre Rush"),
    ("Shannon", "Shannon Musical Society", "St. Patrick's Comprehensive School, Shannon"),
    ("Sligo", "Sligo Fun Company", "Hawk's Well Theatre, Sligo"),
    ("Sligo", "Sligo Musical Society", "Hawk's Well Theatre, Sligo"),
    ("Clonmel", "St. Mary's Choral Society, Clonmel", "White Memorial Theatre, Clonmel"),
    ("Navan", "St. Marys Musical Society, Navan", "Solstice Arts Centre"),
    ("Longford", "St. Mel's Musical Society, Longford", "Backstage Theatre, Longford"),
    ("Arklow", "Studio 55 Dance Academy", "St. Mary's College Arklow"),
    ("Tullyvin", "Tullyvin Musical Society", "Tullyvin Community Centre"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    unmatched = []
    corrected_rows = 0
    corrected_pairs = 0

    for placeholder, society, real_name in CORRECTIONS:
        rows = db.execute(
            """
            SELECT shows.id, shows.venue FROM shows
              JOIN societies ON societies.id = shows.society_id
             WHERE societies.name = ?
            """,
            (society,),
        ).fetchall()
        matching = [r for r in rows if normalize_venue(r["venue"]) == normalize_venue(placeholder)]
        if not matching:
            unmatched.append((placeholder, society, real_name))
            continue

        changed_here = 0
        for row in matching:
            if row["venue"] == real_name:
                continue
            db.execute(
                "UPDATE shows SET venue = ?, updated_at = datetime('now') WHERE id = ?",
                (real_name, row["id"]),
            )
            changed_here += 1

        corrected_pairs += 1
        corrected_rows += changed_here
        status = f"{changed_here} row(s) corrected" if changed_here else "already correct"
        print(f"  {society} @ {placeholder!r} -> {real_name!r}  ({status}, {len(matching)} show(s) total)")

    if unmatched:
        print("\nNo matching show found (check spelling/society name - the placeholder text "
              "may already have been corrected, or the society's shows moved since this was written):")
        for p, s, r in unmatched:
            print(f"  {s} @ {p!r} -> {r!r}")

    print(f"\n{corrected_pairs} of {len(CORRECTIONS)} (placeholder, society) pairs matched, "
          f"{corrected_rows} show row(s) actually changed")

    print("\nRebuilding venues from corrected shows.venue text...")
    venues_build.build(db, report=print)

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nCommitted. Run enrich_venues.py again to attach capacity/coordinates/website "
              "detail to whichever of these corrected venues it already has researched.")
    db.close()


if __name__ == "__main__":
    main()
