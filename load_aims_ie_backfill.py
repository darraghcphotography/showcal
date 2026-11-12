"""Load the aims.ie (Wix) backfill into a showcal database.

aims_ie_backfill.json was exported read-only from the old aims.ie Wix site
on 2026-11-12 and matched against showcal offline. It holds three things,
each applied conservatively:

  reviews       302 adjudicator reviews from the aims.ie blog (23/24 onwards),
                inserted into historical_reviews with source='aims_ie' - which
                is why the app must have started once on the version that
                allows that value (app/db.py's
                _migrate_historical_reviews_source_check) before this runs.
                They land as 'pending' with show_id already set, so they sit
                in /admin/historical-reviews under "ready" for a moderator to
                read and bulk-approve. --approve publishes them directly.
  review_links  review_url fixes: shows that had no link to their aims.ie
                review, one pointing at the wrong review, one wrong link to
                clear. Applied only while the live value is still exactly
                what it was when the file was built.
  credits       director / musical director / choreographer from the Wix
                events collection (filled in by societies themselves).
                Blank fields only - a value already in showcal is never
                overwritten.

Every row names the show it was matched to (id, society, season) and is
skipped if the live show no longer matches - so a show merged, moved or
deleted since the file was built is reported, not written. Safe to re-run:
a review already loaded (same aims.ie URL) is skipped, and filled fields are
no longer blank.

Usage (in the container - always pass --db, see CLAUDE.md):
    python load_aims_ie_backfill.py --db /data/aims.db --dry-run
    python load_aims_ie_backfill.py --db /data/aims.db
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CREDIT_FIELDS = ("director", "musical_director", "choreographer")


def live_show(db, item):
    """The show this item was matched to, or None if it no longer matches
    (gone, or now a different society/season)."""
    row = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.id = ?
        """,
        (item["show_id"],),
    ).fetchone()
    if row is None or row["society_name"] != item["expect_society"] or row["season"] != item["expect_season"]:
        return None
    return row


def load_reviews(db, reviews, approve, report):
    adjudicators = {r["name"]: r["id"] for r in db.execute("SELECT id, name FROM adjudicators")}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in reviews:
        show = live_show(db, r)
        if show is None:
            report["reviews_skipped"].append(f"{r['wix_title']}: show {r['show_id']} no longer matches")
            continue
        if db.execute(
            "SELECT 1 FROM historical_reviews WHERE source = 'aims_ie' AND source_file = ?", (r["source_file"],)
        ).fetchone():
            report["reviews_already_loaded"] += 1
            continue
        if db.execute(
            "SELECT 1 FROM historical_reviews WHERE show_id = ? AND moderation_status = 'approved'", (show["id"],)
        ).fetchone():
            report["reviews_skipped"].append(f"{r['wix_title']}: show {show['id']} already has an approved review")
            continue
        adjudicator_id = adjudicators.get(r["adjudicator"]) if r["adjudicator"] else None
        if r["adjudicator"] and adjudicator_id is None:
            report["reviews_no_adjudicator"].append(f"{r['wix_title']}: no adjudicator named {r['adjudicator']!r}")
        db.execute(
            """
            INSERT INTO historical_reviews (
                season, tier, show_raw, society_raw, adjudicator_id, review_text, source_issue, source_file,
                show_id, society_id, moderation_status, moderated_by, moderated_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'aims_ie')
            """,
            (
                show["season"], r["tier"], show["show"] or r["show_raw"], show["society_name"], adjudicator_id,
                r["review_text"], r["source_issue"], r["source_file"], show["id"], show["society_id"],
                "approved" if approve else "pending",
                "aims_ie_backfill" if approve else None, now if approve else None,
            ),
        )
        report["reviews_inserted"] += 1


