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
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--backup-dir", default=str(ROOT / "backups"))
    parser.add_argument("--keep", type=int, default=14,
                        help="Always retain at least this many of the most recent backups, "
                             "whatever day they fall on (default 14)")
    parser.add_argument("--keep-days", type=int, default=30,
                        help="Also retain the newest backup from each of the last N days "
                             "(default 30)")
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

    # Retention is deliberately two rules, not one.
    #
    # "Keep the newest N files" alone looks fine and isn't: this runs once on
    # container start as well as daily, so a day with several redeploys spends
    # several of those slots. Measured on the real NAS on 2026-08-24, 14 files
    # covered 3.5 days rather than 14 - ten of them were from that day alone.
    # A fault noticed a week later would already have aged out of every backup.
    #
    # So: keep the newest few whatever happens (roll back a bad script run from
    # an hour ago), AND the newest backup of each recent day (roll back
    # something nobody noticed until next week). Union of the two.
    backups = sorted(backup_dir.glob("aims-*.db"))
    keep = set(backups[-args.keep:]) if args.keep > 0 else set()

    cutoff = datetime.now() - timedelta(days=args.keep_days)
    newest_per_day = {}
    for path in backups:
        stamp = path.stem.removeprefix("aims-")
        try:
            when = datetime.strptime(stamp, "%Y%m%d-%H%M%S")
        except ValueError:
            # Not one of ours, or hand-renamed. Never delete what we can't date.
            keep.add(path)
            continue
        if when >= cutoff:
            newest_per_day[when.date()] = path
    keep.update(newest_per_day.values())

    for old in backups:
        if old in keep:
            continue
        old.unlink()
        print(f"Removed old backup {old}")

    kept = sorted(keep)
    if kept:
        span = f"{kept[0].stem.removeprefix('aims-')[:8]} to {kept[-1].stem.removeprefix('aims-')[:8]}"
        print(f"Retained {len(kept)} backups, spanning {span}")


if __name__ == "__main__":
    main()
