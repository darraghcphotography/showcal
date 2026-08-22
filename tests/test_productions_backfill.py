"""The productions table and the rebuild that fills it (app/productions_build.py).

Covers the two things that make the table worth having - one shared identity
for a staging across shows/historical_results/historical_reviews, and a
four-digit season year that can tell 1912 apart from 2012 - plus the
verification pass that's supposed to stop a bad rebuild from committing.
"""
import sqlite3

import pytest

from app import productions_build
from app.productions import production_key, society_key
from conftest import seed_society


def _add_show(db, society_id=1, season="23/24", show="Oliver!", region="Eastern", source="import", **kw):
    cols = dict(
        society_id=society_id, season=season, region=region, show=show, source=source,
        moderation_status=kw.pop("moderation_status", "approved"),
    )
    cols.update(kw)
    names = ", ".join(cols)
    marks = ", ".join("?" * len(cols))
    return db.execute(f"INSERT INTO shows ({names}) VALUES ({marks})", list(cols.values())).lastrowid


def _add_award(db, year=2024, show="Oliver!", society_name="Test Society", society_id=1,
               category_name="Best Overall Show", result="Winner"):
    return db.execute(
        "INSERT INTO historical_results (year, show, society_name, society_id, category_name, result, source) "
        "VALUES (?, ?, ?, ?, ?, ?, 'manual')",
        (year, show, society_name, society_id, category_name, result),
    ).lastrowid


def _add_review(db, show_id, season="22/23", show_raw="Oliver!", society_raw="Test Society"):
    return db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, show_id, moderation_status) "
        "VALUES (?, ?, ?, 'A fine show.', ?, 'approved')",
        (season, show_raw, society_raw, show_id),
    ).lastrowid


def _build(db):
    db.commit()
    return productions_build.build(db)


def _productions(db):
    return db.execute("SELECT * FROM productions ORDER BY season_start_year, title").fetchall()


# ---------------------------------------------------------------- identity

def test_a_show_and_its_award_records_become_one_production(db):
    seed_society(db)
    show_id = _add_show(db, season="23/24", show="Oliver!")
    _add_award(db, year=2024, show="Oliver!")
    _add_award(db, year=2024, show="Oliver!", category_name="Best Director", result="Nominee")
    _build(db)

    rows = _productions(db)
    assert len(rows) == 1
    assert rows[0]["season"] == "23/24"
    assert rows[0]["season_start_year"] == 2023
    assert db.execute("SELECT production_id FROM shows WHERE id = ?", (show_id,)).fetchone()[0] == rows[0]["id"]
    assert db.execute(
        "SELECT COUNT(*) FROM historical_results WHERE production_id = ?", (rows[0]["id"],)
    ).fetchone()[0] == 2


def test_title_casing_and_punctuation_do_not_split_a_production(db):
    seed_society(db)
    _add_show(db, season="23/24", show="Made In Dagenham")
    _add_award(db, year=2024, show="made in dagenham!")
    _build(db)

    assert len(_productions(db)) == 1


def test_same_title_different_season_stays_two_productions(db):
    seed_society(db)
    _add_show(db, season="23/24", show="Oliver!")
    _add_show(db, season="24/25", show="Oliver!")
    _build(db)

    assert [r["season"] for r in _productions(db)] == ["23/24", "24/25"]


def test_an_unmatched_historical_society_still_gets_a_production(db):
    """71 society names in the real archive have never matched a societies
    row. They staged real productions and have to count, so they key on the
    normalized name instead of an id."""
    _add_award(db, year=1994, show="Carousel", society_name="Long Gone Operatic Society", society_id=None)
    _build(db)

    rows = _productions(db)
    assert len(rows) == 1
    assert rows[0]["society_id"] is None
    assert rows[0]["society_name"] == "Long Gone Operatic Society"
    assert rows[0]["society_key"] == "name:long gone operatic society"


def test_matched_and_unmatched_society_keys_never_collide(db):
    seed_society(db, id=1, name="Test Society")
    assert society_key(1, "Test Society") == "id:1"
    assert society_key(None, "Test Society") == "name:test society"


def test_a_row_with_no_title_names_no_production(db):
    """A "society slotted for this season, title TBA" placeholder isn't a
    production yet, and an award record with a blank show column names none."""
    seed_society(db)
    _add_show(db, season="25/26", show=None)
    _add_award(db, year=1988, show=None, society_name="Test Society")
    _build(db)

    assert _productions(db) == []
    assert production_key(1, None, 2025, None) is None
    assert production_key(1, None, 2025, "   ") is None


# ---------------------------------------------------------------- the century bug

