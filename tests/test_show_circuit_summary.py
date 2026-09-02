"""The "Staged N times..." line on a show page (public.show_detail).

Found in the 2026-09-02 design sweep, on the live site. It read:

    Staged 11 times since 2026, most recently by Portrush Music Society (2027)

and both numbers were wrong.

  - `season_start_year + 1` is the year a season ENDS. St. Agnes Choral Society
    opened Come From Away on 2025-09-04 and the page printed 2026.

  - "most recently" ordered by season alone, so inside a season the winner was
    whichever row SQLite happened to return first. It picked a May 2026 run,
    printed it as 2027, and ignored four later productions - two of which had
    not happened yet, so "most recently" was naming the future.

A production belongs to a season, not a year. The line now states a span of
seasons, and "most recently" is restricted to productions that have actually
opened, ordered by their real date.
"""
from conftest import seed_society

# Future seasons here are 2030s, never 2090s. The app rebuilds the productions
# table from shows (see app/productions_build.py), and the rebuild derives
# season_start_year from the season string through season_start_year(), whose
# 50-pivot resolves "98/99" to 1998. A 2098 fixture is therefore silently
# rewritten into the distant past on the first request - which made two of these
# tests pass for entirely the wrong reason before this note existed.
FUTURE_START_YEAR = 2030
FUTURE_DATE = "2031-03-01"
LATER_FUTURE_DATE = "2031-05-01"


def _add_production(db, society_id, society_name, start_year, title, opening_date=None):
    season = f"{start_year % 100:02d}/{(start_year + 1) % 100:02d}"
    db.execute(
        "INSERT INTO productions (season_start_year, society_key, title_key, season, "
        "society_id, society_name, title) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (start_year, f"id:{society_id}", title.lower().strip(), season,
         society_id, society_name, title),
    )
    production_id = db.execute("SELECT id FROM productions ORDER BY id DESC LIMIT 1").fetchone()["id"]
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status, production_id) VALUES (?, ?, 'Eastern', ?, ?, ?, 'approved', ?)",
        (society_id, season, title, opening_date, opening_date, production_id),
    )
    show_id = db.execute("SELECT id FROM shows ORDER BY id DESC LIMIT 1").fetchone()["id"]
    return production_id, show_id


def test_an_autumn_production_is_not_labelled_with_the_following_year(client, db):
    """The original bug in its simplest form: a September 2025 opening belongs
    to the 25/26 season and must never be printed as "2026"."""
    a = seed_society(db, id=1, name="St. Agnes Choral Society")
    b = seed_society(db, id=2, name="Bravo Theatre Group")
    _add_production(db, a, "St. Agnes Choral Society", 2025, "Come From Away", "2025-09-04")
    _, show_id = _add_production(db, b, "Bravo Theatre Group", 2025, "Come From Away", "2025-09-10")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    summary = body[body.index("Staged"):body.index("Staged") + 260]
    assert "25/26" in summary
    assert "2026" not in summary, f"a season-end year leaked back in: {summary!r}"


