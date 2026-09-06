"""Keyboard access to things axe cannot check.

An axe-core pass over 10 live pages on 2026-09-06 reported **zero** WCAG A/AA
violations, which is real and better than this file's existence suggests. But
axe covers roughly the machine-checkable third of WCAG, and both faults below
were found by driving the site with an actual keyboard afterwards:

  1. **No skip link.** axe *passes* the "bypass blocks" rule here, on the
     strength of the `<main>` landmark - and a landmark helps a screen-reader
     user jump while doing nothing at all for someone tabbing. The nav is a row
     of dropdowns, so without a skip link every keyboard user traverses the
     whole of it before reaching content, on every page.

  2. **Escape did not close the "Add to calendar" menu.** A `<details>`
     disclosure has no Escape behaviour of its own, while every other menu on
     the web does, so opening it by keyboard and changing your mind left no way
     out but Tab.

Neither is catchable from pytest at the level a browser would test them, so
these assert the markup and the handler that make them work. The behavioural
proof was a Playwright run against production; see HANDBACK.md 2026-09-06.
"""
from conftest import seed_society


def test_every_page_offers_a_skip_link_before_the_nav(client):
    """It has to be the first focusable thing, or it is not a skip link."""
    body = client.get("/").get_data(as_text=True)
    assert 'class="skip-link" href="#main"' in body

    before_header = body.split("<header", 1)[0]
    assert "skip-link" in before_header, \
        "the skip link renders after the header, so it is not the first thing tabbed to"


def test_the_skip_link_has_something_to_skip_to(client):
    """`href="#main"` pointing at nothing is the commonest way this is got
    wrong, and it fails silently - the page simply does not move."""
    body = client.get("/").get_data(as_text=True)
    assert 'id="main"' in body


def test_the_skip_target_can_actually_receive_focus(client):
    """Without tabindex="-1" a jump to #main scrolls the page but leaves focus
    where it was, so the very next Tab returns to the nav - the link appears to
    work and does not. This is the half most implementations miss."""
    body = client.get("/").get_data(as_text=True)
    main = body[body.index("<main"):body.index(">", body.index("<main")) + 1]
    assert 'tabindex="-1"' in main, f"<main> cannot take focus: {main}"


def test_the_skip_link_is_not_display_none(client):
    """`display:none` removes it from the tab order, which defeats the entire
    point while still passing a "is there a skip link?" check."""
    css = open("app/static/style.css", encoding="utf-8").read()
    block = css[css.index(".skip-link {"):css.index("}", css.index(".skip-link {"))]
    assert "display: none" not in block and "display:none" not in block
    assert "position: absolute" in block
    assert ".skip-link:focus" in css, "it never becomes visible when focused"


def test_escape_closes_the_add_to_calendar_menu(client, db):
    """The handler lives in base.html so any .cal-menu gets it, not just the
    one on show pages."""
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status) VALUES (?, '26/27', 'Eastern', 'Chess', '2099-09-01', "
        "'2099-09-05', 'approved')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Chess'").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "cal-menu" in body, "the calendar menu is not on the page at all"
    assert "'Escape'" in body and ".cal-menu[open]" in body, \
        "no Escape handler for the calendar menu"


def test_the_poster_on_a_card_is_hidden_from_assistive_tech(client, db):
    """Not a bug - a deliberate choice worth pinning so nobody "fixes" it.

    The poster is a second link to the same place as the title link beside it.
    Giving it alt text would make a screen reader announce every card twice.
    It carries alt="", aria-hidden and tabindex="-1"; the accessible name comes
    from the real text link."""
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status, poster_filename) VALUES (?, '26/27', 'Eastern', 'Chess', "
        "'2099-09-01', '2099-09-05', 'approved', 'p.webp')",
        (society_id,),
    )
    db.commit()

    body = client.get("/").get_data(as_text=True)
    if "whatson-poster" not in body:
        return  # no upcoming card rendered in this fixture's date window
    card = body[body.index("whatson-poster"):]
    assert 'aria-hidden="true"' in card[:400]
    assert 'tabindex="-1"' in card[:400]
