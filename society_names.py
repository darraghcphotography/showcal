"""Comparing society names for "is this the same society?".

Deliberately a root-level module with no dependencies beyond the standard
library, because both halves of the review pipeline need it and they can't
import each other: extract_historical_reviews.py runs locally against the
PDF archive (needs PyMuPDF, no Flask), while the app needs Flask and never
sees a PDF. `COPY . .` in the Dockerfile puts this alongside the app package
in the image, so `import society_names` resolves in both.

The problem this exists to solve: a whole-string character ratio is not
usable on its own for society names, because so many of them end in the
same words. "Clane Musical Society" scores 0.93 against the completely
unrelated "Carnew Musical Society" but only 0.79 against its own real record
"Clane Musical & Dramatic Society" - the shared " musical society" is 15 of
21 characters. Worse in the archive's real failure case: "UCC Musical
Society" scores 0.95 against "UCD Musical Society", one character apart and
a different university, beating the correct "UCC Musical Theatre Society".
That mis-filed seven Cork reviews onto UCD's page before it was caught.

Comparing only the *distinctive* part - what's left once the generic
organisational words are removed - separates these cleanly.
"""
import re
from difflib import SequenceMatcher

# Words common enough across society names to carry no identifying
# information on their own.
_ORG_WORDS_RE = re.compile(
    r"\b(musical|music|dramatic|drama|choral|operatic|opera|light|theatre|theater|society"
    r"|societies|group|company|productions|production|players|ltd|and|the|soc|mus)\b",
    re.I,
)

# Calibrated against 17 confirmed pairs from the ShowTimes archive: every
# genuine name variant scores >= 0.95 here, every confirmed different-society
# pair <= 0.80. See tests/test_historical_reviews.py, which pins both sides.
DISTINCTIVE_THRESHOLD = 0.85

# Two distinctive parts whose words differ only by word form ("Arch" vs
# "Arches") should still count as the same word when testing containment.
# Only applied to words of at least this length, and only when the shorter
# is a prefix of the longer: on a very short word a single character is the
# whole distinction, not an inflection. "CIT" is a prefix of "City" and
# scores 0.86 as a bare ratio, which would otherwise merge CIT Musical
# Society into Cork City Musical Society - confirmed, it did.
_WORD_FORM_RATIO = 0.8
_WORD_FORM_MIN_LENGTH = 4


def _same_word(a, b):
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < _WORD_FORM_MIN_LENGTH:
        return False
    return longer.startswith(shorter) and SequenceMatcher(None, a, b).ratio() >= _WORD_FORM_RATIO


def distinctive_part(name):
    """The identifying part of a society name - what's left once the generic
    organisational words and any parenthesised aside are removed. A trailing
    town after a comma is deliberately KEPT: it is often the only thing
    telling two same-named societies apart ("St Mary's Musical Society,
    Navan" vs "St Mary's Choral Society, Clonmel" both reduce to "st mary s"
    without it, and would then look like a perfect match for each other)."""
    s = name.lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = _ORG_WORDS_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def distinctive_score(a, b):
    """How well two society names agree on the part that actually identifies
    them. When one distinctive part's words are wholly contained in the
    other's, that's a genuine variant carrying an extra qualifier ("9 Arch"
    vs "9 Arch Claregalway"), not a different society, so it scores as a
    strong match rather than being penalised for the extra word."""
    da, db = distinctive_part(a), distinctive_part(b)
    if not da or not db:
        return 0.0
    wa, wb = da.split(), db.split()
    smaller, larger = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    contained = all(any(_same_word(x, y) for y in larger) for x in smaller)
    if contained:
        return max(SequenceMatcher(None, da, db).ratio(), 0.95)
    return SequenceMatcher(None, da, db).ratio()


def is_same_society(a, b):
    """True when two spellings plausibly name the same society."""
    return distinctive_score(a, b) >= DISTINCTIVE_THRESHOLD
