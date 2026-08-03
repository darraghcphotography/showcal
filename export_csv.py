"""Export aims.db back out to societies.csv/shows.csv, in the exact shape
import_csv.py expects to read back in.

This is the inverse of import_csv.py - use it to refresh the master CSVs
from the live database after a manual correction made directly in the app
(admin edit, society self-service), so the fix survives the next re-import
instead of being silently overwritten by a stale spreadsheet value.

Only exports shows.source = 'import' rows - member-submitted/self-service
shows (source = 'submission') were never part of the spreadsheet and
re-importing them wouldn't do anything anyway (import_csv.py's upsert is
guarded to source = 'import' rows only), so including them here would just
be misleading, not incorrect.

Usage:
    py export_csv.py [--db aims.db] [--societies societies.csv] [--shows shows.csv]

In Docker, pass the real paths explicitly, same as any other one-off script:
    docker exec aims-web python export_csv.py --db /data/aims.db --societies /data/societies.csv --shows /data/shows.csv
Then copy the two files back out (File Station, scp) to update the
git-tracked copies in the repo.
"""
import argparse
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

SOCIETY_FIELDS = ["id", "name", "region", "section", "section_as_of", "section_history", "notes"]
SHOW_FIELDS = [
    "season", "region", "section", "society", "show",
    "opening_date", "closing_date", "adjudication_date", "adjudication_month_raw",
    "venue", "director", "musical_director", "choreographer",
    "review_status", "review_url", "status",
]


def export_societies(conn, path):
    rows = conn.execute(
        "SELECT id, name, region, section, section_as_of, section_history, notes FROM societies ORDER BY id"
    ).fetchall()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(SOCIETY_FIELDS)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
    return len(rows)


def export_shows(conn, path):
    rows = conn.execute(
        """
        SELECT
            shows.season, shows.region, shows.section, societies.name AS society, shows.show,
            shows.opening_date, shows.closing_date, shows.adjudication_date, shows.adjudication_month_raw,
            shows.venue, shows.director, shows.musical_director, shows.choreographer,
            shows.review_status, shows.review_url, shows.status
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.source = 'import'
        ORDER BY shows.season, societies.name
        """
    ).fetchall()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(SHOW_FIELDS)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--societies", default=str(ROOT / "societies.csv"))
    parser.add_argument("--shows", default=str(ROOT / "shows.csv"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    n_societies = export_societies(conn, args.societies)
    n_shows = export_shows(conn, args.shows)

    conn.close()

    print(f"Societies: {n_societies} written to {args.societies}")
    print(f"Shows:     {n_shows} written to {args.shows}")


if __name__ == "__main__":
    main()
