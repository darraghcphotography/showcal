"""Fill in societies.default_venue - the venue prefilled on a society's own
show submission when they leave it blank.

Source: GOOGLE_MAPS_INTEGRATION_PROPOSAL.md (Gemini). Its society -> venue
mapping is good: cross-checked against the venue our own archive says each
society most often plays, 90 of the 112 judgeable claims agreed. Where the two
disagreed it was usually our data at fault, not the mapping - the archive had
"Roscommon" for Boyle Musical Society, "Donegal" for Ballyshannon, "Castelbar"
for Castlebar, "40th Anniversary (March run)" for Trim. Those are the same junk
venue strings looks_unresolved() flags in the admin merge queue and cannot fix
on its own, because naming the real building is not something our data can
infer.

Every row below is tagged with how it was reached:

  * "confirmed"          - our own show history already puts this society in
                           this venue. 53 rows.
  * "names the building" - our archive held only a bare county or a note; the
                           mapping supplies the actual building. 12 rows.
  * "proposed"           - the society has no venue history at all here, so
                           there was nothing to check it against. 19 rows.

Where both name the same building, the more precise spelling wins - ours is
usually the one already on a venue record, but it is sometimes just the town
("Sligo" -> "Hawk's Well Theatre, Sligo", "Birr" -> "Birr Theatre & Arts
Centre").

Deliberately left out
---------------------
  * The 10 societies where our archive names a genuinely different building
    (Mitchelstown, Creative Minds, Striking Productions, DCU Drama, Rathmines &
    Rathgar, The Odd Theatre Company and others). A real per-society judgement,
    not something to settle from a list.
  * Four slash-joined proposals ("Grand Opera House / Lyric Theatre, Belfast")
    - those name two buildings, not one venue, same rule enrich_venues.py uses.
  * Anything for a society that already has a default_venue. A value somebody
    set by hand is never overwritten here.
  * Queen's Musical Theatre Society's "Mandela Hall, Belfast" - that venue
    closed in 2018 and the building was demolished in January 2020. The name was
    reused in the new QUB student centre, so it is ambiguous rather than simply
    wrong, and it wants a human.

Usage:
    py backfill_default_venues.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python backfill_default_venues.py --db /data/aims.db
"""
import argparse
import sqlite3
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]


