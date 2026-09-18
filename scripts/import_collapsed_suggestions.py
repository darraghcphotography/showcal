"""Load the archive's findings into the collapsed-societies queue as proposals.

`match_awards_to_archive.py` reads the harvested official AIMS lists and says
which society each award row's nominee is printed against. This turns that into
rows in `collapsed_society_suggestions`, so a moderator sees the evidence and
the citation on `/admin/collapsed-societies` and decides there.

    py scripts/import_collapsed_suggestions.py --dry-run
    py scripts/import_collapsed_suggestions.py

In the container, as ever, name the database explicitly:

    docker compose exec aims-web python scripts/import_collapsed_suggestions.py \
        --db /data/aims.db --suggestions /data/collapsed_suggestions.json

**It proposes and never applies.** Nothing here touches `historical_results`.
A suggestion is a claim with a source attached; moving decades-old award
records is a human decision made on this evidence, not a consequence of
importing it.

The harvest itself is gitignored, so running this needs the harvest present -
either run `harvest_aims_archive.py` first, or hand it a `--suggestions` JSON
file exported from a machine that has it.
"""
import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from match_awards_to_archive import (  # noqa: E402
    attributions_for,
    load_pages,
    normalise,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "aims.db"
DEFAULT_HARVEST = ROOT / "archive_harvest" / "text"

# Sections, matching app/collapsed_societies.py. A row with no tier is not a
# side of anything and is never proposed for reassignment.
SECTIONS = ("Gilbert", "Sullivan")


def conflicted_society_ids(db):
    return [row[0] for row in db.execute(
        """
        SELECT DISTINCT hr.society_id
          FROM historical_results hr
         WHERE hr.tier IN (?, ?)
           AND hr.society_id IS NOT NULL
           AND EXISTS (
                 SELECT 1 FROM historical_results other
                  WHERE other.society_id = hr.society_id
                    AND other.year = hr.year
                    AND other.tier IN (?, ?)
                    AND other.tier <> hr.tier
           )
        """,
        SECTIONS + SECTIONS,
    )]


def build_suggestions(db, pages, society_ids, first_year=2001, last_year=2010,
                      log=print):
    """One proposal per (society, season, section, other-society-named).

    Only a **three-point** hit votes - the nominee's name and the row's show
    title both beside the society on the page. A bare name match is a common
    name appearing somewhere else on the site, and that is not evidence for
    moving anybody's award record.

    The society the rows are already filed under is not proposed back to
    itself; a season where the archive agrees with us produces no suggestion,
    which is the correct outcome and keeps the queue's counter honest.

    Bounded to the years the harvest actually covers. Outside them a hit is a
    nominee's name turning up on a page about a different season, which is a
    coincidence dressed as evidence - a 2011 row matched against a 2007 page
    was the first thing this produced.
    """
    suggestions = []
    for society_id in society_ids:
        society = db.execute("SELECT id, name FROM societies WHERE id = ?",
                             (society_id,)).fetchone()
        if society is None:
            continue
        ours = normalise(society["name"])
        rows = db.execute(
            """
            SELECT year, tier, show, nominee_name
              FROM historical_results
             WHERE society_id = ? AND tier IN (?, ?)
               AND year BETWEEN ? AND ?
               AND nominee_name IS NOT NULL AND TRIM(nominee_name) <> ''
            """,
            (society_id,) + SECTIONS + (first_year, last_year),
        ).fetchall()

        groups = defaultdict(lambda: {"rows": 0, "votes": defaultdict(list)})
        for award in rows:
            group = groups[(award["year"], award["tier"])]
            group["rows"] += 1
            for key, (name, show_too, capture, source) in attributions_for(
                    pages, award["nominee_name"], award["show"]).items():
                if show_too and key != ours:
                    group["votes"][key].append((name, capture, source))

        for (year, tier), group in sorted(groups.items()):
            for _key, hits in group["votes"].items():
                name, capture, source = hits[0]
                suggestions.append({
                    "society_id": society_id,
                    "society_name": society["name"],
                    "year": year,
                    "tier": tier,
                    "suggested_name": name,
                    "confidence": len(hits),
                    "row_count": group["rows"],
                    "evidence_capture": capture,
                    "evidence_url": source,
                })
        log("  {}: {} suggestion(s) across {} season-sections".format(
            society["name"],
            sum(len(g["votes"]) for g in groups.values()), len(groups)))
    return suggestions


def resolve_society(db, name):
    """The societies row this printed name refers to, if we hold it at all.

    Exact first, then on the identifying part of the name, because the old site
    wrote "Clara Mus Society" and "Clara Musical Society" in the same season.
    Deliberately conservative: an unresolved name shows on the queue as "not on
    our list", which is a true and useful thing to say - Athenry has no row at
    all - and is much better than a near-miss silently resolving to a
    neighbouring society.
    """
    row = db.execute("SELECT id FROM societies WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    wanted = normalise(name)
    if not wanted:
        return None
    matches = [r[0] for r in db.execute("SELECT id, name FROM societies")
               if normalise(r[1]) == wanted]
    return matches[0] if len(matches) == 1 else None


def store(db, suggestions, dry_run=False, log=print):
    written = unresolved = skipped = 0
    for item in suggestions:
        # Re-resolve the society being corrected by *name*. A suggestions file
        # is routinely built against one database and loaded into another - the
        # harvest only exists on a developer's machine, the queue only matters
        # in production - and a primary key does not survive that trip on its
        # own. Cheap insurance against filing evidence against the wrong
        # society entirely.
        society_id = resolve_society(db, item["society_name"]) \
            if item.get("society_name") else item["society_id"]
        if society_id is None:
            skipped += 1
            log("  SKIPPED - no society named {!r} here".format(item["society_name"]))
            continue
        item = dict(item, society_id=society_id)

        suggested_id = resolve_society(db, item["suggested_name"])
        if suggested_id is None:
            unresolved += 1
        log("  {} {} {} -> {}{}".format(
            item["society_name"], item["year"], item["tier"],
            item["suggested_name"],
            "" if suggested_id else "  (not a society we hold)"))
        if dry_run:
            continue
        db.execute(
            """
            INSERT INTO collapsed_society_suggestions
                   (society_id, year, tier, suggested_name, suggested_id,
                    confidence, row_count, evidence_url, evidence_capture)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(society_id, year, tier, suggested_name) DO UPDATE SET
                   suggested_id = excluded.suggested_id,
                   confidence   = excluded.confidence,
                   row_count    = excluded.row_count,
                   evidence_url = excluded.evidence_url,
                   evidence_capture = excluded.evidence_capture
            """,
            (item["society_id"], item["year"], item["tier"],
             item["suggested_name"], suggested_id, item["confidence"],
             item["row_count"], item["evidence_url"], item["evidence_capture"]),
        )
        written += 1
    if not dry_run:
        db.commit()
    return written, unresolved, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--harvest", default=str(DEFAULT_HARVEST))
    parser.add_argument("--suggestions",
                        help="a JSON file of suggestions instead of the harvest "
                             "(written by --export on a machine that has it)")
    parser.add_argument("--export", help="write the suggestions to this JSON file and stop")
    parser.add_argument("--from-year", type=int, default=2001,
                        help="earliest season the harvest covers (default 2001)")
    parser.add_argument("--to-year", type=int, default=2010,
                        help="latest season the harvest covers (default 2010)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be written and change nothing")
    args = parser.parse_args(argv)

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    if args.suggestions:
        suggestions = json.loads(Path(args.suggestions).read_text(encoding="utf-8"))
        print("{} suggestion(s) from {}".format(len(suggestions), args.suggestions))
    else:
        harvest = Path(args.harvest)
        if not harvest.exists():
            print("No harvest at {} - run scripts/harvest_aims_archive.py first, "
                  "or pass --suggestions.".format(harvest))
            return 2
        pages = load_pages(harvest)
        print("{} harvested pages".format(len(pages)))
        society_ids = conflicted_society_ids(db)
        print("{} society(s) with a two-section conflict".format(len(society_ids)))
        suggestions = build_suggestions(db, pages, society_ids,
                                        args.from_year, args.to_year)

    if args.export:
        Path(args.export).write_text(json.dumps(suggestions, indent=2), encoding="utf-8")
        print("Wrote {} suggestion(s) to {}".format(len(suggestions), args.export))
        return 0

    written, unresolved, skipped = store(db, suggestions, dry_run=args.dry_run)
    if args.dry_run:
        print("\nDry run - nothing written. {} suggestion(s), {} naming a society "
              "we do not hold, {} skipped.".format(len(suggestions), unresolved, skipped))
    else:
        print("\n{} suggestion(s) stored, {} naming a society we do not hold "
              "(the queue shows those as a blocker), {} skipped."
              .format(written, unresolved, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
