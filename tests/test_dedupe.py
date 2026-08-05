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
