"""The thresholds in scripts/backfills/guess_society_lifecycle.py.

All 194 societies had a NULL lifecycle_status, so the coverage checklist could
not tell a live society from a panto company that has never appeared in a single
result. The backfill fills those NULLs from one signal - the last year we have
any record of a society producing anything - and these are the lines it draws.

The asymmetry matters more than the exact years: a wrong "Active" costs one
wasted email, a wrong "Closed" quietly drops a living society off the chasing
list. Anything borderline is expected to land on the generous side.
"""
from guess_society_lifecycle import ACTIVE_SINCE, DORMANT_SINCE, classify, season_year


def status(has_upcoming=False, last_year=None, section="Gilbert"):
    return classify(has_upcoming, last_year, section)[0]


def test_an_upcoming_production_is_active_whatever_else_is_true():
    assert status(has_upcoming=True) == "Active"
    assert status(has_upcoming=True, last_year=1998) == "Active"
    assert status(has_upcoming=True, section="Inactive") == "Active"


def test_recently_produced_is_active_even_with_nothing_announced():
    assert status(last_year=2026) == "Active"
    assert status(last_year=ACTIVE_SINCE) == "Active"


def test_a_few_quiet_years_is_dormant_not_closed():
    """Covid sits inside this window - silence here is a question, not an answer."""
    assert status(last_year=ACTIVE_SINCE - 1) == "Dormant"
    assert status(last_year=DORMANT_SINCE) == "Dormant"


def test_long_silence_is_closed():
    assert status(last_year=DORMANT_SINCE - 1) == "Closed"
    assert status(last_year=2012) == "Closed"


def test_nothing_on_record_and_not_in_a_tier_is_out_of_scope():
    """The panto companies, youth theatres and school societies on the list."""
    assert status(section="Inactive") == "Out of scope"


def test_nothing_on_record_but_in_a_tier_stays_a_question():
    """In scope by definition, invisible in our data - that is not an answer,
    so it must stay chaseable rather than being written off."""
    assert status(section="Gilbert") == "Unverified"
    assert status(section="Sullivan") == "Unverified"


def test_every_status_is_one_the_database_actually_allows():
    """schema.sql CHECKs the column, so a typo here would fail at write time."""
    allowed = {"Active", "Dormant", "Closed", "Out of scope", "Unverified"}
    cases = [
        (True, None, "Gilbert"), (False, 2026, "Gilbert"), (False, 2020, "Sullivan"),
        (False, 2011, "Gilbert"), (False, None, "Inactive"), (False, None, "Sullivan"),
    ]
    for case in cases:
        assert classify(*case)[0] in allowed, case


def test_every_guess_explains_itself():
    """The reason is printed beside each judgement call, so a moderator
    correcting one can see what it was based on."""
    for case in [(True, None, "Gilbert"), (False, 2011, "Gilbert"), (False, None, "Inactive")]:
        _, why = classify(*case)
        assert why and isinstance(why, str)


def test_season_year_reads_the_end_of_a_season_string():
    assert season_year("25/26") == 2026
    assert season_year("99/00") == 2000
    assert season_year(None) is None
    assert season_year("2026") is None
    assert season_year("garbage/x") is None
