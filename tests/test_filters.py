"""app/filters.py's irish_datetime - converts a stored UTC timestamp
(SQLite's datetime('now'), or __init__.py's deployed_at) to real Irish
local time via zoneinfo, rather than just reformatting the string as-is.
Ireland alternates GMT/BST, so this has to actually shift the clock, not
apply a fixed offset - see the 2026-08-05 bug where "Latest version
deployed" was showing exactly one hour behind during BST."""
from app.filters import initials, irish_datetime, place_label


def test_bst_summer_timestamp_shifts_forward_one_hour():
    assert irish_datetime("2026-08-05 20:52:00") == "05 Aug 2026, 21:52"


def test_gmt_winter_timestamp_unchanged():
    assert irish_datetime("2026-01-05 20:52:00") == "05 Jan 2026, 20:52"


def test_blank_value_passes_through():
    assert irish_datetime("") == ""
    assert irish_datetime(None) is None


def test_malformed_value_falls_back_unchanged():
    assert irish_datetime("not a real timestamp") == "not a real timestamp"


def test_initials_skips_connecting_words():
    assert initials("The Hired Man") == "HM"
    assert initials("Shrek the Musical") == "SM"


def test_place_label_drops_the_duplicate_when_town_equals_county():
    assert place_label("Dublin", "Dublin") == "Dublin"


def test_place_label_joins_a_real_town_and_county():
    assert place_label("Ballyshannon", "Donegal") == "Ballyshannon, Donegal"


def test_place_label_handles_a_missing_half():
    assert place_label("Ballyshannon", None) == "Ballyshannon"
    assert place_label(None, "Donegal") == "Donegal"
    assert place_label(None, None) == ""


def test_initials_two_words_no_stopwords():
    assert initials("Calamity Jane") == "CJ"
    assert initials("Sweeney Todd") == "ST"


def test_initials_single_word_uses_own_first_two_letters():
    assert initials("Oklahoma!") == "OK"


def test_initials_blank_value():
    assert initials("") == "?"
    assert initials(None) == "?"


def test_initials_ignores_leading_punctuation():
    assert initials("42nd Street") == "4S"
