"""One-time (but safe to re-run) cleanup of known duplicate/mangled show
titles, found by inspecting distinct show titles for near-duplicates.

Fixes both aims.db (immediate effect) AND shows.csv (so a future
import_csv.py re-run - which treats the CSV as authoritative for
source='import' rows - doesn't quietly undo this). If you maintain the
master spreadsheet these CSVs came from, apply the same renames there so a
future re-export doesn't reintroduce the duplicates.

This intentionally only includes exact-match, unambiguous same-show renames
(case/punctuation/subtitle variants of a title clearly referring to the same
production). It does NOT touch the handful of rows that look like two show
titles concatenated together, or ambiguous naming - those need a human who
knows what the show actually was; see the conversation/README notes.
"""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

RENAMES = {
    "Into The Woods": "Into the Woods",
    "Beauty & The Beast": "Beauty and the Beast",
    "Charlie & The Chocolate Factory": "Charlie and the Chocolate Factory",
    "Cry Baby": "Cry-Baby",
    "RENT": "Rent",
    "Rock Of Ages": "Rock of Ages",
    "The Addams family": "The Addams Family",
    "Hunchback of Notre Dame": "The Hunchback of Notre Dame",
    "Sound of Music": "The Sound of Music",
    "Little Mermaid": "The Little Mermaid",
    "Seussical! The Musical": "Seussical",
    "Michael Collins: A Musical Drama": "Michael Collins",
    "Annie The Musical": "Annie",
    "Sister Act  CANCELLED": "Sister Act",  # status column already says Cancelled

    # Confirmed with the maintainer:
    "Penzane! The Pirates Musical (New)": "Pirates! The Penzance Musical",  # correct title of a new show
    "Guys and Dolls: Guy Harder": "Guys and Dolls",  # was a joking subtitle, not part of the real title
    "Pirates of Penzance": "The Pirates of Penzance",  # matches the historical archive's dominant spelling
    # Concatenated titles were a struck-through-original + actual-replacement in the
    # source spreadsheet (a show changed after being announced); strikethrough
    # formatting doesn't survive CSV export, so both runs of text landed in one
    # field. Confirmed with the maintainer: the second title in each is the show
    # that actually went ahead.
    "Fiddler on the Roof Little Shop of Horrors": "Little Shop of Horrors",
    "The Witches of Eastwick   Anything Goes": "Anything Goes",
    "The Witches of Eastwick Footloose": "Footloose",
    "Michael Collins: A Musical Drama FROZEN": "Frozen",
    "Oklahoma Annie": "Annie",

    "American Idiot!": "American Idiot",  # official title has no exclamation mark
}

# Not a real show title - a stray placeholder that should be NULL, like the
# other ~146 "registered for this season, TBA" rows.
BLANK_OUT = {
    "NO SHOW THIS SEASON",
    # Same struck-through-original pattern as above, but here the replacement
    # (Calendar Girls) was itself cancelled - so there ended up being no show
    # at all. status is already 'Cancelled' on this row and is left as-is;
    # only the mangled title text is cleared.
    "Oklahoma Calendar Girls CANCELLED",
}


def fix_db():
    conn = sqlite3.connect(ROOT / "aims.db")
    changed = 0
    for old, new in RENAMES.items():
        cur = conn.execute("UPDATE shows SET show = ? WHERE show = ?", (new, old))
        changed += cur.rowcount
    for old in BLANK_OUT:
        cur = conn.execute("UPDATE shows SET show = NULL WHERE show = ?", (old,))
        changed += cur.rowcount
    conn.commit()
    conn.close()
    print(f"aims.db: {changed} row(s) updated")


def fix_csv():
    path = ROOT / "shows.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    changed = 0
    for row in rows:
        if row["show"] in RENAMES:
            row["show"] = RENAMES[row["show"]]
            changed += 1
        elif row["show"] in BLANK_OUT:
            row["show"] = ""
            changed += 1

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"shows.csv: {changed} row(s) updated")


if __name__ == "__main__":
    fix_db()
    fix_csv()
