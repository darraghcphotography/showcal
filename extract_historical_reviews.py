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

# The running masthead ("ShowTimes"), the "Reviews" contents-page label, and
# the "ShowReviews" section banner sometimes share a block with real heading
# text, in either order and either combined onto one line or split across
# several ('ShowTimes Reviews', 'Reviews ShowTimes', 'ShowReviews' alone,
# etc. - all confirmed in testing) - matches any line made up of nothing but
# these three words, so all variants get caught by one check rather than
# hand-listing each combination as it turns up.
MASTHEAD_LINE_RE = re.compile(r"^(ShowTimes|Reviews|ShowReviews)(\s+(ShowTimes|Reviews|ShowReviews))*$")
SHORT_BLOCK_MAX_HEIGHT = 30
SHORT_BLOCK_MAX_LINES = 2
# Body text and photo captions both sit at ~9pt across the archive; a real
# title set in a visibly larger font (confirmed 14pt in a 2010-11 issue)
# clears this with room to spare either way.
LARGE_TITLE_FONT_SIZE = 12
TITLE_LINE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 '&!,.\-]{1,60}$")
# A dotted initialism ('S.O.N.G.', 'S.O.N.G') is a society's own short form,
# not a title - TITLE_LINE_RE's character class allows periods (needed for
# real titles like 'MR. CARTER, THE MUSICAL') so an acronym like this
# otherwise matches it too, and gets picked as the title itself ahead of
# the real one right after it - confirmed against the source PDF (Issue 70
# Summer 2011, 'S.O.N.G.' / 'CHESS' / 'Tain Theatre, Dundalk' - extracted as
# show_raw='S.O.N.G. Chess', society_raw='Tain Theatre, Dundalk').
ACRONYM_RE = re.compile(r"^([A-Z]\.){2,}$")
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


HEADER_LINE_RE = re.compile(r"^(Gilbert|Sullivan) Sections?$|^\d{4}\s*-\s*\d{4}$", re.MULTILINE)


def looks_like_name_line(line):
    """A candidate adjudicator name: 1-4 capitalised words, no digits or
    slashes - excludes a wrapped year fragment ('2018-'/'2019') and a
    section heading sharing the header area ('Top Three Tunes/Reviews',
    confirmed in testing to get mismatched onto a Section line as if it
    were the adjudicator's own name) without having to blacklist either by
    its exact text. Checked with str.isupper() rather than an [A-Z] regex
    class - a real name here is as often 'Ciarán Mooney' or 'Séamus
    Cullen' as 'Billy Rea', and an ASCII-only class silently dropped those,
    which broke sign-off matching for every review in several whole
    issues (confirmed - Issues 124-133, 2017-18) rather than just mis-
    parsing the one name. The masthead words ('ShowTimes', 'ShowReviews',
    'Reviews' - the last is how older issues label the contents-page entry
    for this section, sometimes sharing a block with 'ShowReviews' itself)
    otherwise pass this shape check too, so they're excluded by name here
    rather than relying on select_header_blocks to have kept them out.
    'Top Three Tunes' - the reader-feature heading itself, not just the
    '/Reviews' variant - is excluded by name rather than by shape: unlike
    the wrapped-year and masthead-word cases, its position relative to the
    real adjudicator names isn't consistent across issues (confirmed -
    it sits *before* the real name in Issue 142/October 2019 but *after*
    it, immediately before the Gilbert Section line, in the April 2020
    print issue), so no positional heuristic (picking the oldest or the
    most recent name-shaped candidate) can rule it out in every issue -
    only recognising the recurring heading itself can. 'News' (the
    magazine's society-news section, confirmed - Issue 148/May 2020 PRINT,
    same failure shape as 'Top Three Tunes') is excluded the same way, for
    the same reason."""
    if not line or any(ch.isdigit() for ch in line) or "/" in line:
        return False
    if line in ("ShowTimes", "ShowReviews", "Reviews", "News") or line.startswith("Top Three Tunes"):
        return False
    words = line.split()
    return 1 <= len(words) <= 4 and all(w[0].isupper() for w in words)


