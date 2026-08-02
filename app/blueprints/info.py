from datetime import date

from flask import Blueprint, render_template, request

from ..constants import REGIONS, SHOW_SECTIONS
from ..db import get_db
from ..season import current_season

bp = Blueprint("info", __name__)

TOP_N = 10


@bp.route("/stats")
def stats():
    db = get_db()

    total_societies = db.execute("SELECT COUNT(*) FROM societies").fetchone()[0]
    total_shows = db.execute(
        "SELECT COUNT(*) FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'"
    ).fetchone()[0]
    total_titles = db.execute(
        "SELECT COUNT(DISTINCT show) FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'"
    ).fetchone()[0]

    # All-time counts fold in historical_results (AIMS awards archive, 1977
    # through the season before shows.csv's own coverage begins - see
    # schema.sql for why that split can't double-count a production).
    most_performed = db.execute(
        """
        SELECT show, COUNT(*) AS n FROM (
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION ALL
            SELECT show FROM historical_results WHERE show IS NOT NULL
        )
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """,
        (TOP_N,),
    ).fetchall()

    # "Most selected" = how many *different* societies have put this show on,
    # as opposed to "most performed" which also counts a society doing the
    # same show twice - a cleaner measure of a show's popularity across the
    # circuit than raw staging count. Split into two eras: the site's own
    # tracked data (23/24 onward - the "DC Database") on its own, and an
    # all-time view folding in the pre-2024 AIMS awards archive too. A
    # historical society without a societies.id match still counts as a
    # distinct selector, keyed by its name instead.
    most_selected_recent_era = db.execute(
        """
        SELECT show, COUNT(DISTINCT society_id) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved'
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """,
        (TOP_N,),
    ).fetchall()

    most_selected = db.execute(
        """
        SELECT show, COUNT(DISTINCT society_key) AS n FROM (
            SELECT show, 'id:' || society_id AS society_key FROM shows
            WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION ALL
            SELECT show, COALESCE('id:' || society_id, 'name:' || society_name) AS society_key
            FROM historical_results WHERE show IS NOT NULL
        )
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """,
        (TOP_N,),
    ).fetchall()

    one_offs = db.execute(
        """
        SELECT show FROM (
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION ALL
            SELECT show FROM historical_results WHERE show IS NOT NULL
        )
        GROUP BY show HAVING COUNT(*) = 1
        ORDER BY show
        """
    ).fetchall()

    historical_years = db.execute(
        "SELECT MIN(year), MAX(year), COUNT(DISTINCT year || show || society_name) FROM historical_results"
    ).fetchone()
    historical_from, historical_to, historical_productions = historical_years

    by_season = db.execute(
        """
        SELECT
            season,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled,
            COUNT(DISTINCT show) AS distinct_titles
        FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved'
        GROUP BY season ORDER BY season DESC
        """
    ).fetchall()

    by_region = db.execute(
        """
        SELECT region AS label, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved'
        GROUP BY region ORDER BY n DESC
        """
    ).fetchall()

    by_tier = db.execute(
        """
        SELECT section AS label, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND section IS NOT NULL
        GROUP BY section ORDER BY n DESC
        """
    ).fetchall()

    return render_template(
        "stats.html",
        total_societies=total_societies,
        total_shows=total_shows,
        total_titles=total_titles,
        most_performed=most_performed,
        most_selected=most_selected,
        most_selected_recent_era=most_selected_recent_era,
        one_offs=one_offs,
        by_season=by_season,
        by_region=by_region,
        by_tier=by_tier,
        historical_from=historical_from,
        historical_to=historical_to,
        historical_productions=historical_productions,
    )


@bp.route("/season")
def season_summary():
    db = get_db()

    all_seasons = [
        r["season"]
        for r in db.execute(
            "SELECT DISTINCT season FROM shows WHERE show IS NOT NULL ORDER BY season DESC"
        ).fetchall()
    ]

    current = current_season(db)
    requested = request.args.get("season", "")
    season = requested if requested in all_seasons else current

    region = request.args.get("region", "")
    tier = request.args.get("tier", "")

    query = """
        SELECT shows.*, societies.name AS society_name,
            (COALESCE(shows.closing_date, shows.opening_date) < ?) AS is_past
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.season = ? AND shows.moderation_status = 'approved' AND shows.show IS NOT NULL
    """
    params = [date.today().isoformat(), season]
    if region in REGIONS:
        query += " AND shows.region = ?"
        params.append(region)
    if tier in SHOW_SECTIONS:
        query += " AND shows.section = ?"
        params.append(tier)
    query += " ORDER BY (shows.opening_date IS NULL), shows.opening_date"

    rows = db.execute(query, params).fetchall()
    upcoming = [r for r in rows if not r["is_past"]]
    finished = [r for r in rows if r["is_past"]]

    return render_template(
        "season.html", season=season, upcoming=upcoming, finished=finished, all_seasons=all_seasons,
        is_current=(season == current),
        regions=REGIONS, tiers=SHOW_SECTIONS, selected_region=region, selected_tier=tier,
    )
