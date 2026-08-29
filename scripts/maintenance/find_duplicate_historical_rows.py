"""Diagnostic (and optional cleanup) for a specific bug in
admin.bulk_historical_productions, fixed 2026-08-06: earlier versions of
that tool only checked for an existing *bare* historical_results row
(no category/result) before inserting - not a real award-archive row for
the same (year, show, society), and not a matching shows table entry
either. Anyone who ran the bulk-add tool against a society with existing
award-archive coverage, or for a year already in `shows`, before that fix
shipped may have ended up with a redundant bare row duplicating a
production already on record.

This finds bare rows (no category_name, no result - the tool's own
signature) that have a "sibling": either another historical_results row
for the same (year, show, society_id), or a matching shows table row. It
never touches a real award-record row itself, only ever a redundant bare
one.

Usage:
    py find_duplicate_historical_rows.py [--db aims.db]   # report only
    py find_duplicate_historical_rows.py [--db aims.db] --fix   # delete the redundant bare rows
"""
import argparse
import sqlite3
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]


def find_duplicates(conn):
    dup_vs_historical = conn.execute(
        """
        SELECT h1.id, h1.year, h1.show, h1.society_name
        FROM historical_results h1
        WHERE h1.category_name IS NULL AND h1.result IS NULL
          AND h1.society_id IS NOT NULL AND h1.show IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM historical_results h2
            WHERE h2.year = h1.year AND h2.show = h1.show AND h2.society_id = h1.society_id
              AND h2.id != h1.id
          )
        ORDER BY h1.society_name, h1.year
        """
    ).fetchall()

    dup_vs_shows = conn.execute(
        """
        SELECT h.id, h.year, h.show, h.society_name
        FROM historical_results h
        WHERE h.category_name IS NULL AND h.result IS NULL
          AND h.society_id IS NOT NULL AND h.show IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM shows s
            WHERE s.society_id = h.society_id AND s.show = h.show
              AND substr(s.opening_date, 1, 4) = CAST(h.year AS TEXT)
          )
        ORDER BY h.society_name, h.year
        """
    ).fetchall()

    return dup_vs_historical, dup_vs_shows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--fix", action="store_true", help="Delete the redundant bare rows found")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    dup_vs_historical, dup_vs_shows = find_duplicates(conn)

    if not dup_vs_historical and not dup_vs_shows:
        print("No duplicates found - nothing to do.")
        return

    if dup_vs_historical:
        print(f"{len(dup_vs_historical)} bare row(s) duplicating another historical_results row:")
        for row_id, year, show, society_name in dup_vs_historical:
            print(f"  id={row_id}  {year}  {show!r}  {society_name}")
    if dup_vs_shows:
        print(f"{len(dup_vs_shows)} bare row(s) duplicating a shows table entry:")
        for row_id, year, show, society_name in dup_vs_shows:
            print(f"  id={row_id}  {year}  {show!r}  {society_name}")

    if args.fix:
        all_ids = {r[0] for r in dup_vs_historical} | {r[0] for r in dup_vs_shows}
        conn.executemany("DELETE FROM historical_results WHERE id = ?", [(i,) for i in all_ids])
        conn.commit()
        print(f"\nDeleted {len(all_ids)} redundant row(s).")
    else:
        print("\nRun again with --fix to delete these redundant rows.")

    conn.close()


if __name__ == "__main__":
    main()
