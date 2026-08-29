"""Researched detail for the venues AIMS societies actually play, plus the
handful of duplicate spellings that were still splitting one building in two.

Every venue field on the site already existed and already rendered - there was
just nothing in any of them. Measured 2026-08-23 on a production copy: 0 of 145
venues had a capacity, an auditorium type, a website, a tech spec, a map pin or
a county. This fills in the venues with 5 or more productions on record, which
between them carry about 70% of every show that names a venue at all.

Sourcing standard, and it is the whole point of this file
--------------------------------------------------------
These are real buildings. A wrong seating capacity is worse than a blank one,
because a blank one is visibly missing and a wrong one is quietly believed. So:

  * Capacities, websites and tech specs come from the venue's own site where it
    has one, and from a named, checkable source otherwise.
  * Coordinates come from OpenStreetMap's own record of the building - the same
    data the "See X on a map" link points at - or, where OSM has no entry, from
    the building's Wikipedia article. Never from a town centre: a pin on the
    wrong building is worse than no pin.
  * auditorium_type is only set where a source uses the word. A black-box
    studio "with retractable seating" is not enough to call End-on, so it's
    left blank. Only the values in AUDITORIUM_TYPES (app/blueprints/admin/
    venues.py) are used, or the admin dropdown won't match what's here.
  * Anything not confirmable is left NULL and listed below, rather than guessed.

Left deliberately blank, so nobody re-researches them thinking they were missed:

  * No coordinates for St. Mary's College Arklow, The Abbey Clane or Temperance
    Hall Loughrea. All three venues are confirmed (Darragh, 2026-08-24) - it's
    OpenStreetMap that has no entry for them findable by name, and every
    candidate was a town-centre pin or a same-named housing estate rather than
    the building. Eircodes don't help: Nominatim doesn't index them, and asked
    for one it fuzzy-matched to an unrelated address with a different Eircode.
  * No capacity for any of the school, college and GAA halls, or for Temperance
    Hall Loughrea and The Hub Castlerea. None publishes one.
  * No website for Strand Theatre Carrick-on-Suir - it has a Facebook page and a
    ticketing page, but no site of its own.

Judgment calls worth knowing about
----------------------------------
  * Where a venue's own pages disagree with themselves, the audience-facing
    figure wins over the technical maximum, because that's what the number means
    to a reader: Dean Crowe is 442 (their FAQ) not 466 (their tech spec's
    absolute max), and Gorey Little Theatre is 300 (the figure their own venue
    hire page uses) rather than the 340 some listings carry.
  * Capacities are the main auditorium, never the building. The National Opera
    House is 855 (the O'Reilly Theatre) and not 855 + the 172-seat Jerome Hynes;
    Mill Theatre is the 205-seat Karen Carleton Auditorium, not the studio too.
  * Dun Mhuire Theatre, Wexford is recorded as reported demolished. That's a
    moderator-facing note, not a public claim, and it is deliberately not acted
    on here beyond writing it down - see notes.

Safe to re-run, and safe against the rebuild
--------------------------------------------
Venues are a derived table (app/venues_build.py) but a partly authored one: the
columns filled in here are its CURATED_COLUMNS, which a rebuild never overwrites
and which stop a venue being deleted when no show points at it any more. Rows are
found through venue_aliases rather than venues.name_key, so a venue that has been
merged or renamed since still resolves. Re-running writes the same values again.

Usage:
    py enrich_venues.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python enrich_venues.py --db /data/aims.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import venues_build  # noqa: E402
from app.venues import merge_venue_into, normalize_venue  # noqa: E402

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]


# (spelling to fold away, the spelling it belongs to, why it's the same building)
#
# Each pair was confirmed by looking at which societies staged under each
# spelling, not by name similarity - app/venues.py's merge_candidates() is
# deliberately loose enough to propose three different Town Hall Theatres as one
# venue, so the suggestion alone is never evidence.
MERGES = [
    ("Town Hall Theare Galway", "Town Hall Theatre, Galway",
     "Typo for the same building. All 11 productions are Galway Musical Society."),
    ("Premier Hall", "The Premier Hall",
     "Thurles Musical Society both sides."),
    ("The Premier Hall, Thurles", "The Premier Hall",
     "Thurles Musical Society both sides."),
    ("Solstice Arts Centre, Navan", "Solstice Arts Centre",
     "Same building; the Navan suffix is the town it's already in."),
    ("St. Mary's GAA Club Hall, Leixlip", "Leixlip GAA",
     "St. Mary's is Leixlip's GAA club. Leixlip Musical & Variety Group both sides."),
    ("Kilcock GAA Clubhouse / St. Joseph's Hall", "Kilcock GAA",
     "Darragh confirmed 2026-08-24 that Kilcock perform at Kilcock GAA. Held back on "
     "the first pass because a slash-joined name normally means two buildings."),
    ("Pavilion Theatre, Dún Laoghaire", "Pavillion Theatre",
     "One building under two spellings, and ours is the typo. Folded into the record "
     "that carries the productions and the researched detail; the display name still "
     "wants correcting by hand in /admin/venue-directory."),
]

# Shows whose venue was typed as something ambiguous. Correcting the text is the
# fix - the rebuild then resolves each row to the right venue on its own - so
# these are not merges and must not be done as merges.
#
# All six were filed under a bare "Town Hall Theatre", which is four different
# buildings: Ballinasloe, Claremorris and Galway all have one. Matched on
# society + season + title rather than a row id, so a mismatch fails loudly
# instead of quietly rewriting the wrong show's venue.
#
# (society, season, show, venue as typed, venue it should read)
VENUE_CORRECTIONS = [
    ("Ballinasloe Musical Society", "10/11", "South Pacific",
     "Town Hall Theatre", "Town Hall Theatre, Ballinasloe"),
    ("Ballinasloe Musical Society", "12/13", "The Pirates Of Penzance",
     "Town Hall Theatre", "Town Hall Theatre, Ballinasloe"),
    ("Ballinasloe Musical Society", "22/23", "The Sound of Music",
     "Town Hall Theatre", "Town Hall Theatre, Ballinasloe"),
    ("Claremorris Musical Society", "21/22", "Sister Act",
     "Town Hall Theatre", "Town Hall Theatre, Claremorris"),
    ("Galway University Musical Society", "11/12", "Spring Awakening",
     "Town Hall Theatre", "Town Hall Theatre, Galway"),
    # Twin Productions are Galway-based (Darragh, 2026-08-24), so the Galway
    # Town Hall Theatre is the one they'll have played.
    ("Twin Productions", "18/19", "Peter Pan",
     "Town Hall Theatre", "Town Hall Theatre, Galway"),
]

# Not merged, on purpose, and each one is a decision rather than an oversight:
#
#   * "Town Hall Theatre, Claremorris" / ", Ballinasloe" / ", Galway" are three
#     different buildings. The merge queue proposes them as one; they are not.
#   * Slash-joined names ("Grand Opera House / Lyric Theatre, Belfast", "glór,
#     Ennis / St. Patrick's Comprehensive, Shannon") name two buildings, not one
#     venue recorded two ways. Darragh confirmed 2026-08-24 that the Grand Opera
#     House and the Lyric are two different Belfast venues; folding that record
#     into either half would assert something the data doesn't say.
#   * The bare "Town Hall Theatre" record isn't a duplicate at all - it's four
#     buildings under one label. Handled as VENUE_CORRECTIONS above.

# Display name -> the fields researched for it. Keys are matched through
# venue_aliases after normalize_venue(), so the spelling here only has to be one
# the archive actually used.
DATA = {
    "National Opera House, Wexford": {
        "town": "Wexford", "county": "Wexford", "capacity": 855,
        "website_url": "https://www.nationaloperahouse.ie/",
        "latitude": 52.3380264, "longitude": -6.4623710,
    },
    "St. Michael's Theatre for the Arts, New Ross": {
        "town": "New Ross", "county": "Wexford", "capacity": 298,
        "website_url": "https://stmichaelsnewross.com/",
        "latitude": 52.3941928, "longitude": -6.9453189,
    },
    "dlr Mill Theatre, Dundrum": {
        "town": "Dundrum", "county": "Dublin", "capacity": 205,
        "auditorium_type": "Proscenium",
        "website_url": "https://www.milltheatre.ie/",
        "tech_spec_url": "https://www.milltheatre.ie/about/tech-specs/",
        "latitude": 53.2884217, "longitude": -6.2430476,
    },
    "Civic Theatre Tallaght": {
        "town": "Tallaght", "county": "Dublin", "capacity": 309,
        "auditorium_type": "Proscenium",
        "website_url": "https://www.civictheatre.ie/",
        "tech_spec_url": "https://www.civictheatre.ie/wp-content/uploads/2026/01/"
                         "Main-Auditorium-Tech-Spec-2025-1.pdf",
        "latitude": 53.2885169, "longitude": -6.3721224,
    },
    "Draiocht Blanchardstown": {
        "town": "Blanchardstown", "county": "Dublin", "capacity": 286,
        "website_url": "https://www.draiocht.ie/",
        "tech_spec_url": "https://www.draiocht.ie/about/hire-a-space",
        "latitude": 53.3909593, "longitude": -6.3918252,
    },
    "The Dean Crowe Theatre": {
        "town": "Athlone", "county": "Westmeath", "capacity": 442,
        "website_url": "https://www.deancrowetheatre.com/",
        "tech_spec_url": "https://www.deancrowetheatre.com/tech-spec/",
        "latitude": 53.4216230, "longitude": -7.9439300,
    },
    "Town Hall Theatre, Galway": {
        "town": "Galway", "county": "Galway", "capacity": 400,
        "website_url": "https://tht.ie/",
        "latitude": 53.2761290, "longitude": -9.0540280,
    },
    "Theatre Royal, Waterford": {
        "town": "Waterford", "county": "Waterford", "capacity": 432,
        "website_url": "https://theatreroyal.ie/",
        "latitude": 52.2597854, "longitude": -7.1069047,
    },
    "Solstice Arts Centre": {
        "town": "Navan", "county": "Meath", "capacity": 320,
        "website_url": "https://solsticeartscentre.ie/",
        "tech_spec_url": "https://solsticeartscentre.ie/assets/Documents/"
                         "Technical-Specifications-2018-2.docx",
        "latitude": 53.6504468, "longitude": -6.6859476,
    },
    "An Táin Arts Centre": {
        "town": "Dundalk", "county": "Louth", "capacity": 350,
        "website_url": "https://www.antain.ie/",
        "latitude": 54.0047, "longitude": -6.4006,
    },
    "Pavillion Theatre": {
        "town": "Dún Laoghaire", "county": "Dublin", "capacity": 324,
        "website_url": "https://www.paviliontheatre.ie/",
        "latitude": 53.2939195, "longitude": -6.1338924,
    },
    "Moat Theatre, Naas": {
        "town": "Naas", "county": "Kildare", "capacity": 200,
        "website_url": "https://www.moattheatre.com/",
        "latitude": 53.218531, "longitude": -6.664107,
    },
    "The Riverbank": {
        "town": "Newbridge", "county": "Kildare", "capacity": 180,
        "website_url": "https://www.riverbank.ie/",
        "latitude": 53.1818268, "longitude": -6.7946691,
    },
    "Gorey Little Theatre": {
        "town": "Gorey", "county": "Wexford", "capacity": 300,
        "website_url": "https://www.goreytheatre.ie",
        "latitude": 52.6771059, "longitude": -6.2938895,
    },
    "Millbank Theatre Rush": {
        "town": "Rush", "county": "Dublin", "capacity": 140,
        "website_url": "https://www.millbanktheatre.ie/",
        "latitude": 53.5218744, "longitude": -6.1029752,
    },
    "Strand Theatre": {
        "town": "Carrick-on-Suir", "county": "Tipperary", "capacity": 360,
        "latitude": 52.3449710, "longitude": -7.4107326,
    },
    "O'Reilly Theatre Belvedere": {
        "town": "Dublin", "county": "Dublin", "capacity": 500,
        "website_url": "https://www.oreillytheatre.com/",
        "latitude": 53.3557584, "longitude": -6.2624302,
    },
    "UCD Astra Hall": {
        "town": "Dublin", "county": "Dublin",
        "latitude": 53.3081357, "longitude": -6.2262190,
    },
    "St. Patricks College DCU": {
        "town": "Dublin", "county": "Dublin",
        "latitude": 53.3715505, "longitude": -6.2534333,
    },
    "Inchicore College of Further Education (ICFE)": {
        "town": "Dublin", "county": "Dublin",
        "latitude": 53.3401584, "longitude": -6.3123171,
    },
    "Malahide Community School": {
        "town": "Malahide", "county": "Dublin",
        "latitude": 53.4385371, "longitude": -6.1528383,
    },
    "St. Jarlaths College Tuam": {
        "town": "Tuam", "county": "Galway",
        "latitude": 53.5146720, "longitude": -8.8443189,
    },
    "The Premier Hall": {
        "town": "Thurles", "county": "Tipperary",
        "latitude": 52.6804585, "longitude": -7.8141471,
    },
    "Dun Mhuire Theatre, Wexford": {
        "town": "Wexford", "county": "Wexford",
        "latitude": 52.3366219, "longitude": -6.4596623,
        "notes": "Reported demolished by Wexford County Council. Not confirmed "
                 "against a primary source - check before treating this as a "
                 "venue a society could still play.",
    },
    "The Hub Castlerea": {
        "town": "Castlerea", "county": "Roscommon",
        "website_url": "https://www.thehubcastlerea.com/",
        # OSM knows the building as "The Hub Gym" - The Hub's own description of
        # itself lists a gym among what the community centre houses, so this is
        # the same building under the tenant's name rather than a near miss.
        "latitude": 53.7673005, "longitude": -8.4763084,
    },
    # Below the 5-production threshold, but only because the bare "Town Hall
    # Theatre" label was hiding their real counts - they're here because
    # VENUE_CORRECTIONS above put those productions back.
    "Town Hall Theatre, Ballinasloe": {
        "town": "Ballinasloe", "county": "Galway",
        "latitude": 53.3305956, "longitude": -8.2249983,
    },
    "Town Hall Theatre, Claremorris": {"town": "Claremorris", "county": "Mayo"},
    # ---- Second pass, 2026-08-24, from GOOGLE_MAPS_INTEGRATION_PROPOSAL.md ----
    #
    # That document supplied the shortlist: venues our archive uses that nobody
    # had researched yet. Its capacities check out where the venue publishes one
    # - Watergate 328, Hawk's Well 340, Lime Tree 510, Backstage 212 all
    # confirmed exactly against the venues' own pages - so they're taken as
    # given here.
    #
    # Its coordinates are not taken. They were spot-checked against OSM and are
    # right for some venues and badly out for others: Backstage Theatre by 1.8km,
    # Dunboyne GAA by 1.2km, Ballinrobe by 700m, glór by 380m. Every coordinate
    # below is OSM's own, looked up per venue, with the proposal's value used
    # only as the prompt to go and look. Where OSM has no record, there's no pin
    # - same rule as the first pass.
    #
    # Capacities are left off the schools, GAA halls and community centres it
    # lists. Those publish no figure, and its numbers for them are round
    # (300, 300, 250, 180...) in a way its arts-centre figures are not.
    "Grand Opera House, Belfast": {
        "town": "Belfast", "county": "Antrim", "capacity": 1058,
        "auditorium_type": "Proscenium", "website_url": "https://www.goh.co.uk/",
        "latitude": 54.5953336, "longitude": -5.9351922,
    },
    "The Helix, Dublin": {
        "town": "Dublin", "county": "Dublin", "capacity": 1050,
        "auditorium_type": "Proscenium", "website_url": "https://thehelix.ie/",
        "latitude": 53.3864895, "longitude": -6.2592607,
    },
    "Watergate Theatre, Kilkenny": {
        "town": "Kilkenny", "county": "Kilkenny", "capacity": 328,
        "auditorium_type": "Proscenium", "website_url": "https://watergatetheatre.com/",
        "latitude": 52.6552640, "longitude": -7.2545853,
    },
    "Hawk's Well Theatre, Sligo": {
        "town": "Sligo", "county": "Sligo", "capacity": 340,
        "auditorium_type": "Proscenium", "website_url": "https://www.hawkswell.com/",
        "latitude": 54.2688590, "longitude": -8.4771140,
    },
    "Lime Tree Theatre, Limerick": {
        "town": "Limerick", "county": "Limerick", "capacity": 510,
        "auditorium_type": "Proscenium", "website_url": "https://limetreetheatre.ie/",
        "latitude": 52.6535316, "longitude": -8.6422575,
    },
    "Backstage Theatre, Longford": {
        "town": "Longford", "county": "Longford", "capacity": 212,
        "auditorium_type": "Proscenium", "website_url": "https://backstage.ie/",
        "latitude": 53.7155902, "longitude": -7.8001114,
    },
    "Dunamaise Arts Centre, Portlaoise": {
        "town": "Portlaoise", "county": "Laois", "capacity": 240,
        "auditorium_type": "Proscenium", "website_url": "https://www.dunamaise.ie/",
        "latitude": 53.0344802, "longitude": -7.2997520,
    },
    "Mermaid Arts Centre, Bray": {
        "town": "Bray", "county": "Wicklow", "capacity": 242,
        "auditorium_type": "Proscenium", "website_url": "https://www.mermaidartscentre.ie/",
        "latitude": 53.2015930, "longitude": -6.1091051,
    },
    "glór, Ennis": {
        "town": "Ennis", "county": "Clare", "capacity": 485,
        "auditorium_type": "Proscenium", "website_url": "https://glor.ie/",
        "latitude": 52.8446512, "longitude": -8.9770509,
    },
    "Esker Arts Centre, Tullamore": {
        "town": "Tullamore", "county": "Offaly", "capacity": 228,
        "auditorium_type": "Proscenium", "website_url": "https://eskerarts.ie/",
        "latitude": 53.2734911, "longitude": -7.4940266,
    },
    "The Venue Theatre, Ratoath": {
        "town": "Ratoath", "county": "Meath", "capacity": 230,
        "auditorium_type": "Proscenium", "website_url": "https://venuetheatre.ie/",
        "latitude": 53.5074501, "longitude": -6.4628350,
    },
    "White Memorial Theatre, Clonmel": {
        "town": "Clonmel", "county": "Tipperary",
        "latitude": 52.3533915, "longitude": -7.7061769,
    },
    "Ballinrobe Community School": {
        "town": "Ballinrobe", "county": "Mayo",
        "latitude": 53.6230631, "longitude": -9.2134073,
    },
    "Dunboyne GAA Hall": {
        "town": "Dunboyne", "county": "Meath",
        "latitude": 53.4102744, "longitude": -6.4731824,
    },
    "Gleneagle Arena, Killarney": {
        "town": "Killarney", "county": "Kerry",
        "website_url": "https://www.gleneaglearena.com/",
        # The Gleneagle complex's own OSM point - the arena sits inside it.
        "latitude": 52.0439227, "longitude": -9.5014985,
    },
    "St. Mary's College Arklow": {"town": "Arklow", "county": "Wicklow"},
    "Temperance Hall, Loughrea": {"town": "Loughrea", "county": "Galway"},
    "Leixlip GAA": {
        "town": "Leixlip", "county": "Kildare",
        "latitude": 53.3643146, "longitude": -6.5025255,
    },
    "Kilcock GAA": {
        "town": "Kilcock", "county": "Kildare",
        "latitude": 53.3938661, "longitude": -6.6664450,
    },
    "The Abbey Clane": {"town": "Clane", "county": "Kildare"},
}


# Venues whose display name is a typo or a fragment. The rebuild picks a name
# from the spellings in shows.venue, so where every show carries the misspelling
# it has no better option - correcting it is an authored act, like a merge.
#
# The slug is deliberately left alone: it was minted from the old name, existing
# links use it, and /venues/<slug> is stable. Same as the admin edit form, which
# also doesn't re-slug on rename.
RENAMES = [
    ("Pavillion Theatre", "Pavilion Theatre, Dún Laoghaire",
     "Missing an 'l'. The correctly-spelled record was merged into this one, so "
     "this is the surviving name and it's the wrong one."),
]


def resolve(db, name):
    """The venue a spelling belongs to today, following any merge. Returns None
    if nothing in the archive ever used this spelling."""
    row = db.execute(
        "SELECT venue_id FROM venue_aliases WHERE name_key = ?", (normalize_venue(name),)
    ).fetchone()
    return row["venue_id"] if row else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    # Same as the app does per connection (app/db.py). Not optional here: the
    # rebuild below deletes a venue nothing points at any more, and without
    # this its venue_aliases rows don't cascade - the rebuild's own
    # verification pass catches the orphan and refuses to commit.
    db.execute("PRAGMA foreign_keys = ON")

    unmatched = []

    print("Venue corrections on individual shows")
    for society, season, show, typed, corrected in VENUE_CORRECTIONS:
        row = db.execute(
            """
            SELECT shows.id, shows.venue FROM shows
              JOIN societies ON societies.id = shows.society_id
             WHERE societies.name = ? AND shows.season = ? AND shows.show = ?
            """,
            (society, season, show),
        ).fetchone()
        if row is None:
            print(f"  no such show: {society}, {season}, {show}")
            continue
        if row["venue"] == corrected:
            print(f"  already corrected: {society}, {season}, {show}")
            continue
        if row["venue"] != typed:
            # Somebody has edited this row since the correction was written.
            # Theirs wins - never overwrite a moderator with a stale script.
            print(f"  SKIPPED, venue has changed since: {society}, {season}, {show} "
                  f"(reads {row['venue']!r}, expected {typed!r})")
            continue
        db.execute("UPDATE shows SET venue = ?, updated_at = datetime('now') WHERE id = ?",
                   (corrected, row["id"]))
        print(f"  {society}, {season}, {show}: {typed!r} -> {corrected!r}")

    # Re-derive so those rows point at the venue they now name, and so a venue
    # nothing refers to any more is cleaned up before the merges below run.
    venues_build.build(db)

    print("\nMerges")
    for source_name, target_name, why in MERGES:
        source_id = resolve(db, source_name)
        target_id = resolve(db, target_name)
        if target_id is None:
            unmatched.append(target_name)
            continue
        if source_id is None:
            unmatched.append(source_name)
            continue
        if source_id == target_id:
            print(f"  already merged: {source_name} -> {target_name}")
            continue
        merge_venue_into(db, source_id, target_id)
        print(f"  {source_name} -> {target_name}")
        print(f"      {why}")

    print("\nCorrected names")
    for current, corrected, why in RENAMES:
        venue_id = resolve(db, current)
        if venue_id is None:
            unmatched.append(current)
            continue
        row = db.execute("SELECT name FROM venues WHERE id = ?", (venue_id,)).fetchone()
        if row["name"] == corrected:
            print(f"  already correct: {corrected}")
            continue
        db.execute(
            "UPDATE venues SET name = ?, updated_at = datetime('now') WHERE id = ?",
            (corrected, venue_id),
        )
        print(f"  {row['name']!r} -> {corrected!r}")
        print(f"      {why}")

    print("\nDetail")
    for name, fields in DATA.items():
        venue_id = resolve(db, name)
        if venue_id is None:
            unmatched.append(name)
            continue
        current = db.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
        # Only write what actually moves, so a re-run reports honestly rather
        # than claiming to have set 26 venues it changed nothing about.
        changing = {f: v for f, v in fields.items() if current[f] != v}
        if not changing:
            print(f"  {current['name']}: unchanged")
            continue
        assignments = ", ".join(f"{f} = :{f}" for f in changing)
        db.execute(
            f"UPDATE venues SET {assignments}, updated_at = datetime('now') WHERE id = :id",
            dict(changing, id=venue_id),
        )
        print(f"  {current['name']}: {', '.join(sorted(changing))}")

    if unmatched:
        print("\nNo venue in this database uses these spellings (check the name):")
        for name in unmatched:
            print(f"  {name}")

    filled = db.execute(
        "SELECT COUNT(*) FROM venues WHERE capacity IS NOT NULL"
    ).fetchone()[0]
    pinned = db.execute(
        "SELECT COUNT(*) FROM venues WHERE latitude IS NOT NULL"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    print(f"\n{filled} of {total} venues now have a capacity, {pinned} have a map pin")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