def select_header_blocks(doc, start_page):
    """The section-start page's masthead/season/adjudicator-name blocks -
    shared by parse_header (which reads season and adjudicator names out of
    them) and extract_issue (which uses their lowest edge as the cutoff
    below which real review body content begins). A fixed 120pt-from-the-
    top cutoff isn't enough on its own: some issues (confirmed, Summer 2019/
    2019-08.pdf) carry a full unrelated reader feature ('Top Three Tunes', a
    member's favourite-songs write-up) between the masthead and the real
    season/adjudicator-name lines, pushing them well past 120pt - a
    y-only filter either missed them (falling back to majority-vote names)
    or, worse, left the unrelated feature itself in the body content to be
    silently extracted as a fake review (society_raw 'Goosebumps! ...',
    show_raw 'Mary Smyth', body her bio and song list - confirmed against
    the source PDF). Matching by content (the season year-range, or a
    'Gilbert/Sullivan Section' line) as well as position catches these
    wherever they actually sit on the page.

    Sorted into left-column-then-right-column reading order (mirroring
    page_body_lines) rather than left in the PDF's own internal block
    order, which doesn't reliably match visual top-to-bottom position -
    confirmed directly responsible for a wrong name/tier pairing in testing
    (a block naming the Gilbert-section adjudicator got read before the
    block naming the Sullivan-section one, even though it sits below it on
    the page), which silently mismatched an adjudicator name to the wrong
    tier."""
    blocks = doc[start_page].get_text("blocks")
    header_blocks = [b for b in blocks if b[3] < 120 or HEADER_LINE_RE.search(b[4])]
    mid = doc[start_page].rect.width / 2
    header_blocks.sort(key=lambda b: (b[0] >= mid, b[1]))
    return header_blocks


def parse_header(header_blocks):
    header_text = "\n".join(clean(b[4]) for b in header_blocks)
    year_match = re.search(r"\d{4}\s*-\s*\d{4}", header_text)
    season = season_from_header_year(year_match.group(0)) if year_match else None

    lines = [l.strip() for l in header_text.splitlines() if l.strip()]
    tier_by_name = {}
    pending_names = []
    for line in lines:
        m = re.match(r"^(Gilbert|Sullivan) Sections?$", line)
        if m:
            # The real layout always puts a Section line directly after its
            # own adjudicator's name ('Billy Rea' / 'Sullivan Section' /
            # 'Tony McCleane-Fay' / 'Gilbert Section') - taking the *most
            # recently seen* name-shaped line (a stack, not a FIFO queue)
            # means an earlier stray candidate that shape-matched but was
            # never a real name (a reader-feature heading spelled without
            # the '/' that would otherwise exclude it, e.g. plain 'Top
            # Three Tunes' rather than 'Top Three Tunes/Reviews' -
            # confirmed in testing, Issue 142 October 2019) just gets left
            # behind on the stack unconsumed, rather than being handed to
            # this Section as if it were the adjudicator's own name.
            if pending_names:
                tier_by_name[pending_names.pop()] = m.group(1)
        # Only a name-shaped line (1-4 capitalised words, no digits or
        # slashes) is a candidate adjudicator name - broadening
        # select_header_blocks to also pull in the season/tier area wherever
        # it actually sits on the page (rather than only the top 120pt)
        # means this list can now also see other header furniture that
        # isn't a name at all: a year that's wrapped across two lines
        # ('2018-' / '2019', neither of which alone matches the full
        # year-range exclusion below) and a reader-feature heading sharing
        # the top-of-page area. A real name never has digits or a slash,
        # so shape alone rules most of this out; the stack-not-queue pop
        # above absorbs the rest.
        elif looks_like_name_line(line):
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


