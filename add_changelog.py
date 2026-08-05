"""Publish a changelog entry directly to changelog_entries - the same table
/admin/changelog writes to, just without needing to log in and paste text
into a form.

Each positional argument becomes its own bullet line on the public
/suggestions Roadmap page's "Recently shipped" section (same one-line-per-
bullet behavior as pasting multi-line text into the admin form).

Usage:
    py add_changelog.py "Headline" "Supporting detail" "Another detail" [--db aims.db]

In Docker:
    docker exec aims-web python add_changelog.py --db /data/aims.db "Headline" "Detail"
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent


def publish(conn, lines):
    """Insert one changelog entry (each item in `lines` becomes its own
    bullet) and return the joined entry text. Raises ValueError if every
    line is blank."""
    entry = "\n".join(line.strip() for line in lines if line.strip())
    if not entry:
        raise ValueError("No non-blank lines given.")
    conn.execute("INSERT INTO changelog_entries (entry) VALUES (?)", (entry,))
    conn.commit()
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lines", nargs="+", help="one or more lines - each becomes its own bullet")
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        entry = publish(conn, args.lines)
    except ValueError as e:
        raise SystemExit(str(e))
    finally:
        conn.close()

    print("Published:")
    for line in entry.split("\n"):
        print(f"  - {line}")


if __name__ == "__main__":
    main()
