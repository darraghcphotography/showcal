"""Best-effort suggestions for a historical show's blank production-team and
venue fields, pulled from its linked ShowTimes review text (see
extract_historical_reviews.py for the review import itself) and the
society's own known default venue. Suggestions only - never written to the
shows table directly, always shown to a moderator on the edit-show form to
accept, edit, or ignore, the same "suggest, don't overwrite" pattern as the
historical reviews queue's society/title matching.

Coverage is real but partial - 14 years of reviews from many different
adjudicators, each writing in their own style, means "Director <Name>"
doesn't appear in every review. Tested against all 815 approved historical
reviews: ~29% named a Director this way, ~16% a Musical Director, ~12% a
Choreographer. That's expected and fine for a suggestion feature - a miss
just leaves the field for a moderator to fill in by hand, same as today."""
import re

# A "word" allows an internal capital with no separator (McCarthy) or after
# an apostrophe (O'Brien, O'Gorman) - both common in Irish surnames, and
# without this a naive [A-Z][a-z]+ class truncates them (confirmed: "Dermot
# O'Callaghan" was coming out as just "Dermot O'").
_WORD = r"[A-Z][a-zà-ÿ]*(?:['’]?[A-Z][a-zà-ÿ]*)*"
_NAME = rf"{_WORD}(?:\s+{_WORD}){{1,2}}"

_MUSICAL_DIRECTOR_RE = re.compile(rf"Musical Director\s+(?:and\s+\w+\s+)?({_NAME})")
# Negative lookbehinds so "Musical Director X" / "Assistant Director X" /
# "Co-Director X" don't also register as a plain Director match.
_DIRECTOR_RE = re.compile(rf"(?<!Musical )(?<!Assistant )(?<!Co-)Director\s+(?:and\s+[\w\-\s]+?\s+)?({_NAME})")
_CHOREOGRAPHER_RE = re.compile(rf"Choreograph(?:er|y)(?:\s+and\s+[\w\-\s]+?)?\s+({_NAME})")

# Only venue names that look like an actual building (not the many
# societies.default_venue/shows.venue rows that are really just a town name,
# e.g. "Galway", "Clare" - matching those verbatim against review text
# false-positives constantly on cast members' own first names and hometown
# mentions, confirmed against real data). A plain town name still helps
# nothing here since it's not real venue detail beyond what the society's
# region already shows.
_VENUE_BUILDING_WORDS = re.compile(
    r"\b(theatre|theater|hall|centre|center|arts|opera house|auditorium|hub|complex|school|college|abbey)\b",
    re.I,
)


def suggest_credits(review_text):
    """Returns {'director': str|None, 'musical_director': str|None,
    'choreographer': str|None} extracted from a ShowTimes review's prose.
    Each is independent - a review might name the director but not the
    choreographer, or vice versa."""
    if not review_text:
        return {"director": None, "musical_director": None, "choreographer": None}
    director = _DIRECTOR_RE.search(review_text)
    musical_director = _MUSICAL_DIRECTOR_RE.search(review_text)
    choreographer = _CHOREOGRAPHER_RE.search(review_text)
    return {
        "director": director.group(1) if director else None,
        "musical_director": musical_director.group(1) if musical_director else None,
        "choreographer": choreographer.group(1) if choreographer else None,
    }


def suggest_venue(review_text, known_venues):
    """Returns the first building-shaped venue name (see
    _VENUE_BUILDING_WORDS) from known_venues that appears verbatim in
    review_text, or None. known_venues is every distinct shows.venue/
    societies.default_venue value already on record - reusing real,
    previously-confirmed venue names is far more reliable than trying to
    parse a venue out of free-form review prose from scratch (no consistent
    phrasing across reviewers to anchor on, unlike "Director <Name>")."""
    if not review_text:
        return None
    for venue in known_venues:
        if venue and _VENUE_BUILDING_WORDS.search(venue) and venue in review_text:
            return venue
    return None
