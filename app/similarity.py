import re

from .season import historical_results_year

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


def find_award_record_match(db, society_id, title, season):
    """Return the historical_results show title if this society already has
    an award-archive record (any category, any result) for the same season
    under a normalized-matching title, or None. A society adding this same
    production again via self-service would otherwise double-count it: once
    from the old award import, once from this new submission."""
    norm = normalize_title(title)
    if not norm:
        return None

    year = historical_results_year(season)
    rows = db.execute(
        "SELECT DISTINCT show FROM historical_results WHERE society_id = ? AND year = ? AND show IS NOT NULL",
        (society_id, year),
    ).fetchall()
    for row in rows:
        if normalize_title(row["show"]) == norm:
            return row["show"]
    return None
