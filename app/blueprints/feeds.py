import csv
import io
import json
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, current_app, request, send_from_directory, url_for

from ..constants import REGIONS
from ..db import get_db
from ..productions import ON_RECORD_PRODUCTION

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
    maintain). Optional ?section=Gilbert/Sullivan and/or ?region=<region>
    narrow it - same feed mechanism, just filtered (and combinable, e.g.
    ?section=Gilbert&region=Eastern), so e.g. an adjudicator who only covers
    one tier, or a visitor who only cares about their own region, can
    subscribe to just their own shows and have it genuinely auto-update
    (calendar apps periodically re-fetch a subscribed .ics URL) rather than
    needing a one-off export. Any other/missing value falls back to
    unfiltered on that dimension, same "invalid param -> default" convention
    as the rest of the site."""
    section = request.args.get("section")
    if section not in ("Gilbert", "Sullivan"):
        section = None
    region = request.args.get("region")
    if region not in REGIONS:
        region = None

    db = get_db()
    query = """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved' AND shows.show IS NOT NULL
          AND shows.opening_date IS NOT NULL
          AND NOT societies.hidden
    """
    params = []
    if section:
        query += " AND shows.section = ?"
        params.append(section)
    if region:
        query += " AND shows.region = ?"
        params.append(region)
    query += " ORDER BY shows.opening_date"
    rows = db.execute(query, params).fetchall()

    calname_bits = [b for b in (section, region) if b]
    calname = f"DC Show Tracker - {' - '.join(calname_bits)}" if calname_bits else "DC Show Tracker"
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DC Show Tracker//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{calname}",
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


@bp.route("/manifest.webmanifest")
def manifest():
    body = json.dumps({
        "name": "DC Show Tracker",
        "short_name": "DC Show Tracker",
        "start_url": url_for("public.index"),
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#c8102e",
        "icons": [
            {"src": url_for("static", filename="favicon.svg"), "sizes": "any", "type": "image/svg+xml"},
            {"src": url_for("static", filename="icons/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": url_for("static", filename="icons/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": url_for("static", filename="icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    })
    return Response(body, mimetype="application/manifest+json")


@bp.route("/sw.js")
def service_worker():
    """Served at the root path (not /static/sw.js) so the service worker's
    default scope covers the whole site, not just /static/ - registered via
    url_for('feeds.service_worker') so this still resolves correctly when
    the app is mounted under a URL_PREFIX sub-path in production."""
    return send_from_directory(
        current_app.static_folder, "sw.js", mimetype="application/javascript"
    )


@bp.route("/robots.txt")
def robots_txt():
    body = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /submit/\n" f"Sitemap: {url_for('feeds.sitemap_xml', _external=True)}\n"
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap_xml():
    db = get_db()
    today = date.today().isoformat()

    urls = [(url_for("public.index", _external=True), today)]
    urls.append((url_for("public.societies_list", _external=True), today))
    urls.append((url_for("info.season_summary", _external=True), today))
    urls.append((url_for("info.stats", _external=True), today))
    urls.append((url_for("public.adjudicators_list", _external=True), today))
    # The rest of the public site - present in the app's own nav but missing
    # from here until now, which meant search engines could never find them.
    urls.append((url_for("public.titles_list", _external=True), today))
    urls.append((url_for("public.venues_index", _external=True), today))
    urls.append((url_for("info.awards", _external=True), today))
    urls.append((url_for("public.reviews_index", _external=True), today))
    urls.append((url_for("info.stats_trends", _external=True), today))
    urls.append((url_for("public.about", _external=True), today))

    for row in db.execute("SELECT id FROM societies WHERE section != 'Inactive'").fetchall():
        urls.append((url_for("public.society_detail", society_id=row["id"], _external=True), today))

    for row in db.execute(
        "SELECT id, updated_at FROM shows WHERE moderation_status = 'approved' AND show IS NOT NULL"
    ).fetchall():
        lastmod = (row["updated_at"] or today)[:10]
        urls.append((url_for("public.show_detail", show_id=row["id"], _external=True), lastmod))

    # One entry per distinct title, matching titles_list()'s own definition of
    # "a title on record" - these are some of the site's best, most-searched
    # pages and were entirely absent from the sitemap before. Read off
    # productions for the same reason the A-Z is: the old union's year filter
    # hid every title known only from a 2024+ award record, so those title
    # pages were missing from the sitemap as well as from the A-Z.
    for row in db.execute(
        f"""
        SELECT MIN(title) AS show FROM productions
        WHERE {ON_RECORD_PRODUCTION}
        GROUP BY title_key
        """
    ).fetchall():
        urls.append((url_for("public.title_detail", title=row["show"], _external=True), today))

    for row in db.execute("SELECT slug FROM venues").fetchall():
        urls.append((url_for("public.venue_detail", venue=row["slug"], _external=True), today))

    # Only an adjudicator with at least one real assignment has a live page -
    # one added in /admin/adjudicators but never assigned yet 404s, same
    # rule adjudicators_list() applies to its own roster.
    for row in db.execute("SELECT DISTINCT adjudicator_id FROM adjudicator_assignments").fetchall():
        urls.append((url_for("public.adjudicator_detail", adjudicator_id=row["adjudicator_id"], _external=True), today))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        xml.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    xml.append("</urlset>")

    return Response("\n".join(xml), mimetype="application/xml")
