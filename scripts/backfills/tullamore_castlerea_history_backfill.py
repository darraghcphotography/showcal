"""One-off backfill of productions missing from Tullamore Musical Society's
and Castlerea Musical Society's own anniversary programmes, both submitted
via /submit/photo on 2026-08-24 (photo_submissions ids 2 and 3/4 - 3 and 4
are the same photo submitted twice).

Tullamore's programme lists 1955-2024; Castlerea's lists 1968-2017, plus
both have a detailed awards section (categories/nominees) that this script
deliberately does NOT enter - Darragh's call 2026-08-24, bare "this
happened" rows only, matching the Naas backfill's own scope.

Cross-checked programmatically against historical_results and shows (exact
title match, tolerating a +/-1 year drift for the same recorded-the-
following-year pattern already seen elsewhere - see historical_results'
schema.sql comment) rather than by eye, after an initial by-hand pass
undercounted this by nearly 3x. A handful of poster entries were excluded
because the database already covers that society/year within one year
(the recorded-a-year-later pattern) or because they're a genuine second
production alongside another already on record for that year, both kept in
rather than dropped as duplicates - see PRODUCTIONS below for the final,
confirmed set.

Usage:
    py tullamore_castlerea_history_backfill.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python tullamore_castlerea_history_backfill.py --db /data/aims.db
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

REASON = "From the society's own anniversary programme (photo submission, 2026-08-24)"

# (society name, year, show)
PRODUCTIONS = [
    ("Tullamore Musical Society", 1955, "Trial by Jury"),
    ("Tullamore Musical Society", 1956, "The Pirates of Penzance"),
    ("Tullamore Musical Society", 1957, "The Geisha"),
    ("Tullamore Musical Society", 1958, "Robinson Crusoe"),
    ("Tullamore Musical Society", 1959, "Jack and The Beanstalk"),
    ("Tullamore Musical Society", 1960, "Cinderella"),
    ("Tullamore Musical Society", 1961, "Nuts in May (Revue)"),
    ("Tullamore Musical Society", 1962, "The Desert Song"),
    ("Tullamore Musical Society", 1963, "Rose Marie"),
    ("Tullamore Musical Society", 1964, "Oklahoma!"),
    ("Tullamore Musical Society", 1965, "Wild Violets"),
    ("Tullamore Musical Society", 1967, "The Quaker Girl"),
    ("Tullamore Musical Society", 1968, "The Merry Widow"),
    ("Tullamore Musical Society", 1969, "The Gipsy Princess"),
    ("Tullamore Musical Society", 1970, "Rio Rita"),
    ("Tullamore Musical Society", 1971, "Bless the Bride"),
    ("Tullamore Musical Society", 1972, "Gypsy Baron"),
    ("Tullamore Musical Society", 1973, "Mozart's Coronation Mass"),
    ("Tullamore Musical Society", 1974, "Night in Venice"),
    ("Tullamore Musical Society", 1976, "The Golden Years"),
    ("Tullamore Musical Society", 1977, "Showboat"),
    ("Tullamore Musical Society", 1978, "Magyar Melody"),
    ("Tullamore Musical Society", 1979, "The Arcadians"),
    ("Tullamore Musical Society", 1981, "The White Horse Inn"),
    ("Tullamore Musical Society", 1982, "The Desert Song"),
    ("Tullamore Musical Society", 1986, "The Gipsy Baron"),
    ("Tullamore Musical Society", 1990, "Oh! Susanna"),
    ("Tullamore Musical Society", 1995, "Guys and Dolls"),
    ("Tullamore Musical Society", 1997, "Calamity Jane"),
    ("Tullamore Musical Society", 1998, "Jesus Christ Superstar"),
    ("Tullamore Musical Society", 1999, "West Side Story"),
    ("Tullamore Musical Society", 2000, "My Fair Lady"),
    ("Tullamore Musical Society", 2002, "Joseph and the Amazing Technicolor Dreamcoat"),
    ("Tullamore Musical Society", 2003, "The Best Little Whorehouse in Texas"),
    ("Tullamore Musical Society", 2005, "The King and I"),
    ("Tullamore Musical Society", 2007, "Hello! Dolly"),
    ("Tullamore Musical Society", 2008, "Mack & Mabel"),
    ("Tullamore Musical Society", 2012, "Disney's Beauty and the Beast"),
    ("Tullamore Musical Society", 2013, "The Last Five Years"),
    ("Tullamore Musical Society", 2018, "Sister Act"),
    ("Tullamore Musical Society", 2019, "Jekyll and Hyde"),
    ("Tullamore Musical Society", 2023, "A Musical Journey"),

    ("Castlerea Musical Society", 1968, "The Long Ju Ju"),
    ("Castlerea Musical Society", 1969, "Robin Hood And His Merry Women"),
    ("Castlerea Musical Society", 1970, "The Golden Fleece"),
    ("Castlerea Musical Society", 1972, "Oklahoma!"),
    ("Castlerea Musical Society", 1973, "South Pacific"),
    ("Castlerea Musical Society", 1974, "Calamity Jane"),
    ("Castlerea Musical Society", 1975, "Carousel"),
    ("Castlerea Musical Society", 1976, "Call Me Madam"),
    ("Castlerea Musical Society", 1977, "The White Horse Inn"),
    ("Castlerea Musical Society", 1978, "Annie Get Your Gun"),
    ("Castlerea Musical Society", 1979, "Viva Mexico"),
    ("Castlerea Musical Society", 1980, "Lilac Time"),
    ("Castlerea Musical Society", 1981, "Oklahoma!"),
    ("Castlerea Musical Society", 1982, "The Boyfriend"),
    ("Castlerea Musical Society", 1983, "The Pirates Of Penzance"),
    ("Castlerea Musical Society", 1984, "The Arcadians"),
    ("Castlerea Musical Society", 1985, "Finian's Rainbow"),
    ("Castlerea Musical Society", 1987, "Rio Rita"),
    ("Castlerea Musical Society", 1988, "Guys 'N' Dolls"),
    ("Castlerea Musical Society", 1989, "South Pacific"),
    ("Castlerea Musical Society", 1990, "Fiddler On The Roof"),
    ("Castlerea Musical Society", 1991, "Brigadoon"),
    ("Castlerea Musical Society", 1992, "H.M.S Pinafore"),
    ("Castlerea Musical Society", 1993, "Memories - 25th Celebration"),
    ("Castlerea Musical Society", 1994, "The New Moon"),
    ("Castlerea Musical Society", 1995, "The King And I"),
    ("Castlerea Musical Society", 1996, "Paint Your Wagon"),
    ("Castlerea Musical Society", 1997, "Joseph & the Amazing Technicolour Dreamcoat"),
    ("Castlerea Musical Society", 1998, "Anything Goes"),
    ("Castlerea Musical Society", 1999, "Little Shop Of Horrors"),
    ("Castlerea Musical Society", 2001, "Jesus Christ Superstar"),
    ("Castlerea Musical Society", 2008, "Hello, Dolly!"),
    ("Castlerea Musical Society", 2010, "Sugar"),
    ("Castlerea Musical Society", 2014, "Ragtime"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    inserted, skipped = 0, 0
    for society_name, year, show in PRODUCTIONS:
        society = db.execute("SELECT id, name FROM societies WHERE name = ?", (society_name,)).fetchone()
        if society is None:
            print(f"  NO SUCH SOCIETY: {society_name!r}")
            continue
        # Compared on normalize_title, not the raw string - an exact `show = ?`
        # let punctuation variants past and created redundant bare rows beside
        # the award record they duplicated ("Oh! Susanna" vs "Oh Susanna!" 1990,
        # "Hello! Dolly" vs "Hello, Dolly!" 2007; cleaned up 2026-08-28).
        # Normalisation only, never fuzzy.
        existing = None
        for row in db.execute(
            "SELECT show FROM historical_results "
            " WHERE year = ? AND society_id = ? AND show IS NOT NULL",
            (year, society["id"]),
        ):
            if normalize_title(row["show"]) == normalize_title(show):
                existing = row
                break
        if existing:
            print(f"  already on record: {society_name}, {year} {show!r} (as {existing['show']!r})")
            skipped += 1
            continue
        db.execute(
            "INSERT INTO historical_results (year, show, society_name, society_id, reason, source) "
            "VALUES (?, ?, ?, ?, ?, 'manual')",
            (year, show, society["name"], society["id"], REASON),
        )
        print(f"  added: {society_name}, {year} {show!r}")
        inserted += 1

    print(f"\n{inserted} added, {skipped} already on record")

    if args.dry_run:
        db.rollback()
        print("--dry-run: rolled back, nothing written")
    else:
        db.commit()
    db.close()


if __name__ == "__main__":
    main()
