import difflib
import re

WORD_RE = re.compile(r"[a-z0-9]+")

# Trailing qualifiers common enough across many unrelated titles that
# sharing one inflates the character-similarity ratio for otherwise
# unrelated shows - e.g. "Ghost the Musical" vs "Snoopy The Musical" scored
# 74% purely from sharing " the musical", not because the shows are
# remotely related. Stripped only for the ratio comparison below; the
# original title is still used everywhere else (display, the word-subset
# check, which already handles genuine "X" vs "X Jr." pairs correctly).
GENERIC_SUFFIXES = [" the musical", " a musical", " jr.", " jr", " junior"]

# Below this length (after stripping a generic suffix, if any), a character
# ratio is unreliable - short titles collide by coincidence (e.g. "Bare" vs
# "Cabaret" scored 73% on shared letters alone despite being unrelated
# shows). The word-subset check below still applies regardless of length.
MIN_RATIO_LENGTH = 6


def _words(title):
    return set(WORD_RE.findall(title.lower()))


def _strip_generic_suffix(title):
    lowered = title.lower()
    for suffix in GENERIC_SUFFIXES:
        if lowered.endswith(suffix):
            return lowered[: -len(suffix)]
    return lowered


def find_candidates(titles, dismissed, threshold=0.70):
    """Return every candidate duplicate title pair as (title_a, title_b,
    score), sorted most-similar first - NOT truncated. Truncating here used
    to make the admin dashboard's "possible duplicates" count read as
    permanently stuck at whatever the cap was: resolving the top pair just
    let the next-highest one below the cutoff take its place, so the count
    never visibly moved until the true total dropped below the cap. Callers
    that only want a manageable batch to display (the review page shows the
    top 60) slice the result themselves - the full list was always built and
    sorted before any truncation happened anyway, so returning it uncapped
    costs nothing extra.

    Deliberately over-flags rather than under-flags - e.g. 'Frozen' and
    'Frozen Jr.' will show up here even though they're genuinely different
    licensed editions. That's fine: this only ever *suggests*, a moderator
    reviews and either merges or dismisses every pair, nothing is changed
    automatically.
    """
    titles = sorted(t for t in titles if t)
    candidates = []
    for i, a in enumerate(titles):
        wa = _words(a)
        for b in titles[i + 1:]:
            pair = tuple(sorted((a, b)))
            if pair in dismissed:
                continue
            stripped_a = _strip_generic_suffix(a)
            stripped_b = _strip_generic_suffix(b)
            if len(stripped_a) < MIN_RATIO_LENGTH or len(stripped_b) < MIN_RATIO_LENGTH:
                ratio = 0.0
            else:
                ratio = difflib.SequenceMatcher(None, stripped_a, stripped_b).ratio()
            wb = _words(b)
            # Word-subset match, but only when the longer title adds at most
            # one extra word - this is what catches genuine "X" vs "X Jr."/
            # "X 2.0"/"X Teen" suffix variants without also flagging any
            # short, generic word that happens to appear inside an unrelated
            # longer title (e.g. "Gypsy" is NOT meaningfully similar to "The
            # Gypsy Baron" just because both contain the word "gypsy").
            is_word_subset = (
                bool(wa) and bool(wb) and wa != wb and (wa <= wb or wb <= wa)
                and abs(len(wa) - len(wb)) <= 1
            )
            if ratio >= threshold or is_word_subset:
                score = max(ratio, 0.9) if is_word_subset else ratio
                candidates.append((a, b, round(score, 2)))

    candidates.sort(key=lambda c: -c[2])
    return candidates
