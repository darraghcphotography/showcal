"""Backup retention has to survive a busy day.

The original rule was "keep the newest 14 files". That reads as a fortnight and
isn't: backup_db.py runs on container start as well as daily, so every redeploy
spends a slot. Measured on the real NAS on 2026-08-24, the 14 retained files
covered 3.5 days - ten of them were from that day alone. A fault noticed a week
later would already have aged out of every backup that existed.
"""
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def make_backup_files(backup_dir, stamps):
    for stamp in stamps:
        (backup_dir / f"aims-{stamp}.db").write_bytes(b"not a real database")


def prune(backup_dir, db_path, keep=None, keep_days=None):
    """Run the real script, so the test can't drift from what ships."""
    cmd = [sys.executable, str(ROOT / "backup_db.py"),
           "--db", str(db_path), "--backup-dir", str(backup_dir)]
    if keep is not None:
        cmd += ["--keep", str(keep)]
    if keep_days is not None:
        cmd += ["--keep-days", str(keep_days)]
    subprocess.run(cmd, check=True, capture_output=True)


def remaining(backup_dir):
    return sorted(p.stem.removeprefix("aims-") for p in backup_dir.glob("aims-*.db"))


def test_a_busy_day_no_longer_evicts_older_days(tmp_path):
    """The real failure: ten redeploys in one day used to push out every
    backup from the days before it."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    db = tmp_path / "aims.db"
    import sqlite3
    sqlite3.connect(db).execute("CREATE TABLE t (a)")

    today = datetime.now()
    stamps = []
    # One backup a day for the previous ten days...
    for days_ago in range(10, 0, -1):
        stamps.append((today - timedelta(days=days_ago)).strftime("%Y%m%d-090000"))
    # ...then ten redeploys today.
    for hour in range(10):
        stamps.append(today.strftime(f"%Y%m%d-{hour:02d}0000"))
    make_backup_files(backup_dir, stamps)

    prune(backup_dir, db, keep=14, keep_days=30)
    kept = remaining(backup_dir)

    days_kept = {s[:8] for s in kept}
    # Ten previous days + today + the new backup the run itself just took.
    assert len(days_kept) >= 11, f"only {len(days_kept)} days survived: {sorted(days_kept)}"
    for days_ago in range(10, 0, -1):
        day = (today - timedelta(days=days_ago)).strftime("%Y%m%d")
        assert day in days_kept, f"lost every backup from {day}"


def test_the_most_recent_few_are_always_kept_whatever_day(tmp_path):
    """The other direction: rolling back a script run from an hour ago needs
    the fine-grained recent copies, not just one per day."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    db = tmp_path / "aims.db"
    import sqlite3
    sqlite3.connect(db).execute("CREATE TABLE t (a)")

    today = datetime.now().strftime("%Y%m%d")
    make_backup_files(backup_dir, [f"{today}-{h:02d}0000" for h in range(6)])

    prune(backup_dir, db, keep=4, keep_days=30)
    kept = remaining(backup_dir)

    same_day = [s for s in kept if s.startswith(today)]
    assert len(same_day) >= 4, f"expected at least 4 recent copies, kept {same_day}"


def test_backups_beyond_the_window_are_removed(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    db = tmp_path / "aims.db"
    import sqlite3
    sqlite3.connect(db).execute("CREATE TABLE t (a)")

    ancient = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d-090000")
    make_backup_files(backup_dir, [ancient])

    prune(backup_dir, db, keep=1, keep_days=30)

    assert ancient not in remaining(backup_dir)


def test_a_file_we_cannot_date_is_never_deleted(tmp_path):
    """A hand-renamed copy somebody kept on purpose. Deleting what we can't
    date would be exactly the wrong instinct for a backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    db = tmp_path / "aims.db"
    import sqlite3
    sqlite3.connect(db).execute("CREATE TABLE t (a)")

    (backup_dir / "aims-before-the-big-import.db").write_bytes(b"keep me")

    prune(backup_dir, db, keep=1, keep_days=1)

    assert (backup_dir / "aims-before-the-big-import.db").exists()
