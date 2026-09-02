"""Word lists for auto-generated invite codes (admin.py's _generate_invite_code) -
kept in its own module, same pattern as season.py/similarity.py.

An adjective + noun pair (e.g. "silver-otter") is easier to read aloud, type,
and remember than a random alphanumeric string. Deliberately plain, common
words with no profanity or homophones - a code that's ambiguous when spoken
over the phone defeats the point.

~40 of each gives ~1,600 pairs. That was originally described here as
"comfortable headroom for issuing codes to every AIMS society", which is true
and is also the wrong question - see CODE_DIGITS below, which answers the one
that matters.
"""

# Digits appended to the adjective-noun pair, and the reason is guessing, not
# collisions. The word lists give 40 x 40 = 1,600 pairs, which invite_words.py
# correctly calls "comfortable headroom for issuing codes to every AIMS
# society" - that is a collision argument. It is not a guessing argument: with
# ~21 codes live, roughly 1 in 76 guesses at /society/login was a valid code,
# so at that route's rate limit somebody was into *a* society in about eight
# minutes. A society code is not a read-only key either - it can edit that
# society's shows and upload posters (2026-09-01 audit).
#
# Four digits takes the space to ~16 million, i.e. about 1 in 760,000 with the
# same number of codes live. Digits rather than a third word because the whole
# point of these codes is being read aloud down a phone or across a committee
# room, and "golden-otter-4821" survives that better than three adjectives do.
CODE_DIGITS = 4


ADJECTIVES = [
    "golden", "silver", "quiet", "brave", "quick", "bright", "gentle", "bold",
    "calm", "cheerful", "clever", "cosmic", "cozy", "curious", "daring", "eager",
    "friendly", "happy", "honest", "jolly", "kind", "lively", "lucky", "merry",
    "mighty", "noble", "playful", "proud", "rapid", "sharp", "shiny", "smooth",
    "sturdy", "sunny", "swift", "tidy", "vivid", "warm", "wise", "zesty",
]

NOUNS = [
    "otter", "harbor", "meadow", "falcon", "willow", "comet", "lantern", "orchard",
    "beacon", "garden", "heron", "island", "maple", "oak", "pebble", "ridge",
    "river", "robin", "sparrow", "summit", "thistle", "trail", "valley", "violet",
    "wren", "badger", "canyon", "cedar", "dune", "ember", "fern", "glade",
    "grove", "hollow", "lagoon", "marsh", "moss", "prairie", "reef", "tundra",
]
