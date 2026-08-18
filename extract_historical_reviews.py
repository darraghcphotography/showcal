"""Extract reviews from ShowTimes PDF issues (E:\\showtimes archive) and load
them into historical_reviews as pending moderation-queue entries - see
ROADMAP.md's "Step 4" sections for the full design background.

Parsing approach: PDF text is pulled as positioned blocks, not raw reading-
order text - photo captions and page furniture (masthead, page numbers, the
Calendar listings section) are dropped by block geometry (short blocks are
furniture unless they exactly match a known adjudicator name for that issue,
in which case they're the review's sign-off). That sign-off line is what
actually splits the page text into individual reviews, and identifies each
review's tier (AIMS assigns one adjudicator per tier per season).

Nothing here writes to shows/societies - every row lands in historical_reviews
with moderation_status='pending' and is matched against the *existing*
shows/societies data only to pre-fill a confident (exact-match) society_id/
show_id, or set a flag for the moderator otherwise. See admin.py's
/admin/historical-reviews queue for what happens after that.

Usage:
    py extract_historical_reviews.py [--db aims.db]
"""
import argparse
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

import fitz

ARCHIVE_DIR = Path("E:/showtimes archive")
ROOT = Path(__file__).parent

# Each round of this script adds more issues here as they're processed -
# started with the 2022-2023 pilot season (Round "Step 4 pilot").
ISSUES = [
    ("Show Times November '22 Web.pdf", "Issue 160, December 2022"),
    ("Show Times February '23 WEB .pdf", "Issue 161, February 2023"),
    ("Show Times April '23 Web.pdf", "Issue 163, April 2023"),
    ("Show Times Autumn '23 Web.pdf", "Issue 166, Autumn 2023"),
]

SHORT_BLOCK_MAX_HEIGHT = 30
SHORT_BLOCK_MAX_LINES = 2
TITLE_LINE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 '&!,.\-]{1,60}$")
MAX_SOCIETY_LINES = 4


def clean(s):
    s = "".join(c for c in s if unicodedata.category(c) not in ("Cf", "Co"))
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    return s.strip()


def season_from_header_year(year_range):
    a, b = re.findall(r"\d{4}", year_range)
    return f"{a[2:]}/{b[2:]}"


def find_review_section_start(doc):
    for i, page in enumerate(doc):
        if "ShowReviews" in page.get_text():
            return i
    return None


def parse_header(doc, start_page):
    blocks = doc[start_page].get_text("blocks")
    header_text = "\n".join(clean(b[4]) for b in blocks if b[3] < 120)
    year_match = re.search(r"\d{4}\s*-\s*\d{4}", header_text)
    season = season_from_header_year(year_match.group(0)) if year_match else None

    lines = [l.strip() for l in header_text.splitlines() if l.strip()]
    tier_by_name = {}
    pending_names = []
    for line in lines:
        m = re.match(r"^(Gilbert|Sullivan) Section$", line)
        if m:
            if pending_names:
                tier_by_name[pending_names.pop(0)] = m.group(1)
        elif line not in ("ShowTimes", "ShowReviews") and not re.match(r"^\d{4}\s*-\s*\d{4}$", line):
            pending_names.append(line)
    return season, tier_by_name


def find_calendar_boundary(page):
    for b in page.get_text("blocks"):
        if clean(b[4]) == "Calendar":
            return b[1]
    return None


def page_body_blocks(page, known_names, is_header_page):
    width = page.rect.width
    calendar_y = find_calendar_boundary(page)
    kept = []
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text, *_ = b
        text = clean(text)
        if not text:
            continue
        if calendar_y is not None and y0 >= calendar_y:
            continue
        if is_header_page and y1 < 120:
            continue
        if re.fullmatch(r"\d+", text):
            continue
        if text == "ShowTimes":
            continue
        height = y1 - y0
        nlines = text.count("\n") + 1
        is_short = height < SHORT_BLOCK_MAX_HEIGHT or nlines <= SHORT_BLOCK_MAX_LINES
        if is_short and text not in known_names:
            continue
        kept.append((x0, y0, text))
    mid = width / 2
    kept.sort(key=lambda t: (t[0] >= mid, t[1]))
    return [t[2] for t in kept]


def parse_heading(segment):
    lines = [l.strip() for l in segment.strip("\n").split("\n") if l.strip()]
    idx = 0
    society_lines = []
    while idx < len(lines) and not TITLE_LINE_RE.match(lines[idx]):
        society_lines.append(lines[idx])
        idx += 1
        if idx > MAX_SOCIETY_LINES:
            return None
    if idx >= len(lines):
        return None
    title_lines = [lines[idx]]
    idx += 1
    while idx < len(lines) and TITLE_LINE_RE.match(lines[idx]):
        title_lines.append(lines[idx])
        idx += 1
    society_raw = ", ".join(l.rstrip(",") for l in society_lines)
    show_raw = " ".join(title_lines).rstrip(" .")
    review_text = "\n".join(lines[idx:]).strip()
    return society_raw, show_raw, review_text


