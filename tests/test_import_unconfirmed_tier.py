"""The 27/28 unconfirmed-tier blanking rule in import_csv.py: the spreadsheet
carries forward a guessed tier for seasons AIMS hasn't actually published a
tier list for yet, so import_csv.py blanks section for those seasons rather
than showing a guess as if it were fact (see import_csv.py's
UNCONFIRMED_TIER_SEASONS comment)."""
import sqlite3
from pathlib import Path

import import_csv

ROOT = Path(__file__).resolve().parent.parent

SOCIETIES_CSV = """id,name,region,section,section_as_of,section_history,notes
1,Test Society,Eastern,Gilbert,,,
"""

SHOWS_CSV_TEMPLATE = """season,region,section,society,show,opening_date,closing_date,adjudication_date,adjudication_month_raw,venue,director,musical_director,choreographer,review_status,review_url,status
{season},Eastern,Sullivan,Test Society,Some Show,,,,,,,,,None,,
"""


def _setup_db(tmp_path, season):
    db_path = tmp_path / "tier.db"
    societies_csv = tmp_path / "societies.csv"
    shows_csv = tmp_path / "shows.csv"
    societies_csv.write_text(SOCIETIES_CSV, encoding="utf-8-sig")
    shows_csv.write_text(SHOWS_CSV_TEMPLATE.format(season=season), encoding="utf-8-sig")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    import_csv.load_societies(conn, societies_csv)
    import_csv.load_shows(conn, shows_csv)
    conn.commit()
    return conn


def test_unconfirmed_season_blanks_section(tmp_path):
    conn = _setup_db(tmp_path, "27/28")
    section = conn.execute("SELECT section FROM shows WHERE season = '27/28'").fetchone()[0]
    conn.close()
    assert section is None


def test_confirmed_season_keeps_section(tmp_path):
    conn = _setup_db(tmp_path, "23/24")
    section = conn.execute("SELECT section FROM shows WHERE season = '23/24'").fetchone()[0]
    conn.close()
    assert section == "Sullivan"
