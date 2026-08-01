import csv
import io
from datetime import date

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
