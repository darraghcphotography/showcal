import csv
import io
import json
import re
from datetime import date, timedelta

from flask import (Blueprint, Response, abort, current_app, request,
                   send_from_directory, url_for)

from .. import notify
from ..clock import utcnow_compact
from ..constants import REGIONS
from ..db import get_db
from ..productions import ON_RECORD_PRODUCTION

bp = Blueprint("feeds", __name__)

EXPORT_COLUMNS = [
    "season", "region", "section", "society", "show",
    "opening_date", "closing_date", "adjudication_date",
    "venue", "director", "musical_director", "choreographer",
    "review_status", "review_url", "ticket_url",
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


def _vevent(row, stamp):
    """One show as an all-day VEVENT.

    Shared by the subscribable feed and the single-show download so the two
    cannot drift - a show added to a calendar from its own page and the same
    show arriving via the feed must be the same event, or a subscriber ends up
    with both."""
    opening = row["opening_date"].replace("-", "")
    # DTEND for an all-day event is exclusive (the day *after* it ends), per
    # RFC 5545 - closing_date itself is the last day of the run.
    closing = row["closing_date"] or row["opening_date"]
    end_exclusive = (date.fromisoformat(closing) + timedelta(days=1)).strftime("%Y%m%d")

    summary = f"{row['show']} - {row['society_name']}"
    url = notify.link(url_for("public.show_detail", show_id=row["id"]))
    lines = [
        "BEGIN:VEVENT",
        # The same UID in both, deliberately. A calendar that already holds
        # this show from the feed updates it rather than duplicating it.
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
    return lines


def _calendar(lines, calname):
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DC Show Tracker//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{calname}",
    ] + lines + ["END:VCALENDAR"]
    return Response("\r\n".join(body) + "\r\n", mimetype="text/calendar")


@bp.route("/shows/<int:show_id>/calendar.ics")
def show_calendar_ics(show_id):
    """One show, downloaded rather than subscribed.

    This is the half the site was missing. `/calendar.ics` is a *subscription*
    to many shows that keeps updating; a committee member who just wants this
    one production in their own calendar had only the Google link, which is no
    use to them if they are on Apple Calendar or Outlook - and on an iPhone,
    opening an .ics is the native path, so forcing Google was the worse
    outcome for a large share of the audience.

    Deliberately not restricted to upcoming shows: a past run is a legitimate
    thing to file, and the feed has never restricted it either."""
    db = get_db()
    row = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.id = ? AND shows.moderation_status = 'approved'
          AND shows.show IS NOT NULL AND shows.opening_date IS NOT NULL
          AND NOT societies.hidden
        """,
        (show_id,),
    ).fetchone()
    if row is None:
        abort(404)

    response = _calendar(_vevent(row, utcnow_compact()),
                         f"{row['show']} - {row['society_name']}")
    # A filename makes the difference between "downloads as calendar.ics" and
    # something a person can find again in their downloads folder.
    slug = re.sub(r"[^a-z0-9]+", "-", row["show"].lower()).strip("-") or "show"
    response.headers["Content-Disposition"] = f'attachment; filename="{slug}.ics"'
    return response


@bp.route("/calendar.ics")
def calendar_ics():
    """Subscribable calendar feed of every approved, dated show - the full
    history, not just upcoming ones, since calendar apps handle past events
    fine and it keeps this simple (no separate "upcoming-only" feed to
    maintain). Optional ?section=Gilbert/Sullivan, ?region=<region>,
    ?society=<id> and/or ?season=<season> narrow it - same feed mechanism,
    just filtered (and combinable, e.g. ?society=12&season=25/26), so e.g. an
    adjudicator who only covers one tier, a visitor who only cares about
    their own region, or a society wanting just its own production history
    can subscribe to exactly that and have it genuinely auto-update
    (calendar apps periodically re-fetch a subscribed .ics URL) rather than
    needing a one-off export. Any other/missing value falls back to
    unfiltered on that dimension, same "invalid param -> default" convention
    as the rest of the site."""
    db = get_db()

    section = request.args.get("section")
    if section not in ("Gilbert", "Sullivan"):
        section = None
    region = request.args.get("region")
    if region not in REGIONS:
        region = None
    society_id = request.args.get("society", type=int)
    society_name = None
    if society_id is not None:
        society_row = db.execute(
            "SELECT name FROM societies WHERE id = ? AND NOT hidden", (society_id,)
        ).fetchone()
        if society_row is None:
            society_id = None
        else:
            society_name = society_row["name"]
    season = request.args.get("season")
    if season is not None and db.execute(
        "SELECT 1 FROM shows WHERE season = ? LIMIT 1", (season,)
    ).fetchone() is None:
        season = None

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
    if society_id:
        query += " AND shows.society_id = ?"
        params.append(society_id)
    if season:
        query += " AND shows.season = ?"
        params.append(season)
    query += " ORDER BY shows.opening_date"
    rows = db.execute(query, params).fetchall()

    calname_bits = [b for b in (section, region, society_name, season) if b]
    calname = f"DC Show Tracker - {' - '.join(calname_bits)}" if calname_bits else "DC Show Tracker"
    stamp = utcnow_compact()

    lines = []
    for row in rows:
        lines += _vevent(row, stamp)

    return _calendar(lines, calname)


@bp.route("/manifest.webmanifest")
def manifest():
    body = json.dumps({
        "name": "ShowCal — Irish Musical Society Tracker",
        "short_name": "ShowCal",
        "start_url": url_for("public.index"),
        "display": "standalone",
        "background_color": "#0b0f14",
        "theme_color": "#d4af37",
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
    body = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /submit/\n" f"Sitemap: {notify.link(url_for('feeds.sitemap_xml'))}\n"
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap_xml():
    db = get_db()
    today = date.today().isoformat()

    urls = [(notify.link(url_for("public.index")), today)]
    urls.append((notify.link(url_for("public.societies_list")), today))
    urls.append((notify.link(url_for("info.season_summary")), today))
    urls.append((notify.link(url_for("info.season_calendar")), today))
    urls.append((notify.link(url_for("info.stats")), today))
    urls.append((notify.link(url_for("public.adjudicators_list")), today))
    # The rest of the public site - present in the app's own nav but missing
    # from here until now, which meant search engines could never find them.
    urls.append((notify.link(url_for("public.titles_list")), today))
    urls.append((notify.link(url_for("public.venues_index")), today))
    urls.append((notify.link(url_for("info.awards")), today))
    urls.append((notify.link(url_for("public.reviews_index")), today))
    urls.append((notify.link(url_for("info.stats_trends")), today))
    urls.append((notify.link(url_for("public.about")), today))

    for row in db.execute("SELECT id FROM societies WHERE section != 'Inactive'").fetchall():
        urls.append((notify.link(url_for("public.society_detail", society_id=row["id"])), today))

    for row in db.execute(
        "SELECT id, updated_at FROM shows WHERE moderation_status = 'approved' AND show IS NOT NULL"
    ).fetchall():
        lastmod = (row["updated_at"] or today)[:10]
        urls.append((notify.link(url_for("public.show_detail", show_id=row["id"])), lastmod))

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
        urls.append((notify.link(url_for("public.title_detail", title=row["show"])), today))

    for row in db.execute("SELECT slug FROM venues").fetchall():
        urls.append((notify.link(url_for("public.venue_detail", venue=row["slug"])), today))

    # Only an adjudicator with at least one real assignment has a live page -
    # one added in /admin/adjudicators but never assigned yet 404s, same
    # rule adjudicators_list() applies to its own roster.
    for row in db.execute("SELECT DISTINCT adjudicator_id FROM adjudicator_assignments").fetchall():
        urls.append((notify.link(url_for("public.adjudicator_detail", adjudicator_id=row["adjudicator_id"])), today))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        xml.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    xml.append("</urlset>")

    return Response("\n".join(xml), mimetype="application/xml")
