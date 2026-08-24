"""str.title() capitalizes the first letter after ANY non-alphabetic
character, including a digit - "25TH ANNUAL..." became "25Th Annual...".
Ordinals are common in show titles, so extract_historical_reviews.py's
_title_case() undoes just that one artifact (see its own docstring) - found
2026-08-24 and fixed for both new extractions and the 7 already-affected
rows in historical_reviews_pilot.json / production (fix_ordinal_titlecasing.py)."""
from extract_historical_reviews import _title_case


def test_does_not_capitalize_the_letter_after_a_digit():
    assert _title_case("THE 25TH ANNUAL PUTNAM COUNTY SPELLING BEE") == \
        "The 25th Annual Putnam County Spelling Bee"


def test_ordinal_in_the_middle_of_a_title():
    assert _title_case("42ND STREET") == "42nd Street"


def test_still_capitalizes_normal_words():
    assert _title_case("THE SOUND OF MUSIC") == "The Sound Of Music"


def test_multiple_ordinals_in_one_title():
    assert _title_case("A 1ST AND 2ND CHANCE") == "A 1st And 2nd Chance"
