"""Export historical_results back out to "AIMS_Awards - Results.csv", in
the exact shape import_awards.py expects to read back in.

This is the inverse of import_awards.py - use it to refresh the tracked CSV
from the live database after a correction made directly in the app
(/admin/awards), so the fix survives the next re-import instead of being
silently overwritten by a stale spreadsheet value.

Unlike export_csv.py, this exports EVERY row regardless of source ('import'
or 'manual') - editing an existing award record in the app sets its source
to 'manual' too, not just brand-new additions (see admin.edit_award()), so
filtering to source='import' would drop exactly the corrections this script
exists to capture.

Columns import_awards.py never reads (Tier/Category/Society/Region/Title -
internal GUIDs and lookups from the original spreadsheet export, long since
superseded by resolving through the societies table at import time instead)
are kept in the header for round-trip compatibility but always written
blank - nothing in the database has ever populated them.

Usage:
    py export_awards.py [--db aims.db] [--csv "AIMS_Awards - Results.csv"]

In Docker:
    docker exec aims-web python export_awards.py --db /data/aims.db --csv "/data/AIMS_Awards - Results.csv"
Then copy the file back out (File Station, scp) to update the git-tracked copy.
"""
import argparse
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

FIELDS = [
    "Year", "SchemeName", "Tier", "CategoryName", "Category", "ResultText",
    "NomineeName", "Role", "Showname", "ResolvedSocietyName", "Society",
    "Region", "Reason", "Title",
]


def export_awards(conn, path):
    rows = conn.execute(
        """
        SELECT year, tier, category_name, result, nominee_name, role, show, society_name, reason
        FROM historical_results
        ORDER BY year, category_name, society_name
        """
    ).fetchall()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        for year, tier, category_name, result, nominee_name, role, show, society_name, reason in rows:
            writer.writerow([
                year, tier or "", "", category_name or "", "", result or "",
                nominee_name or "", role or "", show or "", society_name or "", "",
                "", reason or "", "",
            ])
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--csv", default=str(ROOT / "AIMS_Awards - Results.csv"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    n = export_awards(conn, args.csv)
    conn.close()

    print(f"Award results: {n} written to {args.csv}")


if __name__ == "__main__":
    main()
