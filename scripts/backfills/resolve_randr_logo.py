"""Backfill logo for Rathmines & Rathgar Musical Society (society_id=93).

Copies the generated high-res logo into uploads/ and updates
societies.logo_filename while resolving the pending logo_candidates row.

Run with --dry-run first:
    py scripts/backfills/resolve_randr_logo.py --db aims.db --dry-run
"""
import argparse
import hashlib
import shutil
import sqlite3
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2] if "__file__" in globals() and Path(__file__).name != "<stdin>" else Path("/app")
SOURCE_IMAGE = ROOT / "uploads" / "320beb5936cd5bdfbdd4e0722bfe6cac.webp"


def apply_logo(db_path: Path, upload_dir: Path, dry_run: bool = True):
    print(f"Opening database: {db_path}")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    dest_filename = "320beb5936cd5bdfbdd4e0722bfe6cac.webp"
    # 1. Process and save WebP logo image
    if SOURCE_IMAGE.exists():
        data = SOURCE_IMAGE.read_bytes()
        file_hash = hashlib.md5(data).hexdigest()
        dest_filename = f"{file_hash}.webp"
        dest_path = upload_dir / dest_filename

        print(f"Converting {SOURCE_IMAGE.name} to {dest_filename} in {upload_dir}")
        if not dry_run:
            upload_dir.mkdir(parents=True, exist_ok=True)
            with Image.open(SOURCE_IMAGE) as img:
                img.save(dest_path, "WEBP", quality=85)
            print(f"Saved: {dest_path}")
    else:
        print(f"Using pre-uploaded logo {dest_filename} in {upload_dir}")

    # 2. Update societies table
    soc = con.execute("SELECT id, name, logo_filename FROM societies WHERE id = 93").fetchone()
    if soc:
        print(f"Society 93 ({soc['name']}): logo_filename = '{soc['logo_filename']}' -> '{dest_filename}'")
        if not dry_run:
            con.execute("UPDATE societies SET logo_filename = ? WHERE id = 93", (dest_filename,))

    # 3. Update logo_candidates table
    cand = con.execute("SELECT id, society_id, status FROM logo_candidates WHERE society_id = 93 AND status = 'pending'").fetchone()
    if cand:
        print(f"Logo candidate {cand['id']}: status = 'pending' -> 'approved'")
        if not dry_run:
            con.execute("UPDATE logo_candidates SET status = 'approved', moderated_by = 'admin', moderated_at = datetime('now') WHERE id = ?", (cand['id'],))

    if dry_run:
        print("\n[DRY RUN] No changes committed.")
        con.rollback()
    else:
        con.commit()
        print("\n[LIVE] Changes successfully committed.")
    con.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill Rathmines & Rathgar logo")
    parser.add_argument("--db", type=Path, default=ROOT / "aims.db", help="Path to database")
    parser.add_argument("--uploads", type=Path, default=ROOT / "uploads", help="Path to uploads directory")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without committing")
    args = parser.parse_args()

    apply_logo(args.db, args.uploads, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