def apply_review_links(db, links, report):
    for link in links:
        show = live_show(db, link)
        if show is None:
            report["links_skipped"].append(f"show {link['show_id']}: no longer matches")
            continue
        if link.get("set_title") and not show["show"]:
            clash = db.execute(
                "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ? COLLATE NOCASE",
                (show["society_id"], show["season"], link["set_title"]),
            ).fetchone()
            if clash:
                report["links_skipped"].append(f"show {show['id']}: title {link['set_title']!r} already on show {clash['id']}")
                continue
            db.execute(
                "UPDATE shows SET show = ?, updated_at = datetime('now') WHERE id = ?", (link["set_title"], show["id"])
            )
            report["titles_set"] += 1
        if (show["review_url"] or None) == (link["new"] or None):
            report["links_already_applied"] += 1
            continue
        if (show["review_url"] or None) != (link["current"] or None):
            report["links_skipped"].append(
                f"show {show['id']}: review_url changed since the file was built (now {show['review_url']!r})"
            )
            continue
        if link["new"]:
            db.execute(
                "UPDATE shows SET review_url = ?, review_status = 'Published', updated_at = datetime('now') WHERE id = ?",
                (link["new"], show["id"]),
            )
        else:
            db.execute(
                "UPDATE shows SET review_url = NULL, updated_at = datetime('now') WHERE id = ?", (show["id"],)
            )
        report["links_changed"] += 1


def apply_credits(db, credits, report):
    for c in credits:
        if c["field"] not in CREDIT_FIELDS:
            raise ValueError(f"unexpected credit field {c['field']!r}")
        show = live_show(db, c)
        if show is None:
            report["credits_skipped"].append(f"show {c['show_id']}: no longer matches")
            continue
        if (show[c["field"]] or "").strip():
            report["credits_already_filled"] += 1
            continue
        db.execute(
            f"UPDATE shows SET {c['field']} = ?, updated_at = datetime('now') WHERE id = ?", (c["value"], show["id"])
        )
        report["credits_filled"][c["field"]] += 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", default=str(ROOT / "aims_ie_backfill.json"))
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true", help="report what would change, then roll back")
    parser.add_argument("--approve", action="store_true", help="publish reviews now instead of queueing them")
    parser.add_argument(
        "--only", default="reviews,links,credits", help="comma-separated subset of reviews,links,credits"
    )
    args = parser.parse_args(argv)
    parts = {p.strip() for p in args.only.split(",") if p.strip()}

    data = json.loads(Path(args.json).read_text(encoding="utf-8"))
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    table_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'historical_reviews'"
    ).fetchone()
    if "reviews" in parts and (table_sql is None or "aims_ie" not in table_sql[0]):
        sys.exit(
            "historical_reviews does not allow source='aims_ie' yet - start the app once on the version that "
            "adds it (it migrates on startup), then re-run."
        )

    report = {
        "reviews_inserted": 0, "reviews_already_loaded": 0, "reviews_skipped": [], "reviews_no_adjudicator": [],
        "links_changed": 0, "links_already_applied": 0, "titles_set": 0, "links_skipped": [],
        "credits_filled": {f: 0 for f in CREDIT_FIELDS}, "credits_already_filled": 0, "credits_skipped": [],
    }
    if "reviews" in parts:
        load_reviews(db, data["reviews"], args.approve, report)
    if "links" in parts:
        apply_review_links(db, data["review_links"], report)
    if "credits" in parts:
        apply_credits(db, data["credits"], report)

    if args.dry_run:
        db.rollback()
    else:
        db.commit()
    db.close()

    print(("DRY RUN - nothing written. " if args.dry_run else "") + f"Database: {args.db}")
    status = "approved" if args.approve else "pending, in /admin/historical-reviews"
    print(f"Reviews: {report['reviews_inserted']} inserted ({status}), {report['reviews_already_loaded']} already loaded")
    print(
        f"Review links: {report['links_changed']} changed, {report['links_already_applied']} already right, "
        f"{report['titles_set']} missing title(s) set"
    )
    filled = ", ".join(f"{n} {f.replace('_', ' ')}" for f, n in report["credits_filled"].items())
    print(f"Credits: {filled}; {report['credits_already_filled']} already had a value")
    for key in ("reviews_skipped", "reviews_no_adjudicator", "links_skipped", "credits_skipped"):
        if report[key]:
            print(f"\n{key.replace('_', ' ').capitalize()} ({len(report[key])}):")
            for line in report[key]:
                print(f"  - {line}")
    return report


if __name__ == "__main__":
    main()
