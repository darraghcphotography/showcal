"""Link unlinked historical society names in historical_society_links,
clear pending photo submissions, and update lifecycle statuses for KATS and Seven Woods.

Run with --dry-run first to inspect changes before committing to production.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Confirmed historical society name -> society_id links
CONFIRMED_LINKS = {
    "Encore Theatre Company, Galway": 10009,  # Encore Theatre Company
    "Patrician Musical Society, Galway": 10011,  # Patrician Musical Society
    "Headford Choral Society": 10012,  # Headford Musical Society
}

# Confirmed standalone defunct/historical entities with no matching active societies row (no_match=1)
DEFUNCT_NO_MATCH_NAMES = [
    "De La Salle Musical Society, Waterford",
    "Bangor Operatic Society",
    "Edmund Rice Choral & Musical Society, Waterford",
    "Dublin Area Youth Musical Society",
    "Playback Productions, Dublin",
    "Arthur's Team, Dublin",
    "Dublin Musical Theatre Players",
    "Lakeland Productions, Mullingar",
    "Mullingar Charity Variety Group",
    "Taibhdhearc Na Gaillimhe",
    "Cameron Musical & Dramatic Society, Dublin",
    "First Act Musical Company, Belfast",
    "Flaggy Lane Productions, Waterford",
    "FACT School of Performing Arts, Dublin",
    "UCD Community Musical, Dublin",
    "Bank Of Ireland Group Musical Society",
    "Stillorgan Youth Musical Company",
    "Dolmen Music Theatre, Carlow",
    "Dundrum Musical & Dramatic Society, Dublin",
    "St. Oliver's Musical Society, Dundrum, Tipperary",
    "Good Counsel Musical Society, Drimnagh",
    "AIB Group Musical Society, Dublin",
    "Imagine Theatre Group, Waterford",
    "Lurgan Operatic Society",
    "Real Theatre Company, Dublin",
    "Bowler Hat Theatre Company, Waterford",
    "National Youth Musical Theatre, Dublin",
    "Navan Road Musical & Dramatic Society, Dublin",
    "Next Stage Productions, Dublin",
    "Talbot & Brady Stage Bratz",
    "Tristar Productions, Kilkenny",
    "West County Musical Society, Dublin",
    "Bord Gais Variety Group, Dublin",
    "Keable Young Generation, Kildare",
    "Premier Productions, Waterford",
    "Shield Insurance Musical Society",
    "St. John's Musical Society, Kilbarrack",
    "Stage Fright Musical Company, Waterford",
    "Tuam Youth Theatre",
    "Blackout Productions, Dublin",
    "Dungarvan Choral Society",
    "Galway Choral Association",
    "Greystones Operatic & Dramatic Society",
    "JH Academy of Theatre Arts, Belfast",
    "Marian Musical & Dramatic Society, Skerries",
    "Midas Music Company, Dublin",
    "Stillorgan Musical Company",
    "Telecom Eireann Galway Tops Musical Society",
    "AIMS",
    "Belfast Youth In The Arts",
    "Corpus Christi Musical Society, Dublin",
    "LARK, Kildare",
    "Making Waves Productions, Donegal",
    "Our Lady's Musical Society, Sallynoggin",
    "St. Louis Rathmines Musical Society",
    "Take Four",
    "Theatrix Musical Theatre Company, Bangor",
    "UCC DRAMAT, Cork",
    "UCD Dramsoc",
    "Upstart Productions",
    "Waterford Music Theatre",
]

# Lifecycle updates: KATS and Seven Woods are new in their Debut season -> Active
LIFECYCLE_UPDATES = {
    10004: ("Active", "Debut season (confirmed by Darragh 2026-08-30)"),  # KATS
    10002: ("Active", "Debut season (confirmed by Darragh 2026-08-30)"),  # Seven Woods Productions
}

# Photo submission IDs to clear per Darragh's instruction (2026-08-30)
PHOTO_SUBMISSION_IDS_TO_CLEAR = [8, 9, 10]


def run(db_path, dry_run=True):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    print(f"Opening database: {db_path} (dry_run={dry_run})")

    # 1. Historical society links
    links_added = 0
    no_match_added = 0

    for name, soc_id in CONFIRMED_LINKS.items():
        existing = cur.execute("SELECT * FROM historical_society_links WHERE society_name = ?", (name,)).fetchone()
        if not existing:
            soc_exists = cur.execute("SELECT id FROM societies WHERE id = ?", (soc_id,)).fetchone()
            if soc_exists:
                print(f"[LINK] Linking '{name}' -> society_id {soc_id}")
                cur.execute(
                    """
                    INSERT INTO historical_society_links (society_name, society_id, no_match, note, decided_by)
                    VALUES (?, ?, 0, 'Matched historical name variant', 'Gemini Antigravity (Darragh approved)')
                    """,
                    (name, soc_id),
                )
                links_added += 1
            else:
                print(f"[SKIP] Society id {soc_id} does not exist for '{name}', skipping link.")

    for name in DEFUNCT_NO_MATCH_NAMES:
        existing = cur.execute("SELECT * FROM historical_society_links WHERE society_name = ?", (name,)).fetchone()
        if not existing:
            print(f"[NO MATCH] Marking '{name}' -> no_match = 1")
            cur.execute(
                """
                INSERT INTO historical_society_links (society_name, society_id, no_match, note, decided_by)
                VALUES (?, NULL, 1, 'Defunct / historical group with no matching active society', 'Gemini Antigravity (Darragh approved)')
                """,
                (name,),
            )
            no_match_added += 1

    # 2. Lifecycle updates
    lifecycle_updated = 0
    for soc_id, (status, note) in LIFECYCLE_UPDATES.items():
        row = cur.execute("SELECT name, lifecycle_status FROM societies WHERE id = ?", (soc_id,)).fetchone()
        if row:
            print(f"[LIFECYCLE] Updating {row['name']} (id={soc_id}): {row['lifecycle_status']} -> {status} ({note})")
            cur.execute("UPDATE societies SET lifecycle_status = ? WHERE id = ?", (status, soc_id))
            lifecycle_updated += 1

    # 3. Clear photo submissions
    photos_cleared = 0
    for photo_id in PHOTO_SUBMISSION_IDS_TO_CLEAR:
        row = cur.execute("SELECT * FROM photo_submissions WHERE id = ?", (photo_id,)).fetchone()
        if row and row["status"] == "pending":
            print(f"[PHOTO] Clearing photo submission id={photo_id} ({row['society_guess']}) -> done")
            cur.execute(
                """
                UPDATE photo_submissions 
                SET status = 'done', 
                    moderator_notes = 'Cleared per Darragh instructions 2026-08-30; to be re-uploaded',
                    moderated_by = 'Gemini Antigravity',
                    moderated_at = datetime('now')
                WHERE id = ?
                """,
                (photo_id,),
            )
            photos_cleared += 1

    print("\n--- Summary ---")
    print(f"Historical links matched: {links_added}")
    print(f"Historical links marked no_match: {no_match_added}")
    print(f"Lifecycles updated: {lifecycle_updated}")
    print(f"Photo submissions cleared: {photos_cleared}")

    if dry_run:
        conn.rollback()
        print("\n[DRY RUN] Rolled back all changes. No database writes were committed.")
    else:
        conn.commit()
        # Trigger derived table rebuild so productions reflect any newly linked society awards
        from app import productions_build
        productions_build.build(conn)
        conn.commit()
        print("\n[LIVE] Committed changes and rebuilt derived productions table successfully.")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resolve historical society links, photos, and lifecycle.")
    parser.add_argument("--db", default=str(ROOT / "aims.db"), help="Path to aims.db")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run without committing")
    args = parser.parse_args()

    run(args.db, dry_run=args.dry_run)