def page_body_lines(page, known_names, header_cutoff_y, known_societies=()):
    """Returns this page's kept content as a flat list of (text, width_ratio,
    is_headline) tuples, in left-column-then-right-column reading order.
    width_ratio is this line's width divided by its block's widest line,
    used later to spot paragraph-ending lines. is_headline flags a line set
    in a visibly larger font than the magazine's ~9pt body/caption text -
    some older issues (confirmed 2010-11) set the show title this way
    without also putting it in ALL CAPS, so this has to survive alongside
    each line's own text for parse_heading to use, not just get used here to
    decide what to keep."""
    width = page.rect.width
    calendar_y = find_calendar_boundary(page)
    kept_blocks = []  # each: (x0, y0, [(line_x0, line_y0, text, width, is_headline), ...])
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        bx0, by0, bx1, by1 = block["bbox"]
        block_lines = []
        max_font_size = 0
        for line in block["lines"]:
            lx0, ly0, lx1, ly1 = line["bbox"]
            text = clean("".join(span["text"] for span in line["spans"]))
            if text:
                line_font_size = max(span["size"] for span in line["spans"])
                block_lines.append((lx0, ly0, text, lx1 - lx0, line_font_size >= LARGE_TITLE_FONT_SIZE))
                max_font_size = max(max_font_size, line_font_size)
        if not block_lines:
            continue

        block_text = clean(" ".join(t for _, _, t, _, _ in block_lines))
        if calendar_y is not None and by0 >= calendar_y:
            continue
        if header_cutoff_y is not None and by1 < header_cutoff_y:
            continue
        if re.fullmatch(r"\d+", block_text):
            continue
        if block_text == "ShowTimes":
            continue
        height = by1 - by0
        is_short = height < SHORT_BLOCK_MAX_HEIGHT or len(block_lines) <= SHORT_BLOCK_MAX_LINES
        # A short block is furniture (a photo caption, most often) unless:
        # it's a known adjudicator's sign-off; its font is meaningfully
        # bigger than this magazine's ~9pt body/caption text; or one of its
        # own lines fuzzy-matches a real society name (some issues lay the
        # Society/TITLE heading out as its own short block, separate from the
        # body text block that follows, rather than joined into one long
        # block the way most do - without this, a heading in that shape gets
        # discarded exactly like a caption, since a short 2-line block looks
        # identical either way). Any of the three is enough to keep it.
        is_headline_sized = max_font_size >= LARGE_TITLE_FONT_SIZE
        keep_short_block = is_headline_sized or fuzzy_name_match(block_text, known_names) is not None
        # The fuzzy society search is the most expensive check here (a full
        # sliding-window scan against every known society) - only run it,
        # and only against lines with enough letters to plausibly be a name,
        # when the cheaper checks above didn't already settle it.
        if is_short and not keep_short_block and known_societies:
            keep_short_block = any(
                find_society_span([t], known_societies) is not None
                for _, _, t, _, _ in block_lines
                if sum(c.isalpha() for c in t) >= 4
            )
        if is_short and not keep_short_block:
            continue
        kept_blocks.append((bx0, by0, block_lines))

    mid = width / 2
    kept_blocks.sort(key=lambda b: (b[0] >= mid, b[1]))

    out = []
    for _, _, block_lines in kept_blocks:
        max_width = max(w for *_, w, _ in block_lines) or 1
        for _, _, text, w, is_headline in block_lines:
            # The running masthead ("ShowTimes"), the "Reviews" contents-page
            # label, and the season year-range banner ("2022 - 2023") all
            # sometimes share a block with real heading text (see
            # parse_header's own note on the first two) - the whole-block
            # text != check above only catches a *standalone* masthead block,
            # so also drop these at the line level. All three happen to be
            # set in a large enough font to otherwise pass as a real title
            # (confirmed - the year banner did exactly that in testing).
            if MASTHEAD_LINE_RE.fullmatch(text) or re.fullmatch(r"\d{4}\s*-\s*\d{4}", text):
                continue
            out.append((text, w / max_width, is_headline))
    return out


SOCIETY_MATCH_THRESHOLD = 0.80
SOCIETY_SEARCH_LOOKBACK = 8
SOCIETY_SEARCH_MAX_SPAN = 3
# Tried adding a "first word must itself fuzzy-match" gate here, to stop a
# whole-string character ratio letting two *unrelated* town names sharing a
# common suffix ("X Musical Society") coincidentally outscore the real
# match (confirmed real cases - Issue 120 April 2017's 'Malahide Musical
# Society' matched 'Baldoyle Musical Society' at 0.83 over the real
# 'Malahide Musical & Dramatic Society' at 0.81; Issue 70's 'Leixlip
# Musical Society' matched 'Boyle Musical Society' the same way). Reverted:
# it also cost real reviews elsewhere in the archive that should have been
# unaffected (confirmed, e.g. Issue 90 November 2013's Ratoath Musical
# Society review, an exact-name match with no ambiguity at all) - not yet
# root-caused before running out of session time to investigate safely,
# and at least one involved source PDF has garbled/corrupted font encoding
# in places, muddying the investigation further. The Malahide/Leixlip bug
# is real and confirmed, just not yet safely fixed - see ROADMAP.md rather
# than re-attempting this exact approach without first understanding why
# it broke Ratoath.


