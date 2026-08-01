import re

_STRIP_RE = re.compile(r"[^a-z0-9\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize_title(title):
    """Lowercase, strip punctuation, collapse whitespace - catches the exact
    kind of near-duplicate that caused real problems in this dataset (case
    and punctuation variants of the same show, e.g. 'RENT' vs 'Rent',
    'Beauty & The Beast' vs 'Beauty and the Beast'). Deliberately not a fuzzy/
    Levenshtein match - that would also flag genuinely different shows with
    similar names, and be much harder to reason about for a false-positive
    report to a member filling in a form.
    """
    title = title.lower()
    title = _STRIP_RE.sub("", title)
    title = _SPACE_RE.sub(" ", title).strip()
    return title


def find_close_title(db, title):
    """Return an existing show title that normalizes the same as `title` but
    isn't an exact match, or None if there's no such near-duplicate (including
    when `title` itself is already an exact match to something on record)."""
    norm = normalize_title(title)
    if not norm:
        return None

    rows = db.execute(
        "SELECT DISTINCT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'"
    ).fetchall()
    for row in rows:
        existing = row["show"]
        if existing == title:
            return None
        if normalize_title(existing) == norm:
            return existing
    return None
