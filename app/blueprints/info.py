import random
from datetime import date, datetime

from flask import Blueprint, render_template, request

from ..constants import (
    AWARD_CATEGORIES,
    AWARD_CATEGORY_BY_KEY,
    AWARD_RESULTS,
    DEFAULT_AWARD_CATEGORY,
    REGIONS,
    SHOW_SECTIONS,
    SHOWS_COVERAGE_START_YEAR,
    SOCIETY_AWARD_CATEGORY_NAMES,
)
from ..db import get_db
from ..search import fts_match_ids
from ..season import current_season

bp = Blueprint("info", __name__)

TOP_N = 10


@bp.route("/stats")
def stats():
    db = get_db()
    today = date.today().isoformat()
    region = request.args.get("region", "")
    if region not in REGIONS:
        region = ""

    # A show only counts toward "how many have actually happened" once it's
    # opened and wasn't cancelled - excludes announced-but-not-yet-run shows
    # (which may still fall through) and cancelled slots from every count/
    # chart below that isn't explicitly about the awards archive (which is
    # inherently already-happened, since an award implies it was judged).
    happened = "shows.status IS NOT 'Cancelled' AND COALESCE(shows.closing_date, shows.opening_date) <= ?"

    def region_clause(params):
        if region:
            params.append(region)
            return " AND shows.region = ?"
        return ""

    # For historical_results-based queries: a society resolves to a region
    # either via a matched current societies row, or via a moderator-
    # confirmed guess for a defunct/unmatched historical society (see
    # /admin/historical-societies) - falling back to societies.region first
    # since that's the authoritative, current value. Still excludes anything
    # neither matched nor confirmed whenever a region is selected.
    hist_join = (
        "LEFT JOIN societies hr_soc ON hr_soc.id = historical_results.society_id "
        "LEFT JOIN historical_society_regions hr_guess ON hr_guess.society_name = historical_results.society_name"
    )

    def hist_region_clause(params):
        if region:
            params.append(region)
            return " AND COALESCE(hr_soc.region, hr_guess.confirmed_region) = ?"
        return ""

    total_societies = db.execute("SELECT COUNT(*) FROM societies").fetchone()[0]

    params = [today]
    query = f"SELECT COUNT(*) FROM shows WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND {happened}"
    query += region_clause(params)
    total_shows = db.execute(query, params).fetchone()[0]

    params = [today]
    query = f"SELECT COUNT(DISTINCT shows.show) FROM shows WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND {happened}"
    query += region_clause(params)
    total_titles = db.execute(query, params).fetchone()[0]

    # All-time counts fold in historical_results (AIMS awards archive, 1977
    # through the season before shows.csv's own coverage begins - see
    # SHOWS_COVERAGE_START_YEAR above for why that split can't double-count
    # a production, even though historical_results itself now holds the full
    # archive through the present day for the Awards page/society pages).
    # Region-filterable on both halves - an unmatched historical society has
    # no region on record, so it's excluded whenever a region is selected.
    params = [today]
    hist_params = [SHOWS_COVERAGE_START_YEAR]
    hist_region_sql = hist_region_clause(hist_params)
    query = f"""
        SELECT show, COUNT(*) AS n FROM (
            SELECT shows.show AS show FROM shows
            WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND {happened}
            {region_clause(params)}
            UNION ALL
            SELECT historical_results.show AS show FROM historical_results {hist_join}
            WHERE historical_results.show IS NOT NULL AND historical_results.year < ?
            {hist_region_sql}
        )
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """
    most_performed = db.execute(query, params + hist_params + [TOP_N]).fetchall()

    # "Most selected" = how many *different* societies have put this show on,
    # as opposed to "most performed" which also counts a society doing the
    # same show twice - a cleaner measure of a show's popularity across the
    # circuit than raw staging count. Split into two eras: the site's own
    # tracked data (23/24 onward - the "DC Database") on its own, and an
    # all-time view folding in the pre-2024 AIMS awards archive too. A
    # historical society without a societies.id match still counts as a
    # distinct selector, keyed by its name instead.
    params = [today]
    query = f"""
        SELECT show, COUNT(DISTINCT society_id) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND {happened}
    """
    query += region_clause(params)
    query += " GROUP BY show ORDER BY n DESC, show LIMIT ?"
    params.append(TOP_N)
    most_selected_recent_era = db.execute(query, params).fetchall()

    params = [today]
    hist_params = [SHOWS_COVERAGE_START_YEAR]
    hist_region_sql = hist_region_clause(hist_params)
    query = f"""
        SELECT show, COUNT(DISTINCT society_key) AS n FROM (
            SELECT shows.show AS show, 'id:' || shows.society_id AS society_key FROM shows
            WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND {happened}
            {region_clause(params)}
            UNION ALL
            SELECT historical_results.show AS show,
                   COALESCE('id:' || historical_results.society_id, 'name:' || historical_results.society_name) AS society_key
            FROM historical_results {hist_join}
            WHERE historical_results.show IS NOT NULL AND historical_results.year < ?
            {hist_region_sql}
        )
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """
    most_selected = db.execute(query, params + hist_params + [TOP_N]).fetchall()

    params = [today]
    hist_params = [SHOWS_COVERAGE_START_YEAR]
    hist_region_sql = hist_region_clause(hist_params)
    query = f"""
        SELECT show FROM (
            SELECT shows.show AS show FROM shows
            WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND {happened}
            {region_clause(params)}
            UNION ALL
            SELECT historical_results.show AS show FROM historical_results {hist_join}
            WHERE historical_results.show IS NOT NULL AND historical_results.year < ?
            {hist_region_sql}
        )
        GROUP BY show HAVING COUNT(*) = 1
        ORDER BY show
        """
    one_offs = db.execute(query, params + hist_params).fetchall()

    params = [SHOWS_COVERAGE_START_YEAR]
    query = f"""
        SELECT MIN(historical_results.year), MAX(historical_results.year),
               COUNT(DISTINCT historical_results.year || historical_results.show || historical_results.society_name)
        FROM historical_results {hist_join}
        WHERE historical_results.year < ?
    """
    query += hist_region_clause(params)
    historical_years = db.execute(query, params).fetchone()
    historical_from, historical_to, historical_productions = historical_years

    # Full archive (1977-present) - award-category detail isn't tracked in
    # shows at all, so no double-counting risk here, unlike the stats above.
    params = []
    query = f"""
        SELECT COUNT(*), SUM(CASE WHEN historical_results.result = 'Winner' THEN 1 ELSE 0 END),
               MIN(historical_results.year), MAX(historical_results.year)
        FROM historical_results {hist_join}
        WHERE 1=1
    """
    query += hist_region_clause(params)
    award_totals = db.execute(query, params).fetchone()
    award_total_records, award_total_winners, award_from, award_to = award_totals

    params = []
    query = f"""
        SELECT COALESCE(historical_results.society_name, 'Unknown') AS label, COUNT(*) AS n
        FROM historical_results {hist_join}
        WHERE historical_results.result = 'Winner' AND historical_results.society_name IS NOT NULL
    """
    query += hist_region_clause(params)
    query += " GROUP BY COALESCE(historical_results.society_id, historical_results.society_name) ORDER BY n DESC, label LIMIT ?"
    params.append(TOP_N)
    most_award_wins = db.execute(query, params).fetchall()

    # Award category leaderboard picker - one category (default "Best Overall
    # Show") + optional Gilbert/Sullivan tier, chosen via dropdowns on the
    # page (GET params, same pattern as the region filter). Replaces what
    # used to be a fixed "Best Overall Show" wins card - that's now just the
    # default selection rather than the only category on offer. "person"
    # categories (Best Director, Best Actor, etc.) group/label by
    # nominee_name; "society" categories group/label by society_name, same
    # as most_award_wins above - see AWARD_CATEGORIES in constants.py for
    # which is which and why (it's checked against real data, not assumed
    # from the column name).
    # A bare visit (no award_category param at all) picks a random category
    # each time, rather than always landing on Best Overall Show - avoids the
    # Explorer's default view itself becoming a fixed "who's won the most"
    # leaderboard for whichever society happens to lead that one category.
    # An explicitly-chosen-but-invalid value (a stale/hand-edited URL) still
    # falls back to the fixed default rather than randomizing - that's a
    # correction, not a fresh landing.
    award_category_param = request.args.get("award_category")
    if award_category_param is None:
        award_category = random.choice(AWARD_CATEGORIES)["key"]
    elif award_category_param in AWARD_CATEGORY_BY_KEY:
        award_category = award_category_param
    else:
        award_category = DEFAULT_AWARD_CATEGORY
    award_tier = request.args.get("award_tier", "")
    if award_tier not in ("Gilbert", "Sullivan"):
        award_tier = ""
    award_category_entry = AWARD_CATEGORY_BY_KEY[award_category]

    db_names = award_category_entry["db_names"]
    params = list(db_names)
    cat_placeholders = ",".join("?" * len(db_names))
    tier_sql = ""
    if award_tier:
        tier_sql = " AND historical_results.tier = ?"
        params.append(award_tier)
    if award_category_entry["person"]:
        query = f"""
            SELECT historical_results.nominee_name AS label, COUNT(*) AS n
            FROM historical_results {hist_join}
            WHERE historical_results.result = 'Winner'
              AND historical_results.category_name IN ({cat_placeholders})
              AND historical_results.nominee_name IS NOT NULL
              {tier_sql}
        """
        query += hist_region_clause(params)
        query += " GROUP BY historical_results.nominee_name ORDER BY n DESC, label LIMIT ?"
    else:
        query = f"""
            SELECT COALESCE(historical_results.society_name, 'Unknown') AS label, COUNT(*) AS n
            FROM historical_results {hist_join}
            WHERE historical_results.result = 'Winner'
              AND historical_results.category_name IN ({cat_placeholders})
              AND historical_results.society_name IS NOT NULL
              {tier_sql}
        """
        query += hist_region_clause(params)
        query += " GROUP BY COALESCE(historical_results.society_id, historical_results.society_name) ORDER BY n DESC, label LIMIT ?"
    params.append(TOP_N)
    award_leaderboard = db.execute(query, params).fetchall()

    # Winner counts grouped BY region (not filtered to the page's selected
    # region - this chart shows every region side by side). Covers societies
    # matched to a current societies row, plus any defunct/unmatched
    # historical society with a moderator-confirmed region guess (see
    # /admin/historical-societies) - anything still neither is left out.
    wins_by_region = db.execute(
        f"""
        SELECT COALESCE(hr_soc.region, hr_guess.confirmed_region) AS label, COUNT(*) AS n
        FROM historical_results {hist_join}
        WHERE historical_results.result = 'Winner'
        GROUP BY label HAVING label IS NOT NULL ORDER BY n DESC
        """
    ).fetchall()

    # Unmatched societies (when no region filter) included by name - a society
    # with several nominations but not a single win. Aggregates over every
    # result type per society (not just pre-filtered to 'Nominee' rows) since
    # the HAVING clause needs to see the Winner rows too, to confirm there are
    # none - filtering them out in WHERE would make that check vacuously true.
    params = []
    query = f"""
        SELECT COALESCE(historical_results.society_name, 'Unknown') AS label,
               SUM(CASE WHEN historical_results.result = 'Nominee' THEN 1 ELSE 0 END) AS n
        FROM historical_results {hist_join}
        WHERE historical_results.society_name IS NOT NULL
    """
    query += hist_region_clause(params)
    query += """
        GROUP BY COALESCE(historical_results.society_id, historical_results.society_name)
        HAVING SUM(CASE WHEN historical_results.result = 'Winner' THEN 1 ELSE 0 END) = 0 AND n >= 3
        ORDER BY n DESC, label
        LIMIT ?
    """
    params.append(TOP_N)
    most_nominated_no_wins = db.execute(query, params).fetchall()

    # Wins as a share of (wins + nominations) - rewards a strong hit rate
    # over sheer volume. Minimum 5 nominations so one lucky nomination can't
    # look like a 100% record.
    params = []
    query = f"""
        SELECT COALESCE(historical_results.society_name, 'Unknown') AS label,
               SUM(CASE WHEN historical_results.result = 'Winner' THEN 1 ELSE 0 END) AS wins,
               COUNT(*) AS total,
               ROUND(SUM(CASE WHEN historical_results.result = 'Winner' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS pct
        FROM historical_results {hist_join}
        WHERE historical_results.result IN ('Winner', 'Nominee') AND historical_results.society_name IS NOT NULL
    """
    query += hist_region_clause(params)
    query += """
        GROUP BY COALESCE(historical_results.society_id, historical_results.society_name)
        HAVING total >= 5
        ORDER BY pct DESC, wins DESC
        LIMIT ?
    """
    params.append(TOP_N)
    win_rate_leaderboard = db.execute(query, params).fetchall()

    # Recent era only (region-filterable, like the other shows-table stats) -
    # each society's own most-repeated title, i.e. their "usual suspect".
    # Needs at least 2 stagings of the same title to count as a real signature.
    params = [today]
    region_sql = ""
    if region:
        region_sql = " AND region = ?"
        params.append(region)
    signature_show = db.execute(
        f"""
        WITH counts AS (
            SELECT society_id, show, COUNT(*) AS n,
                   ROW_NUMBER() OVER (PARTITION BY society_id ORDER BY COUNT(*) DESC, show) AS rn
            FROM shows
            WHERE show IS NOT NULL AND moderation_status = 'approved' AND {happened}{region_sql}
            GROUP BY society_id, show
        )
        SELECT societies.name AS label, counts.show, counts.n
        FROM counts JOIN societies ON societies.id = counts.society_id
        WHERE counts.rn = 1 AND counts.n >= 2
        ORDER BY counts.n DESC, label
        LIMIT ?
        """,
        (*params, TOP_N),
    ).fetchall()

    # All-time, combining both eras like most_selected/most_performed above.
    # Region-filterable on both halves - the recent-era half via its
    # societies join, the historical half via the same societies-or-
    # confirmed-guess fallback as the rest of the awards-archive stats above.
    region_filter_shows = " AND societies.region = ?" if region else ""
    region_filter_hist = " AND COALESCE(societies.region, hr_guess.confirmed_region) = ?" if region else ""
    params = [today] + ([region] if region else [])
    hist_params = [SHOWS_COVERAGE_START_YEAR] + ([region] if region else [])
    query = f"""
        SELECT label, COUNT(*) AS n FROM (
            SELECT 'id:' || shows.society_id AS key, societies.name AS label
            FROM shows JOIN societies ON societies.id = shows.society_id
            WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND {happened}
            {region_filter_shows}
            UNION ALL
            SELECT COALESCE('id:' || historical_results.society_id, 'name:' || historical_results.society_name) AS key,
                   COALESCE(societies.name, historical_results.society_name) AS label
            FROM historical_results
            LEFT JOIN societies ON societies.id = historical_results.society_id
            LEFT JOIN historical_society_regions hr_guess ON hr_guess.society_name = historical_results.society_name
            WHERE historical_results.show IS NOT NULL AND historical_results.year < ?
            {region_filter_hist}
        )
        GROUP BY key ORDER BY n DESC, label LIMIT ?
        """
    most_prolific_society = db.execute(query, params + hist_params + [TOP_N]).fetchall()

    # total/distinct_titles only count shows that have actually happened
    # (see `happened` above) - cancelled shows aren't counted or referenced
    # here at all.
    params = [today, today]
    query = f"""
        SELECT
            season,
            SUM(CASE WHEN {happened} THEN 1 ELSE 0 END) AS total,
            COUNT(DISTINCT CASE WHEN {happened} THEN show END) AS distinct_titles
        FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved'
    """
    query += region_clause(params)
    query += " GROUP BY season ORDER BY season DESC"
    by_season = db.execute(query, params).fetchall()

    # Split at the site's own tracked-data boundary (see SHOWS_COVERAGE_START_YEAR)
    # rather than an arbitrary "top N" - a society backfilling decades of its own
    # history via bulk-add is expected/encouraged, but it shouldn't make the
    # by-far-most-complete recent seasons look like a rounding error in a page-long
    # list of mostly-1-show seasons. Earlier seasons stay fully visible, just
    # collapsed behind a <details> disclosure by default.
    coverage_start_season = f"{(SHOWS_COVERAGE_START_YEAR - 1) % 100:02d}/{SHOWS_COVERAGE_START_YEAR % 100:02d}"
    by_season_recent = [r for r in by_season if r["season"] >= coverage_start_season]
    by_season_earlier = [r for r in by_season if r["season"] < coverage_start_season]

    by_region = db.execute(
        f"""
        SELECT region AS label, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND {happened}
        GROUP BY region ORDER BY n DESC
        """,
        (today,),
    ).fetchall()

    params = [today]
    query = f"""
        SELECT section AS label, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND section IS NOT NULL AND {happened}
    """
    query += region_clause(params)
    query += " GROUP BY section ORDER BY n DESC"
    by_tier = db.execute(query, params).fetchall()

    # A few computed highlights - region-aware where that naturally applies.
    fun_facts = []

    params = [today]
    query = f"""
        SELECT season, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND {happened}
    """
    query += region_clause(params)
    query += " GROUP BY season ORDER BY n DESC LIMIT 1"
    busiest = db.execute(query, params).fetchone()
    if busiest:
        where = f" in {region}" if region else ""
        fun_facts.append(f"The busiest season on record{where} is {busiest['season']}, with {busiest['n']} shows.")

    params = []
    query = f"""
        SELECT COALESCE(historical_results.society_name, 'Unknown') AS label,
               MIN(historical_results.year) AS first_year, MAX(historical_results.year) AS last_year
        FROM historical_results {hist_join}
        WHERE historical_results.society_name IS NOT NULL
    """
    query += hist_region_clause(params)
    query += """
        GROUP BY COALESCE(historical_results.society_id, historical_results.society_name)
        ORDER BY (last_year - first_year) DESC LIMIT 1
    """
    longest = db.execute(query, params).fetchone()
    if longest and longest["last_year"] > longest["first_year"]:
        span = longest["last_year"] - longest["first_year"]
        fun_facts.append(
            f"{longest['label']} has the longest span on record: {span} years, "
            f"from {longest['first_year']} to {longest['last_year']}."
        )

    params = []
    query = f"""
        SELECT COUNT(DISTINCT historical_results.society_id)
        FROM historical_results {hist_join}
        WHERE historical_results.result = 'Winner' AND historical_results.society_id IS NOT NULL
    """
    query += hist_region_clause(params)
    winning_societies = db.execute(query, params).fetchone()[0]
    if region:
        region_society_total = db.execute(
            "SELECT COUNT(*) FROM societies WHERE region = ?", (region,)
        ).fetchone()[0]
    else:
        region_society_total = total_societies
    where = f" in {region}" if region else ""
    fun_facts.append(
        f"{winning_societies} of {region_society_total} societies{where} have won at least one award category."
    )

    return render_template(
        "stats.html",
        total_societies=total_societies,
        total_shows=total_shows,
        total_titles=total_titles,
        most_performed=most_performed,
        most_selected=most_selected,
        most_selected_recent_era=most_selected_recent_era,
        one_offs=one_offs,
        by_season=by_season_recent,
        by_season_earlier=by_season_earlier,
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
        award_categories=AWARD_CATEGORIES,
        selected_award_category=award_category,
        selected_award_tier=award_tier,
        award_leaderboard=award_leaderboard,
        award_leaderboard_is_person=award_category_entry["person"],
        wins_by_region=wins_by_region,
        most_nominated_no_wins=most_nominated_no_wins,
        win_rate_leaderboard=win_rate_leaderboard,
        signature_show=signature_show,
        most_prolific_society=most_prolific_society,
        fun_facts=fun_facts,
        regions=REGIONS,
        selected_region=region,
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
    hide_cancelled = request.args.get("hide_cancelled") == "1"
    sort = request.args.get("sort", "asc")
    if sort not in ("asc", "desc"):
        sort = "asc"

    query = """
        SELECT shows.*, societies.name AS society_name,
            (COALESCE(shows.closing_date, shows.opening_date) < ?) AS is_past
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.season = ? AND shows.moderation_status = 'approved' AND shows.show IS NOT NULL
          AND NOT societies.hidden
    """
    params = [date.today().isoformat(), season]
    if region in REGIONS:
        query += " AND shows.region = ?"
        params.append(region)
    if tier in SHOW_SECTIONS:
        query += " AND shows.section = ?"
        params.append(tier)
    if hide_cancelled:
        query += " AND shows.status IS NOT 'Cancelled'"
    # NULL opening dates always sort last regardless of direction - only the
    # dated rows actually flip.
    query += f" ORDER BY (shows.opening_date IS NULL), shows.opening_date {'DESC' if sort == 'desc' else 'ASC'}"

    rows = db.execute(query, params).fetchall()
    upcoming = [r for r in rows if not r["is_past"]]
    finished = [r for r in rows if r["is_past"]]

    span = db.execute(
        "SELECT MIN(shows.opening_date), MAX(shows.opening_date) FROM shows "
        "JOIN societies ON societies.id = shows.society_id "
        "WHERE shows.season = ? AND shows.moderation_status = 'approved' AND shows.show IS NOT NULL "
        "AND NOT societies.hidden",
        (season,),
    ).fetchone()
    season_range_label = None
    if span[0] and span[1]:
        start = datetime.strptime(span[0], "%Y-%m-%d")
        end = datetime.strptime(span[1], "%Y-%m-%d")
        if start.year == end.year and start.month == end.month:
            season_range_label = start.strftime("%b %Y")
        else:
            season_range_label = f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"

    return render_template(
        "season.html", season=season, upcoming=upcoming, finished=finished, all_seasons=all_seasons,
        is_current=(season == current), is_past_season=(season < current), is_future_season=(season > current),
        season_range_label=season_range_label,
        regions=REGIONS, tiers=SHOW_SECTIONS, selected_region=region, selected_tier=tier,
        hide_cancelled=hide_cancelled, sort=sort,
    )


AWARDS_PAGE_SIZES = [50, 100]


@bp.route("/awards")
def awards():
    db = get_db()

    year = request.args.get("year", "").strip()
    category = request.args.get("category", "")
    tier = request.args.get("tier", "")
    result = request.args.get("result", "Winner")
    q = request.args.get("q", "").strip()

    per_page = request.args.get("per_page", type=int, default=AWARDS_PAGE_SIZES[0])
    if per_page not in AWARDS_PAGE_SIZES:
        per_page = AWARDS_PAGE_SIZES[0]
    page = request.args.get("page", type=int, default=1)
    if page < 1:
        page = 1

    years = [r[0] for r in db.execute(
        "SELECT DISTINCT year FROM historical_results ORDER BY year DESC"
    ).fetchall()]
    categories = [r[0] for r in db.execute(
        "SELECT DISTINCT category_name FROM historical_results WHERE category_name IS NOT NULL ORDER BY category_name"
    ).fetchall()]

    where = """
        FROM historical_results
        LEFT JOIN societies ON societies.id = historical_results.society_id
        WHERE 1=1
    """
    params = []
    if year.isdigit():
        where += " AND year = ?"
        params.append(int(year))
    if category:
        where += " AND category_name = ?"
        params.append(category)
    if tier in ("Gilbert", "Sullivan"):
        where += " AND tier = ?"
        params.append(tier)
    if result in AWARD_RESULTS:
        where += " AND result = ?"
        params.append(result)
    if q:
        ids = fts_match_ids(db, "historical_results_fts", q)
        if ids is not None:
            where += f" AND historical_results.id IN ({','.join('?' * len(ids))})" if ids else " AND 0"
            params.extend(ids)
        else:
            where += """ AND (society_name LIKE ? ESCAPE '\\' OR show LIKE ? ESCAPE '\\'
                         OR nominee_name LIKE ? ESCAPE '\\' OR reason LIKE ? ESCAPE '\\')"""
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{escaped}%"
            params += [like, like, like, like]

    total = db.execute(f"SELECT COUNT(*) {where}", params).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    query = f"""
        SELECT historical_results.*, societies.id AS resolved_society_id {where}
        ORDER BY year DESC, category_name, society_name
        LIMIT ? OFFSET ?
    """
    rows = db.execute(query, params + [per_page, (page - 1) * per_page]).fetchall()

    return render_template(
        "awards.html", rows=rows, years=years, categories=categories, results=AWARD_RESULTS,
        selected_year=year, selected_category=category, selected_tier=tier, selected_result=result, q=q,
        page=page, total_pages=total_pages, total=total, per_page=per_page, page_sizes=AWARDS_PAGE_SIZES,
        society_award_category_names=SOCIETY_AWARD_CATEGORY_NAMES,
    )