def test_most_recently_never_names_a_production_that_has_not_happened(client, db):
    """The worst half of the bug: the page claimed a society had "most
    recently" staged a show that has not opened yet."""
    past = seed_society(db, id=1, name="Past Society")
    future = seed_society(db, id=2, name="Future Society")
    viewing = seed_society(db, id=3, name="Viewing Society")
    _add_production(db, past, "Past Society", 2020, "Chess", "2021-03-01")
    _add_production(db, future, "Future Society", FUTURE_START_YEAR, "Chess", FUTURE_DATE)
    _, show_id = _add_production(db, viewing, "Viewing Society", 2021, "Chess", "2022-03-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    summary = body[body.index("Staged"):body.index("Staged") + 300]
    assert "Future Society" not in summary
    assert "Past Society" in summary


def test_most_recently_picks_the_latest_by_date_within_a_season(client, db):
    """Ordering by season alone left the choice to SQLite. Two productions in
    the same season must be separated by their real opening dates."""
    early = seed_society(db, id=1, name="Early Society")
    late = seed_society(db, id=2, name="Late Society")
    viewing = seed_society(db, id=3, name="Viewing Society")
    # Same season, months apart. Inserted early-first so a naive query that
    # keeps insertion order would get it wrong.
    _add_production(db, early, "Early Society", 2020, "Evita", "2020-09-01")
    _add_production(db, late, "Late Society", 2020, "Evita", "2021-04-01")
    _, show_id = _add_production(db, viewing, "Viewing Society", 2019, "Evita", "2019-10-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    summary = body[body.index("Staged"):body.index("Staged") + 300]
    assert "Late Society" in summary
    assert "Early Society" not in summary


def test_a_span_of_one_season_reads_as_in_not_from_to(client, db):
    a = seed_society(db, id=1, name="Society A")
    b = seed_society(db, id=2, name="Society B")
    _add_production(db, a, "Society A", 2020, "Oliver!", "2020-11-01")
    _, show_id = _add_production(db, b, "Society B", 2020, "Oliver!", "2021-02-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    summary = body[body.index("Staged"):body.index("Staged") + 260]
    assert "in 20/21" in summary
    assert " to " not in summary


def test_a_span_across_seasons_names_both_ends(client, db):
    a = seed_society(db, id=1, name="Society A")
    b = seed_society(db, id=2, name="Society B")
    _add_production(db, a, "Society A", 1998, "The Mikado", "1998-11-01")
    _, show_id = _add_production(db, b, "Society B", 2015, "The Mikado", "2016-03-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    summary = body[body.index("Staged"):body.index("Staged") + 260]
    assert "98/99" in summary and "15/16" in summary


def test_a_title_staged_only_once_gets_no_circuit_line(client, db):
    """Nothing to compare it to - the line would just restate the page."""
    a = seed_society(db, id=1, name="Society A")
    _, show_id = _add_production(db, a, "Society A", 2020, "Rare Title", "2020-11-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Staged" not in body


def test_every_other_production_being_in_the_future_drops_only_the_most_recent_clause(client, db):
    """The count and the span are still true and still worth showing; there is
    simply nothing to call "most recent" yet."""
    future = seed_society(db, id=1, name="Future Society")
    viewing = seed_society(db, id=2, name="Viewing Society")
    _add_production(db, future, "Future Society", FUTURE_START_YEAR, "New Title", FUTURE_DATE)
    _, show_id = _add_production(db, viewing, "Viewing Society", FUTURE_START_YEAR, "New Title", LATER_FUTURE_DATE)
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Staged 2 times" in body
    assert "most recently" not in body


# --- "Elsewhere on ShowCal" -------------------------------------------------
#
# The other half of the same finding: an upcoming show has no review and no
# awards yet - which is every show in the current season - so the page ran out
# after the credits and left a screenful of nothing above the footer.


def test_a_show_with_nothing_related_gets_no_empty_headings(client, db):
    """Three headings over three blanks would be worse than the gap it fixes."""
    a = seed_society(db, id=1, name="Lonely Society")
    _, show_id = _add_production(db, a, "Lonely Society", 2020, "Only Ever Once", "2020-11-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Elsewhere on ShowCal" not in body


def test_other_societies_who_staged_the_same_title_are_listed(client, db):
    a = seed_society(db, id=1, name="Society A")
    b = seed_society(db, id=2, name="Society B")
    _add_production(db, a, "Society A", 2018, "Chess", "2018-11-01")
    _, show_id = _add_production(db, b, "Society B", 2020, "Chess", "2020-11-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Elsewhere on ShowCal" in body
    assert "Others who staged Chess" in body
    assert "Society A" in body


def test_the_show_being_viewed_is_not_listed_among_its_own_related(client, db):
    a = seed_society(db, id=1, name="Society A")
    b = seed_society(db, id=2, name="Society B")
    _add_production(db, a, "Society A", 2018, "Chess", "2018-11-01")
    _, show_id = _add_production(db, b, "Society B", 2020, "Chess", "2020-11-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    related = body[body.index("Elsewhere on ShowCal"):]
    assert "Society B" not in related


def test_more_from_this_society_lists_their_other_shows(client, db):
    a = seed_society(db, id=1, name="Society A")
    _add_production(db, a, "Society A", 2018, "Oklahoma!", "2018-11-01")
    _, show_id = _add_production(db, a, "Society A", 2020, "Chess", "2020-11-01")
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "More from Society A" in body
    assert "Oklahoma!" in body


def test_an_unapproved_show_is_not_surfaced_as_related(client, db):
    """A pending submission must not reach a public page sideways."""
    a = seed_society(db, id=1, name="Society A")
    _, show_id = _add_production(db, a, "Society A", 2020, "Chess", "2020-11-01")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status, source) VALUES (1, '21/22', 'Eastern', 'Unvetted Show', "
        "'2021-11-01', '2021-11-05', 'pending', 'submission')"
    )
    db.commit()

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "Unvetted Show" not in body
