"""Finding the same person written two different ways.

The same human appears in this database under several spellings - as an award
nominee ("Áine Gilmore"), as a show credit typed by a society ("Aine Gilmore"),
with an honorific ("Fr Noel Cannon"), or with a curly apostrophe instead of a
straight one. 1,729 distinct nominee names and 754 distinct credit names, 216
of which already match exactly, and `/admin/backfill-credits` adds more free
text every time it runs - so the problem grows while nothing is done about it.

**Internal only.** This exists so a moderator can say "these two names are one
person"; it deliberately builds no public person pages, which is a separate
question that was answered no.

Two rules shape everything here:

**Block on the surname, never sweep every pair.** 2,267 names is 2.5 million
comparisons, and an admin page that does that per request is the exact shape
that took the site down on 19 August. Names are bucketed by normalised surname
first, and only names inside a bucket are ever compared - which is also more
accurate, because a whole-string ratio on human names is actively misleading:
"Alan McClarty" and "Alan McCarthy" score 87% and are two different people.
Only the *given* name is scored, and only once the surname already matches.

**Suggest, never merge.** Everything here returns candidates for a moderator to
confirm or dismiss, the same contract as dedupe.find_candidates and the venue
directory. Nothing in this module writes.
"""
import difflib
import re
import unicodedata

# A name that starts with one of these is the same person as the name without
# it - the archive has "Fr Noel Cannon" and "Noel Cannon" as separate rows.
HONORIFICS = ("mr", "mrs", "ms", "miss", "dr", "prof", "fr", "sr", "br", "rev")

# Deliberately NO suffix stripping. An early version treated "Senior" and
# "Junior" as noise on the surname, which paired "Sean Costello" with "Sean
# Costello Senior" at full confidence - and those are a father and a son, two
# different people whose award records must never be merged. A suffix is the
# one part of a name that exists precisely to tell two people apart, so it
# stays: "Sean Costello Senior" simply never matches "Sean Costello".

# An entry naming more than one person is a data-quality problem, not an
# identity one - "Aaron Stone, Alan Maleady and Art McGuaran" is three people in
# one field, and pretending it is a person would create a canonical record for
# somebody who does not exist. Left alone for a human to split up.
_MULTI_PERSON = re.compile(r"\s(?:and|&|with)\s|[,/]", re.IGNORECASE)

_PUNCT = re.compile(r"[.’'`´\"()\[\]]")
_SPACE = re.compile(r"\s+")

# Below this, a given-name similarity score is noise: two- and three-letter
# names collide by coincidence ("Jo"/"Joe"/"Jon" all score highly on each
# other and are three different people).
MIN_GIVEN_NAME_LENGTH = 4

# How alike two given names must be, once the surname is already identical,
# before this is worth a moderator's time. Set high on purpose: a false
# "these are the same person" quietly merges two real people's award records,
# which is a much worse outcome than a pair that never gets suggested.
GIVEN_NAME_THRESHOLD = 0.85


def fold(text):
    """Lowercase, unaccented, unpunctuated - the form two spellings share.

    Handles the four differences that actually occur in this data: case,
    accents (Áine/Aine), apostrophe style (O'Brien vs O’Brien), and stray
    punctuation or double spaces.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _SPACE.sub(" ", _PUNCT.sub("", stripped).lower()).strip()


def name_parts(name):
    """(given names, surname) folded, or None if this isn't one person's name.

    Returns None for anything that shouldn't get a canonical record: blanks,
    junk like "-", a single word with no surname to block on, and entries
    naming several people at once.
    """
    if not name or _MULTI_PERSON.search(name):
        return None

    words = fold(name).split()
    while words and words[0] in HONORIFICS:
        words = words[1:]
    # A single word is a mononym or a fragment - there is no surname to block
    # on, so it can never be compared safely. Two words minimum.
    if len(words) < 2:
        return None
    if not any(c.isalpha() for c in "".join(words)):
        return None
    return " ".join(words[:-1]), words[-1]


def normalized(name):
    """The whole name folded to its comparable form, or None if not a person."""
    parts = name_parts(name)
    return None if parts is None else f"{parts[0]} {parts[1]}"


def _given_name_score(a, b):
    """How alike two given names are, or None if they shouldn't be compared.

    An initial matching a full name ("A Gilmore" / "Aine Gilmore") is treated
    as a strong match rather than scored - difflib rates a single letter
    against a whole word very low, which would hide exactly the pairs this is
    for.
    """
    if a == b:
        return 1.0

    first_a, first_b = a.split()[0], b.split()[0]
    if len(first_a) == 1 or len(first_b) == 1:
        return 0.9 if first_a[0] == first_b[0] else None

    if len(a) < MIN_GIVEN_NAME_LENGTH or len(b) < MIN_GIVEN_NAME_LENGTH:
        return None

    score = difflib.SequenceMatcher(None, a, b).ratio()
    return score if score >= GIVEN_NAME_THRESHOLD else None


def find_candidates(names, dismissed=()):
    """Candidate same-person pairs as (name_a, name_b, score, why).

    Most-confident first, and uncapped - a caller that only wants a screenful
    slices it, the same contract as dedupe.find_candidates (a truncated list
    makes an admin counter look permanently stuck).

    `dismissed` holds (name_a, name_b) tuples a moderator has already said are
    different people; they never come back.
    """
    dismissed = {tuple(sorted(pair)) for pair in dismissed}

    # Bucket by surname first. Every comparison below happens inside one
    # bucket, which is what keeps this linear-ish instead of 2.5M pairs.
    buckets = {}
    for name in names:
        parts = name_parts(name)
        if parts is None:
            continue
        buckets.setdefault(parts[1], []).append((name, parts[0]))

    candidates = []
    for surname, entries in buckets.items():
        if len(entries) < 2:
            continue
        entries.sort()
        for i, (name_a, given_a) in enumerate(entries):
            for name_b, given_b in entries[i + 1:]:
                if name_a == name_b:
                    continue
                if tuple(sorted((name_a, name_b))) in dismissed:
                    continue

                score = _given_name_score(given_a, given_b)
                if score is None:
                    continue
                if score == 1.0:
                    why = "same name, written differently"
                elif len(given_a.split()[0]) == 1 or len(given_b.split()[0]) == 1:
                    why = "an initial and a full first name, same surname"
                else:
                    why = "near-identical first name, same surname"
                candidates.append((name_a, name_b, round(score, 3), why))

    candidates.sort(key=lambda c: (-c[2], c[0], c[1]))
    return candidates
