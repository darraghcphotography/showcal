"""Extract reviews from ShowTimes PDF issues (E:\\showtimes archive) into a
JSON file - see ROADMAP.md's "Step 4" sections for the full design
background. Deliberately does NOT touch any database: this needs PyMuPDF
(not a tracked dependency - production never needs to read a PDF) and the
PDF archive itself, neither of which exist inside the Docker container, so
extraction always runs locally. Load the resulting JSON into a database
(local dev or production) with load_historical_reviews.py instead.

Parsing approach: PDF text is pulled as positioned lines (not raw reading-
order text) grouped into blocks - photo captions and page furniture
(masthead, page numbers, the Calendar listings section) are dropped by block
geometry (a short block is furniture unless it exactly matches a known
adjudicator name for that issue, in which case it's the review's sign-off).
That sign-off line is what actually splits the page into individual reviews,
and identifies each review's tier (AIMS assigns one adjudicator per tier per
season).

Within a review's body, each printed line is joined to the next with a
space (not the PDF's own line-wrap newline) to read as flowing prose -
except where a line's width falls well short of its column's normal width,
which is how justified text marks the end of a paragraph in print (the
final line of a paragraph is never stretched to fill the column). That gap
is turned back into a real paragraph break.

Usage:
    py extract_historical_reviews.py [--out historical_reviews_pilot.json]
"""
import argparse
import json
import re
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
# A line narrower than this fraction of its block's widest (fully justified)
# line is treated as the ragged final line of a paragraph, not mid-wrap -
# calibrated against real pages: a genuine paragraph-end line lands well
# under this (e.g. a 25-170pt line in a 170pt-wide column, ratio ~0.15), a
# normal justified line lands at ~0.95-1.0, with enough of a gap between the
# two that this doesn't need to be exact.
PARAGRAPH_BREAK_WIDTH_RATIO = 0.85


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


def page_body_lines(page, known_names, is_header_page):
    """Returns this page's kept content as a flat list of (text, width_ratio)
    tuples, in left-column-then-right-column reading order - width_ratio is
    this line's width divided by its block's widest line, used later to spot
    paragraph-ending lines."""
    width = page.rect.width
    calendar_y = find_calendar_boundary(page)
    kept_blocks = []  # each: (x0, y0, [(line_x0, line_y0, text, width), ...])
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        bx0, by0, bx1, by1 = block["bbox"]
        block_lines = []
        for line in block["lines"]:
            lx0, ly0, lx1, ly1 = line["bbox"]
            text = clean("".join(span["text"] for span in line["spans"]))
            if text:
                block_lines.append((lx0, ly0, text, lx1 - lx0))
        if not block_lines:
            continue

        block_text = clean(" ".join(t for _, _, t, _ in block_lines))
        if calendar_y is not None and by0 >= calendar_y:
            continue
        if is_header_page and by1 < 120:
            continue
        if re.fullmatch(r"\d+", block_text):
            continue
        if block_text == "ShowTimes":
            continue
        height = by1 - by0
        is_short = height < SHORT_BLOCK_MAX_HEIGHT or len(block_lines) <= SHORT_BLOCK_MAX_LINES
        if is_short and block_text not in known_names:
            continue
        kept_blocks.append((bx0, by0, block_lines))

    mid = width / 2
    kept_blocks.sort(key=lambda b: (b[0] >= mid, b[1]))

    out = []
    for _, _, block_lines in kept_blocks:
        max_width = max(w for *_, w in block_lines) or 1
        for _, _, text, w in block_lines:
            out.append((text, w / max_width))
    return out


def parse_heading(segment):
    """segment is a list of (text, width_ratio) tuples - everything after the
    previous review's sign-off (or the start of the section, for the first
    review). Returns (society_raw, show_raw, review_text) or None if no
    title-shaped line turns up in the first few lines."""
    lines = [(t.strip(), r) for t, r in segment if t.strip()]
    idx = 0
    society_lines = []
    while idx < len(lines) and not TITLE_LINE_RE.match(lines[idx][0]):
        society_lines.append(lines[idx][0])
        idx += 1
        if idx > MAX_SOCIETY_LINES:
            return None
    if idx >= len(lines):
        return None
    title_lines = [lines[idx][0]]
    idx += 1
    while idx < len(lines) and TITLE_LINE_RE.match(lines[idx][0]):
        title_lines.append(lines[idx][0])
        idx += 1
    society_raw = ", ".join(l.rstrip(",") for l in society_lines)
    show_raw = " ".join(title_lines).rstrip(" .")
    review_text = join_paragraphs(lines[idx:])
    return society_raw, show_raw, review_text


TERMINAL_PUNCTUATION_RE = re.compile(r"[.!?][\"'’”)]*$")


def join_paragraphs(lines):
    """Turns a list of (text, width_ratio) printed lines back into flowing
    prose: consecutive lines join with a space (mid-paragraph line-wrap),
    except a line that's both noticeably narrower than its column's full
    width AND ends a complete sentence, which starts a new paragraph
    instead. Width alone isn't enough - a block can have a run of narrower
    lines for reasons that have nothing to do with a paragraph ending (an
    inline image squeezing the column for a few lines produced a run of
    single-word 'paragraphs' in testing, none of them ending mid-sentence);
    requiring real sentence-terminal punctuation too rules those out, since
    a genuine paragraph break can only happen where a sentence actually
    finished."""
    paragraphs = []
    current = []
    for text, ratio in lines:
        current.append(text)
        if ratio < PARAGRAPH_BREAK_WIDTH_RATIO and TERMINAL_PUNCTUATION_RE.search(text):
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(p.strip() for p in paragraphs if p.strip())


def split_reviews(body_lines, tier_by_name, source_issue):
    """body_lines is the whole review section's (text, width_ratio) lines,
    in reading order. Splits on whichever line's text exactly equals one of
    this issue's two adjudicator names - that's each review's sign-off."""
    split_points = [i for i, (text, _) in enumerate(body_lines) if text in tier_by_name]
    reviews = []
    prev_end = 0
    for split_i in split_points:
        adjudicator = body_lines[split_i][0]
        segment = body_lines[prev_end:split_i]
        prev_end = split_i + 1
        parsed = parse_heading(segment)
        if parsed is None:
            preview = " ".join(t for t, _ in segment[:6])
            print(f"  !! no heading found before sign-off '{adjudicator}' - "
                  f"segment starts: {preview[:80]!r}", file=sys.stderr)
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

    all_lines = []
    for i in range(start, doc.page_count):
        page = doc[i]
        all_lines.extend(page_body_lines(page, set(tier_by_name), i == start))
        if find_calendar_boundary(page) is not None:
            break

    reviews = split_reviews(all_lines, tier_by_name, source_issue)
    for r in reviews:
        r["season"] = season
    return reviews


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "historical_reviews_pilot.json"))
    args = parser.parse_args()

    all_reviews = []
    for filename, source_issue in ISSUES:
        all_reviews.extend(extract_issue(filename, source_issue))
    print(f"\n{len(all_reviews)} reviews extracted from {len(ISSUES)} issue(s)")

    Path(args.out).write_text(json.dumps(all_reviews, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.out} - load it into a database with load_historical_reviews.py.")


if __name__ == "__main__":
    main()
