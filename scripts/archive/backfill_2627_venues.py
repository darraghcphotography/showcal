"""Backfill shows.venue for 26/27-season productions from venues_report.md
(repo root) - a venue-by-venue research pass Darragh ran via Gemini
Antigravity against the site's own 26/27 season page, cross-referenced here
against the live production database before writing anything.

Only the 38 shows below with a currently BLANK venue are applied - pure
gain, nothing to lose by writing them. 27 others already had this exact
venue on record (nothing to do). The remaining 16 are deliberately left
alone (see CONFLICTS below) - each already has a *different*, non-blank
venue on record, and on inspection most of Gemini's versions are just a
more/less detailed phrasing of the same real place (e.g. "UCD Astra Hall"
vs "Astra Hall, UCD Student Centre") rather than a correction - blindly
preferring the newer text risks silently dropping real detail already on
record (a "(75th Anniv.)" note, a county suffix). One (show 352, Bravo
Theatre Group's Dear Evan Hansen) looks like a genuine disagreement, not
just phrasing - "Temperance Hall, Loughrea" already on record vs Gemini's
"Town Hall Theatre, Loughrea" - two different-sounding venues in the same
town. None of the 16 are guessed at here either way.

Safe to re-run: guarded by an assertion of the expected current state.
Defaults to a dry run - pass --apply to actually commit.

Usage:
    py backfill_2627_venues.py [--db aims.db]
    py backfill_2627_venues.py --db aims.db --apply
"""
import argparse
import sqlite3
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

# (show_id, expected_show_title, expected_society_name, venue) - shows.venue
# was blank for every one of these before this script existed.
MATCHES = [
    (351, "Dear Evan Hansen", "Clara Musical Society", "Esker Arts Centre, Tullamore"),
    (353, "Michael Collins - A Musical Drama", "St. Michael's Theatre Musical Society", "St. Michael's Theatre, New Ross"),
    (356, "All Shook Up", "9 Arch Musical Society", "Town Hall Theatre, Galway"),
    (368, "Evita", "Carnew Musical Society", "St. Brigid's Hall, Carnew"),
    (364, "Come From Away", "Aghada Centre Theatre Group", "Aghada Community Centre"),
    (382, "Made in Dagenham", "Avonmore Musical Society", "St. Mary's College Hall, Arklow"),
    (344, "Newsies", "Roscrea Musical Society", "Abbey Hall, Roscrea"),
    (359, "Beauty And The Beast", "Bray Musical Society", "Mermaid Arts Centre, Bray"),
    (362, "Chess", "Newbridge Musical Society", "Riverbank Arts Centre / Newbridge College"),
    (367, "Come From Away", "Rush Musical Society", "Millbank Theatre, Rush"),
    (371, "Disney’s Frozen: The Broadway Musical", "Castlerea Musical Society", "The Hub Community Centre, Castlerea"),
    (372, "Guys and Dolls", "Enniscorthy Musical Society", "Coláiste Bríde / IFA Centre, Enniscorthy"),
    (374, "Jekyll & Hyde", "Light Opera Society of Tralee (LOST)", "Siamsa Tíre, Tralee"),
    (375, "Jekyll & Hyde", "Waterford Musical Society", "Theatre Royal Waterford"),
    (376, "Jesus Christ Superstar", "New Ross Musical Society", "St. Michael's Theatre, New Ross"),
    (377, "Little Shop of Horrors", "Kilcock Musical & Dramatic Society", "Kilcock GAA Clubhouse / St. Joseph's Hall"),
    (378, "Little Shop of Horrors", "Lisnagarvey Operatic and Dramatic Society", "Island Arts Centre (Lagan Valley Island), Lisburn"),
    (380, "Little Shop of Horrors", "Teachers' Musical Society", "DCU St. Patrick's Campus Auditorium / The Helix"),
    (381, "Made in Dagenham", "Tralee Musical Society", "Siamsa Tíre, Tralee"),
    (390, "Shrek the Musical", "Baldoyle Musical Society", "St. Mary's Secondary School Hall, Baldoyle"),
    (391, "Shrek the Musical", "St. Agnes Choral Society", "Grand Opera House / Lyric Theatre, Belfast"),
    (395, "Sister Act", "Tipperary Musical Society", "Simon Ryan Theatre, Tipperary Excel Centre"),
    (396, "Sweeney Todd", "Clane Musical & Dramatic Society", "The Abbey Community Centre, Clane"),
    (400, "The Addams Family", "North East Musical and Dramatic Society", "Íontas Arts Centre, Castleblayney"),
    (401, "The Addams Family", "Ulster Operatic Company", "Grand Opera House, Belfast"),
    (405, "The Clockmaker's Daughter", "Malahide Musical & Dramatic Society", "Scoil Íosa Hall (Malahide Community School)"),
    (412, "The Hunchback of Notre Dame", "Rathmines & Rathgar Musical Society", "Christ Church Taney / National Concert Hall"),
    (413, "The Little Mermaid", "Mitchelstown Musical Society", "Mitchelstown Community Leisure Centre"),
    (414, "The Prince of Egypt", "Ballinasloe Musical Society", "Town Hall Theatre, Ballinasloe"),
    (417, "The Producers", "Tullamore Musical Society", "Esker Arts Centre, Tullamore"),
    (419, "The Wedding Singer", "Athlone Musical Society", "Dean Crowe Theatre, Athlone"),
    (422, "We Will Rock You", "Kilmainham Inchicore Musical Society", "Inchicore College of Further Education (ICFE)"),
    (425, "West Side Story", "Muse Productions", "glór, Ennis / St. Patrick's Comprehensive, Shannon"),
    (434, "9 To 5", "Ennis Musical Society", "glór, Ennis"),
    (345, "Guys and Dolls", "Belfast Operatic Company", "Grand Opera House, Belfast"),
    (346, "Come From Away", "Portrush Music Society", "The Playhouse, Portrush"),
    (347, "Rent", "DCG Project, The", "Dublin Venue (Community/Theatre Stage)"),
    (348, "Made in Dagenham", "Creative Minds Productions", "White Memorial Theatre, Clonmel"),
]

