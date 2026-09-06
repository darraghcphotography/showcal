"""Build the ticket-link worklist for delegated research.

Every upcoming show that has no ticket_url yet, with enough context for someone
to find the right booking page and enough of our own data to check their answer
against afterwards. Writes enrichment/ticket_worklist.json.

Run it in the container so it sees the real data:

    docker compose exec aims-web python build_ticket_worklist.py --db /data/aims.db \
        --out /data/ticket_worklist.json

then pull the file out and commit it beside the brief. Run against a local copy
of aims.db and you will get a worklist for whatever that copy last knew about,
which is not the same thing - the upcoming set turns over every week.
"""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(db_path, out_path, horizon_days=None):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    where = [
        "date(COALESCE(sh.closing_date, sh.opening_date)) >= date('now')",
        "sh.moderation_status = 'approved'",
        "(sh.ticket_url IS NULL OR TRIM(sh.ticket_url) = '')",
    ]
    params = []
    if horizon_days:
        where.append("date(sh.opening_date) <= date('now', ?)")
        params.append(f"+{horizon_days} days")

    rows = db.execute(
        f"""
        SELECT sh.id            AS show_id,
               sh.show          AS title,
               sh.opening_date,
               sh.closing_date,
               sh.venue,
               s.name           AS society_name,
               s.region,
               s.website_url    AS society_website,
               s.facebook_url   AS society_facebook,
               v.name           AS venue_name,
               v.town           AS venue_town,
               v.county         AS venue_county,
               v.website_url    AS venue_website,
               v.box_office_url AS venue_box_office
        FROM shows sh
        JOIN societies s ON s.id = sh.society_id
        LEFT JOIN venues v ON v.id = sh.venue_id
        WHERE {' AND '.join(where)}
        ORDER BY sh.opening_date, s.name
        """,
        params,
    ).fetchall()

    worklist = []
    for r in rows:
        worklist.append({
            # --- ours: context to search with. Do not edit these (RULES.md #3).
            "show_id": r["show_id"],
            "known_title": r["title"],
            "known_society": r["society_name"],
            "known_region": r["region"],
            "known_venue": r["venue_name"] or r["venue"],
            "known_town": r["venue_town"],
            "known_county": r["venue_county"],
            "known_opening_date": r["opening_date"],
            "known_closing_date": r["closing_date"],
            "known_society_website": r["society_website"],
            "known_society_facebook": r["society_facebook"],
            "known_venue_website": r["venue_website"],
            "known_venue_box_office": r["venue_box_office"],
            # --- theirs: to fill in, or to leave exactly as they are.
            "ticket_url": None,
            "ticket_url_kind": None,     # society | venue | ticketing_platform
            "dates_shown_on_page": None,
            "society_shown_on_page": None,
            "title_shown_on_page": None,
            "source_url": None,
            "notes": None,
        })

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(worklist, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(worklist)} shows without a ticket link -> {out_path}")
    return worklist


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="aims.db",
                   help="database to read (use /data/aims.db in the container)")
    p.add_argument("--out", default=str(ROOT / "enrichment" / "ticket_worklist.json"))
    p.add_argument("--horizon-days", type=int, default=None,
                   help="only shows opening within this many days (default: all upcoming)")
    args = p.parse_args()
    build(args.db, args.out, args.horizon_days)


if __name__ == "__main__":
    main()
