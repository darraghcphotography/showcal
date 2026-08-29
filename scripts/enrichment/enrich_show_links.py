"""One-off/re-runnable seed of confirmed Wikipedia links (show_links) and
world-premiere data (show_info.premiere_year/premiere_place) for the top 50
most-performed titles on the AIMS circuit. Every URL and premiere date was
gathered via web search and confirmed against the actual Wikipedia article's
infobox, not guessed - two titles ("The New Pirates of Penzance", "Michael
Collins - A Musical Drama") turned out to have no dedicated, internationally
notable Wikipedia article and are deliberately left out rather than linked to
something loosely related.

A couple of judgment calls worth knowing about:
- Several "world premiere" entries are pre-Broadway/West End tryouts (e.g.
  The Addams Family in Chicago, Legally Blonde in San Francisco) rather than
  the eventual big-city opening - that's genuinely correct, a tryout run is
  still the first performance, and it's whatever Wikipedia's own infobox
  lists first under "Productions".
- The Wizard of Oz is ambiguous: there's a separate 1902 Broadway musical and
  a 1987 RSC stage adaptation. This seeds the 1987 RSC version, since that's
  the one actually licensed to amateur/community theatres today (Tams-
  Witmark/Concord) - reconsider if an AIMS society is known to have staged a
  different edition.
- The Hired Man's premiere venue isn't in its own Wikipedia article; sourced
  via web search instead, corroborated across multiple independent sources.

Only ever updates url/premiere_year/premiere_place - never touches an
existing show_info row's synopsis/rights fields (set separately by
enrich_show_info.py or a moderator via /admin/titles/<title>/info).

Usage:
    py enrich_show_links.py [--db aims.db]
"""
import argparse
import sqlite3
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