def find_society_span(line_texts, known_societies):
    """Finds where the real society name sits among the first
    SOCIETY_SEARCH_LOOKBACK lines, by fuzzy-matching every contiguous 1-3
    line span against the site's own real society list (societies.csv,
    passed in as {lowercase name: canonical name}) - ground truth, not a
    guess from capitalization. AIMS's own back issues don't apply
    capitalization consistently: sometimes the show title is in ALL CAPS and
    the society name isn't (the pilot's convention), sometimes the reverse
    (confirmed directly in the source PDF - 'ENNIS MUSICAL SOCIETY' /
    'Little Shop Of Horrors', Issue 121 May 2017) - a capitalization-only
    heuristic silently mis-splits whichever of the two it guesses wrong on.
    Searching a *span* starting anywhere in the lookback window (not just
    line 0) also means unrelated content sitting before the real heading (a
    stray caption or sidebar paragraph the block-level furniture filter
    didn't catch - confirmed in a different review, whose society_raw ended
    up prefixed with an unrelated interview snippet) gets left out rather
    than absorbed into the society name. Returns (start, end, canonical_name)
    for the winning span, or None if nothing scores above threshold - the
    caller falls back to the old capitalization heuristic (some defunct
    historical societies aren't in the current societies.csv at all)."""
    best = None
    search_space = line_texts[:SOCIETY_SEARCH_LOOKBACK]
    for start in range(len(search_space)):
        for span in range(1, SOCIETY_SEARCH_MAX_SPAN + 1):
            end = start + span
            if end > len(search_space):
                break
            candidate = " ".join(l.rstrip(",") for l in search_space[start:end]).lower()
            for lower_name, canonical_name in known_societies.items():
                score = SequenceMatcher(None, candidate, lower_name).ratio()
                if best is None or score > best[3]:
                    best = (start, end, canonical_name, score)
    if best and best[3] >= SOCIETY_MATCH_THRESHOLD:
        return best[0], best[1], best[2]
    return None


VENUE_RE = re.compile(r"\b(Theatre|Theater|Hall|Centre|Center|Cinema|Opera House|Arena|Auditorium)\b", re.I)
# A real venue-type word alone isn't enough - plenty of real society names
# legitimately contain one too ('National Youth Musical Theatre', 'Bravo
# Theatre Group'). A line with one of *these* qualifier words alongside is a
# society, not a venue, regardless of whether it also matches VENUE_RE.
SOCIETY_QUALIFIER_RE = re.compile(
    r"\b(Musical|Society|Group|Company|Productions|Youth|Operatic|Dramatic|Players|Panto)\b", re.I
)


def looks_like_venue(text):
    return bool(VENUE_RE.search(text)) and not SOCIETY_QUALIFIER_RE.search(text)


def looks_like_title(text, is_headline):
    """A line is title-shaped if it's in ALL CAPS (the modern convention) or
    set in a visibly larger font than body/caption text (the 2010-11
    convention, where the title keeps normal capitalization - 'Spring
    Awakening', not 'SPRING AWAKENING' - so ALL-CAPS alone would miss it).
    A bare dotted initialism never counts, even in a large font - it's a
    society's own short form (see ACRONYM_RE), not a real title. Neither
    does a single character, even in a large font - PyMuPDF gives a
    decorative drop-cap (a season-opening editorial's oversized first
    letter, its own text run at well above body size) its own line, which
    otherwise reads exactly like a real large-font title (confirmed, Issue
    107 October 2015 - a lone 'A' opening 'As the new show season
    begins...' got picked up as a fake review title, and the real
    adjudicator names appearing in that same intro's own bio paragraphs
    then looked exactly like their sign-offs, fabricating a fake review
    from editorial text no adjudicator wrote)."""
    if ACRONYM_RE.match(text) or len(text) < 2:
        return False
    return bool(TITLE_LINE_RE.match(text)) or is_headline


