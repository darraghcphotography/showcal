"""C4 (small-items queue): app/invite_words.py's ADJECTIVES/NOUNS lists,
which admin.py's _generate_invite_code() draws from, had no test guarding
their basic shape (non-empty, lowercase, no accidental duplicates or
whitespace) before this."""
from app.invite_words import ADJECTIVES, NOUNS


def test_word_lists_are_non_empty():
    assert len(ADJECTIVES) > 0
    assert len(NOUNS) > 0


def test_word_lists_have_no_duplicates():
    assert len(ADJECTIVES) == len(set(ADJECTIVES))
    assert len(NOUNS) == len(set(NOUNS))


def test_words_are_plain_lowercase_with_no_stray_whitespace():
    for word in ADJECTIVES + NOUNS:
        assert word == word.strip()
        assert word == word.lower()
        assert word.isalpha()
