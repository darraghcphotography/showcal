"""
Backfill GPS coordinates (latitude, longitude), town, and county for
unpinned upcoming venues so the "Near Me" radius filter has 100% coverage
across announced productions.

Usage:
  python scripts/backfills/backfill_upcoming_venue_coordinates.py [--db PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_parents = Path(__file__).resolve().parents
ROOT = _parents[2] if len(_parents) > 2 else _parents[0]

# Verified coordinates and locations for unpinned venues
VENUE_COORDINATES: dict[str, dict[str, str | float]] = {
    "the-civic-theatre-tallaght": {
        "name": "The Civic Theatre",
        "town": "Tallaght",
        "county": "Dublin",
        "latitude": 53.2872,
        "longitude": -6.3705,
    },
    "university-concert-hall-limerick": {
        "name": "University Concert Hall",
        "town": "Limerick",
        "county": "Limerick",
        "latitude": 52.6749,
        "longitude": -8.5727,
    },
    "the-barbican-centre-drogheda": {
        "name": "The Barbican Centre",
        "town": "Drogheda",
        "county": "Louth",
        "latitude": 53.7161,
        "longitude": -6.3475,
    },
    "the-palace-theatre-fermoy": {
        "name": "The Palace Theatre",
        "town": "Fermoy",
        "county": "Cork",
        "latitude": 52.1386,
        "longitude": -8.2778,
    },
    "abbey-hall-roscrea": {
        "name": "Abbey Hall",
        "town": "Roscrea",
        "county": "Tipperary",
        "latitude": 52.9554,
        "longitude": -7.7979,
    },
    "scout-s-hall-nenagh": {
        "name": "Scout's Hall",
        "town": "Nenagh",
        "county": "Tipperary",
        "latitude": 52.8624,
        "longitude": -8.1973,
    },
    "dunboyne-community-centre": {
        "name": "Dunboyne Community Centre",
        "town": "Dunboyne",
        "county": "Meath",
        "latitude": 53.4194,
        "longitude": -6.4742,
    },
    "aghada-community-centre": {
        "name": "Aghada Community Centre",
        "town": "Aghada",
        "county": "Cork",
        "latitude": 51.8488,
        "longitude": -8.2046,
    },
    "st-brigid-s-hall-carnew": {
        "name": "St. Brigid's Hall",
        "town": "Carnew",
        "county": "Wicklow",
        "latitude": 52.7103,
        "longitude": -6.4983,
    },
    "st-mary-s-college-hall-arklow": {
        "name": "St. Mary's College Hall",
        "town": "Arklow",
        "county": "Wicklow",
        "latitude": 52.7953,
        "longitude": -6.1557,
    },
    "st-brigid-s-church-hall-kill-kildare": {
        "name": "St. Brigid's Church Hall",
        "town": "Kill",
        "county": "Kildare",
        "latitude": 53.2508,
        "longitude": -6.5912,
    },
    "st-jarlath-s-college-tuam": {
        "name": "St. Jarlath's College",
        "town": "Tuam",
        "county": "Galway",
        "latitude": 53.5136,
        "longitude": -8.8471,
    },
    "temperance-hall-loughrea": {
        "name": "Temperance Hall",
        "town": "Loughrea",
        "county": "Galway",
        "latitude": 53.1978,
        "longitude": -8.5684,
    },
    "town-hall-theatre-claremorris": {
        "name": "Town Hall Theatre",
        "town": "Claremorris",
        "county": "Mayo",
        "latitude": 53.7214,
        "longitude": -8.9986,
    },
    "scariff-community-college": {
        "name": "Scariff Community College",
        "town": "Scariff",
        "county": "Clare",
        "latitude": 52.9098,
        "longitude": -8.5358,
    },
    "st-patrick-s-comprehensive-shannon": {
        "name": "St. Patrick's Comprehensive",
        "town": "Shannon",
        "county": "Clare",
        "latitude": 52.7099,
        "longitude": -8.8687,
    },
    "tullyvin-community-centre-cavan": {
        "name": "Tullyvin Community Centre",
        "town": "Tullyvin",
        "county": "Cavan",
        "latitude": 54.0453,
        "longitude": -7.1895,
    },
}


def run_backfill(db_path: Path, dry_run: bool = True) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    updated_count = 0
    print(f"[{'DRY-RUN' if dry_run else 'LIVE'}] Connecting to {db_path}...")

    for slug, data in VENUE_COORDINATES.items():
        row = cursor.execute("SELECT id, name, latitude, longitude, town, county FROM venues WHERE slug = ?", [slug]).fetchone()
        if not row:
            # Fallback by name match if slug differs
            row = cursor.execute("SELECT id, name, latitude, longitude, town, county FROM venues WHERE name LIKE ?", [f"%{data['name']}%"]).fetchone()

        if row:
            v_id = row["id"]
            lat = data["latitude"]
            lng = data["longitude"]
            town = data["town"]
            county = data["county"]
            print(f"  -> Updating Venue ID {v_id} ('{row['name']}'): lat={lat}, lng={lng}, town={town}, county={county}")
            if not dry_run:
                cursor.execute("""
                    UPDATE venues 
                    SET latitude = ?, longitude = ?, 
                        town = COALESCE(town, ?), 
                        county = COALESCE(county, ?)
                    WHERE id = ?
                """, [lat, lng, town, county, v_id])
            updated_count += 1
        else:
            print(f"  [!] Venue slug '{slug}' not found in database.")

    if dry_run:
        print(f"\n[DRY-RUN COMPLETE] Would update {updated_count} venues. Rolling back.")
        conn.rollback()
    else:
        conn.commit()
        print(f"\n[LIVE UPDATE COMPLETE] Successfully updated {updated_count} venues in {db_path}.")

    conn.close()
    return updated_count


def main():
    parser = argparse.ArgumentParser(description="Backfill GPS coordinates for unpinned venues.")
    parser.add_argument("--db", default=str(ROOT / "aims.db"), help="Path to database file")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run without committing")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"Error: Database {db_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    run_backfill(db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
