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
from difflib import SequenceMatcher
from pathlib import Path

import fitz

ARCHIVE_DIR = Path("E:/showtimes archive")
ROOT = Path(__file__).parent

MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "spring": 4, "summer": 7, "autumn": 10, "winter": 12,
}
MONTH_NAME_RE = "|".join(MONTH_NUMBERS)
# "December '15/January '16" (spans a year boundary) - checked first since it's
# a more specific shape than the plain "<Month> <Year>" pattern below.
DOUBLE_MONTH_DATE_RE = re.compile(
    rf"({MONTH_NAME_RE})\s*.(\d{{2}})/({MONTH_NAME_RE})\s*.(\d{{2}})", re.I
)
MONTH_YEAR_DATE_RE = re.compile(rf"({MONTH_NAME_RE})\s+(\d{{4}})", re.I)
SEASON_WORD_YEAR_DATE_RE = re.compile(rf"({MONTH_NAME_RE})\s*.?(\d{{2,4}})", re.I)
ISSUE_NUMBER_RE = re.compile(r"Issue\s*(\d+)")


def parse_cover(doc):
    """Every issue's front cover states its own real "Issue N" and a
    month/year (or "Spring/Summer/Autumn/Winter YYYY", or a two-month range
    spanning a year boundary) - far more reliable than anything in the
    ShowReviews section itself, which varies a lot more across 14 years of
    layout changes. Returns (issue_number, date_label, season) or
    (None, None, None) if the cover doesn't match any known shape."""
    text = clean(doc[0].get_text())
    issue_m = ISSUE_NUMBER_RE.search(text)
    if not issue_m:
        return None, None, None
    issue_number = issue_m.group(1)

    m = DOUBLE_MONTH_DATE_RE.search(text)
    if m:
        label, month, year = m.group(0), MONTH_NUMBERS[m.group(1).lower()], 2000 + int(m.group(2))
    else:
        m = MONTH_YEAR_DATE_RE.search(text)
        if m:
            label, month, year = m.group(0), MONTH_NUMBERS[m.group(1).lower()], int(m.group(2))
        else:
            m = SEASON_WORD_YEAR_DATE_RE.search(text)
            if not m:
                return issue_number, None, None
            label, month = m.group(0), MONTH_NUMBERS[m.group(1).lower()]
            year = int(m.group(2)) if len(m.group(2)) == 4 else 2000 + int(m.group(2))
    season = f"{(year - 1) % 100:02d}/{year % 100:02d}" if month < 8 else f"{year % 100:02d}/{(year + 1) % 100:02d}"
    return issue_number, label, season


def discover_issues():
    """Scans the whole archive directory rather than a hand-maintained list -
    every PDF's own front cover carries the metadata needed. A handful of
    issues exist twice under two different filenames (confirmed identical or
    near-identical by page count) - deduping on (issue_number, date_label)
    keeps exactly one copy of each, without wrongly treating AIMS's own
    occasional duplicate-printed issue-number (e.g. two real, different
    issues both say 'Issue 64') as the same thing, since those have
    different dates."""
    seen = set()
    issues = []
    skipped = []
    for path in sorted(ARCHIVE_DIR.glob("*.pdf")):
        doc = fitz.open(path)
        issue_number, label, season = parse_cover(doc)
        if not issue_number or not label:
            skipped.append(path.name)
            continue
        key = (issue_number, label)
        if key in seen:
            continue
        seen.add(key)
        issues.append((path.name, f"Issue {issue_number}, {label}", season))
    return issues, skipped

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
        m = re.match(r"^(Gilbert|Sullivan) Sections?$", line)
        if m:
            if pending_names:
                tier_by_name[pending_names.pop(0)] = m.group(1)
        # "Reviews" - older issues render this as one block with ShowReviews
        # itself ("Reviews\nShowReviews\n...") rather than two separate ones -
        # without excluding it too, it gets treated as a fake adjudicator name.
        elif line not in ("ShowTimes", "ShowReviews", "Reviews") and not re.match(r"^\d{4}\s*-\s*\d{4}$", line):
            pending_names.append(line)
    return season, tier_by_name


# Known-bad spellings found while auditing the full archive's output, not
# guessed - "Gred Currid" is a typo repeated across many real printed issues
# of that era (64 reviews' worth), and "Ciar�n Mooney" is the PDF's own
# font encoding permanently losing the accented "á" (confirmed by looking
# at the raw extracted bytes - not something extraction can recover, only
# correct once the right spelling is already known).
NAME_CORRECTIONS = {
    "Gred Currid": "Greg Currid",
    "Ciar�n Mooney": "Ciarán Mooney",
    "Ritchie Ryan": "Richie Ryan",
}

