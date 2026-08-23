"""How a venue is identified, and how a free-text venue string is read.

shows.venue records what someone typed. This turns that into a stable identity
so a capacity, a map pin or a link can hang off it - see the venues table in
schema.sql for why that has to be a separate record.

Normalization here is the same shape as normalize_title(): lowercase, strip
punctuation, collapse whitespace, and nothing fuzzier. "Civic Theatre Tallaght"
and "Civic Theatre, Tallaght" become one venue; "Town Hall Theatre, Galway" and
"Town Hall Theatre, Claremorris" stay two, because they are two - a fuzzy rule
loose enough to merge the first pair also merges those, which was checked
against the real archive before this was written.
"""

import re

_STRIP_RE = re.compile(r"[^a-z0-9\s]")
_SPACE_RE = re.compile(r"\s+")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
_PAREN_RE = re.compile(r"\(.*?\)")

# Written out rather than stripped as punctuation, so "Foo & Bar" and "Foo and
# Bar" are the same venue.
_AMPERSAND_RE = re.compile(r"\s*&\s*")

# Accented characters appear in real venue names (Draíocht, An Táin, glór) and
# get typed both ways. Folded so the two spellings are one venue.
_FOLD = str.maketrans("áàâäãéèêëíìîïóòôöõúùûüýÿñç", "aaaaaeeeeiiiiooooouuuuyync")


def normalize_venue(name):
    """The identity key for a venue name."""
    if not name:
        return ""
    name = name.lower().translate(_FOLD)
    name = _AMPERSAND_RE.sub(" and ", name)
    name = _STRIP_RE.sub(" ", name)
    return _SPACE_RE.sub(" ", name).strip()


def venue_slug(name):
    """URL segment for a venue. Not the identity - two venues could in
    principle slug the same, so the caller de-duplicates."""
    slug = _SLUG_STRIP_RE.sub("-", (name or "").lower().translate(_FOLD)).strip("-")
    return slug or "venue"


# Strings that name no venue at all. Every one of these is real, found in the
# live archive: a note about the run rather than a place, or a bare county.
# Kept as their own venue records anyway (the data is what it is, and hiding it
# would just make it unfindable) but flagged so the admin merge tool can lead
# with them.
_NON_VENUE_RE = re.compile(
    r"^\s*(tba|tbc|various|multiple)\b|\b(run|anniversary|tour)\s*\)?\s*$", re.I
)

# A venue string that's just a place name - "Dublin", "Cork", "Meath". Real,
# but it names a town or a county rather than a building, so it can't carry a
# capacity or a pin until someone says which venue was meant.
_BARE_PLACE_RE = re.compile(r"^[A-Za-zÀ-ÿ'’.\- ]{3,20}$")


def looks_unresolved(name):
    """True if this string can't stand for a real building as written - a note
    about the run, or a bare place name. Used only to order the admin merge
    queue, never to hide or drop anything."""
    if not name or not name.strip():
        return False
    if _NON_VENUE_RE.search(name):
        return True
    stripped = _PAREN_RE.sub("", name).strip()
    return "," not in stripped and len(stripped.split()) == 1 and bool(_BARE_PLACE_RE.match(stripped))


# Words that say what kind of building it is, not which building. Dropped
# before looking for a possible duplicate, so "Moat Theatre" and "The Moat
# Theatre, Naas" compare on {moat, naas} vs {moat} rather than on the word
# "theatre" they share with 60 other venues.
_GENERIC = frozenset({
    "theatre", "theater", "theare", "hall", "centre", "center", "arts", "college",
    "school", "community", "club", "gaa", "auditorium", "house", "campus", "the",
    "of", "and", "at", "in", "co", "st", "saint", "a",
})


def distinctive_words(name):
    return frozenset(w for w in normalize_venue(name).split() if w not in _GENERIC and len(w) > 2)


def merge_candidates(venues):
    """Pairs of venues that might be the same building, for a moderator to
    confirm or ignore. Suggestions only - never applied automatically.

    The rule is containment of the distinctive words, which is deliberately
    loose: it catches the real cases ("Astra Hall" / "Astra Hall UCD" / "UCD
    Astra Hall") but also proposes the Galway, Ballinasloe and Claremorris
    Town Hall Theatres as one venue, which they are not. That's the right
    trade for a suggestion a person confirms, and the wrong one for anything
    automatic - which is why no auto-merge exists.

    A venue recorded as a bare place name is skipped: "Dublin" is a subset of
    every Dublin venue's words, so it alone proposed dozens of merges and
    pushed the real ones off the page. It's already in the queue under its own
    "not a building" flag, and picking which venue was meant is a judgement no
    suggestion can help with.

    `venues` is a list of rows with id and name. Returns {venue_id: [ids]}.
    Computed for the whole list in one pass, not re-derived per row.
    """
    words = [
        (v["id"], distinctive_words(v["name"])) for v in venues if not looks_unresolved(v["name"])
    ]
    suggestions = {}
    for i, (id_a, a) in enumerate(words):
        if not a:
            continue
        for id_b, b in words[i + 1:]:
            if not b or a == b:
                continue
            if a <= b or b <= a:
                suggestions.setdefault(id_a, []).append(id_b)
                suggestions.setdefault(id_b, []).append(id_a)
    return suggestions


def merge_venue_into(db, source_id, target_id):
    """Fold one venue into another: the same building recorded under two
    spellings. Every alias and every show move to the target, and the source
    row goes.

    Deliberately never inferred - merge_candidates() above is loose enough to
    propose three different Town Hall Theatres as one venue, so something has
    to confirm each pair. Today that's a moderator in /admin/venue-directory
    or a reviewed pair written into enrich_venues.py; both go through here so
    a merge means the same thing either way.

    Does not commit - the caller does, so a script can apply a whole batch as
    one transaction. Returns (source_name, target_name).
    """
    source = db.execute("SELECT * FROM venues WHERE id = ?", (source_id,)).fetchone()
    target = db.execute("SELECT * FROM venues WHERE id = ?", (target_id,)).fetchone()
    if source is None or target is None:
        raise LookupError("both venues must exist")
    if source_id == target_id:
        raise ValueError("a venue can't be merged into itself")

    # Anything filled in on the source but not the target is carried across
    # rather than dropped - a capacity researched under the other spelling is
    # still that building's capacity.
    carried = {
        f: source[f] for f in ("town", "county", "region", "capacity", "auditorium_type",
                               "latitude", "longitude", "website_url", "tech_spec_url")
        if target[f] is None and source[f] is not None
    }
    if carried:
        assignments = ", ".join(f"{f} = :{f}" for f in carried)
        db.execute(f"UPDATE venues SET {assignments} WHERE id = :id", dict(carried, id=target_id))

    db.execute("UPDATE venue_aliases SET venue_id = ? WHERE venue_id = ?", (target_id, source_id))
    db.execute("UPDATE shows SET venue_id = ? WHERE venue_id = ?", (target_id, source_id))
    db.execute("DELETE FROM venues WHERE id = ?", (source_id,))
    return source["name"], target["name"]


def town_from_name(name):
    """The town a venue string names after its last comma, if it has one -
    "Theatre Royal, Waterford" -> "Waterford". Returns None rather than
    guessing when there's no comma; a wrong town is worse than a blank one."""
    if not name or "," not in name:
        return None
    tail = _PAREN_RE.sub("", name.rsplit(",", 1)[1]).strip(" .")
    if not tail or len(tail) > 30 or any(ch.isdigit() for ch in tail):
        return None
    return tail
