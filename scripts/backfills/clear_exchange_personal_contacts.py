"""Clears personal contact details out of existing Costumes & Props Exchange listings.

Found in the 2026-09-01 audit: `/exchange/<id>` published `contact_name` and
`contact_phone` - a named volunteer and a personal mobile, the latter as a
clickable `tel:` link - on a fully public, crawlable page, and the listing form
actively invited both ("e.g. Mary Kelly (Wardrobe Head)", "e.g. 087 123 4567")
without saying anywhere that they would be published.

The code no longer collects or renders either field. This handles the rows that
were created before that change: the app cannot un-publish what is already in
the database, and "we stopped collecting it" is not the same as "it is gone".

Only `contact_name` and `contact_phone` are cleared. `contact_email` is kept -
it is the society's own shared address, it is now shown only to a signed-in
society, and it is the one field that makes a listing usable at all.

The columns themselves are deliberately left in place rather than dropped:
SQLite would need a full table rebuild, and the value of doing that is small
next to the risk of rebuilding a table that holds societies' own uploads. They
are documented as unused in schema.sql, no code writes them, and `vault_edit`
now sets both to NULL on every save, so they cannot come back.

Usage:
    py scripts/backfills/clear_exchange_personal_contacts.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python \\
        scripts/backfills/clear_exchange_personal_contacts.py --db /data/aims.db
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    affected = db.execute(
        """
        SELECT wi.id, wi.title, s.name AS society,
               wi.contact_name, wi.contact_phone
          FROM wardrobe_items wi
          JOIN societies s ON s.id = wi.society_id
         WHERE (wi.contact_name IS NOT NULL AND wi.contact_name != '')
            OR (wi.contact_phone IS NOT NULL AND wi.contact_phone != '')
         ORDER BY wi.id
        """
    ).fetchall()

    for r in affected:
        # Printed so there is a record of what was removed, and from whom - if a
        # society asks why their coordinator vanished off a listing, the answer
        # should be in the handback log rather than reconstructed.
        print(f"  #{r['id']} {r['society']} - {r['title']}")
        if r["contact_name"]:
            print(f"      name  removed: {r['contact_name']}")
        if r["contact_phone"]:
            print(f"      phone removed: {r['contact_phone']}")

    db.execute("UPDATE wardrobe_items SET contact_name = NULL, contact_phone = NULL")
    print(f"\n{len(affected)} listing(s) cleared of personal contact details.")

    remaining = db.execute(
        "SELECT COUNT(*) FROM wardrobe_items "
        "WHERE contact_name IS NOT NULL OR contact_phone IS NOT NULL"
    ).fetchone()[0]
    print(f"{remaining} listing(s) still holding either field (should be 0).")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nWritten.")
    db.close()


if __name__ == "__main__":
    main()
