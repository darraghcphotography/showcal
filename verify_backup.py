"""Prove a backup would actually come back, rather than assuming it.

A backup nobody has ever restored is a hope, not a backup. This restores one to
a scratch copy and puts it through everything short of serving traffic:

  1. It opens, and SQLite's own integrity_check passes.
  2. No foreign key violations.
  3. Every table the live database has exists in the backup, with a row count.
     Drift against live is reported, not failed - the live database has moved on
     since the backup was taken, and that's the normal case.
  4. The app's own derived tables rebuild from it cleanly. This is the part a
     plain integrity_check can't tell you: productions_build and venues_build
     both end in a verification pass that re-derives their totals from the
     database and raises rather than committing on disagreement. If those pass
     against a restored copy, the app can genuinely run on it.

Exits non-zero if any check fails, so it can be scheduled and shout.

Usage:
    py verify_backup.py [--backup-dir backups] [--db aims.db]
    py verify_backup.py --backup backups/aims-20260824-000000.db

    docker exec aims-web python verify_backup.py \\
        --backup-dir /data/backups --db /data/aims.db
"""
import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import productions_build, venues_build  # noqa: E402

ROOT = Path(__file__).parent


def newest_backup(backup_dir):
    backups = sorted(Path(backup_dir).glob("aims-*.db"))
    return backups[-1] if backups else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backup-dir", default=str(ROOT / "backups"))
    parser.add_argument("--backup", help="A specific backup file (default: the newest)")
    parser.add_argument("--db", default=str(ROOT / "aims.db"),
                        help="The live database, for a row-count comparison")
    args = parser.parse_args()

    backup = Path(args.backup) if args.backup else newest_backup(args.backup_dir)
    if backup is None or not backup.exists():
        print(f"FAIL: no backup found in {args.backup_dir}")
        return 1
    print(f"Verifying {backup} ({backup.stat().st_size / 1_048_576:.1f} MB)")

    failures = []

    # Work on a copy throughout. The rebuild in step 4 writes, and a backup that
    # a verification run has modified is no longer the thing that was backed up.
    with tempfile.TemporaryDirectory() as tmp:
        restored = Path(tmp) / "restored.db"
        shutil.copy2(backup, restored)

        db = sqlite3.connect(restored)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")

        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        print(f"  integrity_check: {integrity}")
        if integrity != "ok":
            failures.append("integrity_check did not return ok")

        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        print(f"  foreign key violations: {len(violations)}")
        if violations:
            failures.append(f"{len(violations)} foreign key violations")

        # Compare against live, if it's there. Counts drifting is expected;
        # a table missing entirely is not.
        live_path = Path(args.db)
        if live_path.exists():
            live = sqlite3.connect(f"file:{live_path}?mode=ro", uri=True)
            tables = [
                r[0] for r in live.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%' ORDER BY name"
                )
            ]
            drift = []
            for table in tables:
                try:
                    backed_up = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.Error:
                    failures.append(f"table {table} is missing from the backup")
                    continue
                current = live.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if backed_up != current:
                    drift.append(f"{table} {backed_up} vs {current}")
            live.close()
            print(f"  tables present: {len(tables)}")
            if drift:
                print(f"  rows changed since the backup ({len(drift)}): {', '.join(drift)}")
            else:
                print("  row counts identical to live")
        else:
            print(f"  (no live database at {live_path}, skipping the comparison)")

        # The real test: can the app rebuild what it derives, from this data?
        for name, module in (("productions", productions_build), ("venues", venues_build)):
            try:
                module.build(db)
                db.commit()
                print(f"  {name} rebuild: verification passed")
            except Exception as exc:  # the build's own verification raises
                print(f"  {name} rebuild: FAILED - {exc}")
                failures.append(f"{name} rebuild failed on the restored copy")

        db.close()

    if failures:
        print()
        print(f"FAILED ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print()
    print("OK - this backup restores cleanly and the app can run on it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
