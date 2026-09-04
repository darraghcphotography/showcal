"""Builds the casting-data worklist handed to Antigravity.

Pairs with `enrichment/REPERTOIRE_DATA_BRIEF.md`. Darragh, 2026-09-04: committees
choose a season by asking "can we cast this?" - cast size and the male/female
split are the real constraint, not taste - so the repertoire finder needs
casting data before it can exist at all.

WHY THIS IS DELEGABLE WHEN THE FOUNDING-YEARS WORK WAS NOT. The answer is
printed on a page we can already name: 221 of 299 titles carry a `rights_url`,
and every one of the rest names a `licensing_house`. That makes it transcription
from a named source rather than research, which is the only shape of delegated
task with a good record on this project.

Rows are ordered most-staged first, so a partial return is still the most
useful subset rather than an alphabetical slice.

Usage:
    py scripts/enrichment/build_repertoire_worklist.py [--db aims.db] [--limit N]

    docker compose exec aims-web python \\
        scripts/enrichment/build_repertoire_worklist.py --db /data/aims.db
"""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "enrichment" / "repertoire_worklist.json"

# Blank in every row, so the shape of the answer is unambiguous and a returned
# file can be diffed against the sent one.
FIELDS = {
    "cast_size_min": None,
    "cast_size_max": None,
    "principal_roles": None,
    "roles_male": None,
    "roles_female": None,
    "roles_flexible": None,
    "chorus": None,
    "act_count": None,
    "runtime_minutes": None,
    "orchestra_size": None,
    "youth_version": None,
    "cast_source_url": None,
    "cast_notes": None,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--limit", type=int, default=0, help="0 = every title")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    query = """
        SELECT
            si.show                AS title,
            si.licensing_house     AS licensing_house,
            si.rights_url          AS rights_url,
            si.composer            AS composer,
            (SELECT COUNT(*) FROM productions p
              WHERE p.title_key = (SELECT title_key FROM productions q
                                    WHERE q.title = si.show LIMIT 1)) AS times_staged
        FROM show_info si
        ORDER BY times_staged DESC, si.show
    """
    rows = db.execute(query).fetchall()
    if args.limit:
        rows = rows[: args.limit]

    payload = []
    for row in rows:
        payload.append({
            "title": row["title"],
            # Context, not fields to change - they tell the worker which page
            # to open and give a sanity check that they found the right show.
            "licensing_house": row["licensing_house"],
            "rights_url": row["rights_url"],
            "composer": row["composer"],
            "times_staged_by_aims_societies": row["times_staged"],
            **FIELDS,
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with_url = sum(1 for r in payload if r["rights_url"])
    print(f"{len(payload)} titles -> {out}")
    print(f"  {with_url} carry a rights_url (the page to read is already named)")
    print(f"  {len(payload) - with_url} need the house's own search")
    db.close()


if __name__ == "__main__":
    main()
