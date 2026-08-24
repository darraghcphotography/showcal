"""Import societies.csv and shows.csv into aims.db (SQLite).

Safe to re-run: this is an upsert, not a wipe-and-reload.
  - societies are always fully refreshed from the CSV (the spreadsheet is the
    only source of truth for that table).
  - shows rows created by the CSV import (source='import') are refreshed from
    the CSV, EXCEPT review_status/review_url/venue/director/musical_director/
    choreographer are never regressed to blank - if a moderator (or the app
    itself) has already filled one of these in, a stale/blank value in the
    spreadsheet won't erase it. A *non-blank* spreadsheet value still wins,
    since the spreadsheet is the source of truth when it actually has an
    answer - this only guards against a blank overwriting a real value.
  - shows rows created via the in-app member-submission workflow
    (source='submission') are never touched by this script.

Usage:
    py import_csv.py [--db aims.db] [--societies societies.csv] [--shows shows.csv]
"""
import argparse
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

# The spreadsheet fills in a tier for these seasons' rows as a copied-forward
# guess (whatever the society was last confirmed as), not an actual AIMS
# decision - there's no confirmed tier list published yet. Showing that guess
# as if it were fact was already wrong once (a real society's actual 26/27
# tier differed from the spreadsheet's guess). Blank it out on import instead
# of trusting it - every template already renders a blank section as '-'.
# Remove a season from this set once AIMS has actually published its tier
# list and the spreadsheet reflects real decisions, not guesses.
UNCONFIRMED_TIER_SEASONS = {"27/28"}


def normalize(value):
    """Blank/whitespace-only strings become None; 'n/a' also becomes None."""
    value = (value or "").strip()
    if not value or value.lower() == "n/a":
        return None
    return value


def load_societies(conn, path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        conn.execute(
            """
            INSERT INTO societies (id, name, region, section, section_as_of, section_history, notes)
            VALUES (:id, :name, :region, :section, :section_as_of, :section_history, :notes)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                region=excluded.region,
                section=excluded.section,
                section_as_of=excluded.section_as_of,
                section_history=excluded.section_history,
                notes=excluded.notes
            """,
            {
                "id": int(row["id"]),
                "name": row["name"].strip(),
                "region": row["region"].strip(),
                "section": row["section"].strip(),
                "section_as_of": normalize(row["section_as_of"]),
                "section_history": normalize(row["section_history"]),
                "notes": normalize(row["notes"]),
            },
        )
    return len(rows)


def load_shows(conn, path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    name_to_id = dict(conn.execute("SELECT name, id FROM societies").fetchall())

    inserted_or_updated = 0
    skipped_unknown_society = []

    for row in rows:
        society_name = row["society"].strip()
        society_id = name_to_id.get(society_name)
        if society_id is None:
            skipped_unknown_society.append(society_name)
            continue

        season = row["season"].strip()
        params = {
            "society_id": society_id,
            "season": season,
            "region": row["region"].strip(),
            "section": None if season in UNCONFIRMED_TIER_SEASONS else normalize(row["section"]),
            "show": normalize(row["show"]),
            "opening_date": normalize(row["opening_date"]),
            "closing_date": normalize(row["closing_date"]),
            "adjudication_date": normalize(row["adjudication_date"]),
            "adjudication_month_raw": normalize(row["adjudication_month_raw"]),
            "venue": normalize(row["venue"]),
            "director": normalize(row["director"]),
            "musical_director": normalize(row["musical_director"]),
            "choreographer": normalize(row["choreographer"]),
            "review_status": normalize(row["review_status"]) or "None",
            "review_url": normalize(row["review_url"]),
        }

        conn.execute(
            """
            INSERT INTO shows (
                society_id, season, region, section, show,
                opening_date, closing_date, adjudication_date, adjudication_month_raw,
                venue, director, musical_director, choreographer,
                review_status, review_url,
                moderation_status, source
            ) VALUES (
                :society_id, :season, :region, :section, :show,
                :opening_date, :closing_date, :adjudication_date, :adjudication_month_raw,
                :venue, :director, :musical_director, :choreographer,
                :review_status, :review_url,
                'approved', 'import'
            )
            ON CONFLICT(society_id, season, COALESCE(show, '')) DO UPDATE SET
                region=excluded.region,
                section=excluded.section,
                opening_date=excluded.opening_date,
                closing_date=excluded.closing_date,
                adjudication_date=excluded.adjudication_date,
                adjudication_month_raw=excluded.adjudication_month_raw,
                venue=COALESCE(excluded.venue, shows.venue),
                director=COALESCE(excluded.director, shows.director),
                musical_director=COALESCE(excluded.musical_director, shows.musical_director),
                choreographer=COALESCE(excluded.choreographer, shows.choreographer),
                review_url=COALESCE(NULLIF(excluded.review_url, ''), shows.review_url),
                review_status=CASE
                    WHEN excluded.review_status != 'None' THEN excluded.review_status
                    ELSE shows.review_status
                END,
                updated_at=datetime('now')
            WHERE shows.source = 'import'
            """,
            params,
        )
        inserted_or_updated += 1

    return inserted_or_updated, skipped_unknown_society


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--societies", default=str(ROOT / "societies.csv"))
    parser.add_argument("--shows", default=str(ROOT / "shows.csv"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")

    schema_sql = (ROOT / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    n_societies = load_societies(conn, args.societies)
    n_shows, skipped = load_shows(conn, args.shows)

    conn.commit()

    print(f"Societies: {n_societies} loaded from {args.societies}")
    print(f"Shows:     {n_shows} loaded from {args.shows}")
    if skipped:
        print(f"\nWARNING: {len(skipped)} show row(s) skipped - society name not found in societies.csv:")
        for name in sorted(set(skipped)):
            print(f"  - {name!r}")

    conn.close()
    print(f"\nDone -> {args.db}")


if __name__ == "__main__":
    main()
