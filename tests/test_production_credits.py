"""C4 (small-items queue): production_credits.py's suggest_credits/
suggest_venue are pure regex functions over free-form review text - no
Flask, no database - and had no direct test at all before this."""
from app.production_credits import suggest_credits, suggest_venue


def test_suggest_credits_finds_all_three_roles():
    text = (
        "Director Thomas O'Leary brought real energy to the production. "
        "Musical Director, Shane Farrell kept the band tight throughout. "
        "Choreographer Aisling Doyle gave the ensemble numbers real polish."
    )
    result = suggest_credits(text)
    assert result["director"] == "Thomas O'Leary"
    assert result["musical_director"] == "Shane Farrell"
    assert result["choreographer"] == "Aisling Doyle"


def test_suggest_credits_ignores_an_honorific_as_a_name():
    text = "Musical Director Roisin Heenan led the orchestra; Mr Milford sang the lead."
    result = suggest_credits(text)
    assert result["musical_director"] == "Roisin Heenan"


def test_suggest_credits_does_not_confuse_musical_director_with_director():
    text = "Musical Director Roisin Heenan led the orchestra."
    result = suggest_credits(text)
    assert result["director"] is None


def test_suggest_credits_handles_possessive_phrasing():
    text = "Niamh McGowan's choreography lifted every number in the second act."
    result = suggest_credits(text)
    assert result["choreographer"] == "Niamh McGowan"


def test_suggest_credits_returns_all_none_for_blank_text():
    result = suggest_credits("")
    assert result == {"director": None, "musical_director": None, "choreographer": None}


def test_suggest_venue_matches_a_building_shaped_name_verbatim_in_text():
    text = "The production ran at the Dean Crowe Theatre to a packed house."
    result = suggest_venue(text, known_venues=["Dean Crowe Theatre", "Galway"])
    assert result == "Dean Crowe Theatre"


def test_suggest_venue_skips_a_bare_town_name():
    """A plain town name (no building word) is deliberately never suggested,
    even if it appears in the text - false-positives on hometown mentions."""
    text = "Several cast members hail from Galway and travelled for rehearsals."
    result = suggest_venue(text, known_venues=["Galway"])
    assert result is None


def test_suggest_venue_returns_none_with_no_match():
    text = "A lovely evening all round."
    result = suggest_venue(text, known_venues=["Dean Crowe Theatre"])
    assert result is None
