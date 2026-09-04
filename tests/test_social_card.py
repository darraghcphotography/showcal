"""The shareable show card (app/social_card.py, public.show_card).

An image a society downloads and *posts* to its own Instagram - not to be
confused with `og-card.png`, which is what a scraper renders when someone
pastes a ShowCal link. Darragh conflated the two on 2026-09-04, reasonably:
both get called "the share card". The link preview already worked; this did
not exist.

Why it was built: 175 of 194 societies have never uploaded a poster, and every
approach so far has *asked* them for one. This is the only thing on the board
that gives them something first - a card is worth posting, and the card gets
better if they upload their poster.

Two layout faults are pinned here because both shipped in the first draft and
both are invisible to a test that only checks "did a PNG come back":

  1. The playbill clipped a long title to "VERYBODY'" - the shrink loop checked
     line *count* but not line *width*, and the text is centred, so one
     unbreakable word overflowed at both ends.
  2. On the story shape every size was keyed to canvas height, so at 1920 tall
     the countdown was drawn on top of the venue line and the QR caption ran
     off the right edge.
"""
import io

import pytest
from PIL import Image

from app import social_card
from conftest import seed_society

SHOW = {
    "show": "Come From Away",
    "society_name": "Thurles Musical Society",
    "opening_date": "2099-09-10",
    "closing_date": "2099-09-13",
    "venue": "The Premier Hall, Thurles",
}


def _render(size="post", **over):
    show = dict(SHOW)
    kw = {k: over.pop(k) for k in ("url", "today", "poster_path") if k in over}
    show.update(over)
    return Image.open(io.BytesIO(social_card.render_card(show, size=size, **kw)))


@pytest.mark.parametrize("size,expected", [
    ("post", (1200, 630)),
    ("square", (1080, 1080)),
    ("story", (1080, 1920)),
])
def test_each_shape_is_exactly_the_size_the_platform_wants(size, expected):
    """A wrong ratio is centre-cropped differently by each platform, which is
    how you end up with a card nobody designed."""
    assert _render(size).size == expected


def test_the_card_is_flat_rgb_so_a_cdn_cannot_recolour_it():
    """The lesson from the WhatsApp preview: an alpha channel is an invitation
    for Cloudflare's image optimisation to composite against its own
    background. Every brand image on this site is flat RGB for that reason."""
    im = _render()
    assert im.mode == "RGB"
    assert "transparency" not in im.info


def test_a_long_title_is_not_clipped_by_the_playbill():
    """The "VERYBODY'" bug. With no poster the title is typeset into the
    playbill panel and centred; a word wider than the panel bled off both
    edges. Checked by looking at the panel's own edge columns - if the title
    overflows, ink lands in them."""
    im = _render(show="Everybody's Talking About Jamie").convert("RGB")
    w, h = im.size
    panel_w = int(w * 0.34)
    # A two-pixel gutter at each edge of the playbill panel must stay flat
    # background. Text bleeding out of the panel shows up here first.
    for x in (0, 1, panel_w - 3, panel_w - 2):
        column = [im.getpixel((x, y)) for y in range(int(h * 0.2), int(h * 0.8), 5)]
        assert len(set(column)) == 1, f"ink at x={x} - the playbill title is overflowing its panel"


def test_the_story_shape_does_not_collide_its_footer_with_its_text():
    """Sizes were keyed to canvas height, so the 1920-tall story trebled every
    size and the countdown landed on the venue line. The regression is visible
    as ink in the band that must separate the meta lines from the footer."""
    im = _render("story").convert("RGB")
    w, h = im.size
    # The gap the layout reserves between the text block and the footer.
    band = [im.getpixel((int(w * 0.07), y)) for y in range(int(h * 0.79), int(h * 0.82))]
    assert len(set(band)) == 1, "text and footer are overlapping on the story card"