# (society name, venue to set, how it was reached, the evidence)
ROWS = [
    ('Achill Musical & Dramatic Society', 'Achill Community Hall',
     'proposed', 'nothing on record to check it against'),
    ('Aghada Centre Theatre Group', 'Aghada Community Centre',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Armagh Creative Theatre Group', 'The Market Place Theatre, Armagh',
     'proposed', 'nothing on record to check it against'),
    ('Baldoyle Musical Society', "St. Mary's Secondary School Hall, Baldoyle",
     'confirmed', 'our archive: 1 production(s) here'),
    ('Ballinasloe Musical Society', 'Town Hall Theatre, Ballinasloe',
     'confirmed', 'our archive: 4 production(s) here'),
    ('Ballinrobe Musical Society', 'Ballinrobe Community School',
     'confirmed', 'our archive: 3 production(s) here'),
    ('Ballyshannon Musical Society', 'Abbey Arts Centre, Ballyshannon',
     'names the building', 'our archive only had "Donegal"'),
    ('Ballywillan Drama Group', 'Riverside Theatre, Coleraine',
     'names the building', 'our archive only had "Down"'),
    ('Banbridge Musical Society', 'Market Place Armagh',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Belfast Music and Drama Society', 'The MAC, Belfast',
     'proposed', 'nothing on record to check it against'),
    ('Belfast Operatic Company', 'Grand Opera House, Belfast',
     'confirmed', 'our archive: 2 production(s) here'),
    ('Bellvue Academy of Performing Arts', 'The Everyman, Cork',
     'names the building', 'our archive only had "Cork run"'),
    ('Birr Stage Guild', 'Birr Theatre & Arts Centre',
     'confirmed', 'our archive had the vaguer "Birr" (1x)'),
    ('Bosco Drama Group', 'Newry Town Hall',
     'confirmed', 'our archive had the vaguer "Newry" (1x)'),
    ('Boyle Musical Society', "St. Joseph's Hall, Boyle",
     'names the building', 'our archive only had "Roscommon"'),
    ('Bray Musical Society', 'Mermaid Arts Centre, Bray',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Carnew Musical Society', "St. Brigid's Hall, Carnew",
     'confirmed', 'our archive: 1 production(s) here'),
    ('Carrick-on-Suir Musical Society', 'Strand Theatre',
     'confirmed', 'our archive: 8 production(s) here'),
    ('Carrigaline Musical Society', 'Carrigaline Community Complex',
     'proposed', 'nothing on record to check it against'),
    ('Castlebar Musical & Dramatic Society', 'TF Royal Theatre Castlebar',
     'names the building', 'our archive only had "Castelbar"'),
    ('Cecilian Musical Society, Limerick', 'Lime Tree Theatre, Limerick',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Clara Musical Society', 'Esker Arts Centre, Tullamore',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Claremorris Musical Society', 'Town Hall Theatre, Claremorris',
     'confirmed', 'our archive: 3 production(s) here'),
    ('Craic Theatre', 'Craic Theatre, Coalisland',
     'names the building', 'our archive only had "Belfast"'),
    ('Drogheda Musical Society', 'The Barbican Centre, Drogheda',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Dundalk Musical Society', 'An Táin Arts Centre, Dundalk',
     'confirmed', 'our archive had the vaguer "An Táin Arts Centre" (3x)'),
    ('Dunmore Musical Society', 'Dunmore Community Centre',
     'proposed', 'nothing on record to check it against'),
    ('ESB Musical and Dramatic Society', 'National Concert Hall (NCH), Dublin',
     'proposed', 'nothing on record to check it against'),
    ('East Clare Musical Society', 'Scariff Community College',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Encore Performing Arts Academy', 'The Alley Theatre, Strabane',
     'confirmed', 'our archive had the vaguer "Strabane" (2x)'),
    ('Encore Theatre Company', 'Town Hall Theatre, Galway',
     'proposed', 'nothing on record to check it against'),
    ('Ennis Musical Society', 'glór, Ennis',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Ennistymon Choral Society', 'Ennistymon Community Centre',
     'names the building', 'our archive only had "Clare"'),
    ('Fermanagh Musical Theatre', 'Ardhowen Theatre, Enniskillen',
     'names the building', 'our archive only had "Fermanagh"'),
    ('Fermoy Musical Society', 'The Palace Theatre, Fermoy',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Fortwilliam Musical Society', 'Courtyard Theatre, Newtownabbey',
     'names the building', 'our archive only had "Fortwilliam"'),
    ('Fun House Theatre Company', 'Esker Arts Centre, Tullamore',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Fusion Theatre Group', 'Island Arts Centre, Lisburn',
     'proposed', 'nothing on record to check it against'),
    ('Glenamaddy Musical Society', 'Glenamaddy Town Hall Theatre',
     'confirmed', 'our archive had the vaguer "Glenamaddy" (1x)'),
    ('Greasepaint Productions', 'Belvoir Studio Theatre, Belfast',
     'proposed', 'nothing on record to check it against'),
    ('Greenhills Variety Group', 'Greenhills Community Centre',
     'proposed', 'nothing on record to check it against'),
    ('Headford Musical Society', 'Presentation College Hall, Headford',
     'proposed', 'nothing on record to check it against'),
    ('Kilkenny Musical Society', 'Watergate Theatre, Kilkenny',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Kill Musical & Dramatic Society', "St. Brigid's Church Hall, Kill, Kildare",
     'confirmed', 'our archive: 1 production(s) here'),
    ('Killarney Musical Society', 'Gleneagle Arena, Killarney',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Kilrush Choral Society', 'Kilrush Community School Hall',
     'confirmed', 'our archive had the vaguer "Kilrush" (1x)'),
    ('Light Opera Society of Tralee (LOST)', 'Siamsa Tíre, Tralee',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Limerick Musical Society', 'University Concert Hall (UCH), Limerick',
     'confirmed', 'our archive had the vaguer "University Concert Hall, Limerick" (1x)'),
    ('Lisnagarvey Operatic and Dramatic Society', 'Island Arts Centre (Lagan Valley Island), Lisburn',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Londonderry Musical Society', 'Millennium Forum, Derry',
     'names the building', 'our archive only had "Londonderry"'),
    ('MTU Musical Society', 'Curtis Auditorium, MTU Cork School of Music',
     'proposed', 'nothing on record to check it against'),
    ('Maree Musical Society', 'Maree Community Centre, Oranmore',
     'proposed', 'nothing on record to check it against'),
    ('Mary I Dramatic Arts Society', 'Lime Tree Theatre, Limerick',
     'confirmed', 'our archive had the vaguer "Limerick" (1x)'),
    ('Meath Youth Musical Society', 'Solstice Arts Centre',
     'confirmed', 'our archive: 2 production(s) here'),
    ('New Lyric Operatic Company, Belfast', 'Grand Opera House, Belfast',
     'proposed', 'nothing on record to check it against'),
    ('Newbridge Musical Society', 'The Riverbank',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Newcastle Glees Musical Society', 'Annesley Hall, Newcastle',
     'confirmed', 'our archive had the vaguer "Newcastle" (1x)'),
    ('Newcastlewest Musical Society', 'Newcastle West Community Centre',
     'names the building', 'our archive only had "Antrim"'),
    ('Newry Musical Society', 'Newry Town Hall',
     'confirmed', 'our archive had the vaguer "Newry" (1x)'),
    ('Newry Youth Performing Arts', 'Newry Town Hall',
     'confirmed', 'our archive had the vaguer "Newry" (1x)'),
    ('North East Musical and Dramatic Society', 'Íontas Arts Centre, Castleblayney',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Patrician Musical Society', 'Town Hall Theatre, Galway',
     'proposed', 'nothing on record to check it against'),
    ('Pop-Up Theatre, Sligo', 'ATU Knocknarea Arena, Sligo',
     'proposed', 'nothing on record to check it against'),
    ('Portlaoise Musical Society', 'Dunamaise Arts Centre, Portlaoise',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Portrush Music Society', 'The Playhouse, Portrush',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Ratoath Musical Society', 'The Venue Theatre, Ratoath',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Roscrea Musical Society', 'Abbey Hall, Roscrea',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Seven Woods Productions', 'Gort Community Centre',
     'proposed', 'nothing on record to check it against'),
    ('Shannon Musical Society', "St. Patrick's Comprehensive, Shannon",
     'confirmed', 'our archive: 1 production(s) here'),
    ('Sligo Fun Company', "Hawk's Well Theatre, Sligo",
     'confirmed', 'our archive had the vaguer "Sligo" (1x)'),
    ('Sligo Musical Society', "Hawk's Well Theatre, Sligo",
     'confirmed', 'our archive had the vaguer "Sligo" (1x)'),
    ("St. Mary's Choral Society, Clonmel", 'White Memorial Theatre, Clonmel',
     'confirmed', 'our archive: 1 production(s) here'),
    ('St. Marys Musical Society, Navan', 'Solstice Arts Centre',
     'confirmed', 'our archive: 5 production(s) here'),
    ("St. Patrick's Choral Society, Downpatrick", 'Down Arts Centre, Downpatrick',
     'proposed', 'nothing on record to check it against'),
    ('Studio 55 Dance Academy', "St. Mary's College Arklow",
     'confirmed', 'our archive had the vaguer "Arklow" (1x)'),
    ('Thurles Musical Society', 'The Premier Hall',
     'confirmed', 'our archive: 12 production(s) here'),
    ('Tipperary Musical Society', 'Simon Ryan Theatre, Tipperary Excel Centre',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Tralee Musical Society', 'Siamsa Tíre, Tralee',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Trim Musical Society', 'Swift Cultural Centre, Trim',
     'names the building', 'our archive only had "40th Anniversary (March run)"'),
    ('Tullamore Musical Society', 'Esker Arts Centre, Tullamore',
     'confirmed', 'our archive: 2 production(s) here'),
    ('Tullyvin Musical Society', 'Tullyvin Community Centre, Cavan',
     'confirmed', 'our archive: 1 production(s) here'),
    ('Ulster Operatic Company', 'Grand Opera House, Belfast',
     'confirmed', 'our archive: 1 production(s) here'),
    ('University of Limerick Musical Theatre Society', 'University Concert Hall (UCH), Limerick',
     'confirmed', 'our archive had the vaguer "Limerick" (1x)'),
    ('Youghal Musical Society', 'Mall Arts Centre, Youghal',
     'proposed', 'nothing on record to check it against'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    set_count = 0
    already = []
    missing = []
    for society, venue, kind, why in ROWS:
        row = db.execute(
            "SELECT id, default_venue FROM societies WHERE name = ?", (society,)
        ).fetchone()
        if row is None:
            missing.append(society)
            continue
        if row["default_venue"]:
            # Somebody has set one since this list was built. Theirs wins.
            already.append((society, row["default_venue"]))
            continue
        db.execute("UPDATE societies SET default_venue = ? WHERE id = ?", (venue, row["id"]))
        print(f"  {society}: {venue}")
        print(f"      [{kind}] {why}")
        set_count += 1

    if already:
        print()
        print(f"Left alone - already had a default venue ({len(already)}):")
        for society, venue in already:
            print(f"  {society}: {venue}")
    if missing:
        print()
        print(f"No society by that name ({len(missing)}):")
        for society in missing:
            print(f"  {society}")

    filled = db.execute(
        "SELECT COUNT(*) FROM societies WHERE default_venue IS NOT NULL AND default_venue != ''"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM societies").fetchone()[0]
    print()
    print(f"Set {set_count}. {filled} of {total} societies now have a default venue.")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
