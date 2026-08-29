"""Show detail page restructure (2026-08-29).

After the society/homepage redesign this became the weakest public page, and
it is where every homepage card lands. Four things were wrong with what it
chose to emphasise:

  - Three stacked meta paragraphs (society/season/tier, the circuit summary,
    a "see every production" link) ran before the page said anything about
    the show itself.
  - Director / Musical Director / Choreographer rendered unconditionally, so
    a historical show printed three rows of "-" - stating that we know
    nothing, on a page whose problem was already empty space.
  - "Buy tickets" was a plain link in the middle of the definition list,
    between the venue and the director, on a page whose entire purpose for an
    upcoming show is that link.
  - The society's "About" blurb sat above the show's own dates and venue.
"""
from datetime import date, timedelta

from conftest import seed_society


def _add_show(db, society_id, show="Oliver!", days_ahead=None, **cols):
    opening = (date.today() + timedelta(days=days_ahead)).isoformat() if days_ahead is not None else None
    fields = {
        "society_id": society_id, "season": "26/27", "region": "Eastern", "show": show,
        "source": "import", "moderation_status": "approved", "opening_date": opening,
    }
    fields.update(cols)
    keys = ", ".join(fields)
    marks = ", ".join("?" * len(fields))
    db.execute(f"INSERT INTO shows ({keys}) VALUES ({marks})", tuple(fields.values()))
    return db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]


def test_credits_with_no_value_are_not_rendered(client, db):
    society_id = seed_society(db)
    show_id = _add_show(db, society_id, director="Jane Doe")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Director" in body
    assert "Jane Doe" in body
    # The two with nothing on record are absent entirely, not rendered as "-".
    assert "Musical Director" not in body
    assert "Choreographer" not in body


def test_a_show_with_no_credits_at_all_renders_none_of_the_rows(client, db):
    society_id = seed_society(db)
    show_id = _add_show(db, society_id)
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    for label in ("Musical Director", "Choreographer"):
        assert label not in body


def test_all_three_credits_render_when_present(client, db):
    society_id = seed_society(db)
    show_id = _add_show(
        db, society_id, director="A Director",
        musical_director="An MD", choreographer="A Choreographer",
    )
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "A Director" in body and "An MD" in body and "A Choreographer" in body


def test_an_upcoming_show_gets_a_ticket_call_to_action(client, db):
    society_id = seed_society(db)
    show_id = _add_show(db, society_id, days_ahead=30, ticket_url="https://tickets.example/wss")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "ticket-cta" in body
    assert "Buy tickets" in body


def test_a_past_show_does_not_get_the_call_to_action(client, db):
    """The link is kept - it's on record - but a run that has already
    finished should not be shouting "Buy tickets"."""
    society_id = seed_society(db)
    show_id = _add_show(db, society_id, season="23/24", days_ahead=-400,
                        ticket_url="https://tickets.example/old")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "ticket-cta" not in body
    assert "Ticket link" in body


def test_the_byline_carries_society_season_and_tier(client, db):
    society_id = seed_society(db)
    show_id = _add_show(db, society_id, section="Gilbert")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    byline = body.split('class="show-byline"')[1].split("</p>")[0]
    assert "Test Society" in byline
    assert "26/27" in byline
    assert "tier-dot-gilbert" in byline


def test_the_society_blurb_comes_after_the_shows_own_facts(client, db):
    """It is a show page. The dates and venue are what someone came for."""
    society_id = seed_society(db)
    db.execute("UPDATE societies SET about = 'A long-running society.' WHERE id = ?", (society_id,))
    show_id = _add_show(db, society_id, days_ahead=30, venue="The Example Theatre")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "A long-running society." in body
    assert body.index("The Example Theatre") < body.index("A long-running society.")
