"""Society invite codes have to survive being guessed, not just being unique.

Found in the 2026-09-01 audit. `_generate_invite_code` drew an adjective-noun
pair from two 40-word lists - 1,600 possible codes. With ~21 codes live that is
roughly 1 valid code in every 76 guesses, so at /society/login's 10/min limit
somebody was inside *a* society account in about eight minutes.

`app/invite_words.py` called 1,600 "comfortable headroom for issuing codes to
every AIMS society", which is true and is about *collisions*. The number that
matters for guessing is space divided by codes in circulation, and nothing had
ever asked that question. These tests ask it.

What is behind the gate makes it worse than a read-only leak: a society code
can edit that society's shows and upload posters, and (until the same audit)
could read every contact detail in the Costumes & Props Exchange.
"""
import re

from conftest import seed_invite_code, seed_society, seed_user

from app.blueprints.admin.auth import CODE_DIGITS, _generate_invite_code
from app.invite_words import ADJECTIVES, NOUNS

# How many codes we might plausibly have live at once - every AIMS society
# several times over. The guessing odds below are computed against this rather
# than against today's count, so the test keeps meaning something as codes are
# issued.
PLAUSIBLE_LIVE_CODES = 500

# One valid code per this many guesses, at minimum. At /society/login's hourly
# cap that is centuries of sustained guessing; the old scheme managed minutes.
MIN_GUESSES_PER_HIT = 10_000


def test_the_code_space_is_large_enough_to_resist_guessing():
    space = len(ADJECTIVES) * len(NOUNS) * (10 ** CODE_DIGITS)
    assert space // PLAUSIBLE_LIVE_CODES >= MIN_GUESSES_PER_HIT, (
        f"{space:,} possible codes is too few: with {PLAUSIBLE_LIVE_CODES} live that is "
        f"1 valid code every {space // PLAUSIBLE_LIVE_CODES:,} guesses"
    )


def test_a_generated_code_has_the_documented_shape(app, db):
    """word-word-digits, lowercase, no ambiguity when read down a phone -
    which is the entire reason these aren't random strings."""
    with app.app_context():
        from app.db import get_db

        code = _generate_invite_code(get_db())

    assert re.fullmatch(rf"[a-z]+-[a-z]+-\d{{{CODE_DIGITS}}}", code), code
    adjective, noun, _ = code.split("-")
    assert adjective in ADJECTIVES
    assert noun in NOUNS


def test_generated_codes_are_not_all_the_same(app):
    """A generator that always returns one value would pass every other test
    here. Cheap insurance against a refactor dropping the randomness."""
    with app.app_context():
        from app.db import get_db

        db = get_db()
        codes = {_generate_invite_code(db) for _ in range(25)}
    assert len(codes) > 20


def test_the_generator_avoids_a_code_that_already_exists(app, db):
    society_id = seed_society(db)
    with app.app_context():
        from app.db import get_db

        live = get_db()
        taken = _generate_invite_code(live)
        live.execute(
            "INSERT INTO invite_codes (code, society_id) VALUES (?, ?)", (taken, society_id)
        )
        live.commit()
        assert _generate_invite_code(live) != taken


def test_codes_issued_under_the_old_scheme_still_work(client, db):
    """The 17 permanent two-word codes in production must not be locked out by
    this change - they are retired deliberately, not broken from under a
    society mid-season."""
    society_id = seed_society(db)
    seed_invite_code(db, code="golden-otter", society_id=society_id)

    resp = client.post("/society/login", data={"code": "golden-otter"})
    assert resp.status_code == 302
    assert "/society" in resp.headers["Location"]


def test_society_login_caps_sustained_guessing_not_just_bursts():
    """A per-minute limit alone lets a patient attacker guess forever. The
    hourly cap is the one that actually bounds the attempt count."""
    import inspect

    from app.blueprints import society

    # Flask-Limiter doesn't expose a decorator's limits consistently across
    # versions, so this asserts on the declaration itself rather than on
    # introspection that could quietly start returning nothing.
    source = inspect.getsource(society)
    assert "per hour" in source, "society login needs an hourly cap, not only a per-minute one"
    assert "10 per minute;40 per hour" in source
