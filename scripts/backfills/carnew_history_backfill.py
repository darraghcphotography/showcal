"""One-off backfill of Carnew Musical Society's production history, read off
their own programme page "The Society's Previous Shows" (a photo submitted via
/submit/photo, ids 8 and 9, 2026-08-28). The list runs 1967-2022.

THE YEAR OFFSET, AND WHY IT IS NOT THE SAME AS NAAS'S. Carnew's printed years
are one BEHIND the award year we hold. Measured against everything already on
record for this society, before writing anything:

    programme year +0  ->   0 of 52 entries match
    programme year +1  ->  22 of 52 entries match
    programme year -1  ->   0 of 52 entries match

Twenty-two overlaps, every one at +1, and not a single contradiction. The
reason is visible in the programme itself: Carnew stages in autumn, and one
entry says so outright ("1979: The Golden Years (Nov)"). An autumn show in year
Y is season Y/Y+1, and AIMS award years are the season's *ending* year. So
Carnew's printed year is the season's start.

This is deliberately NOT generalised into a rule. `naas_history_backfill.py`
faced the same question on 2026-08-24 and the evidence there pointed the other
way (14 of 30 matched with no offset, against 2 that wanted one), so Naas was
taken as-is. Wexford Light Opera's printed history, checked the same night as
this one, matched the award year exactly at 28 of 28 - they stage in spring.
The offset is a property of when a society performs, so it has to be measured
per source. Taking Carnew's list at face value would have shifted 30
productions by a year, which is precisely the failure that forced the Oyster
Lane rollback and precisely what an unweighted overlap check cannot see.

WHAT IS SKIPPED. Five entries are not productions of a musical: "Concert
(Tinahely)" (1967), "Variety 4" (1975), "The Golden Years (Nov)" (1979),
"Showtime (Variety Show)" (1988), and "No Show - Covid 19" (2020). They are
listed here rather than quietly dropped, so the decision is visible.

Same insert shape as `naas_history_backfill.py` and
`admin.bulk_historical_productions`: a bare `historical_results` row, no
award or category attached, just "this happened". The REASON tag is what makes
the whole import reversible by rule rather than by hardcoded id - the lesson
`rollback_oyster_lane_archive.py` had to learn the hard way.

Usage:
    py carnew_history_backfill.py [--db aims.db] [--dry-run]

    docker exec aims-web python carnew_history_backfill.py --db /data/aims.db --dry-run
"""
import argparse
import sqlite3
import sys
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.similarity import normalize_title  # noqa: E402


def match_key(title):
    """normalize_title, plus '&' read as 'and'.

    normalize_title strips punctuation, so "Guys & Dolls" becomes "guys dolls"
    while "Guys and Dolls" becomes "guys and dolls" - they do not match, and
    this programme prints the ampersand form for a show the database already
    holds spelled out, at 1999 and again at 2023. Without this, both would be
    inserted beside the records they duplicate.

    This is still normalisation, not fuzzy matching: one fixed substitution of
    a word for its own symbol. It cannot conflate two different shows the way a
    similarity ratio can, which is the distinction app/similarity.py exists to
    protect.
    """
    return normalize_title(title.replace("&", " and "))


SOCIETY_NAME = "Carnew Musical Society"
REASON = "From the society's own programme, 'The Society's Previous Shows' (photo submission, 2026-08-28)"

# Award year = the programme's printed year + 1. See the note above.
PROGRAMME_YEAR_OFFSET = 1

