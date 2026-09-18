"""Reading a society name off an official AIMS page.

The pages are two-column tables flattened to text, so "who does this nominee
belong to?" is a proximity question, and proximity questions go wrong quietly.
Every case here is taken from a page actually in the harvest - the failures
especially, because each of them produced a confident wrong attribution before
it was fixed.
"""
from match_awards_to_archive import (
    attribution,
    attributions_for,
    normalise,
    shortest_name,
    title_words,
)


def flat(text):
    return " ".join(text.split())


def find(body, nominee, show=None):
    body = flat(body)
    start = body.lower().index(nominee.lower())
    return attribution(body, start, start + len(nominee), show)


def names_near(body, nominee, show=None):
    return [name for name, _show_too in find(body, nominee, show)]


def show_matched(body, nominee, show, society):
    return next(flag for name, flag in find(body, nominee, show) if name == society)


# --------------------------------------------------------------------------
# Trimming a match down to the name
# --------------------------------------------------------------------------

def test_the_show_title_is_trimmed_off_the_front():
    # /awards/nominations_gilbert.asp, 2004
    assert shortest_name("Hot Mikado Clane Musical Society") == "Clane Musical Society"


def test_trimming_stops_before_the_bare_descriptor():
    # Trimming to the last thing that parses leaves "Musical Society", which
    # names nobody - and it read as a confident verdict in the summary.
    assert shortest_name("Ko-Ko Hot Mikado Clane Musical Society") == "Clane Musical Society"
    assert shortest_name("Athenry Musical Society") == "Athenry Musical Society"


def test_a_town_suffix_is_part_of_the_name():
    assert shortest_name("Cabaret Cecilian Musical Society, Limerick") == \
        "Cecilian Musical Society, Limerick"


# --------------------------------------------------------------------------
# Which way the page reads
# --------------------------------------------------------------------------

def test_a_nominee_is_matched_to_the_society_printed_after_them():
    page = """
        BEST DIRECTOR GILBERT (Dick Meany Trophy) SULLIVAN (Tommy Ebbs Trophy)
        PAULA SHORT ANYTHING GOES Athenry Musical Society
    """
    assert "Athenry Musical Society" in names_near(page, "Paula Short", "Anything Goes")
    assert show_matched(page, "Paula Short", "Anything Goes", "Athenry Musical Society")


def test_a_nominee_is_matched_when_the_page_prints_the_society_first():
    # /awards/nominations_results_sullivan.asp, 2003, reads society-then-nominee.
    # Searching forward only, this returned the *next* row's society.
    page = """
        Best Stage Manager Athenry Musical Society Brian Brady Sugar
        Killarney Musical Society Karl O'Leary Annie Get Your Gun
    """
    assert "Athenry Musical Society" in names_near(page, "Brian Brady", "Sugar")


def test_both_neighbours_are_offered_rather_than_one_being_guessed():
    # The page reads: ... Athenry / Brian Brady / Sugar / Killarney / Karl ...
    # Athenry is his; Killarney belongs to the next row. Nothing local says so,
    # so both are returned and the tally across pages decides.
    page = ("Best Stage Manager Athenry Musical Society Brian Brady Sugar "
            "Killarney Musical Society Karl O'Leary Annie Get Your Gun")
    assert set(names_near(page, "Brian Brady", "Sugar")) == {
        "Athenry Musical Society", "Killarney Musical Society"}


def test_a_different_show_does_not_count_as_a_three_point_match():
    page = "Marie Cusack Hot Mikado Clane Musical Society"
    assert show_matched(page, "Marie Cusack", "My Fair Lady", "Clane Musical Society") is False


def test_a_nominee_with_no_society_anywhere_near_yields_nothing():
    assert find("Best Comedian Brendan Farrell as Ko-Ko", "Brendan Farrell") == []


# --------------------------------------------------------------------------
# Names that are the same name
# --------------------------------------------------------------------------

def test_the_two_spellings_the_old_site_used_are_one_society():
    assert normalise("Clara Mus Society") == normalise("Clara Musical Society")


def test_an_ampersand_spelling_is_the_same_society():
    assert normalise("Kilcock Musical & Dramatic Society") == \
        normalise("Kilcock Musical and Dramatic Society")


def test_two_different_societies_stay_different():
    # One letter apart, which is how they came to be merged in the first place.
    assert normalise("Clara Musical Society") != normalise("Clane Musical Society")


def test_title_words_ignore_articles():
    assert title_words("The King & I") == ["king", "i"]


# --------------------------------------------------------------------------
# Across pages
# --------------------------------------------------------------------------

def pages(*bodies):
    return [("f{}.txt".format(i), "http://aims.ie/p{}".format(i), "2004060{}".format(i),
             flat(body)) for i, body in enumerate(bodies)]


def test_the_same_nominee_on_two_pages_gives_both_attributions():
    found = attributions_for(
        pages("Marie Cusack Hot Mikado Clane Musical Society",
              "Marie Cusack Fiddler on the Roof Clara Musical Society"),
        "Marie Cusack", "Hot Mikado")

    assert set(found) == {normalise("Clane Musical Society"), normalise("Clara Musical Society")}


def test_a_three_point_hit_beats_a_bare_name_hit_for_the_same_society():
    found = attributions_for(
        pages("Marie Cusack something else Clane Musical Society",
              "Marie Cusack Hot Mikado Clane Musical Society"),
        "Marie Cusack", "Hot Mikado")

    _name, show_too, _capture, _source = found[normalise("Clane Musical Society")]
    assert show_too
