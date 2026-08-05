"""app/dedupe.py's find_candidates - used to be capped at 60 results
internally, which made the admin dashboard's "possible duplicate titles"
count read as permanently stuck at 60: resolving the top pair just let the
next-highest one below the cutoff take its place. Now returns every
candidate uncapped; callers slice for display (see admin.duplicate_titles())."""
from app.dedupe import find_candidates


def test_returns_more_than_the_old_hardcoded_cap_when_that_many_exist():
    # "Show N" vs "Show N Extra" is a word-subset match (one extra word) for
    # every N - cheap way to generate more than the old cap's worth of
    # genuine candidates (title text also fuzzy-matches across different Ns,
    # so the real total comfortably clears 60 - not asserting an exact count).
    titles = set()
    for i in range(70):
        titles.add(f"Show {i}")
        titles.add(f"Show {i} Extra")

    candidates = find_candidates(titles, dismissed=set())
    assert len(candidates) > 60


def test_does_not_flag_unrelated_titles_sharing_a_generic_suffix():
    """Real false positives from the live queue (2026-08-05) - short/generic
    titles matched purely because they share a common trailing phrase like
    "the musical", which dominates the character-similarity ratio for a
    short string even though the actual distinctive words share nothing."""
    bad_pairs = [
        ("Ghost the Musical", "Snoopy The Musical"),
        ("Ragtime The Musical", "Titanic The Musical"),
        ("Bare", "Cabaret"),
        ("Fame: The Musical", "Titanic The Musical"),
        ("Nativity! The Musical", "Snoopy The Musical"),
    ]
    titles = {t for pair in bad_pairs for t in pair}
    assert find_candidates(titles, dismissed=set()) == []


def test_still_flags_genuine_near_duplicates():
    good_pairs = [
        ("Nativity", "Nativity! The Musical"),
        ("Oliver", "Oliver!"),
        ("Fiddler on the Roof", "Fidler on the Roof"),
        ("Frozen", "Frozen Jr."),
    ]
    titles = {t for pair in good_pairs for t in pair}
    candidates = find_candidates(titles, dismissed=set())
    flagged_pairs = {tuple(sorted((a, b))) for a, b, _ in candidates}
    for pair in good_pairs:
        assert tuple(sorted(pair)) in flagged_pairs


def test_default_threshold_is_70_percent():
    """Darragh's own call (2026-08-05) after reviewing the live queue - below
    70% was mostly noise (coincidental character overlap between otherwise
    unrelated titles), not real near-duplicates."""
    # A pair below 70% (pure ratio, no word-subset match) must not appear...
    below = find_candidates({"Xyzabc Theatre", "Abcxyz Players"}, dismissed=set())
    assert below == []

    # ...but one at/above 70% still does.
    above = find_candidates({"Fiddler on the Roof", "Fidler on the Roof"}, dismissed=set())
    assert len(above) == 1


def test_count_drops_as_pairs_are_resolved():
    titles = {"Nativity", "Nativity! The Musical", "Oliver", "Oliver!"}
    before = find_candidates(titles, dismissed=set())
    assert len(before) == 2

    # Simulate what _merge_titles/_dismiss_pair actually do: a merge removes
    # one title from the pool entirely, a dismiss adds the pair to `dismissed`.
    titles_after_merge = titles - {"Oliver"}
    after_merge = find_candidates(titles_after_merge, dismissed=set())
    assert len(after_merge) == 1

    dismissed = {tuple(sorted(("Nativity", "Nativity! The Musical")))}
    after_dismiss = find_candidates(titles, dismissed=dismissed)
    assert len(after_dismiss) == 1
