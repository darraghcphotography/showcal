"""Best-effort suggestions for a historical show's blank production-team and
venue fields, pulled from its linked ShowTimes review text (see
extract_historical_reviews.py for the review import itself) and the
society's own known default venue. Suggestions only - never written to the
shows table without a moderator accepting them, the same "suggest, don't
overwrite" pattern as the historical reviews queue's society/title matching.

Adjudicators write about a production team in whatever phrasing they like,
so matching one fixed form ("Director Jane Murphy") finds only a fraction of
what's actually there. All of these are real forms from the archive, for the
same three roles:

    Director Thomas O'Leary          Directors Cian Gallagher and Colin Gilligan
    directed by Paul Norton          Under the Direction of Paul Norton
    musical director Roisin Heenan   Musical Director, Shane Farrell
    Roisin Heenan's musical direction
    Choreographer Aisling Doyle      Choreography by Niamh McGowan
    choreographed by Alex McFarlane  Lynn Gourley's choreography

Only the first match for each role is used, and each role is independent -
a review naming the director but not the choreographer fills one and leaves
the other blank.
"""
import re

# A "word" allows an internal capital with no separator (McCarthy) or after
# an apostrophe (O'Brien, O'Gorman) - both common in Irish surnames, and
# without this a naive [A-Z][a-z]+ class truncates them (confirmed: "Dermot
# O'Callaghan" came out as just "Dermot O'").
_WORD = r"[A-Z][a-zà-ÿ]*(?:['’]?[A-Z][a-zà-ÿ]*)*"
# An honorific is not a first name - "Musical Director ... Mr Milford" was
# being captured as the name "Mr Milford". Reviews use these constantly
# ("Ms Johnston sang...", "Mr Nicholl's performance"), so a credit that
# starts with one is a reference back to someone already introduced, not the
# credit line itself; skip it and let a later pattern find the real name.
_HONORIFICS = r"(?:Mr|Mrs|Ms|Miss|Dr|Prof|Fr|Sr|Br)"
_NAME = rf"(?!{_HONORIFICS}\b){_WORD}(?:\s+{_WORD}){{1,2}}"

# Role words are matched case-insensitively (adjudicators write both
# "Musical Director" and "musical director"); the name itself is not, since
# capitalisation is what identifies it as a name at all.
_DIRECTOR_PATTERNS = (
    # "Director Thomas O'Leary" / "Directors Cian Gallagher and Colin Gilligan".
    # The lookbehinds keep "Musical Director X", "Assistant Director X" and
    # "Co-Director X" out of the plain-director result.
    rf"(?<!Musical )(?<!musical )(?<!Assistant )(?<!assistant )(?<!Co-)(?i:directors?),?\s+(?:and\s+[\w\-\s]+?\s+)?({_NAME})",
    rf"(?i:under the direction of)\s+({_NAME})",
    rf"(?i:direct(?:ed|ion))\s+(?i:by)\s+({_NAME})",
    rf"({_NAME})'s\s+(?i:direction)",
)
_MUSICAL_DIRECTOR_PATTERNS = (
    rf"(?i:musical director),?\s+(?:and\s+\w+\s+)?({_NAME})",
    rf"(?i:musical direction)\s+(?i:by)\s+({_NAME})",
    rf"({_NAME})'s\s+(?i:musical direction)",
    # "the baton of MD Shane Farrell" - only as a last resort, since a bare
    # "MD" is ambiguous enough that a fuller phrasing should always win.
    rf"\bMD,?\s+({_NAME})",
)
_CHOREOGRAPHER_PATTERNS = (
    rf"(?i:choreographer),?\s+(?:and\s+[\w\-\s]+?\s+)?({_NAME})",
    rf"(?i:choreograph(?:y|ed))\s+(?i:by)\s+({_NAME})",
    rf"({_NAME})'s\s+(?i:choreograph(?:y|ed))",
    rf"({_NAME})\s+(?i:took care of the)[\w\s]{{0,30}}?(?i:choreography)",
)

_PATTERNS_BY_FIELD = {
    "director": _DIRECTOR_PATTERNS,
    "musical_director": _MUSICAL_DIRECTOR_PATTERNS,
    "choreographer": _CHOREOGRAPHER_PATTERNS,
}

# Only venue names that look like an actual building (not the many
# societies.default_venue/shows.venue rows that are really just a town name,
# e.g. "Galway", "Clare" - matching those verbatim against review text
# false-positives constantly on cast members' own first names and hometown
# mentions, confirmed against real data). A plain town name helps nothing
# here anyway, since it's not real venue detail beyond the society's region.
_VENUE_BUILDING_WORDS = re.compile(
    r"\b(theatre|theater|hall|centre|center|arts|opera house|auditorium|hub|complex|school|college|abbey)\b",
    re.I,
)


def _first_match(patterns, text):
    """The earliest match in the text across all the given patterns - not
    the first pattern that happens to match. A review usually names the
    director in its opening summary and again in passing later; taking the
    earliest occurrence keeps the deliberate credit rather than an aside."""
    best = None
    for pattern in patterns:
        m = re.search(pattern, text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.group(1))
    return best[1] if best else None


def suggest_credits(review_text):
    """Returns {'director': str|None, 'musical_director': str|None,
    'choreographer': str|None} extracted from a ShowTimes review's prose."""
    if not review_text:
        return {field: None for field in _PATTERNS_BY_FIELD}
    return {
        field: _first_match(patterns, review_text)
        for field, patterns in _PATTERNS_BY_FIELD.items()
    }


def suggest_venue(review_text, known_venues):
    """Returns the first building-shaped venue name (see
    _VENUE_BUILDING_WORDS) from known_venues that appears verbatim in
    review_text, or None. known_venues is every distinct shows.venue/
    societies.default_venue value already on record - reusing real,
    previously-confirmed venue names is far more reliable than parsing a
    venue out of free-form prose, which has no consistent phrasing to anchor
    on the way "Director <Name>" does."""
    if not review_text:
        return None
    for venue in known_venues:
        if venue and _VENUE_BUILDING_WORDS.search(venue) and venue in review_text:
            return venue
    return None
