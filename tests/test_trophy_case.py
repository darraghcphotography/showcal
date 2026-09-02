"""The trophy-case summary on a society's public page: win / runner-up /
third-place counts for Best Overall Show specifically, plus a total win
count across all award categories (app/blueprints/public.py:society_detail).

Moved out of the page header and into an "Awards on record" section above
Show history on 2026-09-02 - Darragh's call that award counts must not be a
society's headline. The counts themselves are unchanged and still required to
be present and correct; what changed is where on the page they sit, which
these tests deliberately do not pin down.
"""
import re

from conftest import seed_society


def _add_result(db, society_id, year, category_name, result, show=None):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_id, source) "
        "VALUES (?, 'Gilbert', ?, ?, ?, ?, 'manual')",
        (year, category_name, result, show, society_id),
    )


def test_trophy_case_counts(client, db):
    """"Active since" is the first year this society is on record, not the
    year of their first win. It used to be read off a MIN(year) inside a query
    scoped to result = 'Winner' - so this fixture, whose earliest record is a
    2017 nomination, reported 2021. It now comes from the productions table
    (82 real society pages move earlier as a result, and 35 that had no value
    at all gain one)."""
    society_id = seed_society(db)
    _add_result(db, society_id, 2023, "Best Overall Show", "Winner", show="Chess")
    _add_result(db, society_id, 2022, "Best Overall Show", "Winner", show="Carousel")
    _add_result(db, society_id, 2021, "Best Director", "Winner", show="Oliver!")
    _add_result(db, society_id, 2020, "Best Overall Show", "Second Place", show="Cabaret")
    _add_result(db, society_id, 2019, "Best Overall Show", "Third Place", show="Evita")
    _add_result(db, society_id, 2018, "Best Overall Show", "Third Place", show="Annie")
    _add_result(db, society_id, 2017, "Best Overall Show", "Nominee", show="Grease")
    db.commit()

    resp = client.get(f"/societies/{society_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "🏆 2" in body and "Best Overall Show" in body
    assert "🥈 1" in body and "runner-up" in body
    assert "🥉 2" in body and "third place" in body
    assert "3 award wins" in body

    # "Active since" stayed in the header - it describes how long the society
    # has been going, not what it won, so it is not part of the awards move.
    # It is a stat tile rather than a pill now, hence the markup match: a bare
    # "2017" elsewhere on the page must not satisfy this.
    assert re.search(
        r'<span class="stat-value">2017</span>\s*<span class="stat-label">Active since</span>',
        body,
    )


def test_awards_are_not_in_the_page_header(client, db):
    """The point of the move: a visitor landing on a society page sees the work
    first. The award block must render below the show-history heading's section
    start, not up beside the name and logo."""
    society_id = seed_society(db)
    _add_result(db, society_id, 2023, "Best Overall Show", "Winner", show="Chess")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)

    hero_end = body.index("Show history")
    assert body.index("awards-record") < hero_end          # sits above Show history
    assert body.index("detail-hero") < body.index("awards-record")   # but below the hero
    # No award number inside the header block itself.
    hero = body[body.index("detail-hero"):body.index("awards-record")]
    assert "award win" not in hero
    assert "Best Overall Show" not in hero


def test_trophy_case_absent_when_no_awards(client, db):
    society_id = seed_society(db)
    db.commit()

    resp = client.get(f"/societies/{society_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "trophy-case" not in body