def test_a_1912_award_year_is_not_filed_under_2012(db):
    """The bug this table exists to make impossible. The app's own 'yy/yy'
    round-trip sent every pre-2001 award year to a year that doesn't exist
    (1912 -> '11/12' -> 2012, 2000 -> '99/00' -> 2100), which hid 823 real
    productions from the Statistics page."""
    seed_society(db, id=1, name="Wexford Light Opera Society", region="South-East")
    _add_award(db, year=1912, show="The Mikado", society_name="Wexford Light Opera Society")
    _add_show(db, society_id=1, season="11/12", show="Legally Blonde", region="South-East")
    _build(db)

    rows = _productions(db)
    assert [(r["season_start_year"], r["title"]) for r in rows] == [
        (1911, "The Mikado"),
        (2011, "Legally Blonde"),
    ]
    # Both legitimately display as the same season label - which is exactly
    # why the label can't be the identity.
    assert {r["season"] for r in rows} == {"11/12"}


def test_the_1999_2000_rollover_survives(db):
    seed_society(db)
    _add_award(db, year=2000, show="Grease")
    _build(db)

    row = _productions(db)[0]
    assert row["season_start_year"] == 1999
    assert row["season"] == "99/00"


# ---------------------------------------------------------------- reviews

def test_a_review_reaches_its_production_through_its_show(db):
    seed_society(db)
    show_id = _add_show(db, season="22/23", show="Chicago", source="historical")
    _add_review(db, show_id, season="22/23", show_raw="Chicago")
    _build(db)

    production_id = _productions(db)[0]["id"]
    assert db.execute(
        "SELECT production_id FROM historical_reviews WHERE show_id = ?", (show_id,)
    ).fetchone()[0] == production_id


def test_an_unmatched_review_gets_no_production(db):
    """A review still in the moderation queue has no show yet, so it has no
    production either - the same state, not a separate one to invent a
    weaker matching rule for."""
    seed_society(db)
    _add_show(db, season="22/23", show="Chicago")
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, moderation_status) "
        "VALUES ('22/23', 'Chicago', 'Test Society', 'text', 'pending')"
    )
    _build(db)

    assert db.execute(
        "SELECT COUNT(*) FROM historical_reviews WHERE production_id IS NULL"
    ).fetchone()[0] == 1


# ---------------------------------------------------------------- display values

def test_a_shows_row_wins_over_an_award_record_for_the_displayed_title(db):
    seed_society(db)
    _add_show(db, season="23/24", show="Ghost: The Musical")
    _add_award(db, year=2024, show="Ghost the Musical")
    _build(db)

    assert _productions(db)[0]["title"] == "Ghost: The Musical"


def test_region_resolves_from_the_shows_snapshot_first(db):
    """shows.region is the society's region *at the time* of that staging,
    which is the accurate historical value even after a society moves."""
    seed_society(db, id=1, name="Test Society", region="Eastern")
    _add_show(db, season="23/24", show="Oliver!", region="Midlands")
    _build(db)

    assert _productions(db)[0]["region"] == "Midlands"


def test_region_falls_back_to_a_confirmed_guess_for_a_defunct_society(db):
    _add_award(db, year=1994, show="Carousel", society_name="Long Gone Operatic Society", society_id=None)
    db.execute(
        "INSERT INTO historical_society_regions (society_name, confirmed_region) VALUES (?, 'Western')",
        ("Long Gone Operatic Society",),
    )
    _build(db)

    assert _productions(db)[0]["region"] == "Western"


def test_region_stays_null_when_nothing_resolves_it(db):
    _add_award(db, year=1994, show="Carousel", society_name="Long Gone Operatic Society", society_id=None)
    _build(db)

    assert _productions(db)[0]["region"] is None


# ---------------------------------------------------------------- rebuilds

def test_rebuilding_is_idempotent_and_keeps_production_ids(db):
    seed_society(db)
    _add_show(db, season="23/24", show="Oliver!")
    _add_award(db, year=2024, show="Oliver!")
    _build(db)
    before = {(r["id"], r["title"]) for r in _productions(db)}

    _build(db)
    _build(db)

    assert {(r["id"], r["title"]) for r in _productions(db)} == before


def test_a_new_source_row_adds_a_production_without_disturbing_the_others(db):
    seed_society(db)
    _add_show(db, season="23/24", show="Oliver!")
    _build(db)
    first_id = _productions(db)[0]["id"]

    _add_show(db, season="24/25", show="Cabaret")
    _build(db)

    rows = _productions(db)
    assert len(rows) == 2
    assert rows[0]["id"] == first_id


def test_a_production_whose_last_source_row_is_gone_is_removed(db):
    seed_society(db)
    show_id = _add_show(db, season="23/24", show="Oliver!")
    _add_show(db, season="24/25", show="Cabaret")
    _build(db)
    assert len(_productions(db)) == 2

    db.execute("DELETE FROM shows WHERE id = ?", (show_id,))
    _build(db)

    assert [r["title"] for r in _productions(db)] == ["Cabaret"]


