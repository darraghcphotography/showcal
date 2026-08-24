"""app/filters.py's irish_datetime - converts a stored UTC timestamp
(SQLite's datetime('now'), or __init__.py's deployed_at) to real Irish
local time via zoneinfo, rather than just reformatting the string as-is.
Ireland alternates GMT/BST, so this has to actually shift the clock, not
apply a fixed offset - see the 2026-08-05 bug where "Latest version
deployed" was showing exactly one hour behind during BST."""
from app.filters import irish_datetime, show_initials


def test_bst_summer_timestamp_shifts_forward_one_hour():
    assert irish_datetime("2026-08-05 20:52:00") == "05 Aug 2026, 21:52"


def test_gmt_winter_timestamp_unchanged():
    assert irish_datetime("2026-01-05 20:52:00") == "05 Jan 2026, 20:52"


def test_blank_value_passes_through():
    assert irish_datetime("") == ""
    assert irish_datetime(None) is None


def test_malformed_value_falls_back_unchanged():
    assert irish_datetime("not a real timestamp") == "not a real timestamp"


def test_show_initials_skips_connecting_words():
    assert show_initials("The Hired Man") == "HM"
    assert show_initials("Shrek the Musical") == "SM"


def test_show_initials_two_words_no_stopwords():
    assert show_initials("Calamity Jane") == "CJ"
    assert show_initials("Sweeney Todd") == "ST"


def test_show_initials_single_word_uses_own_first_two_letters():
    assert show_initials("Oklahoma!") == "OK"


def test_show_initials_blank_value():
    assert show_initials("") == "?"
    assert show_initials(None) == "?"


def test_show_initials_ignores_leading_punctuation():
    assert show_initials("42nd Street") == "4S"