NAME_MATCH_RATIO = 0.85


def fuzzy_name_match(text, known_names):
    """Returns the known_names entry text most likely matches, or None. The
    header banner and a review's own printed sign-off don't always spell an
    adjudicator's name identically across 14 years of hand-typed issues
    (e.g. 'Ritchie Ryan' in one place, 'Richie Ryan' in another, in the
    same issue) - exact matching alone silently drops every review signed
    with the variant spelling. A close (but not exact) match is safe here
    specifically because sign-off lines are short, distinctive full names,
    not generic text a false-positive match could plausibly collide with."""
    if text in known_names:
        return text
    for name in known_names:
        if abs(len(text) - len(name)) > 4:
            continue  # a real spelling variant is a character or two, not a length shift
        if SequenceMatcher(None, text.lower(), name.lower()).ratio() >= NAME_MATCH_RATIO:
            return name
    return None


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
        if is_short and fuzzy_name_match(block_text, known_names) is None:
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
    in reading order. Splits on whichever line's text closely matches one of
    this issue's two adjudicator names - that's each review's sign-off (see
    fuzzy_name_match - the header banner and a review's own sign-off don't
    always agree on spelling)."""
    matches = [(i, fuzzy_name_match(text, tier_by_name)) for i, (text, _) in enumerate(body_lines)]
    split_points = [(i, name) for i, name in matches if name is not None]
    reviews = []
    prev_end = 0
    for split_i, adjudicator in split_points:
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


def extract_issue(filename, source_issue, season_hint=None, fallback_names=None):
    path = ARCHIVE_DIR / filename
    doc = fitz.open(path)
    start = find_review_section_start(doc)
    if start is None:
        print(f"!! no ShowReviews header found in {filename}", file=sys.stderr)
        return []
    season, tier_by_name = parse_header(doc, start)
    season = season or season_hint
    used_fallback = False
    if not tier_by_name and fallback_names and season in fallback_names:
        tier_by_name = fallback_names[season]
        used_fallback = True
    print(f"{filename}: season={season} adjudicators={tier_by_name}" + (" (fallback)" if used_fallback else ""))
    if not tier_by_name or not season:
        print(f"  !! skipping {filename} - no season and/or adjudicator names available", file=sys.stderr)
        return []

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


def build_fallback_names(issues):
    """A season -> {tier: name} lookup built by majority vote across every
    issue where the in-body ShowReviews header *did* state names, for the
    handful of issues where it doesn't (a real layout gap in those specific
    issues, not a parsing failure - see the archive survey). Deliberately
    derived from the data itself rather than hand-typed, since a hand-typed
    list would need updating every time more issues are added here."""
    from collections import Counter
    votes = {}  # season -> tier -> Counter(name)
    for filename, source_issue, season_hint in issues:
        doc = fitz.open(ARCHIVE_DIR / filename)
        start = find_review_section_start(doc)
        if start is None:
            continue
        season, tier_by_name = parse_header(doc, start)
        season = season or season_hint
        if not season or not tier_by_name:
            continue
        for name, tier in tier_by_name.items():
            votes.setdefault(season, {}).setdefault(tier, Counter())[name] += 1
    fallback = {}
    for season, tiers in votes.items():
        fallback[season] = {name: tier for tier, counter in tiers.items() for name, _ in [counter.most_common(1)[0]]}
    # fallback[season] above is built {name: tier}; split_reviews/extract_issue
    # expect tier_by_name in that same {name: tier} shape, so this is already
    # the right structure to pass straight through.
    return fallback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "historical_reviews_pilot.json"))
    parser.add_argument("--limit", type=int, default=None, help="process only the first N discovered issues (for testing)")
    args = parser.parse_args()

    issues, skipped_covers = discover_issues()
    print(f"Discovered {len(issues)} issues ({len(skipped_covers)} couldn't be identified from their cover page)")
    if skipped_covers:
        print("  unidentified:", ", ".join(skipped_covers), file=sys.stderr)
    if args.limit:
        issues = issues[: args.limit]

    fallback_names = build_fallback_names(issues)

    all_reviews = []
    for filename, source_issue, season_hint in issues:
        all_reviews.extend(extract_issue(filename, source_issue, season_hint, fallback_names))
    for r in all_reviews:
        r["adjudicator"] = NAME_CORRECTIONS.get(r["adjudicator"], r["adjudicator"])
    print(f"\n{len(all_reviews)} reviews extracted from {len(issues)} issue(s)")

    Path(args.out).write_text(json.dumps(all_reviews, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.out} - load it into a database with load_historical_reviews.py.")


if __name__ == "__main__":
    main()