def split_reviews(body_text, tier_by_name, source_issue):
    names_pattern = "|".join(re.escape(n) for n in tier_by_name)
    parts = re.split(rf"\n({names_pattern})(?:\n|$)", body_text)
    reviews = []
    for i in range(1, len(parts) - 1, 2):
        adjudicator = parts[i]
        parsed = parse_heading(parts[i - 1])
        if parsed is None:
            print(f"  !! no heading found before sign-off '{adjudicator}' - "
                  f"segment starts: {parts[i - 1][:80]!r}", file=sys.stderr)
            continue
        society_raw, show_raw, review_text = parsed
        reviews.append({
            "society_raw": society_raw,
            "show_raw": show_raw.title() if show_raw.isupper() else show_raw,
            "adjudicator": adjudicator,
            "tier": tier_by_name[adjudicator],
            "review_text": review_text,
            "source_issue": source_issue,
        })
    return reviews


def extract_issue(filename, source_issue):
    path = ARCHIVE_DIR / filename
    doc = fitz.open(path)
    start = find_review_section_start(doc)
    if start is None:
        print(f"!! no ShowReviews header found in {filename}", file=sys.stderr)
        return []
    season, tier_by_name = parse_header(doc, start)
    print(f"{filename}: season={season} adjudicators={tier_by_name}")

    body_pages = []
    for i in range(start, doc.page_count):
        page = doc[i]
        body_pages.append("\n".join(page_body_blocks(page, set(tier_by_name), i == start)))
        if find_calendar_boundary(page) is not None:
            break

    reviews = split_reviews("\n".join(body_pages), tier_by_name, source_issue)
    for r in reviews:
        r["season"] = season
    return reviews


def get_or_create_adjudicator(db, name):
    row = db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    return db.execute("INSERT INTO adjudicators (name) VALUES (?)", (name,)).lastrowid


def match_society(db, society_raw):
    """Exact match only (see docs/data-model.md's title-matching convention -
    this project deliberately never fuzzy-matches). Tries the raw name as
    printed, then the part before a comma (many issues append a location,
    e.g. 'Bravo Theatre Group, Loughrea', that isn't part of the society's
    actual name on record)."""
    for candidate in (society_raw, society_raw.split(",")[0].strip()):
        row = db.execute("SELECT id FROM societies WHERE name = ?", (candidate,)).fetchone()
        if row:
            return row[0]
    return None


def match_show(db, society_id, season, show_raw):
    row = db.execute(
        "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ? AND moderation_status = 'approved'",
        (society_id, season, show_raw),
    ).fetchone()
    return row[0] if row else None


def load_reviews(db, reviews):
    inserted = skipped = 0
    for r in reviews:
        exists = db.execute(
            "SELECT 1 FROM historical_reviews WHERE source_issue = ? AND society_raw = ? AND show_raw = ?",
            (r["source_issue"], r["society_raw"], r["show_raw"]),
        ).fetchone()
        if exists:
            skipped += 1
            continue

        adjudicator_id = get_or_create_adjudicator(db, r["adjudicator"])
        society_id = match_society(db, r["society_raw"])
        show_id = None
        flag = "needs_check"
        if society_id is not None:
            show_id = match_show(db, society_id, r["season"], r["show_raw"])
            flag = None if show_id is not None else "no_show_match"

        db.execute(
            """
            INSERT INTO historical_reviews
                (season, tier, show_raw, society_raw, adjudicator_id, review_text,
                 source_issue, show_id, society_id, flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (r["season"], r["tier"], r["show_raw"], r["society_raw"], adjudicator_id, r["review_text"],
             r["source_issue"], show_id, society_id, flag),
        )
        inserted += 1
    db.commit()
    return inserted, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    args = parser.parse_args()

    all_reviews = []
    for filename, source_issue in ISSUES:
        all_reviews.extend(extract_issue(filename, source_issue))
    print(f"\n{len(all_reviews)} reviews extracted from {len(ISSUES)} issue(s)")

    db = sqlite3.connect(args.db)
    inserted, skipped = load_reviews(db, all_reviews)
    matched = db.execute(
        "SELECT COUNT(*) FROM historical_reviews WHERE flag IS NULL AND created_at >= datetime('now', '-1 minute')"
    ).fetchone()[0]
    print(f"Inserted {inserted}, skipped {skipped} already-loaded. {matched} of this run's inserts matched cleanly.")


if __name__ == "__main__":
    main()