# (printed year, show) exactly as printed. The offset is applied at insert
# time, so this list stays a faithful transcription of the source.
PRODUCTIONS = [
    (1968, "Trial by Jury"),
    (1969, "Pirates of Penzance"),
    (1970, "The Mikado"),
    (1971, "H.M.S. Pinafore"),
    (1972, "Yeomen of the Guard"),
    (1973, "Iolanthe"),
    (1974, "Ruddigore"),
    (1976, "The Maid of the Mountains"),
    (1977, "Pirates of Penzance"),
    (1978, "Oklahoma"),
    (1979, "Calamity Jane"),
    (1980, "Viva Mexico"),
    (1981, "Salad Days"),
    (1982, "Finian's Rainbow"),
    (1983, "The Wizard of Oz"),
    (1984, "South Pacific"),
    (1985, "Oh Susanna"),
    (1986, "Annie Get Your Gun"),
    (1987, "Little Mary Sunshine"),
    (1989, "The Boyfriend"),
    (1990, "Seven Brides for Seven Brothers"),
    (1991, "The Musicman"),
    (1992, "Paint Your Wagon"),
    (1993, "God Bless Archie Dean"),
    (1994, "My Fair Lady"),
    (1995, "The Pajama Game"),
    (1996, "Oklahoma"),
    (1997, "Carrie"),
    (1998, "Guys & Dolls"),
    (1999, "Fiddler on the Roof"),
    (2000, "Best Little Whorehouse in Texas"),
    (2001, "Brigadoon"),
    (2002, "Carousel"),
    (2003, "The Sound of Music"),
    (2004, "Hello Dolly"),
    (2005, "The Hired Man"),
    (2006, "The New Pirates of Penzance"),
    (2007, "Calamity Jane"),
    (2008, "The Mikado"),
    (2009, "Honk"),
    (2010, "Viva Mexico"),
    (2011, "Jesus Christ Superstar"),
    (2012, "Man of La Mancha"),
    (2013, "Annie Get Your Gun"),
    (2014, "A Christmas Carol"),
    (2015, "Me and My Girl"),
    (2016, "Fiddler On The Roof"),
    (2017, "Sister Act"),
    (2018, "My Fair Lady"),
    (2019, "Oklahoma"),
    (2021, "All Together Now"),
    (2022, "Guys & Dolls"),
]

# Printed on the same page, deliberately not imported.
NOT_A_MUSICAL = [
    (1967, "Concert (Tinahely)"),
    (1975, "Variety 4"),
    (1979, "The Golden Years (Nov)"),
    (1988, "Showtime (Variety Show)"),
    (2020, "No Show - Covid 19"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    society = db.execute("SELECT id, name FROM societies WHERE name = ?", (SOCIETY_NAME,)).fetchone()
    if society is None:
        raise SystemExit(f"No society named {SOCIETY_NAME!r} found.")

    print(f"{SOCIETY_NAME} (id {society['id']}), "
          f"applying +{PROGRAMME_YEAR_OFFSET} to every printed year\n")

    inserted, skipped = 0, 0
    for printed_year, show in PRODUCTIONS:
        year = printed_year + PROGRAMME_YEAR_OFFSET
        # Compared on normalize_title, not the raw string - an exact `show = ?`
        # lets case and punctuation variants past and inserts a redundant bare
        # row beside the record it duplicates. Normalisation only, never fuzzy.
        #
        # BOTH tables are checked, which the earlier backfill scripts did not
        # do. A production can already be on record as a `shows` row with no
        # award record of its own - and after the 2026-08-28 nomination
        # backfill, 1,090 productions are exactly that. Checking only
        # historical_results would add a bare "this happened" row beside a show
        # page that already says it happened, which is precisely the class of
        # redundant row rollback_oyster_lane_archive.py had to go back and
        # delete.
        existing = None
        for row in db.execute(
            "SELECT show FROM historical_results "
            " WHERE year = ? AND society_id = ? AND show IS NOT NULL",
            (year, society["id"]),
        ):
            if match_key(row["show"]) == match_key(show):
                existing = row
                break
        if existing is None:
            season = f"{(year - 1) % 100:02d}/{year % 100:02d}"
            for row in db.execute(
                "SELECT show FROM shows "
                " WHERE season = ? AND society_id = ? AND show IS NOT NULL",
                (season, society["id"]),
            ):
                if match_key(row["show"]) == match_key(show):
                    existing = row
                    break
        if existing:
            print(f"  already on record: {printed_year} -> {year} {show!r} (as {existing['show']!r})")
            skipped += 1
            continue
        db.execute(
            "INSERT INTO historical_results (year, show, society_name, society_id, reason, source) "
            "VALUES (?, ?, ?, ?, ?, 'manual')",
            (year, show, society["name"], society["id"], REASON),
        )
        print(f"  added: {printed_year} -> {year} {show!r}")
        inserted += 1

    print(f"\n{inserted} added, {skipped} already on record")
    print(f"{len(NOT_A_MUSICAL)} entries on the page were not productions of a musical "
          f"and were not imported:")
    for printed_year, show in NOT_A_MUSICAL:
        print(f"  {printed_year} {show!r}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nCommitted.")
    db.close()


if __name__ == "__main__":
    main()
