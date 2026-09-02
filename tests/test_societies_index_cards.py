"""/societies card contents (public.societies_list + _society_card_facts).

Two things these pin down, and they pull in opposite directions:

  1. The card has to say what a society has actually DONE. Before 2026-09-02 all
     143 of them carried a name, a region and a tier and nothing else, so the
     directory told a visitor almost nothing.

  2. It must not say what they have WON. Darragh's call, same day: these are
     volunteer societies, and a directory that ranks them by silverware becomes
     a league table rather than a record of who staged what.

The third is a performance guard. The obvious way to get per-society counts
onto a list page is a helper call inside the loop, which at 50 cards is 100
round trips - the exact per-row pattern that put an admin page into a 524 on
2026-08-19. test_query_count_does_not_grow_with_the_number_of_societies is what
stops that coming back.
"""
import sqlite3

import pytest

from conftest import seed_society


def _add_production(db, society_id, society_name, start_year, title):
    """A production plus the historical_results row that makes it 'on record'
    (see ON_RECORD_PRODUCTION) - a productions row alone is not counted."""
    db.execute(
        "INSERT INTO productions (season_start_year, society_key, title_key, season, "
        "society_id, society_name, title) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (start_year, f"id:{society_id}", title.lower(), f"{start_year % 100:02d}/{(start_year + 1) % 100:02d}",
         society_id, society_name, title),
    )
    production_id = db.execute("SELECT id FROM productions ORDER BY id DESC LIMIT 1").fetchone()["id"]
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_id, "
        "production_id, source) VALUES (?, 'Gilbert', 'Best Overall Show', ?, ?, ?, ?, 'manual')",
        (start_year + 1, "Winner", title, society_id, production_id),
    )


def test_a_card_shows_what_the_society_has_staged(client, db):
    society_id = seed_society(db, id=1, name="Wexford Light Opera Society")
    _add_production(db, society_id, "Wexford Light Opera Society", 1998, "Oliver!")
    _add_production(db, society_id, "Wexford Light Opera Society", 2011, "Chess")
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    assert "2" in body and "Productions" in body
    # Active since is the first year on record, +1 for the season's second half.
    assert "1999" in body
    assert "Active since" in body


def test_no_award_count_appears_anywhere_on_the_index(client, db):
    """The values test. Both productions below are Best Overall Show wins, so
    a card that reported wins would have something to report - it must not."""
    society_id = seed_society(db, id=1, name="Wexford Light Opera Society")
    _add_production(db, society_id, "Wexford Light Opera Society", 1998, "Oliver!")
    _add_production(db, society_id, "Wexford Light Opera Society", 2011, "Chess")
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    for phrase in ("award win", "Award win", "Best Overall Show", "Wins", "Trophy", "trophy"):
        assert phrase not in body, f"{phrase!r} must not appear on the societies index"


def test_a_card_names_the_next_announced_show(client, db):
    society_id = seed_society(db, id=1, name="Thurles Musical Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '26/27', 'Eastern', 'Come From Away', '2099-09-10', '2099-09-12', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    assert "Come From Away" in body
    assert "Next" in body


def test_a_past_show_is_not_offered_as_the_next_one(client, db):
    society_id = seed_society(db, id=1, name="Thurles Musical Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, moderation_status) "
        "VALUES (?, '20/21', 'Eastern', 'Long Gone Show', '2001-09-10', '2001-09-12', 'approved')",
        (society_id,),
    )
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    assert "Long Gone Show" not in body


def test_an_unapproved_submission_is_not_offered_as_the_next_show(client, db):
    """A member's pending submission must not surface on a public directory
    before a moderator has seen it."""
    society_id = seed_society(db, id=1, name="Thurles Musical Society")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status, source) VALUES (?, '26/27', 'Eastern', 'Unvetted Show', "
        "'2099-09-10', '2099-09-12', 'pending', 'submission')",
        (society_id,),
    )
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    assert "Unvetted Show" not in body


def test_the_placeholder_uses_the_societys_initials_not_one_letter(client, db):
    """The list is alphabetical, so a single first letter made the whole first
    column read A, A, A, B, B, B - decoration that repeated rather than a
    monogram. 176 of 194 societies have no logo, so this is the normal case."""
    seed_society(db, id=1, name="Thurles Musical Society")
    db.commit()

    body = client.get("/societies").get_data(as_text=True)
    assert "society-logo-placeholder" in body
    card = body[body.index("society-logo-placeholder"):]
    assert "TMS" in card[:200]


@pytest.mark.parametrize("society_count", [3, 40])
def test_query_count_does_not_grow_with_the_number_of_societies(client, db, monkeypatch, society_count):
    """The N+1 guard. Card facts are gathered in two aggregate queries for the
    whole page, run after pagination - not one lookup per row. If someone moves
    that work back inside the loop this fails loudly rather than quietly
    costing a round trip per society.

    Asserted as an absolute ceiling rather than a comparison between two runs,
    because a ceiling is what actually protects the page: 40 societies rendering
    in a handful of queries cannot be an N+1 whatever else changed.
    """
    for i in range(1, society_count + 1):
        seed_society(db, id=i, name=f"Society {i:03d}", region="Eastern")
        _add_production(db, i, f"Society {i:03d}", 2000 + (i % 20), f"Show {i}")
    db.commit()

    statements = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.set_trace_callback(
            lambda sql: statements.append(sql) if not sql.strip().upper().startswith("PRAGMA") else None
        )
        return conn

    monkeypatch.setattr(sqlite3, "connect", traced_connect)

    resp = client.get(f"/societies?per_page={society_count}")
    assert resp.status_code == 200
    assert f"Society {society_count:03d}" in resp.get_data(as_text=True)

    assert len(statements) < 30, (
        f"{len(statements)} queries to render {society_count} societies - "
        "that looks like a per-row lookup crept back in:\n"
        + "\n".join(statements[:40])
    )
