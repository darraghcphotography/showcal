import csv
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, url_for

from ..db import get_db

bp = Blueprint("feeds", __name__)

EXPORT_COLUMNS = [
    "season", "region", "section", "society", "show",
    "opening_date", "closing_date", "adjudication_date",
    "venue", "director", "musical_director", "choreographer",
    "review_status", "review_url", "ticket_url", "status",
]


@bp.route("/export/shows.csv")
def export_shows_csv():
    """Public read-only export of everything visible on the site - the same
    data as the browse pages, just as one file. Approved shows only, same as
    everywhere else; this can never leak a pending/rejected submission."""
    db = get_db()
    rows = db.execute(
        """
        SELECT societies.name AS society, shows.*
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved' AND shows.show IS NOT NULL
        ORDER BY shows.season, societies.name
        """
    ).fetchall()

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=aims-shows.csv"},
    )


def _ics_escape(text):
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


@bp.route("/calendar.ics")
def calendar_ics():
    """Subscribable calendar feed of every approved, dated show - the full
    history, not just upcoming ones, since calendar apps handle past events
    fine and it keeps this simple (no separate "upcoming-only" feed to
    maintain)."""
    db = get_db()
    rows = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved' AND shows.show IS NOT NULL
          AND shows.opening_date IS NOT NULL
        ORDER BY shows.opening_date
        """
    ).fetchall()

    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Unofficial AIMS Show Tracker//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:AIMS Show Tracker",
    ]

    for row in rows:
        opening = row["opening_date"].replace("-", "")
        # DTEND for an all-day event is exclusive (the day *after* it ends),
        # per RFC 5545 - closing_date itself is the last day of the run.
        closing = row["closing_date"] or row["opening_date"]
        end_exclusive = (date.fromisoformat(closing) + timedelta(days=1)).strftime("%Y%m%d")

        summary = f"{row['show']} - {row['society_name']}"
        url = url_for("public.show_detail", show_id=row["id"], _external=True)

        lines += [
            "BEGIN:VEVENT",
            f"UID:show-{row['id']}@aims-show-tracker",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{opening}",
            f"DTEND;VALUE=DATE:{end_exclusive}",
            f"SUMMARY:{_ics_escape(summary)}",
            f"URL:{url}",
        ]
        if row["venue"]:
            lines.append(f"LOCATION:{_ics_escape(row['venue'])}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    return Response("\r\n".join(lines) + "\r\n", mimetype="text/calendar")


@bp.route("/robots.txt")
def robots_txt():
    body = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /submit/\n" f"Sitemap: {url_for('feeds.sitemap_xml', _external=True)}\n"
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap_xml():
    db = get_db()
    today = date.today().isoformat()

    urls = [(url_for("public.index", _external=True), today)]
    urls.append((url_for("info.season_summary", _external=True), today))
    urls.append((url_for("info.stats", _external=True), today))

    for row in db.execute("SELECT id FROM societies WHERE section != 'Inactive'").fetchall():
        urls.append((url_for("public.society_detail", society_id=row["id"], _external=True), today))

    for row in db.execute(
        "SELECT id, updated_at FROM shows WHERE moderation_status = 'approved' AND show IS NOT NULL"
    ).fetchall():
        lastmod = (row["updated_at"] or today)[:10]
        urls.append((url_for("public.show_detail", show_id=row["id"], _external=True), lastmod))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        xml.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    xml.append("</urlset>")

    return Response("\n".join(xml), mimetype="application/xml")
