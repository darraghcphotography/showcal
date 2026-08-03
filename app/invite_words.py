"""Word lists for auto-generated invite codes (admin.py's _generate_invite_code) -
kept in its own module, same pattern as season.py/similarity.py.

An adjective + noun pair (e.g. "silver-otter") is easier to read aloud, type,
and remember than a random alphanumeric string. Deliberately plain, common
words with no profanity or homophones - a code that's ambiguous when spoken
over the phone defeats the point. ~40 of each gives ~1,600 combinations,
comfortable headroom for issuing codes to every AIMS society.
"""

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
