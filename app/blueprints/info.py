import random
from datetime import date, datetime

from flask import Blueprint, render_template, request

from ..constants import (
    ARCHIVE_CIRCUIT_START_YEAR,
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
from ..search import escape_like, fts_match_ids
from ..season import current_season, season_start_year, season_weeks

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
    # opened - excludes announced-but-not-yet-run shows (which may still fall
    # through) from every count/chart below that isn't explicitly about the
    # awards archive (which is inherently already-happened, since an award
    # implies it was judged).
    happened = "COALESCE(shows.closing_date, shows.opening_date) <= ?"

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
    query = f"SELECT COUNT(*) FROM shows WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND shows.source != 'historical' AND {happened}"
    query += region_clause(params)
    total_shows = db.execute(query, params).fetchone()[0]

    params = [today]
    query = f"SELECT COUNT(DISTINCT shows.show) FROM shows WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND shows.source != 'historical' AND {happened}"
    query += region_clause(params)
    total_titles = db.execute(query, params).fetchone()[0]

    params = [today]
    hist_params = [SHOWS_COVERAGE_START_YEAR]
    hist_region_sql = hist_region_clause(hist_params)
    query = f"""
        SELECT show FROM (
            SELECT shows.show AS show FROM shows
            WHERE shows.show IS NOT NULL AND shows.moderation_status = 'approved' AND shows.source != 'historical' AND {happened}
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

    # Award category leaderboard picker - one category (default "Best Overall
    # Show") + optional Gilbert/Sullivan tier, chosen via dropdowns on the
    # page (GET params, same pattern as the region filter). Replaces what
    # used to be a fixed "Best Overall Show" wins card - that's now just the
    # default selection rather than the only category on offer. "person"
    # categories (Best Director, Best Actor, etc.) group/label by
    # nominee_name; "society" categories group/label by society_name - see
    # AWARD_CATEGORIES in constants.py for which is which and why (it's
    # checked against real data, not assumed from the column name).
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

    # Unified "productions on record", straight off the productions table -
    # one row per real staging, whether the site knows it from the live shows
    # catalogue, the awards archive, a ShowTimes review, or all three (see
    # schema.sql). This used to be five separate GROUP BY queries merged in
    # Python across a season-string boundary, and it was wrong twice: it
    # undercounted by 371 productions until 20 Aug, and by a further 823 -
    # every season before 00/01, reported as zero - until this table existed,
    # because the 'yy/yy' round-trip it leaned on can't express an award year
    # before 2001. A production doesn't need an award record to count; not
    # every show is nominated for anything.
    params = [today]
    happened_production = f"""
        (EXISTS (SELECT 1 FROM historical_results WHERE production_id = productions.id)
         OR EXISTS (SELECT 1 FROM shows
                     WHERE shows.production_id = productions.id
                       AND shows.moderation_status = 'approved'
                       AND (shows.source = 'historical'
                            OR COALESCE(shows.closing_date, shows.opening_date) <= ?)))
    """
    # "Reviewed" is coverage of that same total, never a rival count: a
    # ShowTimes write-up, or a Published review link on aims.ie (which
    # replaced ShowTimes in 2023). One idea, both eras.
    reviewed_production = """
        (EXISTS (SELECT 1 FROM historical_reviews
                  WHERE production_id = productions.id AND moderation_status = 'approved')
         OR EXISTS (SELECT 1 FROM shows
                     WHERE shows.production_id = productions.id
                       AND shows.review_status = 'Published'
                       AND shows.review_url IS NOT NULL AND shows.review_url != ''))
    """
    # Region resolves once per production when the table is built, so this is
    # a single equality test rather than the three-way COALESCE fallback join
    # every historical query used to hand-roll.
    region_sql = ""
    if region:
        region_sql = " AND productions.region = ?"
        params.append(region)

    season_rows = db.execute(
        f"""
        SELECT productions.season_start_year AS start_year, productions.season AS season,
               COUNT(*) AS productions,
               SUM(CASE WHEN {reviewed_production} THEN 1 ELSE 0 END) AS reviewed
          FROM productions
         WHERE {happened_production}{region_sql}
         GROUP BY productions.season_start_year
         ORDER BY productions.season_start_year DESC
        """,
        params,
    ).fetchall()

    productions_total = sum(row["productions"] for row in season_rows)
    reviewed_total = sum(row["reviewed"] for row in season_rows)

    # Three bands, each answering a different question honestly:
    #  - recent: the seasons the live shows catalogue covers, listed plainly.
    #  - earlier: the awards archive proper, listed season by season but
    #    collapsed by default so a society backfilling its own back catalogue
    #    can't make the most complete seasons look like a rounding error.
    #  - deep: everything before the archive covers the circuit at all, folded
    #    into one labelled row (see ARCHIVE_CIRCUIT_START_YEAR).
    # /season only has real content for seasons the shows table covers -
    # linking out for an older one would land on an empty page.
    def season_entry(row):
        return {
            "season": row["season"],
            "productions": row["productions"],
            "reviewed": row["reviewed"],
            "has_season_page": row["start_year"] >= SHOWS_COVERAGE_START_YEAR - 1,
        }

    productions_by_season_recent = [
        season_entry(r) for r in season_rows if r["start_year"] >= SHOWS_COVERAGE_START_YEAR - 1
    ]
    productions_by_season_earlier = [
        season_entry(r) for r in season_rows
        if ARCHIVE_CIRCUIT_START_YEAR <= r["start_year"] < SHOWS_COVERAGE_START_YEAR - 1
    ]
    deep_rows = [r for r in season_rows if r["start_year"] < ARCHIVE_CIRCUIT_START_YEAR]
    productions_deep_archive = None
    if deep_rows:
        societies_in_deep = db.execute(
            f"""
            SELECT COUNT(DISTINCT COALESCE(productions.society_id, productions.society_key))
              FROM productions
             WHERE productions.season_start_year < ? AND {happened_production}{region_sql}
            """,
            [ARCHIVE_CIRCUIT_START_YEAR] + params,
        ).fetchone()[0]
        productions_deep_archive = {
            "from_year": deep_rows[-1]["start_year"],
            "to_year": deep_rows[0]["start_year"] + 1,
            "seasons": len(deep_rows),
            "productions": sum(r["productions"] for r in deep_rows),
            "reviewed": sum(r["reviewed"] for r in deep_rows),
            "societies": societies_in_deep,
        }

    by_region = db.execute(
        f"""
        SELECT region AS label, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical' AND {happened}
        GROUP BY region ORDER BY n DESC
        """,
        (today,),
    ).fetchall()

    params = [today]
    query = f"""
        SELECT section AS label, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical' AND section IS NOT NULL AND {happened}
    """
    query += region_clause(params)
    query += " GROUP BY section ORDER BY n DESC"
    by_tier = db.execute(query, params).fetchall()

    # A few computed highlights - region-aware where that naturally applies.
    fun_facts = []

    params = [today]
    query = f"""
        SELECT season, COUNT(*) AS n FROM shows
        WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical' AND {happened}
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
        one_offs=one_offs,
        productions_total=productions_total,
        reviewed_total=reviewed_total,
        productions_by_season=productions_by_season_recent,
        productions_by_season_earlier=productions_by_season_earlier,
        productions_deep_archive=productions_deep_archive,
        by_region=by_region,
        by_tier=by_tier,
        award_total_records=award_total_records,
        award_total_winners=award_total_winners,
        award_from=award_from,
        award_to=award_to,
        award_categories=AWARD_CATEGORIES,
        selected_award_category=award_category,
        selected_award_tier=award_tier,
        award_leaderboard=award_leaderboard,
        award_leaderboard_is_person=award_category_entry["person"],
        award_category_note=award_category_entry.get("note"),
        wins_by_region=wins_by_region,
        fun_facts=fun_facts,
        regions=REGIONS,
        selected_region=region,
    )


