import difflib
import re

WORD_RE = re.compile(r"[a-z0-9]+")


def _words(title):
    return set(WORD_RE.findall(title.lower()))


def find_candidates(titles, dismissed, threshold=0.55, limit=60):
    """Return candidate duplicate title pairs as (title_a, title_b, score),
    sorted most-similar first.

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
            ratio = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
            wb = _words(b)
            is_word_subset = bool(wa) and bool(wb) and wa != wb and (wa <= wb or wb <= wa)
            if ratio >= threshold or is_word_subset:
                score = max(ratio, 0.9) if is_word_subset else ratio
                candidates.append((a, b, round(score, 2)))

    candidates.sort(key=lambda c: -c[2])
    return candidates[:limit]