def parse_heading(segment, known_societies=()):
    """segment is a list of (text, width_ratio, is_headline) tuples -
    everything after the previous review's sign-off (or the start of the
    section, for the first review). Returns (society_raw, show_raw,
    review_text) or None if no title-shaped line turns up in the first few
    lines."""
    lines = [(t.strip(), r, h) for t, r, h in segment if t.strip()]
    if not lines:
        return None
    line_texts = [t for t, _, _ in lines]

    span = find_society_span(line_texts, known_societies) if known_societies else None
    if span is not None:
        start, end, canonical_name = span
        society_lines = [canonical_name]
        before_text = line_texts[start - 1] if start > 0 else None
        before_headline = lines[start - 1][2] if start > 0 else False

        # Which side of the matched society the title sits on varies across
        # the archive - checked here by title-*shape*, not by which side is
        # more common, since either is real: modern issues go Society,
        # TITLE, body; older ones (confirmed 2010-11, with or without a
        # venue line after the society) go Title, Society, [Venue,] body
        # instead. The tell is whether the line right before the matched
        # society looks like a title in its own right, rather than assuming
        # everything before a mid-segment match is furniture to discard -
        # that assumption silently ate real titles ('AIDA', 'OLIVER!',
        # 'TITANIC', ...) in testing, exactly when this order was in play.
        if before_text is not None and looks_like_title(before_text, before_headline):
            title_lines = [before_text]
            idx = end
            if idx < len(lines) and looks_like_venue(line_texts[idx]):
                idx += 1  # a venue line right after the society - skip it too
            if start > 1:
                print(f"  .. discarded {start - 1} unrelated line(s) before the real heading: "
                      f"{' / '.join(line_texts[:start - 1])[:100]!r}", file=sys.stderr)
        else:
            if start > 0:
                print(f"  .. discarded {start} unrelated line(s) before the real heading: "
                      f"{' / '.join(line_texts[:start])[:100]!r}", file=sys.stderr)
            if end >= len(lines):
                return None
            # A parenthesised abbreviation right after the society name
            # ('Galway University Musical Society' / '(GUMS)') is the
            # society's own short-form, not the title - skip it before
            # treating the next line as the title instead.
            if re.fullmatch(r"\(.+\)", line_texts[end]) and end + 1 < len(lines):
                end += 1
            # The society's own printed name can wrap onto a second line
            # too - a trailing comma on the matched span's own last line
            # ('North East Music & Dramatic Society,' / 'Castleblayney')
            # signals a continuation (usually the society's town/city)
            # follows, not the title - the span search itself won't have
            # matched across it (adding a location line only dilutes the
            # match score against the canonical name, so the 1-line match
            # already wins), so nothing upstream already accounts for it.
            # Confirmed against the source PDF (Issue 160/November '22 -
            # 'Castleblayney' was extracted as the show's own title, real
            # title 'THE ADDAMS FAMILY'-style all-caps '9 TO 5' silently
            # dropped) - only skip when the continuation doesn't itself
            # look title-shaped, so a genuine same-line title isn't eaten.
            if (
                line_texts[end - 1].endswith(",")
                and not looks_like_title(line_texts[end], lines[end][2])
                and end + 1 < len(lines)
            ):
                end += 1
            title_lines = [line_texts[end]]
            idx = end + 1
            # Only chase a multi-line title if the first line was itself
            # ALL-CAPS - the site's own convention for a wrapped title (e.g.
            # 'JOSEPH AND THE AMAZING' / 'TECHNICOLOR DREAMCOAT') keeps every
            # line of it capitalized, so this doesn't accidentally swallow
            # real body prose that follows a normal-case, single-line title.
            if TITLE_LINE_RE.match(title_lines[0]):
                while idx < len(lines) and TITLE_LINE_RE.match(lines[idx][0]):
                    title_lines.append(lines[idx][0])
                    idx += 1
            # A venue line right after the title (Society / TITLE / Venue,
            # City / body) - the title-first branch above already skips this
            # same shape when the venue sits right after the society instead
            # (Title / Society / Venue); this branch had no equivalent check
            # at all, so the venue line was falling straight into
            # review_text as its own leading sentence - confirmed against
            # the source PDF (Marian Choral Society / TITANIC / "St
            # Jarlath's Hall, Tuam" / body - the venue was the review's
            # printed opening words in the queue).
            if idx < len(lines) and looks_like_venue(line_texts[idx]):
                idx += 1
    else:
        # Last resort: no known society matched at all - scan for the first
        # title-shaped line the old-fashioned way (some historical/defunct
        # societies aren't in the current societies.csv).
        idx = 0
        society_lines = []
        while idx < len(lines) and not looks_like_title(lines[idx][0], lines[idx][2]):
            society_lines.append(lines[idx][0])
            idx += 1
            if idx > MAX_SOCIETY_LINES:
                return None
        if idx >= len(lines):
            return None
        title_lines = [lines[idx][0]]
        idx += 1
        if TITLE_LINE_RE.match(title_lines[0]):
            while idx < len(lines) and TITLE_LINE_RE.match(lines[idx][0]):
                title_lines.append(lines[idx][0])
                idx += 1
        # society_lines came up empty exactly when the title-shaped line was
        # the very first one in the segment - i.e. this is Title-then-Society
        # order (no society name confident enough to anchor the search on -
        # 'CAROUSEL' / 'Newry Musical and Orchestral Society', a real
        # historical name variant, confirmed in testing) rather than the
        # Society-then-Title order this loop otherwise assumes. The society
        # name (uncanonicalized - a moderator matches it by hand) is
        # whatever non-title line follows the title instead - taken as
        # exactly one line (plus an optional venue line after it), never an
        # open-ended scan: with no title-shaped line to signal where the
        # society name ends (unlike the Society-then-Title loop above, which
        # stops at the real title), an unbounded scan here has nothing to
        # stop it at the society name's real end and silently swallows real
        # review prose as fake "society name" lines instead - confirmed
        # against source PDFs (Issue 76 April 2012, 'Fusion Theatre' - a
        # defunct society missing from societies.csv - the next five lines,
        # the review's own opening sentence, got eaten this way and vanished
        # from the published review text entirely).
        if not society_lines and idx < len(lines):
            society_lines = [lines[idx][0]]
            idx += 1
            if idx < len(lines) and looks_like_venue(lines[idx][0]):
                idx += 1  # a venue line right after the society - skip it too
        # society_lines non-empty here means the loop above already found a
        # real Society/TITLE pair (the ACRONYM_RE fix to looks_like_title
        # made this reachable for society names shaped like 'S.O.N.G.',
        # which previously matched as if they were the title themselves) -
        # same venue-after-title shape as the confident-match branch above,
        # so it gets the same skip.
        elif society_lines and idx < len(lines) and looks_like_venue(line_texts[idx]):
            idx += 1

    if idx >= len(lines):
        return None
    society_raw = ", ".join(l.rstrip(",") for l in society_lines)
    show_raw = " ".join(title_lines).rstrip(" .")
    review_text = join_paragraphs(lines[idx:])
    return society_raw, show_raw, review_text


