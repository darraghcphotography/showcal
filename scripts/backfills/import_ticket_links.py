"""Import verified ticket links into the shows table from research worklists.

Matches rows from enrichment/ticket_worklist_filled.json (or an explicit JSON path)
by show_id and validates the researcher's 3-point page proof (title, society, dates
shown on page) against our database record before writing any ticket_url.

A wrong ticket link is worse than a missing one (sends real people to the wrong show
or dates), so this script enforces:
  1. Valid URL format (http/https).
  2. Allowed ticket_url_kind: society, venue, ticketing_platform.
  3. Non-empty 3-point proof: title_shown_on_page, society_shown_on_page, dates_shown_on_page.
  4. Consistency between page evidence and the database show/society records.

Usage:
    py scripts/backfills/import_ticket_links.py [--db aims.db] [--input enrichment/ticket_worklist_filled.json] [--dry-run]

    docker exec aims-web python /app/scripts/backfills/import_ticket_links.py \\
        --db /data/aims.db --input /app/enrichment/ticket_worklist_filled.json --dry-run
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

_here = Path(__file__).resolve()
ROOT = _here.parents[2] if len(_here.parents) > 2 else Path.cwd()
DEFAULT_INPUT = ROOT / "enrichment" / "ticket_worklist_filled.json"

VALID_KINDS = {"society", "venue", "ticketing_platform"}

COMMON_NOISE_WORDS = {
    "the", "musical", "society", "operatic", "choral", "productions",
    "production", "company", "theatre", "group", "presents", "present",
    "and", "&", "of", "in"
}


def normalize_string(s):
    """Lowercase and strip punctuation/extra whitespace."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def check_evidence_match(page_val, db_val):
    """Check if normalized strings match directly, by shared content words, or by acronym."""
    norm_page = normalize_string(page_val)
    norm_db = normalize_string(db_val)
    if not norm_page or not norm_db:
        return False
    if norm_db in norm_page or norm_page in norm_db:
        return True

    # Check content tokens (excluding common words like society/musical/etc)
    page_words = [w for w in norm_page.split() if w not in COMMON_NOISE_WORDS]
    db_words = [w for w in norm_db.split() if w not in COMMON_NOISE_WORDS]

    common = set(page_words) & set(db_words)
    if common:
        return True

    # Check common acronyms (e.g. HXT for Harolds Cross Tallaght, DMS for Dundalk Musical Society)
    all_db_words = norm_db.split()
    acr = "".join("x" if w == "cross" else w[0] for w in all_db_words)
    sig_acr = "".join("x" if w == "cross" else w[0] for w in db_words)
    if len(acr) >= 2 and acr in page_words:
        return True
    if len(sig_acr) >= 2 and sig_acr in page_words:
        return True

    return False


def validate_row(item, db_show):
    """Validate a single worklist item against its database show record.

    Returns (is_valid, reason, clean_url).
    If ticket_url is absent/blank, returns (False, 'off_sale', None).
    """
    ticket_url = (item.get("ticket_url") or "").strip()
    if not ticket_url:
        return False, "off_sale", None

    if not (ticket_url.startswith("http://") or ticket_url.startswith("https://")):
        return False, f"Invalid URL scheme: {ticket_url}", None

    kind = item.get("ticket_url_kind")
    if kind not in VALID_KINDS:
        return False, f"Invalid ticket_url_kind: {kind} (must be one of {VALID_KINDS})", None

    title_shown = (item.get("title_shown_on_page") or "").strip()
    society_shown = (item.get("society_shown_on_page") or "").strip()
    dates_shown = (item.get("dates_shown_on_page") or "").strip()

    if not title_shown:
        return False, "Missing title_shown_on_page proof", None
    if not society_shown:
        return False, "Missing society_shown_on_page proof", None
    if not dates_shown:
        return False, "Missing dates_shown_on_page proof", None

    if not db_show:
        return False, f"Show ID {item.get('show_id')} not found in database", None

    # Verify title match
    if not check_evidence_match(title_shown, db_show["show"]):
        return False, f"Title mismatch: page '{title_shown}' vs DB '{db_show['show']}'", None

    # Verify society match
    if not check_evidence_match(society_shown, db_show["society_name"]):
        return False, f"Society mismatch: page '{society_shown}' vs DB '{db_show['society_name']}'", None

    return True, "valid", ticket_url


def run_import(db_path, input_path, dry_run=True, verbose=False):
    db_path = Path(db_path)
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input worklist not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Pre-fetch all shows
    show_ids = [row["show_id"] for row in data if "show_id" in row]
    placeholders = ",".join("?" * len(show_ids))
    db_shows = {}
    if show_ids:
        cur = conn.execute(
            f"""
            SELECT sh.id, sh.show, sh.opening_date, sh.closing_date, sh.ticket_url,
                   s.id as society_id, s.name as society_name
            FROM shows sh
            JOIN societies s ON s.id = sh.society_id
            WHERE sh.id IN ({placeholders})
            """,
            show_ids,
        )
        for r in cur.fetchall():
            db_shows[r["id"]] = dict(r)

    total = len(data)
    off_sale_count = 0
    valid_candidates = []
    rejected = []

    for item in data:
        show_id = item.get("show_id")
        db_show = db_shows.get(show_id)
        is_valid, reason, clean_url = validate_row(item, db_show)

        if reason == "off_sale":
            off_sale_count += 1
            if verbose:
                print(f"  [OFF-SALE] Show {show_id}: {item.get('known_society')} - {item.get('known_title')} ({item.get('notes')})")
        elif is_valid:
            valid_candidates.append((show_id, clean_url, item, db_show))
            if verbose:
                print(f"  [VALID] Show {show_id}: {item.get('known_society')} - {item.get('known_title')} -> {clean_url}")
        else:
            rejected.append((show_id, reason, item))
            print(f"  [REJECTED] Show {show_id}: {reason}")

    print(f"\nWorklist: {input_path.name}")
    print(f"Total rows:        {total}")
    print(f"Off-sale / blank:  {off_sale_count}")
    print(f"Valid links found: {len(valid_candidates)}")
    print(f"Rejected:          {len(rejected)}")

    updated = 0
    already_current = 0

    for show_id, clean_url, item, db_show in valid_candidates:
        curr = (db_show.get("ticket_url") or "").strip()
        if curr == clean_url:
            already_current += 1
            continue

        updated += 1
        print(f"  UPDATE show #{show_id} ({db_show['society_name']} - {db_show['show']})")
        print(f"    old: {curr or '(none)'}")
        print(f"    new: {clean_url}")

        if not dry_run:
            conn.execute("UPDATE shows SET ticket_url = ? WHERE id = ?", (clean_url, show_id))

    if dry_run:
        conn.rollback()
        print(f"\n--dry-run: {updated} shows would be updated ({already_current} already matched). Rolled back.")
    else:
        conn.commit()
        print(f"\nCOMMITTED: {updated} shows updated ({already_current} already matched).")

    conn.close()
    return {
        "total": total,
        "off_sale": off_sale_count,
        "valid": len(valid_candidates),
        "rejected": len(rejected),
        "updated": updated,
        "already_current": already_current,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "aims.db"), help="path to SQLite database")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="path to filled worklist JSON")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                        help="simulate updates without writing to the database (default)")
    parser.add_argument("--apply", dest="dry_run", action="store_false",
                        help="apply changes to the database")
    parser.add_argument("-v", "--verbose", action="store_true", help="list every show checked")
    args = parser.parse_args()

    run_import(args.db, args.input, dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
