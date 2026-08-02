"""Back up aims.db to a timestamped copy, pruning old backups.

Uses SQLite's own online backup API (not a raw file copy) - a plain copy of
a live database file can capture a torn, inconsistent snapshot if something
is mid-write at that exact moment; sqlite3's backup() always produces a
consistent copy regardless.

Usage:
    py backup_db.py [--db aims.db] [--backup-dir backups] [--keep 14]

Schedule this via the QNAP's own Task Scheduler (Control Panel -> System ->
Task Scheduler -> a nightly cron-style job), running e.g.:
    docker exec aims-web python backup_db.py --db /data/aims.db --backup-dir /data/backups
Or, simpler and just as valid: point QNAP's own snapshot/backup app (HBS3 or
similar) directly at the data/ folder on the NAS instead of running this at
all - either approach works, this script is just the option that needs no
extra NAS configuration beyond a scheduled task.
"""
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--backup-dir", default=str(ROOT / "backups"))
    parser.add_argument("--keep", type=int, default=14, help="How many recent backups to retain (default 14)")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"aims-{timestamp}.db"

    source_conn = sqlite3.connect(args.db)
    dest_conn = sqlite3.connect(dest)
    with dest_conn:
        source_conn.backup(dest_conn)
    source_conn.close()
    dest_conn.close()
    print(f"Backed up {args.db} -> {dest}")

    backups = sorted(backup_dir.glob("aims-*.db"))
    stale = backups[: -args.keep] if args.keep > 0 else []
    for old in stale:
        old.unlink()
        print(f"Removed old backup {old}")


if __name__ == "__main__":
    main()