# (show_id, title, society, gemini_venue, current_db_venue) - NOT applied.
# Each already has a different, non-blank venue on record already - see the
# module docstring for why these are left for a human call rather than
# either auto-applied or auto-skipped.
CONFLICTS = [
    (366, "Come From Away", "Thurles Musical Society", "The Premier Hall, Thurles", "The Premier Hall"),
    (386, "Next To Normal", "UCD Musical Society", "Astra Hall, UCD Student Centre", "UCD Astra Hall"),
    (352, "Dear Evan Hansen", "Bravo Theatre Group", "Town Hall Theatre, Loughrea", "Temperance Hall, Loughrea"),
    (392, "Shrek the Musical", "Tullyvin Musical Society", "Tullyvin Community Centre", "Tullyvin Community Centre, Cavan"),
    (360, "Calamity Jane", "Dundalk Musical Society", "An Táin Arts Centre, Dundalk", "An Táin Arts Centre, Dundalk (75th Anniv.)"),
    (399, "The Addams Family", "Coolmine Musical Society", "Draíocht Arts Centre, Blanchardstown", "Draíocht, Blanchardstown"),
    (457, "Elf", "Stage One New-Musical Group (S.O.N.G.)", "An Táin Arts Centre, Dundalk", "An Táin Arts Centre"),
    (410, "The Hired Man", "Kill Musical & Dramatic Society", "St. Brigid's Church Hall, Kill", "St. Brigid's Church Hall, Kill, Kildare"),
    (384, "Newsies", "Entr'acte Musical Theatre Society", "O'Reilly Theatre, Belvedere College", "O'Reilly Theatre, Belvedere, Dublin"),
    (426, "Wonderland", "Shannon Musical Society", "St. Patrick's Comprehensive School Hall, Shannon", "St. Patrick's Comprehensive, Shannon"),
    (420, "Legally Blonde", "East Clare Musical Society", "Scariff Community College Hall", "Scariff Community College"),
    (385, "Newsies", "Bellvue Academy of Performing Arts", "The Everyman / Firkin Crane / Strand Theatre", "Cork run"),
    (406, "The Clockmaker's Daughter", "Limerick Musical Society", "University Concert Hall (UCH), Limerick", "University Concert Hall, Limerick"),
    (398, "Sweet Charity", "Trim Musical Society", "Swift Cultural Centre / Scoil Mhuire Hall, Trim", "40th Anniversary (March run)"),
    (407, "The Clockmaker's Daughter", "Ballinrobe Musical Society", "Ballinrobe Community School Hall", "Ballinrobe Community School"),
    (421, "Urinetown", "Leixlip Musical & Variety Group", "St. Mary's GAA Club Hall, Leixlip", "St. Mary's, Leixlip"),
]


def run(db_path, apply_changes):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    log = []

    def note(msg):
        log.append(msg)
        print(msg)

    for show_id, title, society_name, venue in MATCHES:
        show = conn.execute(
            "SELECT shows.show, societies.name AS society_name, shows.venue "
            "FROM shows JOIN societies ON societies.id = shows.society_id WHERE shows.id = ?",
            (show_id,),
        ).fetchone()
        assert show is not None, f"show {show_id} missing"
        assert (show["show"], show["society_name"]) == (title, society_name), (
            f"show {show_id}: expected {(title, society_name)}, found "
            f"{(show['show'], show['society_name'])} - skipping, state has changed"
        )
        assert not (show["venue"] or "").strip(), (
            f"show {show_id}: expected a blank venue, found {show['venue']!r} - skipping, state has changed"
        )
        note(f"UPDATE show {show_id} '{title}' ({society_name}): venue -> {venue}")
        if apply_changes:
            conn.execute("UPDATE shows SET venue = ? WHERE id = ?", (venue, show_id))

    print()
    print(f"Left alone - already has a different venue on record ({len(CONFLICTS)} shows):")
    for show_id, title, society_name, venue, current in CONFLICTS:
        print(f"  {show_id}: {society_name} - {title} | on record: {current!r} | report says: {venue!r}")

    if apply_changes:
        conn.commit()
        print(f"\nApplied. {len(MATCHES)} shows given a venue.")
    else:
        print(f"\nDry run only - {len(log)} planned updates above, nothing written. Pass --apply to commit.")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--apply", action="store_true", help="Actually commit the changes (default: dry run)")
    args = parser.parse_args()
    run(args.db, args.apply)