TERMINAL_PUNCTUATION_RE = re.compile(r"[.!?][\"'’”)]*$")


def join_paragraphs(lines):
    """Turns a list of (text, width_ratio, is_headline) printed lines back
    into flowing prose: consecutive lines join with a space (mid-paragraph
    line-wrap), except a line that's both noticeably narrower than its
    column's full width AND ends a complete sentence, which starts a new
    paragraph instead. Width alone isn't enough - a block can have a run of
    narrower lines for reasons that have nothing to do with a paragraph
    ending (an inline image squeezing the column for a few lines produced a
    run of single-word 'paragraphs' in testing, none of them ending mid-
    sentence); requiring real sentence-terminal punctuation too rules those
    out, since a genuine paragraph break can only happen where a sentence
    actually finished."""
    paragraphs = []
    current = []
    for text, ratio, _ in lines:
        current.append(text)
        if ratio < PARAGRAPH_BREAK_WIDTH_RATIO and TERMINAL_PUNCTUATION_RE.search(text):
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(p.strip() for p in paragraphs if p.strip())


_TITLE_AFTER_DIGIT_RE = re.compile(r"(\d)([A-Z])")


def _title_case(all_caps):
    """str.title() capitalizes the first letter after ANY non-alphabetic
    character, including a digit - "25TH ANNUAL..." becomes "25Th Annual...",
    not "25th Annual...". Ordinals are common in show titles ("The 25th
    Annual Putnam County Spelling Bee"), so this undoes just that one
    artifact afterwards rather than reimplementing title-casing from
    scratch - every other .title() behavior (hyphens, apostrophes) is left
    exactly as it was, since only the digit case was ever reported wrong."""
    titled = all_caps.title()
    return _TITLE_AFTER_DIGIT_RE.sub(lambda m: m.group(1) + m.group(2).lower(), titled)


