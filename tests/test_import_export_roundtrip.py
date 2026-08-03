"""import_csv.py / export_csv.py round-trip: importing then exporting the
same CSVs should reproduce the same data (see CLAUDE.md - import_csv.py is
meant to be safe to re-run against a live db and export_csv.py is its
inverse for pulling manual DB fixes back into the tracked CSVs)."""
import csv
import sqlite3
from pathlib import Path

import import_csv
import export_csv

ROOT = Path(__file__).resolve().parent.parent

SOCIETIES_CSV = """id,name,region,section,section_as_of,section_history,notes
1,Test Society,Eastern,Gilbert,,,
2,Other Society,Western,Sullivan,26/27,25/26: Gilbert,Some notes
"""

SHOWS_CSV = """season,region,section,society,show,opening_date,closing_date,adjudication_date,adjudication_month_raw,venue,director,musical_director,choreographer,review_status,review_url,status
23/24,Eastern,Gilbert,Test Society,Oliver!,2024-03-01,2024-03-05,2024-03-15,,Town Hall,Jane Doe,John Smith,,Published,https://example.com/review,
24/25,Western,Sullivan,Other Society,,,,,,,,,,None,,
"""


def _write(path, content):
    path.write_text(content, encoding="utf-8-sig")


def test_import_then_export_round_trips(tmp_path):
    db_path = tmp_path / "roundtrip.db"
    societies_in = tmp_path / "societies_in.csv"
    shows_in = tmp_path / "shows_in.csv"
    _write(societies_in, SOCIETIES_CSV)
    _write(shows_in, SHOWS_CSV)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))

    n_societies = import_csv.load_societies(conn, societies_in)
    n_shows, skipped = import_csv.load_shows(conn, shows_in)
    conn.commit()

    assert n_societies == 2
    assert n_shows == 2
    assert skipped == []

    societies_out = tmp_path / "societies_out.csv"
    shows_out = tmp_path / "shows_out.csv"
    export_csv.export_societies(conn, societies_out)
    export_csv.export_shows(conn, shows_out)
    conn.close()

    with open(societies_in, encoding="utf-8-sig", newline="") as f:
        expected_societies = list(csv.DictReader(f))
    with open(societies_out, encoding="utf-8-sig", newline="") as f:
        actual_societies = list(csv.DictReader(f))
    assert actual_societies == expected_societies

    with open(shows_in, encoding="utf-8-sig", newline="") as f:
        expected_shows = list(csv.DictReader(f))
    with open(shows_out, encoding="utf-8-sig", newline="") as f:
        actual_shows = list(csv.DictReader(f))
    assert actual_shows == expected_shows


def test_reimport_does_not_regress_moderator_set_review(tmp_path):
    """A moderator attaches a review in the app; re-running the import from a
    stale spreadsheet (no review yet) must not blank it back out."""
    db_path = tmp_path / "reimport.db"
    societies_csv = tmp_path / "societies.csv"
    shows_csv = tmp_path / "shows.csv"
    _write(societies_csv, SOCIETIES_CSV)
    _write(shows_csv, SHOWS_CSV)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    import_csv.load_societies(conn, societies_csv)
    import_csv.load_shows(conn, shows_csv)
    conn.commit()

    # Moderator attaches a review to the second (as-yet un-reviewed) show.
    conn.execute(
        "UPDATE shows SET review_status = 'Published', review_url = 'https://example.com/mod-review' "
        "WHERE show IS NULL AND season = '24/25'"
    )
    conn.commit()

    # Re-run the import from the same (still stale) spreadsheet.
    import_csv.load_shows(conn, shows_csv)
    conn.commit()

    row = conn.execute(
        "SELECT review_status, review_url FROM shows WHERE show IS NULL AND season = '24/25'"
    ).fetchone()
    conn.close()
    assert row[0] == "Published"
    assert row[1] == "https://example.com/mod-review"
