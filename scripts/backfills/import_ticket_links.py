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
import unicodedata
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


MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def normalize_string(s):
    """Lowercase, fold accents, strip punctuation and extra whitespace.

    Accent folding matters: without it "Miserábles" normalises to "miser bles"
    and a correct Les Misérables page fails to match its own title."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def _is_token_run(needle, haystack):
    """Is `needle` a run of whole consecutive tokens inside `haystack`?

    Whole tokens, not raw substring: "the wiz" is a substring of "the wizard of
    oz", so a plain `in` test matches The Wiz against The Wizard of Oz."""
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[i:i + len(needle)] == needle
               for i in range(len(haystack) - len(needle) + 1))


def check_evidence_match(page_val, db_val):
    """Does the name printed on the page refer to the same thing as our record?

    Three ways to agree, in order of how much they prove:

    1. One is a run of whole words inside the other - "Cecilian Musical Society"
       against "Cecilian Musical Society, Limerick".
    2. An acronym - venues routinely bill "HXT Musical Society" for Harolds
       Cross Tallaght Musical Society.
    3. At least *two* content words in common. Two, not one: a single shared
       word matches "Sligo Musical Society" against "Sligo Pantomime Society"
       and "Cork School of Music" against "Cork Musical Society". Two societies
       in one town is the normal case in this data, not an edge case.
    """
    page_tokens = normalize_string(page_val).split()
    db_tokens = normalize_string(db_val).split()
    if not page_tokens or not db_tokens:
        return False

    if _is_token_run(db_tokens, page_tokens) or _is_token_run(page_tokens, db_tokens):
        return True

    page_words = [w for w in page_tokens if w not in COMMON_NOISE_WORDS]
    db_words = [w for w in db_tokens if w not in COMMON_NOISE_WORDS]

    # Acronyms, e.g. HXT for Harolds Cross Tallaght ("cross" bills as X).
    acr = "".join("x" if w == "cross" else w[0] for w in db_tokens)
    sig_acr = "".join("x" if w == "cross" else w[0] for w in db_words)
    if len(acr) >= 2 and acr in page_words:
        return True
    if len(sig_acr) >= 2 and sig_acr in page_words:
        return True

    return len(set(page_words) & set(db_words)) >= 2


def page_date_parts(text):
    """Day numbers, month numbers and 4-digit years mentioned in free text.

    `dates_shown_on_page` is copied verbatim off a venue page, so it arrives in
    whatever shape that page used - "Tue 29 Sep - Sat 3 Oct 2026", "Nightly, 6th
    to 10th October", "18 November 2026 - 21 November 2026". Rather than parse
    that into a range, pull out the parts and check ours are among them."""
    if not text:
        return set(), set(), set()
    lowered = str(text).lower()
    # Drop clock times first, or "7:30pm" contributes a spurious day 30.
    lowered = re.sub(r"\d{1,2}[:.]\d{2}\s*(?:am|pm)?", " ", lowered)
    lowered = re.sub(r"\d{1,2}\s*(?:am|pm)\b", " ", lowered)

    years = {int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", lowered)}
    without_years = re.sub(r"\b(?:19\d{2}|20\d{2})\b", " ", lowered)
    days = {int(d) for d in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", without_years)
            if 1 <= int(d) <= 31}
    months = {num for name, num in MONTHS.items()
              if re.search(r"\b%s" % name, lowered)}
    return days, months, years


def check_dates_match(page_dates, opening_date, closing_date=None):
    """Do the dates printed on the page agree with the ones we hold?

    This is the leg that matters most and the one that was missing. Title and
    society can both look right for last year's revival of the same show by the
    same society; the dates are what pin the production. Returns (ok, reason)."""
    if not opening_date:
        # Nothing to check against - say so rather than pass by default.
        return False, "no opening_date on record to check the page dates against"

    try:
        year, month, day = (int(p) for p in str(opening_date)[:10].split("-"))
    except (ValueError, TypeError):
        return False, f"unparseable opening_date on record: {opening_date!r}"

    days, months, years = page_date_parts(page_dates)
    if not days and not months:
        return False, f"no recognisable date in page proof: {page_dates!r}"
    if month not in months:
        return False, (f"month mismatch: page {sorted(months)} vs record {opening_date}")
    if day not in days:
        return False, (f"day mismatch: page {sorted(days)} vs record {opening_date}")
    # A page that omits the year is common and is not a mismatch; a page that
    # states a different one is.
    if years and year not in years:
        return False, (f"year mismatch: page {sorted(years)} vs record {opening_date}")
    return True, "ok"


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

    # Verify society match. Deliberately the loosest of the three legs: a venue
    # page may abbreviate ("HXT Musical Society") or drop a town suffix, so this
    # tolerates more than the others and the date check below carries the weight.
    if not check_evidence_match(society_shown, db_show["society_name"]):
        return False, f"Society mismatch: page '{society_shown}' vs DB '{db_show['society_name']}'", None

    # Verify the dates actually agree. Without this the "3-point proof" is a
    # 2-point proof with a presence check bolted on: a page dated 1998 validated
    # against a 2026 show until 2026-09-07.
    dates_ok, dates_reason = check_dates_match(
        dates_shown, db_show.get("opening_date"), db_show.get("closing_date")
    )
    if not dates_ok:
        return False, f"Date mismatch: {dates_reason}", None

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
