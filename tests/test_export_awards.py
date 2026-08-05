"""export_awards.py - the inverse of import_awards.py, for pulling a
correction made via /admin/awards back into the tracked
"AIMS_Awards - Results.csv" (see export_csv.py for the same pattern
applied to societies/shows)."""
import csv
import subprocess
import sqlite3
import sys
from pathlib import Path

import export_awards

ROOT = Path(__file__).resolve().parent.parent

AWARDS_CSV = """Year,SchemeName,Tier,CategoryName,Category,ResultText,NomineeName,Role,Showname,ResolvedSocietyName,Society,Region,Reason,Title
1977,Gilbert,,Best Overall Show,,Winner,,,Fiddler on the Roof,Test Society,,,,
1977,Sullivan,,Best Director,,Winner,Jane Doe,,Oklahoma!,Other Society,,,,
"""


def _write(path, content):
    path.write_text(content, encoding="utf-8-sig")


def test_export_reproduces_imported_rows(tmp_path):
    db_path = tmp_path / "awards.db"
    csv_in = tmp_path / "awards_in.csv"
    _write(csv_in, AWARDS_CSV)

    conn = sqlite3.connect(db_path)
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, nominee_name) "
        "VALUES (1977, 'Gilbert', 'Best Overall Show', 'Winner', 'Fiddler on the Roof', 'Test Society', NULL)"
    )
    conn.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, nominee_name) "
        "VALUES (1977, 'Sullivan', 'Best Director', 'Winner', 'Oklahoma!', 'Other Society', 'Jane Doe')"
    )
    conn.commit()

    csv_out = tmp_path / "awards_out.csv"
    n = export_awards.export_awards(conn, csv_out)
    conn.close()
    assert n == 2

    with open(csv_out, encoding="utf-8-sig", newline="") as f:
        rows = {r["Showname"]: r for r in csv.DictReader(f)}
    assert rows["Fiddler on the Roof"]["SchemeName"] == "Gilbert"
    assert rows["Oklahoma!"]["NomineeName"] == "Jane Doe"


def test_export_includes_manually_edited_rows_not_just_manually_added(tmp_path):
    """A moderator EDITING an existing award record (not just adding a new
    one) sets its source to 'manual' too - export must not filter those
    out, or the whole point of the backup (capturing corrections) breaks."""
    db_path = tmp_path / "awards.db"
    conn = sqlite3.connect(db_path)
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_name, source) "
        "VALUES (2020, 'Best Overall Show', 'Winner', 'Oliver!', 'Old Name', 'manual')"
    )
    conn.commit()

    csv_out = tmp_path / "awards_out.csv"
    n = export_awards.export_awards(conn, csv_out)
    conn.close()
    assert n == 1

    with open(csv_out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["ResolvedSocietyName"] == "Old Name"


def test_export_then_reimport_round_trips(tmp_path):
    db_path = tmp_path / "awards.db"
    conn = sqlite3.connect(db_path)
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, reason) "
        "VALUES (1999, 'Gilbert', 'Best Overall Show', 'Winner', 'Grease', 'Round-trip Society', 'A great show')"
    )
    conn.commit()

    csv_out = tmp_path / "awards_out.csv"
    export_awards.export_awards(conn, csv_out)
    conn.close()

    # Re-import through the real CLI (not a re-implementation of its
    # parsing logic), so this test reflects exactly what import_awards.py
    # actually does with the exported file.
    reimport_db = tmp_path / "reimport.db"
    subprocess.run(
        [sys.executable, str(ROOT / "import_awards.py"), "--db", str(reimport_db), "--csv", str(csv_out)],
        check=True, capture_output=True, text=True,
    )

    conn3 = sqlite3.connect(reimport_db)
    row = conn3.execute(
        "SELECT tier, category_name, result, show, society_name, reason FROM historical_results"
    ).fetchone()
    conn3.close()
    assert row == ("Gilbert", "Best Overall Show", "Winner", "Grease", "Round-trip Society", "A great show")
