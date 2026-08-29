"""Society show-history redesign (2026-08-29). Reported as "the Thurles page
is a mess - past and present productions unclear, a lot of word vomit".

Three things this pins down, all only visible at real data volume (Thurles:
37 productions, 73 award rows, 25 wins):

  - History is grouped into decades with a per-era win count, so a 37-row
    list has a spine instead of being one flat wall.
  - A win renders as its own gold pill; nominations collapse into a single
    count chip. Previously every nomination was its own beige pill, so row
    heights ranged from 1 to 7 lines and the wins were unfindable.
  - The page renders each production ONCE. It used to emit a wide table and
    a duplicate .table-cards block, which is the pairing that kept producing
    the "content vanishes below 600px" bug (see test_table_cards_mobile.py).
"""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_show(db, society_id, season, show, opening_date=None, poster=None):
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, "
        "opening_date, poster_filename) VALUES (?, ?, 'Eastern', ?, 'import', 'approved', ?, ?)",
        (society_id, season, show, opening_date, poster),
    )
    return db.execute("SELECT id FROM shows WHERE show = ?", (show,)).fetchone()["id"]


def _add_award(db, society_id, year, show, category, result, nominee=None):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, "
        "society_id, nominee_name, source) VALUES (?, 'Gilbert', ?, ?, ?, 'Test Society', ?, ?, 'manual')",
        (year, category, result, show, society_id, nominee),
    )


def test_history_is_grouped_into_decades(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "14/15", "Curtains")
    _add_show(db, society_id, "04/05", "The Scarlet Pimpernel")
    _add_show(db, society_id, "94/95", "West Side Story")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "2010s" in body
    assert "2000s" in body
    assert "1990s" in body
    # Newest era first, and the 1990s decade must not sort above the 2010s -
    # the season-string trap this page has hit twice before.
    assert body.index("2010s") < body.index("2000s") < body.index("1990s")


def test_each_era_reports_its_own_win_count(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "14/15", "Curtains")
    _add_award(db, society_id, 2015, "Curtains", "Best Overall Show", "Winner")
    _add_award(db, society_id, 2015, "Curtains", "Best Actor", "Winner", nominee="Aodan Fox")
    _add_award(db, society_id, 2015, "Curtains", "Best Lighting", "Nominee")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "2 wins" in body


def test_a_win_is_its_own_pill_and_nominations_collapse_to_a_count(client, db):
    """The density fix. Three nominations must not render three pills."""
    society_id = seed_society(db)
    _add_show(db, society_id, "14/15", "Curtains")
    _add_award(db, society_id, 2015, "Curtains", "Best Overall Show", "Winner")
    for category in ("Best Lighting", "Best Sets", "Best Programme"):
        _add_award(db, society_id, 2015, "Curtains", category, "Nominee")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert body.count("pill-win") == 1
    assert "Best Overall Show" in body
    assert "3 nominations" in body
    assert body.count("pill-nom") == 1
    # The collapsed chip still carries every category, in its tooltip - the
    # information is hidden, not dropped.
    assert "Best Lighting" in body and "Best Sets" in body


def test_a_single_nomination_is_not_pluralised(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "14/15", "Curtains")
    _add_award(db, society_id, 2015, "Curtains", "Best Lighting", "Nominee")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "1 nomination<" in body or "1 nomination\n" in body or "1 nomination " in body
    assert "1 nominations" not in body


def test_each_production_is_rendered_once(client, db):
    """The wide-table-plus-duplicate-cards pattern is gone. A second copy is
    now a bug, not the responsive fallback."""
    society_id = seed_society(db)
    _add_show(db, society_id, "14/15", "Curtains")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert body.count(">Curtains</a>") == 1
    assert "table-cards" not in body


def test_next_production_card_uses_the_poster_when_there_is_one(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "26/27", "Come From Away",
              opening_date="2099-09-10", poster="abc123.webp")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "abc123.webp" in body
    assert "next-poster is-placeholder" not in body


def test_next_production_card_falls_back_to_initials_without_a_poster(client, db):
    society_id = seed_society(db)
    _add_show(db, society_id, "26/27", "Come From Away", opening_date="2099-09-10")
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert "next-poster is-placeholder" in body


def test_the_tier_is_a_dot_not_the_word_repeated_on_every_row(client, db):
    """"Gilbert" printed on 30 consecutive rows was pure noise - the tier is
    now a coloured dot, with the name kept as its title attribute."""
    society_id = seed_society(db)
    for season, show in (("14/15", "Curtains"), ("13/14", "Sister Act"), ("12/13", "Titanic")):
        db.execute(
            "INSERT INTO shows (society_id, season, region, show, section, source, moderation_status) "
            "VALUES (?, ?, 'Eastern', ?, 'Gilbert', 'import', 'approved')",
            (society_id, season, show),
        )
    db.commit()

    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    history = body.split("Show history")[1]
    assert history.count("tier-dot-gilbert") == 3
    assert history.count(">Gilbert<") == 0


def test_a_moderator_still_gets_an_edit_link_per_row(client, db):
    society_id = seed_society(db)
    admin_id = seed_user(db)
    show_id = _add_show(db, society_id, "14/15", "Curtains")
    db.commit()

    login_as(client, admin_id)
    body = client.get(f"/societies/{society_id}").get_data(as_text=True)
    assert f"/admin/shows/{show_id}/edit" in body
