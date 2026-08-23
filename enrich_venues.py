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

  * No coordinates for St. Mary's College Arklow, The Hub Castlerea, Leixlip
    GAA, Kilcock GAA, The Abbey Clane or Temperance Hall Loughrea - none of the
    six has an OpenStreetMap entry findable by name, and every candidate was a
    town-centre pin rather than the building.
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

sys.path.insert(0, str(Path(__file__).parent))

from app.venues import merge_venue_into, normalize_venue  # noqa: E402

ROOT = Path(__file__).parent


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
]

# Not merged, on purpose, and each one is a decision rather than an oversight:
#
#   * "Town Hall Theatre, Claremorris" / ", Ballinasloe" / ", Galway" are three
#     different buildings. The merge queue proposes them as one; they are not.
#   * Slash-joined names ("Grand Opera House / Lyric Theatre, Belfast",
#     "glór, Ennis / St. Patrick's Comprehensive, Shannon", "Kilcock GAA
#     Clubhouse / St. Joseph's Hall") name two buildings, not one venue recorded
#     two ways - a production that played both. Folding one into either half
#     would assert something the data doesn't say.
#   * The bare "Town Hall Theatre" record isn't a duplicate at all: its 6
#     productions are Ballinasloe (3), Claremorris (1), Galway University (1)
#     and Twin Productions (1). That's a shows.venue correction, one row at a
#     time, not a venue merge - and the Twin Productions one needs a human.

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
    },
    "St. Mary's College Arklow": {"town": "Arklow", "county": "Wicklow"},
    "Temperance Hall, Loughrea": {"town": "Loughrea", "county": "Galway"},
    "Leixlip GAA": {"town": "Leixlip", "county": "Kildare"},
    "Kilcock GAA": {"town": "Kilcock", "county": "Kildare"},
    "The Abbey Clane": {"town": "Clane", "county": "Kildare"},
}


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

    unmatched = []

    print("Merges")
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