def test_retitling_a_show_moves_it_to_a_new_production(db):
    seed_society(db)
    show_id = _add_show(db, season="23/24", show="Oliver!")
    _build(db)

    db.execute("UPDATE shows SET show = 'Cabaret' WHERE id = ?", (show_id,))
    _build(db)

    rows = _productions(db)
    assert [r["title"] for r in rows] == ["Cabaret"]
    assert db.execute("SELECT production_id FROM shows WHERE id = ?", (show_id,)).fetchone()[0] == rows[0]["id"]


# ---------------------------------------------------------------- staying current

def test_ensure_current_rebuilds_only_when_the_sources_moved(db, monkeypatch):
    """The table is derived, so a page reading it checks first. That check has
    to be free when nothing changed - it runs on a page request."""
    seed_society(db)
    _add_show(db, season="23/24", show="Oliver!")
    db.commit()

    assert productions_build.ensure_current(db) is True
    assert len(_productions(db)) == 1
    assert productions_build.ensure_current(db) is False

    _add_show(db, season="24/25", show="Cabaret")
    db.commit()
    assert productions_build.ensure_current(db) is True
    assert len(_productions(db)) == 2


def test_mark_stale_forces_a_rebuild_the_fingerprint_would_miss(db):
    """historical_results has no updated_at, so an award record edited in
    place is invisible to the freshness check - the routes that do that say
    so explicitly."""
    seed_society(db)
    award_id = _add_award(db, year=2024, show="Oliver!")
    db.commit()
    productions_build.ensure_current(db)
    assert [r["title"] for r in _productions(db)] == ["Oliver!"]

    db.execute("UPDATE historical_results SET show = 'Cabaret' WHERE id = ?", (award_id,))
    db.commit()
    assert productions_build.ensure_current(db) is False   # the gap this exists to close

    productions_build.mark_stale(db)
    assert productions_build.ensure_current(db) is True
    assert [r["title"] for r in _productions(db)] == ["Cabaret"]


def test_correcting_a_skeleton_title_in_admin_marks_the_index_stale(client, db):
    """The title-correction route rewrites shows.show without bumping
    updated_at, so it has to tell the freshness check itself."""
    from conftest import seed_user

    seed_society(db)
    show_id = _add_show(db, season="22/23", show="Olivr!", source="historical")
    db.commit()
    productions_build.ensure_current(db)
    assert [r["title"] for r in _productions(db)] == ["Olivr!"]

    seed_user(db)
    client.post("/admin/login", data={"username": "mod", "password": "password123"})
    client.post(f"/admin/historical-shows/{show_id}/apply-title-match", data={"title": "Oliver!"})

    productions_build.ensure_current(db)
    assert [r["title"] for r in _productions(db)] == ["Oliver!"]


# ---------------------------------------------------------------- verification

def test_verification_rejects_a_rebuild_that_did_not_land(db, monkeypatch):
    """The verify pass has to be able to fail, or it's decoration. Simulate a
    write that silently dropped rows and confirm the run refuses."""
    seed_society(db)
    _add_show(db, season="23/24", show="Oliver!")
    db.commit()

    real_write = productions_build.write

    def sabotaged(conn, productions):
        result = real_write(conn, productions)
        conn.execute(
            "INSERT INTO productions (season_start_year, society_key, title_key, season, society_name, title) "
            "VALUES (1999, 'id:1', 'ghost row', '99/00', 'Test Society', 'Ghost Row')"
        )
        return result

    monkeypatch.setattr(productions_build, "write", sabotaged)
    with pytest.raises(productions_build.VerificationError) as excinfo:
        productions_build.build(db)
    assert "productions row count" in str(excinfo.value)
    assert "productions with no source row" in str(excinfo.value)


def test_verification_rejects_two_shows_rows_under_one_production(db, monkeypatch):
    """Two shows rows sharing a production would mean the natural key is
    merging genuinely distinct stagings - the most damaging way this can go
    wrong, so it's checked explicitly rather than assumed."""
    seed_society(db)
    _add_show(db, season="23/24", show="Oliver!")
    second = _add_show(db, season="24/25", show="Cabaret")
    db.commit()

    real_write = productions_build.write

    def sabotaged(conn, productions):
        result = real_write(conn, productions)
        first = conn.execute("SELECT production_id FROM shows ORDER BY id LIMIT 1").fetchone()[0]
        conn.execute("UPDATE shows SET production_id = ? WHERE id = ?", (first, second))
        return result

    monkeypatch.setattr(productions_build, "write", sabotaged)
    with pytest.raises(productions_build.VerificationError) as excinfo:
        productions_build.build(db)
    assert "more than one shows row" in str(excinfo.value)


def test_the_unique_index_physically_prevents_a_duplicate_production(db):
    db.execute(
        "INSERT INTO productions (season_start_year, society_key, title_key, season, society_name, title) "
        "VALUES (2023, 'id:1', 'oliver', '23/24', 'Test Society', 'Oliver!')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO productions (season_start_year, society_key, title_key, season, society_name, title) "
            "VALUES (2023, 'id:1', 'oliver', '23/24', 'Test Society', 'Oliver!')"
        )
