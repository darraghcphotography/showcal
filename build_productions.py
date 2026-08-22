"""Command-line half of the productions rebuild - see app/productions_build.py
for the actual logic and schema.sql for why the table exists.

The app rebuilds the table itself (on every startup, and lazily whenever the
source data has moved since), so this is for the cases where that isn't
enough: checking what a rebuild *would* do before letting it near production
(--dry-run), or forcing one after a bulk import script has rewritten rows
outside the app.

Usage:
    py build_productions.py [--db aims.db] [--dry-run] [--quiet]

    docker compose exec aims-web python build_productions.py --db /data/aims.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.productions_build import VerificationError, build  # noqa: E402

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="build and verify, then roll back without writing")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        build(db, report=None if args.quiet else print)
    except VerificationError as exc:
        db.rollback()
        print(exc, file=sys.stderr)
        return 1
    if args.dry_run:
        db.rollback()
        if not args.quiet:
            print("--dry-run: rolled back, nothing written.")
    else:
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
