"""Clears `show_info.rights_url` values that lead a visitor to the wrong show.

`title_detail.html` renders `rights_url` as a "Licensing page" link. 102 of the
221 we hold do not go where they say:

    57  redirect to the licensing house's homepage (retired product ID)
    32  serve a DIFFERENT show
    13  HTTP 404

The 32 are the dangerous ones. Concord Theatricals URLs are `/p/<id>/<slug>`
and **the ID is authoritative while the slug is decorative**, so a wrong ID
silently serves someone else's show under our slug:

    ours:  concordtheatricals.co.uk/p/44921/footloose
    lands: concordtheatricals.co.uk/p/44921/the-cocoanuts

A committee following that link researches, budgets or even licenses the wrong
title. A missing link is honest; that one is actively misleading, which is why
these are cleared rather than left until replacements are found.

**This was found by Antigravity's casting-data run** (2026-09-05) - it recorded
the URL it actually landed on rather than echoing back the one it was given,
which is the only reason the fault was visible. Claude initially and wrongly
read that as fabricated citations; see HANDBACK.md.

WHAT THIS DELIBERATELY DOES NOT TOUCH. 28 more URLs could not be checked from
here: 24 on `guidetomusicaltheatre.com` failed to connect and 4 MTI pages
returned 403. **This environment also cannot reach `example.com`**, so those
failures say nothing about the sites - the same trap that nearly had 69 live
society websites recorded as dead in August. They are left exactly as they are.

`licensing_house` is untouched throughout, so the page still tells a visitor
who licenses the show - they lose the deep link, not the information.

Usage:
    py scripts/backfills/clear_dead_rights_urls.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python \\
        scripts/backfills/clear_dead_rights_urls.py --db /data/aims.db --dry-run
"""
import argparse
import json
import sqlite3
from pathlib import Path

_here = Path(__file__).resolve()
# Only used to build the defaults. Falls back rather than raising when the file
# is run from somewhere other than the repo (copied into a container's /tmp, say)
# - both paths can be given explicitly, so an unresolvable root is not an error.
ROOT = _here.parents[2] if len(_here.parents) > 2 else Path.cwd()
DEFAULT_LIST = ROOT / "enrichment" / "dead_rights_urls.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--list", default=str(DEFAULT_LIST),
                        help="JSON of {show, rights_url, reason} confirmed dead")
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    dead = json.loads(Path(args.list).read_text(encoding="utf-8"))
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    cleared = skipped = missing = 0
    for row in dead:
        current = db.execute(
            "SELECT rights_url FROM show_info WHERE show = ?", (row["show"],)
        ).fetchone()
        if current is None:
            print(f"  MISSING  {row['show']} - no show_info row")
            missing += 1
            continue
        # Only clear the exact URL that was checked. If it has changed since,
        # someone has fixed it by hand and this must not undo that.
        if (current["rights_url"] or "").rstrip("/") != row["rights_url"].rstrip("/"):
            print(f"  CHANGED  {row['show']} - stored URL differs from the one checked, left alone")
            skipped += 1
            continue
        db.execute("UPDATE show_info SET rights_url = NULL WHERE show = ?", (row["show"],))
        print(f"  clear    {row['show'][:40]:<42} {row['reason'][:52]}")
        cleared += 1

    remaining = db.execute(
        "SELECT COUNT(*) FROM show_info WHERE rights_url IS NOT NULL AND rights_url != ''"
    ).fetchone()[0]

    print(f"\ncleared {cleared}, skipped {skipped}, missing {missing}")
    print(f"rights_url values remaining: {remaining}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print("\nWritten.")
    db.close()


if __name__ == "__main__":
    main()
