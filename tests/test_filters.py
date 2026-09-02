"""app/filters.py's irish_datetime - converts a stored UTC timestamp
(SQLite's datetime('now'), or __init__.py's deployed_at) to real Irish
local time via zoneinfo, rather than just reformatting the string as-is.
Ireland alternates GMT/BST, so this has to actually shift the clock, not
apply a fixed offset - see the 2026-08-05 bug where "Latest version
deployed" was showing exactly one hour behind during BST."""
from app.filters import initials, irish_datetime, place_label, society_monogram


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


def test_society_monogram_uses_the_letters_a_committee_calls_itself_by():
    """Distinct from initials(), which caps at two because it fills a poster
    box. On /societies the placeholder is the normal case (176 of 194 have no
    logo), so two letters shared across dozens of "... Musical Society" names
    would identify nothing."""
    assert society_monogram("Wexford Light Opera Society") == "WLOS"
    assert society_monogram("Thurles Musical Society") == "TMS"
    # Connecting words are skipped, same stoplist as initials() - which also
    # means a hyphenated place name loses its joiner: Carrick-on-Suir gives
    # C then S, not C-O-S. That is the stoplist working as intended on a name
    # it was not written for, and it is what a member would write anyway.
    assert society_monogram("The Odd Theatre Company") == "OTC"
    assert society_monogram("Carrick-on-Suir Musical Society") == "CSMS"


def test_society_monogram_stays_a_monogram_on_a_very_long_name():
    """Capped at four - past that it stops reading as a monogram."""
    assert len(society_monogram("Maynooth University Musical and Dramatics Society")) == 4


def test_society_monogram_handles_a_one_word_or_empty_name():
    assert society_monogram("Boyle") == "BO"
    assert society_monogram("") == "?"
    assert society_monogram(None) == "?"
