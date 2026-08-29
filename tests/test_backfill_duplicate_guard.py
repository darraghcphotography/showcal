"""The bulk-backfill scripts must not re-insert a production we already hold
under a different capitalisation or punctuation.

All three backfills (`import_society_archives.py`,
`tullamore_castlerea_history_backfill.py`, `naas_history_backfill.py`) guarded
against duplicates with an exact `show = ?` comparison. That let case and
punctuation variants straight through, and it put four redundant bare rows into
production beside the award records they duplicated:

    Limerick   2011  "The Pirates of Penzance"  vs  "The Pirates Of Penzance"
    Tullamore  1990  "Oh! Susanna"              vs  "Oh Susanna!"
    Tullamore  2007  "Hello! Dolly"             vs  "Hello, Dolly!"
    Oyster Lane 2012 "Beauty And The Beast"     vs  "Beauty And The Beast" (award rows)

All three now compare with `app/similarity.py`'s `normalize_title`. That is
normalisation, never fuzzy matching - "Frozen" and "Frozen Jr." must still be
two different shows, which the last test here pins down.
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.similarity import normalize_title  # noqa: E402


def make_db(tmp_path):
    """A database with just enough schema for the backfill scripts to run."""
    path = tmp_path / "backfill.db"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE societies (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            region TEXT, section TEXT
        );
        CREATE TABLE historical_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER, show TEXT, society_name TEXT, society_id INTEGER,
            category_name TEXT, tier TEXT, result TEXT, reason TEXT,
            source TEXT NOT NULL DEFAULT 'import'
        );
    """)
    db.commit()
    db.close()
    return path


def add_society(path, society_id, name):
    db = sqlite3.connect(path)
    db.execute("INSERT INTO societies (id, name, region, section) VALUES (?, ?, 'Eastern', 'Gilbert')",
               (society_id, name))
    db.commit()
    db.close()


def add_result(path, society_id, name, year, show, category_name="Best Actress"):
    db = sqlite3.connect(path)
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, society_id, category_name) "
        "VALUES (?, ?, ?, ?, ?)",
        (year, show, name, society_id, category_name),
    )
    db.commit()
    db.close()


def rows_for(path, society_id):
    db = sqlite3.connect(path)
    rows = [r[0] for r in db.execute(
        "SELECT show FROM historical_results WHERE society_id = ? ORDER BY id", (society_id,))]
    db.close()
    return rows


def run_script(script, db_path, extra=()):
    result = subprocess.run(
        [sys.executable, str(ROOT / script), "--db", str(db_path), *extra],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


# The exact (society, year, title) pairs each script would try to insert, and
# the punctuation variant already on record that must block them.
@pytest.mark.parametrize("script,society_id,name,year,ours", [
    ("scripts/backfills/naas_history_backfill.py", 76, "Naas Musical Society",
     2010, "Fiddler On The Roof"),
    ("scripts/backfills/tullamore_castlerea_history_backfill.py", 119, "Tullamore Musical Society",
     1990, "Oh Susanna!"),
    ("scripts/backfills/tullamore_castlerea_history_backfill.py", 119, "Tullamore Musical Society",
     2007, "Hello, Dolly!"),
])
def test_punctuation_variant_does_not_create_a_second_row(tmp_path, script, society_id, name, year, ours):
    """The real bug: we already hold the production, spelled slightly
    differently, and the backfill inserts it again anyway."""
    path = make_db(tmp_path)
    add_society(path, society_id, name)
    add_result(path, society_id, name, year, ours)

    run_script(script, path)

    for_year = [s for s in rows_for(path, society_id)
                if normalize_title(s) == normalize_title(ours)]
    assert for_year == [ours], (
        f"{script} should have left the one row we already held ({ours!r}) alone, "
        f"got {for_year!r}"
    )


def test_archive_import_skips_a_case_variant_within_a_year(tmp_path):
    """import_society_archives.py's guard is a +/-1 year window as well as a
    title match - the Limerick 'Pirates' case that reached production."""
    import json

    path = make_db(tmp_path)
    add_society(path, 67, "Limerick Musical Society")
    add_result(path, 67, "Limerick Musical Society", 2011, "The Pirates Of Penzance")

    worklist = tmp_path / "worklist.json"
    worklist.write_text(json.dumps([{
        "society": "Limerick Musical Society",
        "productions": [{"year": 2011, "title": "The Pirates of Penzance"}],
    }]), encoding="utf-8")

    run_script("scripts/backfills/import_society_archives.py", path, ("--json", str(worklist)))

    assert rows_for(path, 67) == ["The Pirates Of Penzance"], (
        "the archive import re-inserted a title we already held, in a different case"
    )


def test_a_genuinely_different_show_is_still_inserted(tmp_path):
    """The guard must stay normalisation, not fuzzy matching. 'Frozen' and
    'Frozen Jr.' are two real, different shows on this circuit (CLAUDE.md), and
    holding one must never suppress the other."""
    import json

    path = make_db(tmp_path)
    add_society(path, 67, "Limerick Musical Society")
    add_result(path, 67, "Limerick Musical Society", 2011, "Frozen")

    worklist = tmp_path / "worklist.json"
    worklist.write_text(json.dumps([{
        "society": "Limerick Musical Society",
        "productions": [{"year": 2011, "title": "Frozen Jr."}],
    }]), encoding="utf-8")

    run_script("scripts/backfills/import_society_archives.py", path, ("--json", str(worklist)))

    assert sorted(rows_for(path, 67)) == ["Frozen", "Frozen Jr."], (
        "normalisation was applied too aggressively - 'Frozen Jr.' is a different show"
    )
