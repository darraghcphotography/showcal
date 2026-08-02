from datetime import date

from flask import Blueprint, render_template, request

from ..constants import AWARD_RESULTS, REGIONS, SHOW_SECTIONS
from ..db import get_db
from ..season import current_season

bp = Blueprint("info", __name__)

TOP_N = 10

# shows.csv's own coverage begins at season 23/24, i.e. award-archive Year
# 2024 (see schema.sql). Any stat that treats a historical_results row as
# equivalent to a shows-table row (counting productions/stagings) must stay
# below this year to avoid counting a 23/24+ show twice - the Awards page and
# society pages don't have this problem since they show award-category detail
# that isn't tracked in shows at all, so they use the full archive instead.
SHOWS_COVERAGE_START_YEAR = 2024


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
    # SHOWS_COVERAGE_START_YEAR above for why that split can't double-count
    # a production, even though historical_results itself now holds the full
    # archive through the present day for the Awards page/society pages).
    most_performed = db.execute(
        """
        SELECT show, COUNT(*) AS n FROM (
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION ALL
            SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
        )
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """,
        (SHOWS_COVERAGE_START_YEAR, TOP_N),
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
            FROM historical_results WHERE show IS NOT NULL AND year < ?
        )
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """,
        (SHOWS_COVERAGE_START_YEAR, TOP_N),
    ).fetchall()

    one_offs = db.execute(
        """
        SELECT show FROM (
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION ALL
            SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
        )
        GROUP BY show HAVING COUNT(*) = 1
        ORDER BY show
        """,
        (SHOWS_COVERAGE_START_YEAR,),
    ).fetchall()

    historical_years = db.execute(
        "SELECT MIN(year), MAX(year), COUNT(DISTINCT year || show || society_name) FROM historical_results WHERE year < ?",
        (SHOWS_COVERAGE_START_YEAR,),
    ).fetchone()
    historical_from, historical_to, historical_productions = historical_years

    # Full archive (1977-present) - award-category detail isn't tracked in
    # shows at all, so no double-counting risk here, unlike the stats above.
    award_totals = db.execute(
        """
        SELECT COUNT(*), SUM(CASE WHEN result = 'Winner' THEN 1 ELSE 0 END), MIN(year), MAX(year)
        FROM historical_results
        """
    ).fetchone()
    award_total_records, award_total_winners, award_from, award_to = award_totals

    most_award_wins = db.execute(
        """
        SELECT COALESCE(society_name, 'Unknown') AS label, COUNT(*) AS n
        FROM historical_results
        WHERE result = 'Winner' AND society_name IS NOT NULL
        GROUP BY COALESCE(society_id, society_name)
        ORDER BY n DESC, label
        LIMIT ?
        """,
        (TOP_N,),
    ).fetchall()

    most_best_show_wins = db.execute(
        """
        SELECT COALESCE(society_name, 'Unknown') AS label, COUNT(*) AS n
        FROM historical_results
        WHERE result = 'Winner' AND category_name = 'Best Overall Show' AND society_name IS NOT NULL
        GROUP BY COALESCE(society_id, society_name)
        ORDER BY n DESC, label
        LIMIT ?
        """,
        (TOP_N,),
    ).fetchall()

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
        award_total_records=award_total_records,
        award_total_winners=award_total_winners,
        award_from=award_from,
        award_to=award_to,
        most_award_wins=most_award_wins,
        most_best_show_wins=most_best_show_wins,
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


@bp.route("/awards")
def awards():
    db = get_db()

    year = request.args.get("year", "").strip()
    category = request.args.get("category", "")
    tier = request.args.get("tier", "")
    result = request.args.get("result", "Winner")
    q = request.args.get("q", "").strip()

    years = [r[0] for r in db.execute(
        "SELECT DISTINCT year FROM historical_results ORDER BY year DESC"
    ).fetchall()]
    categories = [r[0] for r in db.execute(
        "SELECT DISTINCT category_name FROM historical_results WHERE category_name IS NOT NULL ORDER BY category_name"
    ).fetchall()]

    query = """
        SELECT historical_results.*, societies.id AS resolved_society_id
        FROM historical_results
        LEFT JOIN societies ON societies.id = historical_results.society_id
        WHERE 1=1
    """
    params = []
    if year.isdigit():
        query += " AND year = ?"
        params.append(int(year))
    if category:
        query += " AND category_name = ?"
        params.append(category)
    if tier in ("Gilbert", "Sullivan"):
        query += " AND tier = ?"
        params.append(tier)
    if result in AWARD_RESULTS:
        query += " AND result = ?"
        params.append(result)
    if q:
        query += " AND (society_name LIKE ? ESCAPE '\\' OR show LIKE ? ESCAPE '\\' OR nominee_name LIKE ? ESCAPE '\\')"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        params += [like, like, like]
    query += " ORDER BY year DESC, category_name, society_name"

    rows = db.execute(query, params).fetchall()

    return render_template(
        "awards.html", rows=rows, years=years, categories=categories, results=AWARD_RESULTS,
        selected_year=year, selected_category=category, selected_tier=tier, selected_result=result, q=q,
    )