def test_nothing_is_drawn_outside_the_canvas_edges():
    """The QR caption ran off the right edge on the story shape. Every margin
    around the *text* side should be clean background.

    Only the text side: the poster panel is meant to bleed to the edge, and it
    sits in a different place per shape - down the left on post and square,
    across the top on story. Checking the whole right edge fails on story for
    a correct reason, which is what the first version of this test did."""
    for size in ("post", "square", "story"):
        im = _render(size).convert("RGB")
        w, h = im.size
        text_top = int(h * 0.55) if size == "story" else 0
        right = [im.getpixel((w - 2, y)) for y in range(text_top, h, 7)]
        bottom = [im.getpixel((x, h - 2)) for x in range(int(w * 0.4), w, 7)]
        assert len(set(right)) == 1, f"{size}: something is drawn against the right edge"
        assert len(set(bottom)) == 1, f"{size}: something is drawn against the bottom edge"


def test_the_countdown_counts_down_and_a_past_show_simply_has_none():
    from datetime import date
    show = dict(SHOW, opening_date="2099-09-10")
    assert social_card._days_to(show["opening_date"], today=date(2099, 9, 4)) == 6
    assert social_card._days_to(show["opening_date"], today=date(2099, 9, 10)) == 0
    assert social_card._days_to("2020-01-01", today=date(2099, 9, 4)) is None


def test_a_single_night_run_reads_as_one_date_not_a_range():
    assert social_card._date_line("2099-09-10", None).startswith("10 September")
    assert social_card._date_line("2099-09-10", "2099-09-10").startswith("10 September")
    assert social_card._date_line("2099-09-10", "2099-09-13") == "10-13 September 2099"


def test_a_run_across_two_months_names_both():
    assert social_card._date_line("2099-09-29", "2099-10-02") == "29 September - 2 October 2099"


def test_the_filename_names_the_show_and_the_society():
    assert social_card.card_filename(SHOW) == "come-from-away-thurles-musical-society-card.png"


# --- the route ---

def _seed(db, status="approved", hidden=0, poster=None):
    society_id = seed_society(db, name="Thurles Musical Society")
    if hidden:
        db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "venue, moderation_status, poster_filename) VALUES (?, '26/27', 'Eastern', "
        "'Come From Away', '2099-09-10', '2099-09-13', 'The Premier Hall, Thurles', ?, ?)",
        (society_id, status, poster),
    )
    db.commit()
    return db.execute("SELECT id FROM shows ORDER BY id DESC LIMIT 1").fetchone()["id"]


def test_the_card_url_serves_a_png(client, db):
    show_id = _seed(db)
    r = client.get(f"/shows/{show_id}/card.png")
    assert r.status_code == 200
    assert r.mimetype == "image/png"
    assert Image.open(io.BytesIO(r.data)).size == (1200, 630)


def test_the_size_parameter_picks_the_shape(client, db):
    show_id = _seed(db)
    r = client.get(f"/shows/{show_id}/card.png?size=story")
    assert Image.open(io.BytesIO(r.data)).size == (1080, 1920)


def test_an_unknown_size_falls_back_rather_than_erroring(client, db):
    """Same "invalid param -> default" convention as the rest of the site."""
    show_id = _seed(db)
    r = client.get(f"/shows/{show_id}/card.png?size=billboard")
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.data)).size == (1200, 630)


def test_an_unapproved_show_has_no_card(client, db):
    assert client.get(f"/shows/{_seed(db, status='pending')}/card.png").status_code == 404


def test_a_hidden_societys_show_has_no_card(client, db):
    assert client.get(f"/shows/{_seed(db, hidden=1)}/card.png").status_code == 404


def test_the_card_is_cached_but_not_forever(client, db):
    """It carries a countdown, so a permanently-cached copy goes stale and
    then wrong."""
    show_id = _seed(db)
    cache = client.get(f"/shows/{show_id}/card.png").headers["Cache-Control"]
    assert "max-age=3600" in cache


def test_a_missing_poster_file_still_produces_a_card(client, db):
    """The row can name a file the disk does not have - a restored database, a
    half-finished upload. The card must fall back to the playbill rather than
    500, because it is public and a broken image is worse than a plain one."""
    show_id = _seed(db, poster="does-not-exist.webp")
    r = client.get(f"/shows/{show_id}/card.png")
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.data)).size == (1200, 630)
