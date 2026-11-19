"""Record live aims.ie review links on their shows.

The aims.ie review publisher (Darragh's separate 26/27 review workflow, kept
in Google Drive, not this repo) posts each adjudicator review to the Wix blog
and then writes review_links.json: one entry per review that is **live on
aims.ie**, naming the ShowCal show it belongs to. This script applies that
file. It is the write-back half of the publisher <-> ShowCal sync (the read
half is the id/society_id/poster_url columns on /export/shows.csv).

    {"links": [
      {"show_id": 3103, "expect_society": "Fusion Theatre Group",
       "expect_season": "26/27", "review_url": "https://www.aims.ie/post/...",
       "adjudicator": "Justin Parkes"}
    ]}

Standing rule (Darragh, 2026-11-19): a review syncs to ShowCal only AFTER it
is live on aims.ie, never before. So before writing anything, each link is
fetched and must come back 200 from an aims.ie /post/ URL; a draft, scheduled
or deleted post (Wix answers those with a 404 or a redirect elsewhere) is
reported and skipped. There is no flag to bypass that check.

Each entry is applied conservatively, the same way load_aims_ie_backfill.py
treats its links:
  - skipped if the show no longer matches (gone, or a different society/season)
  - a show with no review link gets this one, review_status 'Published', and
    review_author from the adjudicator if that is blank
  - a show already holding this exact link is left alone (safe to re-run)
  - a show holding a DIFFERENT link is never overwritten - it is reported for
    a person to check (that is how two wrong links were caught on 2026-11-12)

Usage (in the container - always pass --db, see CLAUDE.md):
    python apply_review_links.py --db /data/aims.db --json /data/review_links.json --dry-run
    python apply_review_links.py --db /data/aims.db --json /data/review_links.json
"""
import argparse
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
AIMS_HOSTS = {"aims.ie", "www.aims.ie"}
USER_AGENT = "ShowCal review-link check"


def is_aims_post_url(url):
    parsed = urlparse(url or "")
    return parsed.scheme == "https" and parsed.netloc.lower() in AIMS_HOSTS and parsed.path.startswith("/post/")


def fetch_live(url, timeout=20):
    """(status, final_url) for a GET of url, following redirects."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, url


def live_problem(url, fetch):
    """None if url is a live aims.ie post, else a short reason it isn't."""
    if not is_aims_post_url(url):
        return "not an https aims.ie /post/ URL"
    try:
        status, final_url = fetch(url)
    except Exception as e:  # network error, timeout, DNS
        return f"could not be fetched ({e.__class__.__name__})"
    if status != 200:
        return f"not live on aims.ie (HTTP {status})"
    if not is_aims_post_url(final_url):
        return f"not live on aims.ie (redirected to {final_url})"
    return None


def apply_links(db, links, fetch, report):
    for item in links:
        label = f"show {item.get('show_id')} ({item.get('expect_society')}, {item.get('expect_season')})"
        url = (item.get("review_url") or "").strip()

        show = db.execute(
            """
            SELECT shows.id, shows.season, shows.review_url, shows.review_author, societies.name AS society_name
            FROM shows JOIN societies ON societies.id = shows.society_id
            WHERE shows.id = ?
            """,
            (item.get("show_id"),),
        ).fetchone()
        if show is None or show["society_name"] != item.get("expect_society") or show["season"] != item.get("expect_season"):
            report["skipped_no_match"].append(f"{label}: show no longer matches")
            continue

        if show["review_url"] == url:
            report["already_applied"] += 1
            continue

        problem = live_problem(url, fetch)
        if problem:
            report["skipped_not_live"].append(f"{label}: {url} - {problem}")
            continue

        if show["review_url"]:
            report["conflicts"].append(f"{label}: has {show['review_url']}, file says {url} - left as is")
            continue

        author = show["review_author"] or (item.get("adjudicator") or "").strip() or None
        db.execute(
            "UPDATE shows SET review_url = ?, review_status = 'Published', review_author = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (url, author, show["id"]),
        )
        report["applied"].append(f"{label}: {url}")


def main(argv=None, fetch=fetch_live):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", default=str(ROOT / "review_links.json"))
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true", help="report what would change, then roll back")
    args = parser.parse_args(argv)

    links = json.loads(Path(args.json).read_text(encoding="utf-8"))["links"]
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    report = {"applied": [], "already_applied": 0, "skipped_no_match": [], "skipped_not_live": [], "conflicts": []}
    apply_links(db, links, fetch, report)

    if args.dry_run:
        db.rollback()
    else:
        db.commit()
    db.close()

    print(("DRY RUN - nothing written. " if args.dry_run else "") + f"Database: {args.db}")
    print(f"Review links: {len(report['applied'])} applied, {report['already_applied']} already applied")
    for key in ("applied", "skipped_not_live", "conflicts", "skipped_no_match"):
        if report[key]:
            print(f"\n{key.replace('_', ' ').capitalize()} ({len(report[key])}):")
            for line in report[key]:
                print(f"  - {line}")
    return report


if __name__ == "__main__":
    main()