# (show, wikipedia_url, premiere_year, premiere_place)
DATA = [
    ("Jesus Christ Superstar", "https://en.wikipedia.org/wiki/Jesus_Christ_Superstar", 1971, "Broadway (Mark Hellinger Theatre, New York)"),
    ("Fiddler on the Roof", "https://en.wikipedia.org/wiki/Fiddler_on_the_Roof", 1964, "Broadway (Imperial Theatre, New York)"),
    ("Oklahoma!", "https://en.wikipedia.org/wiki/Oklahoma!", 1943, "Broadway (St. James Theatre, New York)"),
    ("My Fair Lady", "https://en.wikipedia.org/wiki/My_Fair_Lady", 1956, "Broadway (Mark Hellinger Theatre, New York)"),
    ("West Side Story", "https://en.wikipedia.org/wiki/West_Side_Story", 1957, "Broadway (Winter Garden Theatre, New York)"),
    ("Oliver!", "https://en.wikipedia.org/wiki/Oliver!", 1960, "West End (New Theatre, London)"),
    ("Guys and Dolls", "https://en.wikipedia.org/wiki/Guys_and_Dolls", 1950, "Broadway (46th Street Theatre, New York)"),
    ("The Pirates of Penzance", "https://en.wikipedia.org/wiki/The_Pirates_of_Penzance", 1879, "Broadway (Fifth Avenue Theatre, New York)"),
    ("Hot Mikado", "https://en.wikipedia.org/wiki/Hot_Mikado", 1986, "Ford's Theatre, Washington DC"),
    ("All Shook Up", "https://en.wikipedia.org/wiki/All_Shook_Up_(musical)", 2004, "Cadillac Palace Theatre, Chicago (pre-Broadway tryout)"),
    ("Sister Act", "https://en.wikipedia.org/wiki/Sister_Act_(musical)", 2006, "Pasadena Playhouse, Pasadena, California"),
    ("Chess", "https://en.wikipedia.org/wiki/Chess_(musical)", 1986, "West End (Prince Edward Theatre, London)"),
    ("Sweeney Todd", "https://en.wikipedia.org/wiki/Sweeney_Todd:_The_Demon_Barber_of_Fleet_Street", 1979, "Broadway (Uris Theatre, New York)"),
    ("The Addams Family", "https://en.wikipedia.org/wiki/The_Addams_Family_(musical)", 2009, "Chicago (pre-Broadway tryout)"),
    ("Little Shop of Horrors", "https://en.wikipedia.org/wiki/Little_Shop_of_Horrors_(musical)", 1982, "Off-Broadway (Orpheum Theatre, New York)"),
    ("Me and My Girl", "https://en.wikipedia.org/wiki/Me_and_My_Girl", 1937, "West End (Victoria Palace Theatre, London)"),
    ("Carousel", "https://en.wikipedia.org/wiki/Carousel_(musical)", 1945, "Broadway (Majestic Theatre, New York)"),
    ("The King & I", "https://en.wikipedia.org/wiki/The_King_and_I", 1951, "Broadway (St. James Theatre, New York)"),
    ("The Mikado", "https://en.wikipedia.org/wiki/The_Mikado", 1885, "Savoy Theatre, London"),
    ("South Pacific", "https://en.wikipedia.org/wiki/South_Pacific_(musical)", 1949, "Broadway (Majestic Theatre, New York)"),
    ("Evita", "https://en.wikipedia.org/wiki/Evita_(musical)", 1978, "West End (Prince Edward Theatre, London)"),
    ("Jekyll & Hyde", "https://en.wikipedia.org/wiki/Jekyll_%26_Hyde_(musical)", 1990, "Alley Theatre, Houston, Texas"),
    ("Calamity Jane", "https://en.wikipedia.org/wiki/Calamity_Jane_(musical)", 1961, "Casa Mañana, Fort Worth, Texas"),
    ("Man of La Mancha", "https://en.wikipedia.org/wiki/Man_of_La_Mancha", 1965, "Goodspeed Opera House, East Haddam, Connecticut (tryout)"),
    ("Beauty and the Beast", "https://en.wikipedia.org/wiki/Beauty_and_the_Beast_(musical)", 1993, "Music Hall, Houston, Texas (pre-Broadway tryout)"),
    ("Hello, Dolly!", "https://en.wikipedia.org/wiki/Hello,_Dolly!_(musical)", 1964, "Broadway (St. James Theatre, New York)"),
    ("The Sound of Music", "https://en.wikipedia.org/wiki/The_Sound_of_Music", 1959, "Broadway (Lunt-Fontanne Theatre, New York)"),
    ("The Hired Man", "https://en.wikipedia.org/wiki/The_Hired_Man_(musical)", 1984, "Nuffield Theatre, Southampton"),
    ("Titanic The Musical", "https://en.wikipedia.org/wiki/Titanic_(musical)", 1997, "Broadway (Lunt-Fontanne Theatre, New York)"),
    ("Godspell", "https://en.wikipedia.org/wiki/Godspell", 1971, "Off-Broadway (Cherry Lane Theatre, New York)"),
    ("The Merry Widow", "https://en.wikipedia.org/wiki/The_Merry_Widow", 1905, "Theater an der Wien, Vienna"),
    ("Sweet Charity", "https://en.wikipedia.org/wiki/Sweet_Charity", 1966, "Broadway (Palace Theatre, New York)"),
    ("Show Boat", "https://en.wikipedia.org/wiki/Show_Boat", 1927, "Broadway (Ziegfeld Theatre, New York)"),
    ("Anything Goes", "https://en.wikipedia.org/wiki/Anything_Goes", 1934, "Broadway (Alvin Theatre, New York)"),
    ("Legally Blonde", "https://en.wikipedia.org/wiki/Legally_Blonde_(musical)", 2007, "Golden Gate Theatre, San Francisco (pre-Broadway tryout)"),
    ("9 to 5", "https://en.wikipedia.org/wiki/9_to_5_(musical)", 2008, "Ahmanson Theatre, Los Angeles (pre-Broadway tryout)"),
    ("Cabaret", "https://en.wikipedia.org/wiki/Cabaret_(musical)", 1966, "Shubert Theatre, Boston (pre-Broadway tryout)"),
    ("Annie Get Your Gun", "https://en.wikipedia.org/wiki/Annie_Get_Your_Gun_(musical)", 1946, "Broadway (Imperial Theatre, New York)"),
    ("The Witches of Eastwick", "https://en.wikipedia.org/wiki/The_Witches_of_Eastwick_(musical)", 2000, "West End (Theatre Royal, Drury Lane, London)"),
    ("The Wizard of Oz", "https://en.wikipedia.org/wiki/The_Wizard_of_Oz_(1987_musical)", 1987, "Barbican Centre, London (RSC production)"),
    ("Grease", "https://en.wikipedia.org/wiki/Grease_(musical)", 1971, "Kingston Mines nightclub, Chicago"),
    ("Joseph and the Amazing Technicolor Dreamcoat", "https://en.wikipedia.org/wiki/Joseph_and_the_Amazing_Technicolor_Dreamcoat", 1972, "Edinburgh International Festival (Haymarket ice rink)"),
    ("The Producers", "https://en.wikipedia.org/wiki/The_Producers_(musical)", 2001, "Cadillac Palace Theatre, Chicago (pre-Broadway tryout)"),
    ("H.M.S. Pinafore", "https://en.wikipedia.org/wiki/H.M.S._Pinafore", 1878, "Opera Comique, London"),
    ("Into the Woods", "https://en.wikipedia.org/wiki/Into_the_Woods", 1986, "Old Globe Theatre, San Diego"),
    ("Crazy For You", "https://en.wikipedia.org/wiki/Crazy_for_You_(musical)", 1992, "Broadway (Shubert Theatre, New York)"),
    ("Die Fledermaus", "https://en.wikipedia.org/wiki/Die_Fledermaus", 1874, "Theater an der Wien, Vienna"),
    ("Brigadoon", "https://en.wikipedia.org/wiki/Brigadoon", 1947, "Broadway (Ziegfeld Theatre, New York)"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    for show, url, premiere_year, premiere_place in DATA:
        conn.execute(
            """
            INSERT INTO show_links (show, url, updated_at) VALUES (?, ?, datetime('now'))
            ON CONFLICT(show) DO UPDATE SET url = excluded.url, updated_at = excluded.updated_at
            """,
            (show, url),
        )
        conn.execute(
            """
            INSERT INTO show_info (show, premiere_year, premiere_place, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(show) DO UPDATE SET
                premiere_year = excluded.premiere_year, premiere_place = excluded.premiere_place,
                updated_at = excluded.updated_at
            """,
            (show, premiere_year, premiere_place),
        )
    conn.commit()
    print(f"Upserted show_links + premiere data for {len(DATA)} titles")

    missing = []
    for show, *_ in DATA:
        exists = conn.execute(
            "SELECT 1 FROM shows WHERE show = ? UNION SELECT 1 FROM historical_results WHERE show = ? LIMIT 1",
            (show, show),
        ).fetchone()
        if not exists:
            missing.append(show)
    print("Titles with no matching show/historical_results row (check spelling):", missing or "none")
    conn.close()


if __name__ == "__main__":
    main()