def split_reviews(body_lines, tier_by_name, source_issue, known_societies):
    """body_lines is the whole review section's (text, width_ratio,
    is_headline) lines, in reading order. Splits on whichever line's text
    closely matches one of this issue's two adjudicator names - that's each
    review's sign-off (see fuzzy_name_match - the header banner and a
    review's own sign-off don't always agree on spelling)."""
    matches = [(i, fuzzy_name_match(text, tier_by_name)) for i, (text, _, _) in enumerate(body_lines)]
    split_points = [(i, name) for i, name in matches if name is not None]
    reviews = []
    prev_end = 0
    for split_i, adjudicator in split_points:
        segment = body_lines[prev_end:split_i]
        prev_end = split_i + 1
        parsed = parse_heading(segment, known_societies)
        if parsed is None:
            preview = " ".join(t for t, _, _ in segment[:6])
            print(f"  !! no heading found before sign-off '{adjudicator}' - "
                  f"segment starts: {preview[:80]!r}", file=sys.stderr)
            continue
        society_raw, show_raw, review_text = parsed
        reviews.append({
            "society_raw": society_raw,
            "show_raw": _title_case(show_raw) if show_raw.isupper() else show_raw,
            "adjudicator": adjudicator,
            "tier": tier_by_name[adjudicator],
            "review_text": review_text,
            "source_issue": source_issue,
        })
    return reviews


def extract_issue(filename, source_issue, season_hint=None, fallback_names=None, known_societies=()):
    path = ARCHIVE_DIR / filename
    doc = fitz.open(path)
    start = find_review_section_start(doc)
    if start is None:
        print(f"!! no ShowReviews header found in {filename}", file=sys.stderr)
        return []
    header_blocks = select_header_blocks(doc, start)
    season, tier_by_name = parse_header(header_blocks)
    season = season or season_hint
    start_page_cutoff_y = max((b[3] for b in header_blocks), default=120)
    # A season's own majority-vote fallback looked like a natural way to
    # correct a locally-mis-picked name (a recurring magazine heading like
    # 'News' or 'Top Three Tunes' winning out over the real adjudicator's
    # name - see looks_like_name_line) without blacklisting every such
    # heading by hand. Tried and reverted: the vote itself isn't reliably
    # scoped to the true season, since a handful of issues' own in-body
    # season detection disagrees with where they really belong (confirmed -
    # Issues 124-126 got silently corrected *away* from their own correct
    # in-body names, 'Peter Kennedy'/'Ciarán Mooney', to an unrelated
    # pair pulled in from whichever other season's issues happened to share
    # that same season key). A wrong correction that looks confident is
    # worse than no correction, so this stays narrow and blacklist-based -
    # anything not yet found needs a real per-issue audit, not a broader
    # automatic mechanism.
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
        cutoff_y = start_page_cutoff_y if i == start else None
        all_lines.extend(page_body_lines(page, set(tier_by_name), cutoff_y, known_societies))
        if find_calendar_boundary(page) is not None:
            break

    reviews = split_reviews(all_lines, tier_by_name, source_issue, known_societies)
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
        season, tier_by_name = parse_header(select_header_blocks(doc, start))
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


def load_known_societies():
    """{lowercase name: canonical name} from the git-tracked societies.csv -
    real ground truth for find_society_span, with no database dependency
    (extraction never touches a database - see the module docstring)."""
    import csv
    societies = {}
    with open(ROOT / "societies.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if name:
                societies[name.lower()] = name
    return societies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "historical_reviews_pilot.json"))
    parser.add_argument("--limit", type=int, default=None, help="process only the first N discovered issues (for testing)")
    args = parser.parse_args()

    known_societies = load_known_societies()
    print(f"Loaded {len(known_societies)} known society names from societies.csv")

    issues, skipped_covers = discover_issues()
    print(f"Discovered {len(issues)} issues ({len(skipped_covers)} couldn't be identified from their cover page)")
    if skipped_covers:
        print("  unidentified:", ", ".join(skipped_covers), file=sys.stderr)
    if args.limit:
        issues = issues[: args.limit]

    fallback_names = build_fallback_names(issues)

    all_reviews = []
    for filename, source_issue, season_hint in issues:
        all_reviews.extend(
            extract_issue(filename, source_issue, season_hint, fallback_names, known_societies)
        )
    for r in all_reviews:
        r["adjudicator"] = NAME_CORRECTIONS.get(r["adjudicator"], r["adjudicator"])
    print(f"\n{len(all_reviews)} reviews extracted from {len(issues)} issue(s)")

    Path(args.out).write_text(json.dumps(all_reviews, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.out} - load it into a database with load_historical_reviews.py.")


if __name__ == "__main__":
    main()
