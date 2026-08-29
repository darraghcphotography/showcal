"""One-off resize+re-encode of every poster uploaded before app/uploads.py
started doing this at upload time - see save_poster's docstring and the
2026-08-24 evening run-through that measured the problem: posters serving at
original upload size (one alone 1.36MB) rendered at most 240 CSS px wide
anywhere on the site.

Rewrites shows.poster_filename to the new .webp filename and deletes the old
file, one show at a time - a show missing from disk or already .webp (a
re-run, or a poster uploaded after this shipped) is skipped, not an error.

Usage:
    py backfill_poster_thumbnails.py [--db aims.db] [--upload-dir uploads] [--dry-run]

    docker compose exec aims-web python backfill_poster_thumbnails.py --db /data/aims.db --upload-dir /data/uploads
"""
import argparse
import os
import sqlite3
import sys
import uuid
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.uploads import _resized_webp_bytes  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--upload-dir", default=str(ROOT / "uploads"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT id, poster_filename FROM shows WHERE poster_filename IS NOT NULL AND poster_filename != ''"
    ).fetchall()

    converted, skipped, missing, failed = 0, 0, [], []
    before_total = after_total = 0

    for row in rows:
        old_filename = row["poster_filename"]
        old_path = os.path.join(args.upload_dir, old_filename)
        if old_filename.endswith(".webp"):
            skipped += 1
            continue
        if not os.path.exists(old_path):
            missing.append(old_filename)
            continue

        ext = old_filename.rsplit(".", 1)[1].lower()
        before_size = os.path.getsize(old_path)
        try:
            with open(old_path, "rb") as f:
                data, out_ext = _resized_webp_bytes(f, ext)
        except Exception as e:
            failed.append((old_filename, str(e)))
            continue

        new_filename = f"{uuid.uuid4().hex}.{out_ext}"
        after_size = len(data)
        before_total += before_size
        after_total += after_size
        converted += 1
        print(f"  show {row['id']}: {old_filename} ({before_size // 1024}KB) -> "
              f"{new_filename} ({after_size // 1024}KB)")

        if args.dry_run:
            continue
        new_path = os.path.join(args.upload_dir, new_filename)
        with open(new_path, "wb") as f:
            f.write(data)
        db.execute("UPDATE shows SET poster_filename = ? WHERE id = ?", (new_filename, row["id"]))
        os.remove(old_path)

    print(f"\nConverted {converted}, already WebP {skipped}, missing from disk {len(missing)}, "
          f"failed to read {len(failed)}")
    if before_total:
        print(f"{before_total // 1024}KB -> {after_total // 1024}KB "
              f"({100 * (1 - after_total / before_total):.0f}% smaller)")
    if missing:
        print("\nMissing from disk (db points at a file that isn't there):")
        for f in missing:
            print(f"  {f}")
    if failed:
        print("\nFailed to read (corrupt file, check by hand):")
        for f, err in failed:
            print(f"  {f}: {err}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: nothing written to disk or the database")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
