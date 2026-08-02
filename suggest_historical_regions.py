"""One-off/re-runnable seed of best-guess regions for historical societies that
never resolved to a row in societies (defunct/renamed/never re-registered).
Guesses come from the place name embedded in the society's own name (verified
against AIMS's actual regional listings at aims.ie/<region> where useful) or a
web search where the name gives no location clue - never fabricated. A few
names had no confident guess at all and are seeded with no suggestion, left
for a moderator to research or leave blank.

This only ever sets suggested_region - confirmed_region (the one that
actually feeds into region-filtered stats) is set by a moderator reviewing
each suggestion at /admin/historical-societies. Safe to re-run: upserts
suggested_region/note but never touches a row's confirmed_region once set.

Usage:
    py suggest_historical_regions.py [--db aims.db]
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

# (society_name, suggested_region or None, note)
SUGGESTIONS = [
    ("AIB Group Musical Society, Dublin", "Eastern", "Dublin"),
    ("AIMS", None, "Not an actual society - likely a national-level award attribution, not tied to a region"),
    ("Arthur's Team, Dublin", "Eastern", "Dublin"),
    ("Bangor Operatic Society", "Northern", "Bangor, Co. Down"),
    ("Bank Of Ireland Group Musical Society", "Eastern", "Corporate group, likely Dublin HQ - lower confidence"),
    ("Belfast Music & Drama Society", "Northern", "Belfast"),
    ("Belfast Youth In The Arts", "Northern", "Belfast"),
    ("Blackout Productions, Dublin", "Eastern", "Dublin"),
    ("Bord Gais Variety Group, Dublin", "Eastern", "Dublin"),
    ("Bowler Hat Theatre Company, Waterford", "South-East", "Waterford"),
    ("Cameron Musical & Dramatic Society, Dublin", "Eastern", "Dublin"),
    ("Corpus Christi Musical Society, Dublin", "Eastern", "Dublin"),
    ("De La Salle Musical Society, Waterford", "South-East", "Waterford"),
    ("Dolmen Music Theatre, Carlow", "South-East", "Carlow"),
    ("Dublin Area Youth Musical Society", "Eastern", "Dublin"),
    ("Dublin Musical Theatre Players", "Eastern", "Dublin"),
    ("Dundrum Musical & Dramatic Society, Dublin", "Eastern", "Dublin"),
    ("Dungarvan Choral Society", "South-East", "Dungarvan, Co. Waterford"),
    ("Edmund Rice Choral & Musical Society, Waterford", "South-East", "Waterford"),
    ("Encore Theatre Company, Galway", "Western", "Galway"),
    ("FACT School of Performing Arts, Dublin", "Eastern", "Dublin"),
    ("First Act Musical Company, Belfast", "Northern", "Belfast"),
    ("Flaggy Lane Productions, Waterford", "South-East", "Waterford"),
    ("Fusion Theatre, Lisburn", "Northern", "Lisburn, Co. Antrim - confirmed via web search"),
    ("Galway Choral Association", "Western", "Galway"),
    ("Good Counsel Musical Society, Drimnagh", "Eastern", "Drimnagh, Dublin"),
    ("Greenhills Variety Group", "Eastern", "Likely Greenhills, Dublin - medium confidence"),
    ("Greystones Operatic & Dramatic Society", "South-East", "Greystones, Co. Wicklow"),
    ("Headford Choral Society", "Western", "Headford, Co. Galway"),
    ("Imagine Theatre Group, Waterford", "South-East", "Waterford"),
    ("JH Academy of Theatre Arts, Belfast", "Northern", "Belfast"),
    ("Keable Young Generation, Kildare", "Eastern", "Kildare - could plausibly be Midlands, low-medium confidence"),
    ("LARK, Kildare", "Eastern", "Kildare - could plausibly be Midlands, low-medium confidence"),
    ("Lakeland Productions, Mullingar", "Midlands", "Mullingar, Co. Westmeath (matches Athlone's Midlands grouping)"),
    ("Lurgan Operatic Society", "Northern", "Lurgan, Co. Armagh"),
    ("Making Waves Productions, Donegal", "Northern", "Donegal is grouped under AIMS's Northern region"),
    ("Maree Community Musical Society, Galway", "Western", "Galway"),
    ("Marian Musical & Dramatic Society, Skerries", "Eastern", "Skerries, Co. Dublin"),
    ("Midas Music Company, Dublin", "Eastern", "Dublin"),
    ("Mullingar Charity Variety Group", "Midlands", "Mullingar, Co. Westmeath"),
    ("National Youth Musical Theatre, Dublin", "Eastern", "Dublin"),
    ("Navan Road Musical & Dramatic Society, Dublin", "Eastern", "Navan Road is a Dublin city road (Cabra), not Navan town"),
    ("New Lyric Operatic Company, Belfast", "Northern", "Belfast"),
    ("Next Stage Productions, Dublin", "Eastern", "Dublin"),
    ("Our Lady's Musical Society, Sallynoggin", "Eastern", "Sallynoggin, Co. Dublin"),
    ("Patrician Musical Society, Galway", "Western", "Galway"),
    ("Pioneer Musical Society", "Eastern", "Founded at St Francis Xavier, Gardiner Street, Dublin (confirmed via web search)"),
    ("Playback Productions, Dublin", "Eastern", "Dublin"),
    ("Premier Productions, Waterford", "South-East", "Waterford"),
    ("Real Theatre Company, Dublin", "Eastern", "Dublin"),
    ("Shield Insurance Musical Society", "Eastern", "Corporate group, likely Dublin HQ - lower confidence"),
    ("St. Abban's Musical and Dramatic Society", None, "St Abban is venerated in both Adamstown, Co. Wexford (South-East) and Doonane, Co. Laois (Midlands) - genuinely ambiguous"),
    ("St. John's Musical Society, Kilbarrack", "Eastern", "Kilbarrack, Dublin"),
    ("St. Louis Rathmines Musical Society", "Eastern", "Rathmines, Dublin"),
    ("St. Oliver's Musical Society, Dundrum, Tipperary", "South-West", "Explicitly Tipperary"),
    ("Stage Fright Musical Company, Waterford", "South-East", "Waterford"),
    ("Stillorgan Musical Company", "Eastern", "Stillorgan, Dublin"),
    ("Stillorgan Youth Musical Company", "Eastern", "Stillorgan, Dublin"),
    ("Taibhdhearc Na Gaillimhe", "Western", '"na Gaillimhe" is Irish for "of Galway" - the well-known Galway Irish-language theatre'),
    ("Take Four", None, "No location clue in the name and no useful web search results"),
    ("Talbot & Brady Stage Bratz", None, "No location clue in the name and no useful web search results"),
    ("Telecom Eireann Galway Tops Musical Society", "Western", "Explicitly Galway"),
    ("The O'Connell Musical Society, Dublin", "Eastern", "Dublin"),
    ("Theatrix Musical Theatre Company, Bangor", "Northern", "Bangor, Co. Down"),
    ("Tristar Productions, Kilkenny", "South-East", "Kilkenny"),
    ("Tuam Youth Theatre", "Western", "Tuam, Co. Galway"),
    ("UCC DRAMAT, Cork", "South-West", "Cork (UCC)"),
    ("UCD Community Musical, Dublin", "Eastern", "Dublin (UCD)"),
    ("UCD Dramsoc", "Eastern", "Dublin (UCD)"),
    ("Upstart Productions", None, "No location clue in the name and no useful web search results"),
    ("Waterford Music Theatre", "South-East", "Waterford"),
    ("West County Musical Society, Dublin", "Eastern", "Dublin"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    for society_name, region, note in SUGGESTIONS:
        conn.execute(
            """
            INSERT INTO historical_society_regions (society_name, suggested_region, note, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(society_name) DO UPDATE SET
                suggested_region = excluded.suggested_region, note = excluded.note, updated_at = excluded.updated_at
            WHERE historical_society_regions.confirmed_region IS NULL
            """,
            (society_name, region, note),
        )
    conn.commit()
    print(f"Seeded {len(SUGGESTIONS)} suggestions ({sum(1 for _, r, _ in SUGGESTIONS if r)} with a guessed region)")

    missing = []
    for society_name, *_ in SUGGESTIONS:
        exists = conn.execute(
            "SELECT 1 FROM historical_results WHERE society_name = ? AND society_id IS NULL LIMIT 1",
            (society_name,),
        ).fetchone()
        if not exists:
            missing.append(society_name)
    print("Names with no matching unresolved historical_results row (check spelling):", missing or "none")
    conn.close()


if __name__ == "__main__":
    main()