DECADE_TOP_N = 5


@bp.route("/stats/trends")
def stats_trends():
    db = get_db()
    today = date.today()

    decades = db.execute(
        """
        SELECT (year / 10) * 10 AS decade, COUNT(*) AS n
        FROM historical_results
        WHERE year IS NOT NULL
        GROUP BY decade ORDER BY decade
        """
    ).fetchall()
    if not decades:
        return render_template("stats_trends.html", decades=[], selected=None)

    available = [row["decade"] for row in decades]
    current_decade = (today.year // 10) * 10
    default_decade = current_decade if current_decade in available else available[-1]

    try:
        decade = int(request.args.get("decade", default_decade))
    except ValueError:
        decade = default_decade
    if decade not in available:
        decade = default_decade
    decade_end = decade + 9

    # "Staged" = a distinct (show, year, society) combination - historical_results
    # has one row per award *category* a production was entered for, so a plain
    # COUNT(*) here would count nominations, not productions (a show nominated in
    # 5 categories the same year isn't 5 stagings). "Most-nominated societies"
    # below deliberately doesn't dedupe the same way - that one's meant to be a
    # raw nomination-volume count.
    top_shows = db.execute(
        """
        SELECT show, COUNT(*) AS n FROM (
            SELECT DISTINCT show, year, COALESCE(society_id, society_name) AS soc_key
            FROM historical_results
            WHERE show IS NOT NULL AND show != '' AND year BETWEEN ? AND ?
        )
        GROUP BY show ORDER BY n DESC, show LIMIT ?
        """,
        (decade, decade_end, DECADE_TOP_N),
    ).fetchall()

    top_societies = db.execute(
        """
        SELECT COALESCE(society_name, 'Unknown') AS label, COUNT(*) AS n
        FROM historical_results
        WHERE society_name IS NOT NULL AND year BETWEEN ? AND ?
        GROUP BY COALESCE(society_id, society_name) ORDER BY n DESC, label LIMIT ?
        """,
        (decade, decade_end, DECADE_TOP_N),
    ).fetchall()

    best_overall_winners = db.execute(
        """
        SELECT year, show, society_name, tier FROM historical_results
        WHERE category_name = 'Best Overall Show' AND result = 'Winner'
          AND show IS NOT NULL AND year BETWEEN ? AND ?
        ORDER BY year, tier
        """,
        (decade, decade_end),
    ).fetchall()

    headline = None
    if top_shows:
        headline = (
            f"{top_shows[0]['show']} led the decade, staged {top_shows[0]['n']} times "
            f"by AIMS societies between {decade} and {decade_end}."
        )

    return render_template(
        "stats_trends.html",
        decades=decades,
        selected=decade,
        decade_end=decade_end,
        decade_in_progress=(decade == current_decade),
        top_shows=top_shows,
        top_societies=top_societies,
        best_overall_winners=best_overall_winners,
        headline=headline,
    )


def _season_options(db):
    """All seasons plus the future/current/past split for the season
    <select>'s <optgroup>s (see season.html/season_calendar.html) - sorted in
    Python by season_start_year, not a plain SQL string DESC, since this
    archive spans 05/06 through 27/28 and a text sort of season strings
    breaks across the 1999/2000 rollover (the exact bug already fixed twice
    elsewhere in this codebase - see season.py)."""
    all_seasons = sorted(
        (r["season"] for r in db.execute("SELECT DISTINCT season FROM shows WHERE show IS NOT NULL").fetchall()),
        key=season_start_year, reverse=True,
    )
    current = current_season(db)
    current_year = season_start_year(current)
    future_seasons = [s for s in all_seasons if season_start_year(s) > current_year]
    past_seasons = [s for s in all_seasons if season_start_year(s) < current_year]
    return all_seasons, current, future_seasons, past_seasons


def _season_filtered_shows(db, all_seasons, current, region, tier):
    """Resolve the requested `season` query param against real seasons, then
    return (season, is_past_season, rows) for that season/region/tier - the
    query shape /season and /season/calendar both need, kept in one place so
    the two can't silently drift apart."""
    requested = request.args.get("season", "")
    season = requested if requested in all_seasons else current
    is_past_season = season < current

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
    # NULL opening dates always sort last. Soonest/earliest-first throughout -
    # the reverse-sort toggle this used to have was removed as unnecessary
    # (see ROADMAP, 2026-08-20).
    query += " ORDER BY (shows.opening_date IS NULL), shows.opening_date ASC"

    rows = db.execute(query, params).fetchall()
    return season, is_past_season, rows


@bp.route("/season")
def season_summary():
    db = get_db()
    all_seasons, current, future_seasons, past_seasons = _season_options(db)
    region = request.args.get("region", "")
    tier = request.args.get("tier", "")
    season, is_past_season, rows = _season_filtered_shows(db, all_seasons, current, region, tier)

    upcoming = [r for r in rows if not r["is_past"]]
    finished = [r for r in rows if r["is_past"]]

    # A society can reserve a slot for the season before announcing a title -
    # shows.show is NULL until they do (same "slotted, TBA" placeholder
    # society_detail() already knows about). The query above excludes them
    # entirely (shows.show IS NOT NULL), so they've never had anywhere to
    # show up on this page - only worth surfacing for the current season,
    # since an unfilled slot in a past season is just a gap in the record,
    # not something "unannounced".
    unannounced = []
    if season == current:
        unannounced_query = """
            SELECT shows.id, societies.id AS society_id, societies.name AS society_name, shows.region
            FROM shows JOIN societies ON societies.id = shows.society_id
            WHERE shows.season = ? AND shows.moderation_status = 'approved' AND shows.show IS NULL
              AND NOT societies.hidden
        """
        unannounced_params = [season]
        if region in REGIONS:
            unannounced_query += " AND shows.region = ?"
            unannounced_params.append(region)
        if tier in SHOW_SECTIONS:
            unannounced_query += " AND shows.section = ?"
            unannounced_params.append(tier)
        unannounced_query += " ORDER BY societies.name"
        unannounced = db.execute(unannounced_query, unannounced_params).fetchall()

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

    # A whole season of "Not yet" is a column of identical non-information -
    # the common case on the current season, where nothing has been adjudicated
    # yet. Computed per table since a current season's finished half can have
    # reviews while its upcoming half never does.
    def _has_review(rows_):
        return any(
            (r["review_status"] == "Published" and r["review_url"])
            or r["review_status"] == "Not adjudicated"
            for r in rows_
        )

    return render_template(
        "season.html", season=season, upcoming=upcoming, finished=finished,
        future_seasons=future_seasons, current_season_value=current, past_seasons=past_seasons,
        unannounced=unannounced,
        upcoming_has_review=_has_review(upcoming), finished_has_review=_has_review(finished),
        is_current=(season == current), is_past_season=is_past_season, is_future_season=(season > current),
        season_range_label=season_range_label,
        regions=REGIONS, tiers=SHOW_SECTIONS, selected_region=region, selected_tier=tier,
    )


@bp.route("/season/calendar")
def season_calendar():
    db = get_db()
    all_seasons, current, future_seasons, past_seasons = _season_options(db)
    region = request.args.get("region", "")
    tier = request.args.get("tier", "")
    season, is_past_season, rows = _season_filtered_shows(db, all_seasons, current, region, tier)

    weeks = season_weeks(rows)
    if not is_past_season:
        # For the current/a future season, already-finished weeks at the top
        # are just clutter - nothing left to plan around. A genuinely past
        # season is being browsed as history, so it keeps its full calendar.
        today = date.today()
        weeks = [w for w in weeks if w["end"] >= today]
    calendar_show_count = sum(w["open_count"] for w in weeks)

    return render_template(
        "season_calendar.html", season=season, weeks=weeks, calendar_show_count=calendar_show_count,
        future_seasons=future_seasons, current_season_value=current, past_seasons=past_seasons,
        is_current=(season == current), is_past_season=is_past_season, is_future_season=(season > current),
        regions=REGIONS, tiers=SHOW_SECTIONS, selected_region=region, selected_tier=tier,
    )


AWARDS_PAGE_SIZES = [50, 100]


@bp.route("/awards")
def awards():
    db = get_db()

    year = request.args.get("year", "").strip()
    category = request.args.get("category", "")
    tier = request.args.get("tier", "")
    result = request.args.get("result", "")
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
            escaped = escape_like(q)
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
