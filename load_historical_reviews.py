"""Load reviews extracted by extract_historical_reviews.py into
historical_reviews as pending moderation-queue entries - see ROADMAP.md's
"Step 4" sections for the full design background.

Split from extraction on purpose: extraction needs PyMuPDF and the PDF
archive (E:\\showtimes archive), neither of which exist inside the Docker
container - this half only needs the JSON file and a database, so it's the
half that actually runs in production (`docker compose exec aims-web python
load_historical_reviews.py --db /data/aims.db`).

Nothing here writes to shows/societies - every row lands in historical_reviews
with moderation_status='pending' and is matched against the *existing*
shows/societies data only to pre-fill a confident (exact-match) society_id/
show_id, or set a flag for the moderator otherwise. See admin.py's
/admin/historical-reviews queue for what happens after that. Safe to re-run -
already-loaded reviews (same source_issue/society_raw/show_raw) are skipped.

Usage:
    py load_historical_reviews.py [--json historical_reviews_pilot.json] [--db aims.db]
"""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent


def get_or_create_adjudicator(db, name):
    row = db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    return db.execute("INSERT INTO adjudicators (name) VALUES (?)", (name,)).lastrowid


def match_society(db, society_raw):
    """Exact match only (see docs/data-model.md's title-matching convention -
    this project deliberately never fuzzy-matches). Tries the raw name as
    printed, then the part before a comma (many issues append a location,
    e.g. 'Bravo Theatre Group, Loughrea', that isn't part of the society's
    actual name on record)."""
    for candidate in (society_raw, society_raw.split(",")[0].strip()):
        row = db.execute("SELECT id FROM societies WHERE name = ?", (candidate,)).fetchone()
        if row:
            return row[0]
    return None


def match_show(db, society_id, season, show_raw):
    row = db.execute(
        "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ? AND moderation_status = 'approved'",
        (society_id, season, show_raw),
    ).fetchone()
    return row[0] if row else None


def load_reviews(db, reviews):
    inserted = skipped = matched = refreshed = 0
    for r in reviews:
        existing = db.execute(
            "SELECT id, review_text, moderation_status FROM historical_reviews "
            "WHERE source_issue = ? AND society_raw = ? AND show_raw = ?",
            (r["source_issue"], r["society_raw"], r["show_raw"]),
        ).fetchone()
        if existing:
            # Still pending (never approved or hand-edited) and the freshly
            # re-extracted text differs - re-run this after an extraction
            # fix (e.g. the line-wrap-per-line formatting bug) and already-
            # loaded rows pick up the corrected text too, not just new ones.
            # Never touches an approved row - that's already public/reviewed,
            # so a silent rewrite isn't safe even if the source text changed.
            if existing["moderation_status"] == "pending" and existing["review_text"] != r["review_text"]:
                db.execute(
                    "UPDATE historical_reviews SET review_text = ? WHERE id = ?",
                    (r["review_text"], existing["id"]),
                )
                refreshed += 1
            else:
                skipped += 1
            continue

        adjudicator_id = get_or_create_adjudicator(db, r["adjudicator"])
        society_id = match_society(db, r["society_raw"])
        show_id = None
        flag = "needs_check"
        if society_id is not None:
            show_id = match_show(db, society_id, r["season"], r["show_raw"])
            flag = None if show_id is not None else "no_show_match"
            if flag is None:
                matched += 1

        db.execute(
            """
            INSERT INTO historical_reviews
                (season, tier, show_raw, society_raw, adjudicator_id, review_text,
                 source_issue, show_id, society_id, flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (r["season"], r["tier"], r["show_raw"], r["society_raw"], adjudicator_id, r["review_text"],
             r["source_issue"], show_id, society_id, flag),
        )
        inserted += 1
    db.commit()
    return inserted, skipped, matched, refreshed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(ROOT / "historical_reviews_pilot.json"))
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    args = parser.parse_args()

    reviews = json.loads(Path(args.json).read_text(encoding="utf-8"))
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    inserted, skipped, matched, refreshed = load_reviews(db, reviews)
    print(
        f"Inserted {inserted}, skipped {skipped} already-loaded, {refreshed} refreshed with corrected "
        f"text, {matched} matched an existing show cleanly."
    )


if __name__ == "__main__":
    main()
