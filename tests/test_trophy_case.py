"""The trophy-case summary on a society's public page: win / runner-up /
third-place counts for Best Overall Show specifically, plus a total win
count across all award categories (app/blueprints/public.py:society_detail).
"""
from conftest import seed_society


def _add_result(db, society_id, year, category_name, result):
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, society_id, source) "
        "VALUES (?, 'Gilbert', ?, ?, ?, 'manual')",
        (year, category_name, result, society_id),
    )


def test_trophy_case_counts(client, db):
    society_id = seed_society(db)
    _add_result(db, society_id, 2023, "Best Overall Show", "Winner")
    _add_result(db, society_id, 2022, "Best Overall Show", "Winner")
    _add_result(db, society_id, 2021, "Best Director", "Winner")
    _add_result(db, society_id, 2020, "Best Overall Show", "Second Place")
    _add_result(db, society_id, 2019, "Best Overall Show", "Third Place")
    _add_result(db, society_id, 2018, "Best Overall Show", "Third Place")
    _add_result(db, society_id, 2017, "Best Overall Show", "Nominee")
    db.commit()

    resp = client.get(f"/societies/{society_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "🏆 2" in body and "Best Overall Show" in body
    assert "🥈 1" in body and "runner-up" in body
    assert "🥉 2" in body and "third place" in body
    assert "3 award wins" in body
    assert "Active since 2021" in body


def test_trophy_case_absent_when_no_awards(client, db):
    society_id = seed_society(db)
    db.commit()

    resp = client.get(f"/societies/{society_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "trophy-case" not in body
