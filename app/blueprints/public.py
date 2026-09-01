import itertools
import math
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import quote_plus

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for

from .. import notify
from ..auth import active_society_code, current_user
from ..calendar_links import google_calendar_url
from ..circuit_intelligence import (
    award_tally, best_overall_show_wins, production_ids_for_title,
    regional_distribution, revival_candidate, signature_categories,
    _is_revival_candidate,
)
from ..constants import (
    REGIONS, SOCIETY_SECTIONS, SUGGESTION_CATEGORIES, VENUE_TYPES,
    WARDROBE_ITEM_TYPES, WARDROBE_TERMS, WARDROBE_STATUSES,
)
from ..db import get_db
from ..filters import place_label
from ..productions import ON_RECORD_PRODUCTION
from ..rate_limit import limiter
from ..search import build_phrase_query, escape_like, fts_match_ids
from ..season import current_season, season_has_ended, season_range, season_start_year
from ..shows import is_upcoming as _is_upcoming
from ..similarity import normalize_title
from ..venues import normalize_venue

bp = Blueprint("public", __name__)

# Enough that the homepage reads as a calendar with a few months on it rather
# than a teaser - the site audit's finding 05 was that six shows and no way to
# see the rest is a dead end. The "see the full season" link below the list
# still carries the remainder.
UPCOMING_LIMIT = 12

# /reviews used to render all 1,086 reviews on every visit - 362KB for a page
# you read a screenful of at a time. Big enough that browsing a season rarely
# needs a second page, small enough that the page is a normal weight.
REVIEWS_PER_PAGE = 100

# Same sizes and ?page=/?per_page= convention the awards archive already uses,
# so a habit learned on one long list transfers to the others.
LIST_PAGE_SIZES = [50, 100, 250]


def paginate_args(total):
    """Read ?page/?per_page for a list of `total` rows and clamp both into
    range, returning (per_page, page, total_pages). Clamping rather than
    404ing keeps a stale bookmark or an edited URL harmless - it lands on the
    last real page instead of an error."""
    per_page = request.args.get("per_page", type=int, default=LIST_PAGE_SIZES[0])
    if per_page not in LIST_PAGE_SIZES:
        per_page = LIST_PAGE_SIZES[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = request.args.get("page", type=int, default=1)
    page = max(1, min(page, total_pages))
    return per_page, page, total_pages


def _haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km - Earth's radius is close enough for
    "how far is this venue", not a surveying tool."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


NEAR_ME_LIMIT = 20


@bp.route("/")
def index():
    db = get_db()

    upcoming_region = request.args.get("upcoming_region", "")
    near_me = request.args.get("near") == "1"
    try:
        near_lat = float(request.args["lat"])
        near_lng = float(request.args["lng"])
    except (KeyError, ValueError):
        near_lat = near_lng = None
    near_active = near_me and near_lat is not None

    upcoming_query = """
        SELECT shows.*, societies.name AS society_name, venues.slug AS venue_slug,
               venues.latitude AS venue_lat, venues.longitude AS venue_lng
        FROM shows JOIN societies ON societies.id = shows.society_id
        LEFT JOIN venues ON venues.id = shows.venue_id
        WHERE shows.moderation_status = 'approved'
          AND shows.show IS NOT NULL
          AND shows.opening_date >= ?
          AND NOT societies.hidden
    """
    upcoming_params = [date.today().isoformat()]
    if upcoming_region in REGIONS and not near_active:
        upcoming_query += " AND shows.region = ?"
        upcoming_params.append(upcoming_region)
    # How many there really are, before the limit - so the page can say "50
    # announced" and mean it, rather than implying the handful it shows is all
    # there is. Same WHERE, same params, so the two can't disagree.
    # Wrapped rather than built by replacing the SELECT clause's exact text -
    # that used to match the source file's own indentation/newlines, so any
    # reformat of the query above turned it into a silent no-op that counted
    # the full row width (fetchone()[0] became shows.id) instead of raising.
    upcoming_total = db.execute(
        f"SELECT COUNT(*) FROM ({upcoming_query})",
        upcoming_params,
    ).fetchone()[0]

    # "Near me" needs every upcoming show's distance computed before it can
    # sort and cut down to the closest N, so it can't reuse the plain
    # ORDER BY opening_date LIMIT query below - it runs its own unlimited
    # fetch instead. Only about a third of venues have a lat/lng on record
    # yet (the venue content pass is still working through the long tail),
    # so this is always a partial view - near_unpinned_count says how partial.
    near_shows = []
    near_unpinned_count = 0
    if near_active:
        all_upcoming = db.execute(upcoming_query, upcoming_params).fetchall()
        for row in all_upcoming:
            if row["venue_lat"] is None or row["venue_lng"] is None:
                near_unpinned_count += 1
                continue
            entry = dict(row)
            entry["distance_km"] = _haversine_km(near_lat, near_lng, row["venue_lat"], row["venue_lng"])
            near_shows.append(entry)
        near_shows.sort(key=lambda s: s["distance_km"])
        near_shows = near_shows[:NEAR_ME_LIMIT]

    upcoming_query += " ORDER BY shows.opening_date LIMIT ?"
    upcoming_params.append(UPCOMING_LIMIT)
    upcoming = db.execute(upcoming_query, upcoming_params).fetchall()

    # Grouped into months so the page reads like a calendar rather than a
    # spreadsheet. itertools.groupby is safe here precisely because the query
    # is already ORDER BY opening_date - the groups can't fragment.
    upcoming_months = [
        (month, list(shows))
        for month, shows in itertools.groupby(
            upcoming, key=lambda s: s["opening_date"][:7]
        )
    ]

    return render_template(
        "index.html",
        upcoming=upcoming,
        upcoming_months=upcoming_months,
        upcoming_total=upcoming_total,
        regions=REGIONS,
        upcoming_region=upcoming_region,
        near_me=near_me and near_lat is not None,
        near_shows=near_shows,
        near_unpinned_count=near_unpinned_count,
    )


@bp.route("/societies")
def societies_list():
    region = request.args.get("region", "")
    section = request.args.get("section", "")
    q = request.args.get("q", "").strip()
    # Only a logged-in moderator/admin can even ask to see inactive societies -
    # anonymous visitors always get the filtered default.
    show_inactive = request.args.get("show_inactive") == "1" and current_user() is not None

    db = get_db()

    query = "SELECT * FROM societies WHERE 1=1"
    params = []
    if not show_inactive:
        query += " AND section != 'Inactive' AND NOT hidden"
    if region in REGIONS:
        query += " AND region = ?"
        params.append(region)
    if section in SOCIETY_SECTIONS:
        query += " AND section = ?"
        params.append(section)
    if q:
        # FTS5 (typo/partial-word tolerant), falling back to a plain LIKE if
        # the index isn't available for any reason - search must never hard-fail.
        ids = fts_match_ids(db, "societies_fts", q)
        if ids is not None:
            query += f" AND id IN ({','.join('?' * len(ids))})" if ids else " AND 0"
            params.extend(ids)
        else:
            query += " AND name LIKE ? ESCAPE '\\'"
            escaped = escape_like(q)
            params.append(f"%{escaped}%")
    # Non-AIMS societies sort last within whatever filters are active, rather
    # than being scattered alphabetically among real members - they're kept
    # for completeness (a past award/review credits them), not because
    # they're peers of an AIMS member society.
    query += " ORDER BY (section = 'Non-AIMS'), name"

    societies = db.execute(query, params).fetchall()

    total = len(societies)
    per_page, page, total_pages = paginate_args(total)
    societies = societies[(page - 1) * per_page:page * per_page]

    return render_template(
        "societies_list.html",
        societies=societies,
        regions=REGIONS,
        sections=SOCIETY_SECTIONS,
        selected_region=region,
        selected_section=section,
        q=q,
        show_inactive=show_inactive,
        page=page,
        total_pages=total_pages,
        total=total,
        per_page=per_page,
        page_sizes=LIST_PAGE_SIZES,
    )


SEARCH_RESULT_LIMIT = 12
SEARCH_SNIPPET_CONTEXT = 90

# Straight and curly/smart quote characters stripped before building any LIKE
# pattern - a title typed or pasted with quotes around it (e.g. "Oliver!")
# would otherwise never match, since the stored title has no literal quote
# characters in it. FTS-backed search doesn't need this: its tokenizer
# already treats punctuation as a separator, so quotes are invisible there.
_QUOTE_CHARS = str.maketrans("", "", "\"'‘’“”")


_SNIPPET_MAX_OCCURRENCES_PER_TERM = 20


def _review_snippet(review_text, q):
    """A window of the review centered on where the search terms actually
    cluster together - not just wherever the first term happens to appear,
    which could be nowhere near the others and give a misleading snippet
    even on a genuinely correct match. Without a snippet at all a review
    result is just a show title, giving no clue why it matched - the whole
    point of searching review prose is that the match is a name or a phrase
    that exists nowhere else on the site."""
    if not review_text:
        return ""
    lowered = review_text.lower()
    terms = [t for t in q.lower().split() if t]
    if not terms:
        return review_text[:SEARCH_SNIPPET_CONTEXT * 2].strip() + "…"

    occurrences = []
    for term in terms:
        positions = []
        start = 0
        while len(positions) < _SNIPPET_MAX_OCCURRENCES_PER_TERM:
            found = lowered.find(term, start)
            if found == -1:
                break
            positions.append(found)
            start = found + 1
        if positions:
            occurrences.append(positions)

    if not occurrences:
        return review_text[:SEARCH_SNIPPET_CONTEXT * 2].strip() + "…"

    # Smallest window containing one occurrence of every term that appears
    # at all in the text (terms with no match are simply left out of the
    # window, rather than failing the whole snippet).
    best_lo, best_hi = None, None
    for combo in itertools.product(*occurrences):
        lo, hi = min(combo), max(combo)
        if best_lo is None or (hi - lo) < (best_hi - best_lo):
            best_lo, best_hi = lo, hi

    position = (best_lo + best_hi) // 2
    start = max(0, position - SEARCH_SNIPPET_CONTEXT)
    end = min(len(review_text), position + SEARCH_SNIPPET_CONTEXT)
    return ("…" if start else "") + review_text[start:end].strip() + ("…" if end < len(review_text) else "")


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    db = get_db()
    societies = []
    titles = []
    reviews = []
    awards = []
    if q:
        escaped = escape_like(q.translate(_QUOTE_CHARS))

        # FTS5 (typo/partial-word tolerant), falling back to a plain LIKE -
        # same pattern as societies_list()'s own search box.
        society_ids = fts_match_ids(db, "societies_fts", q)
        if society_ids is not None:
            if society_ids:
                societies = db.execute(
                    f"SELECT * FROM societies WHERE id IN ({','.join('?' * len(society_ids))}) "
                    "AND section != 'Inactive' AND NOT hidden ORDER BY name LIMIT ?",
                    (*society_ids, SEARCH_RESULT_LIMIT),
                ).fetchall()
        else:
            societies = db.execute(
                "SELECT * FROM societies WHERE name LIKE ? ESCAPE '\\' "
                "AND section != 'Inactive' AND NOT hidden ORDER BY name LIMIT ?",
                (f"%{escaped}%", SEARCH_RESULT_LIMIT),
            ).fetchall()

        # Every matching title on record, with its real staging count - the
        # same productions query titles_list() runs, so the number here can
        # never disagree with the one on the A-Z. Deliberately one "Shows"
        # result kind rather than a separate "Award"
        # one, since /titles/<title> already surfaces both a show's
        # production history and its awards together.
        titles = db.execute(
            f"""
            SELECT MIN(title) AS show, COUNT(*) AS n
            FROM productions
            WHERE {ON_RECORD_PRODUCTION}
              AND title LIKE ? ESCAPE '\\'
            GROUP BY title_key ORDER BY show LIMIT ?
            """,
            (f"%{escaped}%", SEARCH_RESULT_LIMIT),
        ).fetchall()

        # Reviews, searched over their full text - this is the only index
        # that covers prose rather than names, so it's what makes a
        # director, a cast member, or a venue findable at all: none of those
        # exist as a column to search. Ranked by bm25 match quality (best
        # first) rather than season, since a strong text match on an old
        # review is more relevant than a weak one on a recent show. Falls
        # back to LIKE + season-DESC for the same reason as the society
        # search above (an FTS table that isn't there yet on an older
        # database, or a MATCH syntax error from unusual input).
        phrase_query = build_phrase_query(q)
        reviews = None
        if phrase_query is not None:
            try:
                reviews = db.execute(
                    """
                    SELECT historical_reviews.id, historical_reviews.show_raw, historical_reviews.season,
                           historical_reviews.review_text, historical_reviews.show_id,
                           societies.name AS society_name
                    FROM historical_reviews_fts
                    JOIN historical_reviews ON historical_reviews.id = historical_reviews_fts.rowid
                    JOIN societies ON societies.id = historical_reviews.society_id
                    WHERE historical_reviews_fts MATCH ?
                      AND historical_reviews.moderation_status = 'approved'
                      AND historical_reviews.show_id IS NOT NULL
                      AND NOT societies.hidden
                    ORDER BY historical_reviews_fts.rank
                    LIMIT ?
                    """,
                    (phrase_query, SEARCH_RESULT_LIMIT),
                ).fetchall()
            except sqlite3.OperationalError:
                reviews = None
        if reviews is None:
            reviews = db.execute(
                """
                SELECT historical_reviews.id, historical_reviews.show_raw, historical_reviews.season,
                       historical_reviews.review_text, historical_reviews.show_id,
                       societies.name AS society_name
                FROM historical_reviews
                JOIN societies ON societies.id = historical_reviews.society_id
                WHERE historical_reviews.review_text LIKE ? ESCAPE '\\'
                  AND historical_reviews.moderation_status = 'approved'
                  AND historical_reviews.show_id IS NOT NULL
                  AND NOT societies.hidden
                ORDER BY historical_reviews.season DESC
                LIMIT ?
                """,
                (f"%{escaped}%", SEARCH_RESULT_LIMIT),
            ).fetchall()
        reviews = [dict(r) | {"snippet": _review_snippet(r["review_text"], q)} for r in reviews]

        # Award/nomination rows, matched on the nominee's own name as well as
        # the show and society - the only way to search for a *person* on the
        # site, since nominees aren't a table of their own. Show- and
        # society-name matches are already covered by the two result kinds
        # above, so this is filtered down to rows that actually matched on a
        # person, to avoid repeating the same production three times over.
        award_ids = fts_match_ids(db, "historical_results_fts", q)
        awards = []
        if award_ids:
            awards = db.execute(
                f"""
                SELECT historical_results.year, historical_results.show, historical_results.tier,
                       historical_results.category_name, historical_results.result,
                       historical_results.nominee_name, historical_results.role,
                       societies.name AS society_name, societies.id AS society_id
                FROM historical_results
                LEFT JOIN societies ON societies.id = historical_results.society_id
                WHERE historical_results.id IN ({','.join('?' * len(award_ids))})
                  AND historical_results.nominee_name IS NOT NULL
                  AND historical_results.nominee_name LIKE ? ESCAPE '\\'
                ORDER BY historical_results.year DESC
                LIMIT ?
                """,
                (*award_ids, f"%{escaped}%", SEARCH_RESULT_LIMIT),
            ).fetchall()

    # An exact full-name hit on a nominee is the strongest possible match
    # this page can produce, but Award nominees was always the last section
    # rendered - a real match could sit buried under three other headings.
    # Float the whole section to the top only in that case; leave the
    # default order (Societies, Shows, Reviews, Award nominees) otherwise.
    q_lower = q.strip().lower()
    awards_exact_match = any((a["nominee_name"] or "").strip().lower() == q_lower for a in awards)

    return render_template(
        "search.html", q=q, societies=societies, titles=titles,
        reviews=reviews, awards=awards, limit=SEARCH_RESULT_LIMIT,
        awards_exact_match=awards_exact_match,
    )


def _ordinal(n):
    """'First' for 1 (matches how a person would actually describe their
    debut season - not '1st'), plain 'Nth' suffixes above that."""
    if n == 1:
        return "First"
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@bp.route("/adjudicators")
def adjudicators_list():
    db = get_db()
    current = current_season(db)

    # Only ever an adjudicator with at least one real season/tier assignment -
    # one added in /admin/adjudicators but never assigned yet has nothing to
    # show publicly (matches the 404 a direct /adjudicators/<id> link to one
    # gets below). Fetched as raw rows rather than aggregated in SQL: season
    # is a 'yy/yy' string, and MIN/MAX/ORDER BY on it as text is unsafe across
    # the 1999/2000 rollover (the Round 25 bug) - min/max/sort all happen in
    # Python via season_start_year instead.
    seasons_by_adjudicator = defaultdict(list)
    for row in db.execute("SELECT adjudicator_id, season, section FROM adjudicator_assignments"):
        seasons_by_adjudicator[row["adjudicator_id"]].append(row)

    if not seasons_by_adjudicator:
        return render_template("adjudicators_list.html", current_card=[], roster=[])

    # An adjudicator's reviews reach the site by two unrelated routes, and both
    # have to be counted or the page lies: AIMS's own link-out workflow
    # (shows.review_url, which only exists from 23/24 onward) and the extracted
    # ShowTimes archive (historical_reviews, everything before that). Counting
    # only the first is what made 13 of 17 adjudicators read "0 published
    # reviews" while the archive held 800+ of theirs. The two can't overlap -
    # a historical review's skeleton show never carries a review_url - so
    # summing them is safe rather than double-counting.
    review_counts = dict(db.execute(
        """
        SELECT adjudicator_id, SUM(n) AS n FROM (
            SELECT adjudicator_assignments.adjudicator_id AS adjudicator_id, COUNT(*) AS n
            FROM adjudicator_assignments
            JOIN shows ON shows.season = adjudicator_assignments.season
                      AND shows.section = adjudicator_assignments.section
            JOIN societies ON societies.id = shows.society_id
            WHERE shows.review_status = 'Published' AND shows.review_url IS NOT NULL
              AND shows.moderation_status = 'approved' AND NOT societies.hidden
            GROUP BY adjudicator_assignments.adjudicator_id

            UNION ALL

            SELECT historical_reviews.adjudicator_id AS adjudicator_id, COUNT(*) AS n
            FROM historical_reviews
            JOIN shows ON shows.id = historical_reviews.show_id
            JOIN societies ON societies.id = shows.society_id
            WHERE historical_reviews.moderation_status = 'approved'
              AND historical_reviews.adjudicator_id IS NOT NULL
              AND shows.moderation_status = 'approved' AND NOT societies.hidden
            GROUP BY historical_reviews.adjudicator_id
        )
        GROUP BY adjudicator_id
        """
    ).fetchall())

    names = dict(db.execute(
        "SELECT id, name FROM adjudicators WHERE id IN ({})".format(
            ",".join("?" * len(seasons_by_adjudicator))
        ),
        tuple(seasons_by_adjudicator),
    ).fetchall())

    # The coverage bar on the roster table is scaled against the whole
    # archive's span, not each adjudicator's own - a two-season stint and a
    # ten-season one need to look like different lengths, not both fill the
    # bar edge to edge.
    all_start_years = [
        season_start_year(row["season"]) for rows in seasons_by_adjudicator.values() for row in rows
    ]
    archive_start = min(all_start_years)
    archive_end = max(all_start_years) + 1  # a season's own coverage runs one year past its start
    archive_span = archive_end - archive_start

    current_card, roster = [], []
    for adjudicator_id, rows in seasons_by_adjudicator.items():
        distinct_seasons = sorted({row["season"] for row in rows}, key=season_start_year)
        season_count = len(distinct_seasons)
        reviews = review_counts.get(adjudicator_id, 0)
        current_rows = [row for row in rows if row["season"] == current]

        if current_rows:
            for row in current_rows:
                current_card.append({
                    "id": adjudicator_id,
                    "name": names[adjudicator_id],
                    "tier": row["section"],
                    "ordinal": _ordinal(season_count),
                    "reviews": reviews,
                })
            continue

        start_year = season_start_year(distinct_seasons[0])
        end_year = season_start_year(distinct_seasons[-1]) + 1
        roster.append({
            "id": adjudicator_id,
            "name": names[adjudicator_id],
            "season_count": season_count,
            "span_label": distinct_seasons[0] if season_count == 1 else f"{distinct_seasons[0]}–{distinct_seasons[-1]}",
            "span_left": round((start_year - archive_start) / archive_span * 100, 1),
            "span_right": round((archive_end - end_year) / archive_span * 100, 1),
            "reviews": reviews,
        })

    current_card.sort(key=lambda e: e["tier"])
    roster.sort(key=lambda e: e["name"])

    return render_template(
        "adjudicators_list.html", current_season=current, current_card=current_card, roster=roster,
    )


@bp.route("/adjudicators/<int:adjudicator_id>")
def adjudicator_detail(adjudicator_id):
    db = get_db()
    adjudicator = db.execute("SELECT * FROM adjudicators WHERE id = ?", (adjudicator_id,)).fetchone()
    if adjudicator is None:
        abort(404)

    assignment_rows = db.execute(
        "SELECT season, section FROM adjudicator_assignments WHERE adjudicator_id = ?",
        (adjudicator_id,),
    ).fetchall()
    if not assignment_rows:
        abort(404)

    # season is a 'yy/yy' string - sorted/min/max'd here via season_start_year
    # rather than in SQL, since plain string ordering is unsafe across the
    # 1999/2000 rollover (the Round 25 bug).
    distinct_seasons = sorted({row["season"] for row in assignment_rows}, key=season_start_year)
    tiers_judged = sorted({row["section"] for row in assignment_rows})
    stats = {
        "season_count": len(distinct_seasons),
        "span": distinct_seasons[0] if len(distinct_seasons) == 1 else f"{distinct_seasons[0]}–{distinct_seasons[-1]}",
        "tiers": "Both" if len(tiers_judged) > 1 else tiers_judged[0],
    }

    # Only actual published reviews here (unlike /admin/adjudicators'
    # cross-check view, which deliberately shows every show in their
    # assigned seasons regardless of review status) - this page is "here's
    # what X has written", not an admin verification tool. Same hidden-
    # society exclusion as the homepage/Season Archive/calendar feed.
    #
    # Both review routes, same as adjudicators_list() above: AIMS's own
    # link-out ('link', opens aims.ie) and the extracted ShowTimes archive
    # ('full_text', which lives on the show's own page here). A reader wants
    # this person's reviews - which of the two a given one happens to be is
    # our plumbing, so they merge into one list and carry a source tag rather
    # than being split into two sections.
    reviews = db.execute(
        """
        SELECT shows.id, shows.show, shows.season, shows.section,
               shows.review_url, societies.name AS society_name, 'link' AS source
        FROM shows
        JOIN adjudicator_assignments ON adjudicator_assignments.season = shows.season
                                     AND adjudicator_assignments.section = shows.section
        JOIN societies ON societies.id = shows.society_id
        WHERE adjudicator_assignments.adjudicator_id = ?
          AND shows.review_status = 'Published' AND shows.review_url IS NOT NULL
          AND shows.moderation_status = 'approved' AND NOT societies.hidden

        UNION ALL

        SELECT shows.id, shows.show, historical_reviews.season, historical_reviews.tier AS section,
               NULL AS review_url, societies.name AS society_name, 'full_text' AS source
        FROM historical_reviews
        JOIN shows ON shows.id = historical_reviews.show_id
        JOIN societies ON societies.id = shows.society_id
        WHERE historical_reviews.adjudicator_id = ?
          AND historical_reviews.moderation_status = 'approved'
          AND shows.moderation_status = 'approved' AND NOT societies.hidden
        """,
        (adjudicator_id, adjudicator_id),
    ).fetchall()
    reviews = sorted(
        reviews, key=lambda r: (-season_start_year(r["season"]), (r["show"] or "").lower())
    )
    stats["review_count"] = len(reviews)

    # Grouped on the review's own season/tier, not the assignment table -
    # keeps a review visible even when it lands on a tier the assignment
    # table doesn't record for that season (the 16/17 case Round 34 found:
    # a stale printed masthead had briefly misfiled 28 reviews a season
    # early, before being corrected against the actual PDFs).
    season_groups = []
    groups_by_season = {}
    for r in reviews:
        group = groups_by_season.get(r["season"])
        if group is None:
            group = {"season": r["season"], "tiers": [], "reviews": []}
            groups_by_season[r["season"]] = group
            season_groups.append(group)
        if r["section"] not in group["tiers"]:
            group["tiers"].append(r["section"])
        group["reviews"].append(r)
    for group in season_groups:
        group["tiers"].sort()

    return render_template(
        "adjudicator_detail.html", adjudicator=adjudicator, stats=stats, season_groups=season_groups,
    )


@bp.route("/reviews")
def reviews_index():
    db = get_db()
    q = request.args.get("q", "").strip()
    season = request.args.get("season", "")
    tier = request.args.get("tier", "")
    if tier not in ("Gilbert", "Sullivan"):
        tier = ""
    adjudicator_id = request.args.get("adjudicator", type=int)

    # AIMS assigns one adjudicator per tier per season, not per show - same
    # "only credit when exactly one candidate is on record" rule show_detail()
    # and adjudicator_detail() above already use for a link-out review. Done
    # here in Python across the whole list at once, rather than per-row in
    # SQL, since a season/tier can rarely have 2 assignment rows (a recorded
    # mid-season change) and a join would silently double a show's row count
    # in exactly that case.
    assignment_candidates = defaultdict(list)
    for row in db.execute("SELECT season, section, adjudicator_id FROM adjudicator_assignments").fetchall():
        assignment_candidates[(row["season"], row["section"])].append(row["adjudicator_id"])
    adjudicator_names = dict(db.execute("SELECT id, name FROM adjudicators").fetchall())

    # Two different eras, one merged list, same "source" tag pattern already
    # used on the adjudicator's own page: AIMS's own link-out (aims.ie, 23/24
    # on) and the extracted ShowTimes archive (full text, lives on the show's
    # own page here). Structurally can't overlap - the archive ends before
    # the link-out era begins - so no dedup needed between the two.
    rows = db.execute(
        """
        SELECT shows.id AS show_id, shows.show AS show, shows.season AS season,
               shows.section AS tier, shows.review_url AS review_url,
               societies.name AS society_name, NULL AS direct_adjudicator_id, 'link' AS source,
               NULL AS review_id
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.review_status = 'Published' AND shows.review_url IS NOT NULL
          AND shows.review_url != '' AND shows.moderation_status = 'approved' AND NOT societies.hidden

        UNION ALL

        SELECT shows.id AS show_id, shows.show AS show, historical_reviews.season AS season,
               historical_reviews.tier AS tier, NULL AS review_url,
               societies.name AS society_name, historical_reviews.adjudicator_id AS direct_adjudicator_id,
               'full_text' AS source, historical_reviews.id AS review_id
        FROM historical_reviews
        JOIN shows ON shows.id = historical_reviews.show_id
        JOIN societies ON societies.id = shows.society_id
        WHERE historical_reviews.moderation_status = 'approved'
          AND shows.moderation_status = 'approved' AND NOT societies.hidden
        """
    ).fetchall()

    all_reviews = []
    for r in rows:
        if r["source"] == "link":
            candidates = assignment_candidates.get((r["season"], r["tier"]), [])
            adj_id = candidates[0] if len(candidates) == 1 else None
        else:
            adj_id = r["direct_adjudicator_id"]
        all_reviews.append({
            "show_id": r["show_id"], "show": r["show"], "season": r["season"], "tier": r["tier"],
            "society_name": r["society_name"], "source": r["source"], "review_url": r["review_url"],
            "adjudicator_id": adj_id, "adjudicator_name": adjudicator_names.get(adj_id),
            "review_id": r["review_id"],
        })
    all_reviews.sort(key=lambda r: (-season_start_year(r["season"]), (r["show"] or "").lower()))

    stats = {
        "total": len(all_reviews),
        "full_text": sum(1 for r in all_reviews if r["source"] == "full_text"),
        "linked": sum(1 for r in all_reviews if r["source"] == "link"),
    }
    if all_reviews:
        seasons_seen = [r["season"] for r in all_reviews]
        stats["span"] = f"{min(seasons_seen, key=season_start_year)}–{max(seasons_seen, key=season_start_year)}"

    reviews = all_reviews
    if q:
        needle = q.lower()
        # Searches the review's actual wording as well as the show and society
        # name. Before this the page carried a notice telling you to go and use
        # the other search box for that, which is the site apologising for a
        # split the visitor never needed to know about (site audit, finding 12).
        #
        # Only archive reviews have text here - a link-out row is a URL on
        # aims.ie, so there's nothing on this site to match. fts_match_ids
        # returns None if the index couldn't answer, in which case this quietly
        # falls back to the name-only match rather than failing the search.
        text_matches = fts_match_ids(db, "historical_reviews_fts", q)
        text_match_ids = set(text_matches) if text_matches else set()
        reviews = [
            r for r in reviews
            if needle in (r["show"] or "").lower()
            or needle in (r["society_name"] or "").lower()
            or (r["review_id"] is not None and r["review_id"] in text_match_ids)
        ]
    if season:
        reviews = [r for r in reviews if r["season"] == season]
    if tier:
        reviews = [r for r in reviews if r["tier"] == tier]
    if adjudicator_id:
        reviews = [r for r in reviews if r["adjudicator_id"] == adjudicator_id]

    # Every matching review still decides the count and the paging; only one
    # page of them is ever rendered. The whole list used to go out at once -
    # 1,086 rows and 362KB on every visit, on a page you can only read a
    # screenful of anyway (site audit, finding 12).
    result_count = len(reviews)
    total_pages = max(1, math.ceil(result_count / REVIEWS_PER_PAGE))
    page = min(max(request.args.get("page", 1, type=int) or 1, 1), total_pages)
    reviews = reviews[(page - 1) * REVIEWS_PER_PAGE:page * REVIEWS_PER_PAGE]

    # Grouped by season for plain browsing (no search text) - matches
    # adjudicator_detail() above; only meaningful once a search narrows the
    # list to something that could reasonably cross seasons/tiers on its own,
    # so a search result stays a single flat list instead. Grouping the page's
    # own slice, not the whole list, so a season heading appears wherever the
    # boundary happens to fall rather than promising rows that aren't here.
    season_groups = []
    if not q:
        groups_by_season = {}
        for r in reviews:
            group = groups_by_season.get(r["season"])
            if group is None:
                group = {"season": r["season"], "reviews": []}
                groups_by_season[r["season"]] = group
                season_groups.append(group)
            group["reviews"].append(r)

    adjudicators = db.execute("SELECT id, name FROM adjudicators ORDER BY name").fetchall()

    return render_template(
        "reviews_index.html",
        q=q, selected_season=season, selected_tier=tier, selected_adjudicator=adjudicator_id,
        seasons=season_range(db), adjudicators=adjudicators,
        stats=stats, result_count=result_count,
        page=page, total_pages=total_pages, per_page=REVIEWS_PER_PAGE,
        season_groups=season_groups, flat_reviews=reviews if q else [],
    )


BADGE_CENTURY_MIN = 100
BADGE_TRIPLE_CROWN_MIN = 3
BADGE_CLEAN_SWEEP_MIN = 8
BADGE_JUBILEE_MIN = 50
BADGE_ALL_ROUNDER_MIN = 5


def _consecutive_year_streak(years):
    """Longest run of years with no gap bigger than one between consecutive
    entries, e.g. {2010, 2011, 2013, 2014, 2015} -> 3 (2013-2015)."""
    if not years:
        return 0
    ordered = sorted(years)
    best = current = 1
    for i in range(1, len(ordered)):
        if ordered[i] - ordered[i - 1] <= 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def _society_badges(db, society_id):
    """Milestone badges for a society's profile page - each only ever
    appears once earned, same as the trophy case above it (nothing renders
    for a society with none). The two "how many productions / which years"
    badges read the productions table; the five award badges read
    historical_results, which is a different question (an award record is a
    fact about a category, and there's nothing in shows to double-count it
    against). Gilbert Grandmaster (3+ Best Overall Show wins in the Gilbert
    tier) was considered and parked, not built - Darragh's call, can
    activate later."""
    badges = []

    # One query, and exactly the same definition /stats and the A-Z use. The
    # two-query version this replaced admitted in its own comment that it was
    # imprecise (it skipped the skeleton-show reconciliation, and it split the
    # eras at SHOWS_COVERAGE_START_YEAR); the precise answer is now cheaper
    # than the approximate one was.
    total_productions = db.execute(
        f"SELECT COUNT(*) FROM productions WHERE society_id = ? AND {ON_RECORD_PRODUCTION}",
        (society_id,),
    ).fetchone()[0]
    if total_productions >= BADGE_CENTURY_MIN:
        badges.append({
            "icon": "🌟", "cls": "b-century", "label": "Century Club",
            "criteria": f"{total_productions} productions on record",
            "tooltip": "100 or more productions staged on record, across the full archive and current seasons.",
        })

    triple_crown = db.execute(
        "SELECT year, show, COUNT(*) AS wins FROM historical_results "
        "WHERE society_id = ? AND result = 'Winner' AND show IS NOT NULL "
        "GROUP BY year, show HAVING wins >= ? ORDER BY wins DESC LIMIT 1",
        (society_id, BADGE_TRIPLE_CROWN_MIN),
    ).fetchone()
    if triple_crown:
        badges.append({
            "icon": "👑", "cls": "b-triple", "label": "Triple Crown",
            "criteria": f"{triple_crown['wins']} wins for one production ({triple_crown['year']})",
            "tooltip": "3 or more wins for the same production in the same year - total dominance in a single outing.",
        })

    clean_sweep = db.execute(
        "SELECT year, COUNT(*) AS noms FROM historical_results "
        "WHERE society_id = ? AND category_name IS NOT NULL "
        "GROUP BY year HAVING noms >= ? ORDER BY noms DESC LIMIT 1",
        (society_id, BADGE_CLEAN_SWEEP_MIN),
    ).fetchone()
    if clean_sweep:
        badges.append({
            "icon": "🧹", "cls": "b-sweep", "label": "The Clean Sweep",
            "criteria": f"{clean_sweep['noms']} nominations in {clean_sweep['year']}",
            "tooltip": "8 or more award nominations across every category in a single year.",
        })

    # Every year this society has a production on record, in one convention.
    # The old version mixed award years with historical_results_year() decoding
    # a season string as 2000+yy+1, which can't express a season before 00/01;
    # season_start_year is every element of the old set shifted by exactly -1,
    # so streak lengths are unchanged and the century bug is gone.
    years = {r[0] for r in db.execute(
        f"SELECT DISTINCT season_start_year FROM productions "
        f"WHERE society_id = ? AND {ON_RECORD_PRODUCTION}",
        (society_id,),
    )}
    streak = _consecutive_year_streak(years)
    if streak >= BADGE_JUBILEE_MIN:
        badges.append({
            "icon": "🎂", "cls": "b-jubilee", "label": "Golden Jubilee Society",
            "criteria": f"{streak} consecutive years active",
            "tooltip": "50 or more consecutive years with at least one production on record - gaps of a year or less don't break the streak.",
        })

    winning_tiers = {r[0] for r in db.execute(
        "SELECT DISTINCT tier FROM historical_results "
        "WHERE society_id = ? AND category_name = 'Best Overall Show' AND result = 'Winner'",
        (society_id,),
    )}
    if {"Gilbert", "Sullivan"} <= winning_tiers:
        badges.append({
            "icon": "🎭", "cls": "b-dual", "label": "Dual Tier Champions",
            "criteria": "Won Best Overall Show in Gilbert & Sullivan",
            "tooltip": "Has won Best Overall Show at least once in both the Gilbert and Sullivan tiers, at different points in its history.",
        })

    category_count = db.execute(
        "SELECT COUNT(DISTINCT category_name) FROM historical_results "
        "WHERE society_id = ? AND result = 'Winner' AND category_name IS NOT NULL",
        (society_id,),
    ).fetchone()[0]
    if category_count >= BADGE_ALL_ROUNDER_MIN:
        badges.append({
            "icon": "🎨", "cls": "b-allrounder", "label": "The All-Rounder",
            "criteria": f"Won in {category_count} different categories",
            "tooltip": "Won 5 or more distinct award categories over its history - not just Best Overall Show, but Direction, Choreography, MD, Costume and the rest.",
        })

    first_year = db.execute(
        "SELECT MIN(year) FROM historical_results WHERE society_id = ? AND show IS NOT NULL", (society_id,)
    ).fetchone()[0]
    if first_year is not None:
        debut = db.execute(
            "SELECT result FROM historical_results WHERE society_id = ? AND year = ? "
            "AND result IN ('Winner', 'Second Place', 'Third Place') LIMIT 1",
            (society_id, first_year),
        ).fetchone()
        if debut:
            verb = "Won" if debut["result"] == "Winner" else debut["result"]
            badges.append({
                "icon": "🌱", "cls": "b-debut", "label": "Debut Delight",
                "criteria": f"{verb} in their first-ever year, {first_year}",
                "tooltip": "Won or placed in the very first year this society appears on record.",
            })

    return badges


@bp.route("/societies/<int:society_id>")
def society_detail(society_id):
    db = get_db()
    society = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
        abort(404)

    viewer = current_user()
    # Hidden means the society asked not to be publicly associated with
    # AIMS - 404 for anyone not logged in as a moderator, so the page still
    # works for a moderator reviewing/unhiding it. Doesn't touch historical
    # stats/awards/Season Archive - see schema.sql's societies.hidden.
    if society["hidden"] and viewer is None:
        abort(404)

    # Only fetched for an admin viewer - lets them hand out this society's
    # login code straight from its own page instead of hunting for it (or
    # re-creating it) on /admin/invite-codes. Same "still valid" check as
    # auth.py's active_society_code().
    society_code = None
    society_login_url = None
    if viewer and viewer["role"] == "admin":
        society_code = db.execute(
            """
            SELECT * FROM invite_codes WHERE society_id = ? AND is_active = 1
            AND (expires_at IS NULL OR expires_at >= ?)
            ORDER BY created_at DESC LIMIT 1
            """,
            (society_id, date.today().isoformat()),
        ).fetchone()
        # Built here (not in the template) so it reuses notify.py's SITE_URL
        # handling - url_for(..., _external=True) can't be trusted behind
        # the Cloudflare Tunnel/PrefixMiddleware setup (see notify.py).
        society_login_url = notify.link(url_for("society.login"))

    shows = db.execute(
        """
        SELECT shows.*, venues.slug AS venue_slug, venues.capacity AS venue_capacity,
               EXISTS(
                   SELECT 1 FROM historical_reviews
                   WHERE historical_reviews.show_id = shows.id AND historical_reviews.moderation_status = 'approved'
               ) AS has_historical_review
        FROM shows
        LEFT JOIN venues ON venues.id = shows.venue_id
        WHERE society_id = ? AND moderation_status = 'approved'
        """,
        (society_id,),
    ).fetchall()
    # Sorted here rather than via SQL's own ORDER BY season DESC - a plain
    # text sort on "yy/yy" breaks across the 1999/2000 rollover (a society
    # with old skeleton rows from the 1970s/80s, season strings like
    # "79/80", sorted as text ABOVE the real current season "27/28" because
    # '7' > '2' - the exact bug season_start_year()'s own docstring warns
    # about, just not yet fixed on this query).
    shows = sorted(shows, key=lambda s: (-season_start_year(s["season"]), s["show"] or ""))

    # Date-based, not season-based (fixed 2026-08-25 - season > current used
    # to be the whole test, so a show dated later in the *current* season -
    # the common case, since a season spans autumn to summer - never got
    # pulled into the "coming up" callout and just blended into history
    # below it). A titled show counts as "coming up" if it has a real date
    # in the future, or if it's in a genuinely future season and doesn't
    # have a date yet (announced, TBA - the one case a date check alone
    # can't catch). An untitled future-season row is still just a "slotted,
    # TBA" placeholder, not worth a blank line either way.
    current = current_season(db)
    current_start_year = season_start_year(current)
    today_iso = date.today().isoformat()
    future_shows = [
        s for s in shows if s["show"] is not None and (
            (s["opening_date"] and s["opening_date"] >= today_iso)
            or (not s["opening_date"] and season_start_year(s["season"]) > current_start_year)
        )
    ]
    future_ids = {s["id"] for s in future_shows}
    shows = [s for s in shows if s["id"] not in future_ids]
    # Soonest first, not the ORDER BY season DESC the source query used -
    # that ordering exists for the history table below, not this list, so
    # sorted() re-derives "soonest" properly: a real date beats a dateless
    # TBA in the same or a later season, and a dateless placeholder falls
    # back to its season's real start year - plain string comparison on
    # "yy/yy" breaks across the 1999/2000 rollover ('79/80' sorts after
    # '26/27' as text despite being decades earlier).
    future_shows.sort(key=lambda s: (s["opening_date"] or "9999-99-99", season_start_year(s["season"])))

    # A titleless row for the current or a future season (no date, no venue
    # either) carries zero real information - just a slot AIMS's own
    # schedule assigned before the society picked a show, imported ahead of
    # time so a moderator has something to attach details to later. Public
    # visitors have nothing to do with it (no show to click, no date to
    # read), so it renders as a blank "TBA" row at the very top of Show
    # history - confusing, since it reads like the top of the list is the
    # most recent *production* rather than an empty future slot. A logged-in
    # moderator still sees it (and its Edit link), since for them it's a
    # real to-do rather than noise. A titleless row for a season that has
    # already happened stays visible either way - "Not recorded" is a real
    # historical gap, not an empty slot.
    if not viewer:
        shows = [
            s for s in shows if not (
                s["show"] is None and s["opening_date"] is None and s["venue"] is None
                and season_start_year(s["season"]) >= current_start_year
            )
        ]
    # "Not recorded" (a real historical gap) vs "TBA" (not yet announced) -
    # computed here rather than as `show['season'] < current_season` in the
    # template, which was the same season-string bug as above: a titled but
    # dateless show from the 1970s/80s would compare as "later" than the
    # current season and wrongly read "TBA", implying an upcoming show
    # rather than a genuine gap in old records.
    shows = [
        dict(s, blank_date_label=(
            "No date on record" if season_start_year(s["season"]) < current_start_year else "TBA"
        ))
        for s in shows
    ]

    # Every award/nomination record for this society, keyed on the production
    # it belongs to - one row per category, so a single production can have
    # several. Grouped once here and handed to both tables below, so a
    # production's awards render the same way whether or not it has a show
    # page of its own.
    awards_by_production = defaultdict(list)
    for r in db.execute(
        """
        SELECT production_id, year, tier, category_name, result, show, nominee_name, role, reason
        FROM historical_results
        WHERE society_id = ? AND production_id IS NOT NULL
        ORDER BY year DESC, show, category_name
        """,
        (society_id,),
    ):
        # A row with no category and no result isn't an award - it's a bare
        # "this production happened" entry (see
        # admin.bulk_historical_productions). It still puts the production on
        # the timeline below; it just isn't a badge.
        if r["category_name"] is not None or r["result"] is not None:
            awards_by_production[r["production_id"]].append(r)

    awards_by_show = {
        r["id"]: awards_by_production.get(r["production_id"], [])
        for r in shows if r["production_id"]
    }

    # This society's own poster wall. Only 13 societies have any posters at
    # all, so this is absent from most pages by design rather than rendering
    # an empty shelf - and where it does appear (S.O.N.G. has 18, Oyster Lane
    # and Maynooth 11 each) it is the most visual thing the page has.
    #
    # The soonest upcoming show is excluded: its poster is already displayed
    # in full on the "Coming this season" card directly above, and showing it
    # twice on one screen reads as a mistake. That also means a society whose
    # only poster is that one gets no strip, which is right.
    next_show_id = future_shows[0]["id"] if future_shows else None
    poster_shows = [
        s for s in (list(future_shows) + list(shows))
        if s["poster_filename"] and s["id"] != next_show_id
    ]

    # Show history grouped into decades (2026-08-29 redesign). A flat 37-row
    # table had no spine; an era header with its own win count gives the page
    # something to scan by, and matches how anyone actually talks about a
    # society's history ("they had a great run in the 90s").
    #
    # Wins and nominations are split here rather than in the template because
    # the whole point of the redesign is that they render *differently* - a
    # win is a gold pill, nominations collapse to one count chip. Doing that
    # split in Jinja would mean three selectattr passes per row.
    eras = []
    for start_year_dec, group in itertools.groupby(
        shows, key=lambda s: (season_start_year(s["season"]) // 10) * 10
    ):
        rows = []
        era_wins = 0
        for s in group:
            aw = awards_by_show.get(s["id"], [])
            wins = [a for a in aw if a["result"] == "Winner"]
            placed = [a for a in aw if a["result"] in ("Second Place", "Third Place")]
            noms = [a for a in aw if a["result"] == "Nominee"]
            era_wins += len(wins)
            rows.append(dict(s, wins=wins, placed=placed, noms=noms))
        eras.append({"decade": start_year_dec, "shows": rows, "wins": era_wins})

    # This society's other productions: the ones with no show page of their
    # own. Split on that rather than on an era - the old query had no year
    # filter at all despite a heading that promised "pre-23/24", so every
    # 2024+ award record was listed here *and* in the show history above it
    # (195 duplicated lines across the site on current production data).
    historical_timeline = [
        dict(r) | {"awards": awards_by_production.get(r["id"], [])}
        for r in db.execute(
            f"""
            SELECT productions.id, productions.season_start_year + 1 AS year, productions.title AS show,
                   (SELECT tier FROM historical_results
                     WHERE production_id = productions.id AND tier IS NOT NULL LIMIT 1) AS tier
            FROM productions
            WHERE productions.society_id = ? AND {ON_RECORD_PRODUCTION}
              AND NOT EXISTS (SELECT 1 FROM shows
                               WHERE shows.production_id = productions.id
                                 AND shows.moderation_status = 'approved')
            ORDER BY year DESC, show
            """,
            (society_id,),
        )
    ]

    # Person-level awards (the Mary Kelly/Unsung Hero class) have no show and
    # so no production by definition - production_key() returns None for a
    # blank title - which is why they can't come through the path above.
    person_awards = db.execute(
        """
        SELECT year, tier, category_name, result, show, nominee_name, role, reason
        FROM historical_results
        WHERE society_id = ? AND show IS NULL
        ORDER BY year DESC, category_name
        """,
        (society_id,),
    ).fetchall()

    # A compact "trophy case" summary - total wins, and Best Overall Show wins
    # specifically.
    total_wins, best_show_wins = db.execute(
        """
        SELECT COUNT(*), SUM(CASE WHEN category_name = 'Best Overall Show' THEN 1 ELSE 0 END)
        FROM historical_results WHERE society_id = ? AND result = 'Winner'
        """,
        (society_id,),
    ).fetchone()

    # Runner-up finishes for Best Overall Show specifically - a separate
    # query rather than folding into award_totals above, since that one's
    # outer WHERE is scoped to result = 'Winner' (needed for total_wins/
    # earliest_award_year) and would silently zero these out otherwise.
    best_show_second, best_show_third = db.execute(
        """
        SELECT
            SUM(CASE WHEN result = 'Second Place' THEN 1 ELSE 0 END),
            SUM(CASE WHEN result = 'Third Place' THEN 1 ELSE 0 END)
        FROM historical_results
        WHERE society_id = ? AND category_name = 'Best Overall Show'
        """,
        (society_id,),
    ).fetchone()

    # The first year this society is on record at all. The old version took
    # MIN(year) from a query scoped to result = 'Winner', so it was really the
    # year of their first *win* - and fell back to a hard-coded 2000 + yy
    # pivot on a season string, the same century assumption that has cost this
    # migration two rounds already.
    active_since = db.execute(
        f"SELECT MIN(season_start_year) + 1 FROM productions "
        f"WHERE society_id = ? AND {ON_RECORD_PRODUCTION}",
        (society_id,),
    ).fetchone()[0]

    badges = _society_badges(db, society_id)

    wardrobe_items = db.execute(
        """
        SELECT * FROM wardrobe_items
        WHERE society_id = ? AND status != 'delisted'
        ORDER BY (status = 'available') DESC, created_at DESC
        """,
        (society_id,),
    ).fetchall()

    return render_template(
        "society_detail.html", society=society, shows=shows, future_shows=future_shows,
        historical_timeline=historical_timeline, person_awards=person_awards,
        awards_by_show=awards_by_show, eras=eras, poster_shows=poster_shows,
        total_wins=total_wins, best_show_wins=best_show_wins, active_since=active_since,
        best_show_second=best_show_second, best_show_third=best_show_third, society_code=society_code,
        society_login_url=society_login_url, badges=badges, current_season=current,
        wardrobe_items=wardrobe_items, item_types=WARDROBE_ITEM_TYPES, terms_labels=WARDROBE_TERMS,
    )


def _may_see_own_show_admin(show):
    """True for the society whose show this is, logged in with their own code,
    or for any moderator. Gates the housekeeping detail on a show page that's
    for the people staging it rather than for the public."""
    code = active_society_code()
    if code and code["society_id"] == show["society_id"]:
        return True
    return current_user() is not None


@bp.route("/shows/<int:show_id>")
def show_detail(show_id):
    db = get_db()
    show = db.execute(
        """
        SELECT shows.*, societies.name AS society_name, societies.about AS society_about,
               societies.website_url AS society_website_url, societies.facebook_url AS society_facebook_url,
               societies.instagram_url AS society_instagram_url,
               venues.slug AS venue_slug, venues.capacity AS venue_capacity, venues.town AS venue_town
        FROM shows JOIN societies ON societies.id = shows.society_id
        LEFT JOIN venues ON venues.id = shows.venue_id
        WHERE shows.id = ? AND shows.moderation_status = 'approved'
        """,
        (show_id,),
    ).fetchone()
    if show is None:
        abort(404)

    # One-line "circuit" summary - how often this title has been staged and
    # who did it most recently - reusing the same title_key identity as
    # /titles/<title>, but only the two numbers a show page needs rather
    # than that page's full award-tally panel.
    circuit_summary = None
    title_key = normalize_title(show["show"])
    circuit_row = db.execute(
        f"SELECT COUNT(*) AS n, MIN(season_start_year) + 1 AS since FROM productions "
        f"WHERE title_key = ? AND {ON_RECORD_PRODUCTION}",
        (title_key,),
    ).fetchone()
    if circuit_row["n"] > 1:
        most_recent = db.execute(
            f"""
            SELECT society_name, season_start_year + 1 AS year FROM productions
            WHERE title_key = ? AND {ON_RECORD_PRODUCTION} AND id != COALESCE(?, -1)
            ORDER BY season_start_year DESC LIMIT 1
            """,
            (title_key, show["production_id"]),
        ).fetchone()
        circuit_summary = {"count": circuit_row["n"], "since": circuit_row["since"], "most_recent": most_recent}

    # Same "upcoming" definition as the homepage's Upcoming shows list -
    # only nudge for details on shows that haven't happened yet.
    is_upcoming = _is_upcoming(show)

    # The show-dates calendar link is redundant once a show has already
    # happened - gated on the same is_upcoming used for the ticket/poster
    # nudge above. (The adjudication-forms reminder used to live here too,
    # but it's only actually useful to the show's own committee, not a
    # random visitor - it now lives on the society's own edit-show page,
    # see society.edit_show().)
    gcal_show_url = None
    # Just opening_date minus 6 weeks (AIMS's real application deadline) -
    # arithmetic on a date the page already displays, never AIMS's own internal
    # scheduling info, so it leaks nothing.
    #
    # Shown only to the society whose show it is, or to a moderator. It's a
    # deadline for the people staging the show and noise to everybody else, and
    # the show page is the one most likely to be shared publicly - the site
    # audit's finding 07. Not a secret, just the wrong audience.
    adjudication_cutoff = None
    if is_upcoming:
        opening = date.fromisoformat(show["opening_date"])
        closing = date.fromisoformat(show["closing_date"]) if show["closing_date"] else opening
        gcal_show_url = google_calendar_url(
            text=f"{show['show']} - {show['society_name']}",
            start=opening,
            end_exclusive=closing + timedelta(days=1),
            details=f"AIMS production - {url_for('public.show_detail', show_id=show['id'], _external=True)}",
            location=show["venue"] or "",
        )
        if show["review_status"] != "Not adjudicated" and _may_see_own_show_admin(show):
            adjudication_cutoff = (opening - timedelta(weeks=6)).isoformat()

    # AIMS assigns one adjudicator per tier per season, not per show - so a
    # published review's likely author is whoever covered this show's own
    # season+section, looked up via app.admin's adjudicator_assignments
    # rather than a per-show author field (see /admin/adjudicators). A
    # season/tier can rarely have two rows (a recorded mid-season change) -
    # there's no per-show date-range data to say which of the two actually
    # wrote this specific review, so deliberately don't guess: only credit
    # when exactly one adjudicator is on record for that season/tier.
    reviewed_by = None
    if show["review_status"] == "Published" and show["review_url"] and show["section"]:
        candidates = db.execute(
            """
            SELECT adjudicators.id, adjudicators.name
            FROM adjudicator_assignments
            JOIN adjudicators ON adjudicators.id = adjudicator_assignments.adjudicator_id
            WHERE adjudicator_assignments.season = ? AND adjudicator_assignments.section = ?
            """,
            (show["season"], show["section"]),
        ).fetchall()
        reviewed_by = candidates[0] if len(candidates) == 1 else None

    # Full extracted review text from the AIMS ShowTimes archive (Step 4) -
    # separate from the review_status/review_url pair above, which is a
    # plain external link for 23/24-onward shows that were never in the PDF
    # archive. A show can only ever have one of these approved at once in
    # practice (the archive stops before this site's own coverage begins),
    # but nothing enforces that - confirmed the hard way (19 Aug 2026's
    # feedback review): a batch re-extraction had left ten shows carrying
    # two approved reviews apiece, and this query's missing ORDER BY meant
    # which one rendered was down to SQLite's incidental scan order, not a
    # real decision. ORDER BY id ASC LIMIT 1 makes the pick deterministic
    # (oldest/first-approved wins) rather than leaving it to chance if this
    # ever recurs.
    historical_review = db.execute(
        """
        SELECT historical_reviews.review_text, historical_reviews.source_issue, historical_reviews.source,
               adjudicators.id AS adjudicator_id, adjudicators.name AS adjudicator_name
        FROM historical_reviews
        LEFT JOIN adjudicators ON adjudicators.id = historical_reviews.adjudicator_id
        WHERE historical_reviews.show_id = ? AND historical_reviews.moderation_status = 'approved'
        ORDER BY historical_reviews.id ASC LIMIT 1
        """,
        (show_id,),
    ).fetchone()

    # AIMS award/nomination history for this exact production, from the awards
    # archive (historical_results). Read straight off production_id - the
    # foreign key that exists precisely to express "same staging" - rather
    # than the hand-rolled join on (society, decoded year, normalized title)
    # this replaced. That join decoded the season with historical_results_year,
    # which returns 2000 + yy + 1 and so cannot express an award year before
    # 2001: latent while shows holds 09/10 onward, live the moment anyone bulk
    # -creates an older row. A titleless placeholder row has no production.
    #
    # The category/result filter is deliberate: it's what stops a bare "this
    # production happened" row (see admin.bulk_historical_productions) from
    # rendering as if it were an award.
    award_history = []
    if show["production_id"]:
        award_history = db.execute(
            """
            SELECT show, tier, category_name, result, nominee_name, role, reason
            FROM historical_results
            WHERE production_id = ?
              AND (category_name IS NOT NULL OR result IS NOT NULL)
            """,
            (show["production_id"],),
        ).fetchall()

    return render_template(
        "show_detail.html", show=show, is_upcoming=is_upcoming,
        gcal_show_url=gcal_show_url, adjudication_cutoff=adjudication_cutoff, reviewed_by=reviewed_by,
        historical_review=historical_review, award_history=award_history,
        season_ended=season_has_ended(db, show["season"]), circuit_summary=circuit_summary,
    )


# Shows A-Z grouping/sort key: a leading "The"/"A"/"An" is stripped so "The
# Mikado" files under M next to "My Fair Lady", not off on its own under T -
# the standard library/index convention (Netflix, IMDB, WorldCat all do this)
# and what the approved Shows A-Z mockup itself assumes. Display always uses
# the real title in full; only grouping/ordering uses the stripped form.
_LEADING_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)


def _az_sort_key(title):
    return _LEADING_ARTICLE_RE.sub("", title).strip().lower()


def _az_letter(title):
    key = _az_sort_key(title)
    return key[0].upper() if key and key[0].isalpha() else "#"


@bp.route("/titles")
def titles_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    flt = request.args.get("filter", "")
    house = request.args.get("house", "").strip()

    # One row per real staging, straight off the productions table. The old
    # union counted historical_results rows, which are one per award
    # *category*, so a production nominated five times counted five times -
    # the whole A-Z overstated the circuit by ~1.67x. MIN(title) rather than a
    # bare column because GROUP BY title_key would otherwise pick an arbitrary
    # row's spelling.
    query = f"""
        SELECT title_key, MIN(title) AS show, COUNT(*) AS n,
               MIN(season_start_year) AS first_year, MAX(season_start_year) AS last_year
        FROM productions
        WHERE {ON_RECORD_PRODUCTION}
    """
    params = []
    if q:
        query += " AND title LIKE ? ESCAPE '\\'"
        escaped = escape_like(q)
        params.append(f"%{escaped}%")
    query += " GROUP BY title_key"
    rows = db.execute(query, params).fetchall()

    manual_links = dict(db.execute("SELECT show, url FROM show_links").fetchall())
    has_info = {r[0] for r in db.execute("SELECT show FROM show_info").fetchall()}
    full_info = {
        r["show"]: dict(r)
        for r in db.execute("SELECT * FROM show_info").fetchall()
    }
    licensing_houses = [
        r[0] for r in db.execute(
            "SELECT DISTINCT licensing_house FROM show_info"
            " WHERE licensing_house IS NOT NULL AND licensing_house <> '' ORDER BY licensing_house"
        ).fetchall()
    ]

    # Nominations/wins per title, bulk rather than per-title (circuit_intelligence.
    # award_tally does this one title at a time for title_detail, which is fine for
    # one page but would be N+1 queries across ~300 titles here).
    tally = {}
    for r in db.execute("""
        SELECT productions.title_key AS title_key, COUNT(*) AS nominations,
               SUM(CASE WHEN historical_results.result = 'Winner' THEN 1 ELSE 0 END) AS wins
        FROM historical_results
        JOIN productions ON productions.id = historical_results.production_id
        WHERE historical_results.category_name IS NOT NULL
        GROUP BY productions.title_key
    """):
        tally[r["title_key"]] = {"nominations": r["nominations"], "wins": r["wins"] or 0}

    # Announced/on-stage productions per title, bulk - same is_upcoming() definition
    # used everywhere else a show's "has this happened yet" question comes up, rather
    # than a fresh opening_date >= today re-derived here with slightly different phrasing.
    upcoming = defaultdict(list)
    for r in db.execute("""
        SELECT productions.title_key AS title_key, shows.season AS season,
               shows.opening_date AS opening_date, societies.name AS society_name
        FROM shows
        JOIN societies ON societies.id = shows.society_id
        JOIN productions ON productions.id = shows.production_id
        WHERE shows.moderation_status = 'approved' AND shows.show IS NOT NULL AND NOT societies.hidden
    """):
        if _is_upcoming(r):
            upcoming[r["title_key"]].append({
                "season": r["season"],
                "society_name": r["society_name"],
                "start_year": season_start_year(r["season"]) if r["season"] else None,
            })

    today_year = date.today().year
    all_shows = []
    for r in rows:
        key, title, n = r["title_key"], r["show"], r["n"]
        first_year, last_year = r["first_year"], r["last_year"]
        gap = (today_year - last_year) if last_year is not None else None
        is_revival = gap is not None and _is_revival_candidate(n, gap)
        up = sorted(upcoming.get(key, []), key=lambda u: (u["start_year"] is None, u["start_year"]))
        on_stage_text = None
        if len(up) == 1:
            on_stage_text = f"On stage {up[0]['season']} · {up[0]['society_name']}"
        elif len(up) >= 2:
            seasons = [u["season"] for u in up if u["season"]]
            span = seasons[0] if (seasons and seasons[0] == seasons[-1]) else (
                f"{seasons[0]}–{seasons[-1]}" if seasons else ""
            )
            on_stage_text = f"\U0001f525 {len(up)} productions in {span}" if span else f"\U0001f525 {len(up)} productions"

        info = full_info.get(title, {})
        all_shows.append({
            "title": title,
            "count": n,
            "first_year": first_year,
            "last_year": last_year,
            "nominations": tally.get(key, {}).get("nominations", 0),
            "wins": tally.get(key, {}).get("wins", 0),
            "url": manual_links.get(title),
            "is_manual": title in manual_links,
            "has_info": title in has_info,
            "search_url": f"https://en.wikipedia.org/w/index.php?search={quote_plus(title + ' musical')}",
            "is_gem": n == 1,
            "is_revival": is_revival,
            "revival_last_year": last_year if is_revival else None,
            "on_stage_text": on_stage_text,
            "rights_status": info.get("rights_status"),
            "licensing_house": info.get("licensing_house"),
            "composer": info.get("composer"),
            "lyricist": info.get("lyricist"),
            "book_author": info.get("book_author"),
            "key_songs": info.get("key_songs"),
            "synopsis": info.get("synopsis"),
            "sort_key": _az_sort_key(title),
            "letter": _az_letter(title),
        })

    total = len(all_shows)
    filter_counts = {
        "onstage": sum(1 for s in all_shows if s["on_stage_text"]),
        "revival": sum(1 for s in all_shows if s["is_revival"]),
        "gems": sum(1 for s in all_shows if s["is_gem"]),
        "available": sum(1 for s in all_shows if s["rights_status"] == "Available"),
        "contact": sum(1 for s in all_shows if s["rights_status"] == "Contact publisher"),
        "restricted": sum(1 for s in all_shows if s["rights_status"] == "Restricted"),
    }

    if flt == "onstage":
        visible = [s for s in all_shows if s["on_stage_text"]]
    elif flt == "revival":
        visible = [s for s in all_shows if s["is_revival"]]
    elif flt == "gems":
        visible = [s for s in all_shows if s["is_gem"]]
    elif flt == "available":
        visible = [s for s in all_shows if s["rights_status"] == "Available"]
    elif flt == "contact":
        visible = [s for s in all_shows if s["rights_status"] == "Contact publisher"]
    elif flt == "restricted":
        visible = [s for s in all_shows if s["rights_status"] == "Restricted"]
    else:
        flt = ""
        visible = all_shows

    # Licensing house is a separate dropdown, not a quick-filter chip (12
    # distinct houses is too many for the chip row) - combines with whichever
    # chip is active rather than replacing it, same as /reviews' season/tier/
    # adjudicator dropdowns all narrow the same result set together.
    if house:
        visible = [s for s in visible if s["licensing_house"] == house]

    visible.sort(key=lambda s: (s["sort_key"], s["title"].lower()))

    letter_groups = [
        {"letter": letter, "shows": list(group)}
        for letter, group in itertools.groupby(visible, key=lambda s: s["letter"])
    ]
    available_letters = {g["letter"] for g in letter_groups}

    # "Most-staged, archive-wide" strip - always the real top 8 by total production
    # count, independent of the current search/filter (a fixed reference point, not
    # a view of whatever's currently filtered).
    staples = [
        {"title": r["show"], "count": r["n"]}
        for r in db.execute(f"""
            SELECT title_key, MIN(title) AS show, COUNT(*) AS n
            FROM productions WHERE {ON_RECORD_PRODUCTION}
            GROUP BY title_key ORDER BY n DESC LIMIT 8
        """)
    ] if not q else []

    return render_template(
        "titles_list.html", letter_groups=letter_groups, staples=staples,
        available_letters=available_letters, q=q, flt=flt,
        total=total, filter_counts=filter_counts,
        licensing_houses=licensing_houses, selected_house=house,
    )


@bp.route("/titles/<path:title>")
def title_detail(title):
    db = get_db()
    title_key = normalize_title(title)

    # Joined through productions rather than matched on the raw title text, so
    # two spellings of one show land on one page, and ordered on a real
    # four-digit year rather than on 'yy/yy' as text (which sorts '76/77' after
    # '09/10' - the Round 25 bug).
    raw_shows = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows
        JOIN societies ON societies.id = shows.society_id
        JOIN productions ON productions.id = shows.production_id
        WHERE productions.title_key = ? AND shows.moderation_status = 'approved'
        ORDER BY productions.season_start_year DESC, societies.name
        """,
        (title_key,),
    ).fetchall()

    curr_season = current_season(db)
    current_start = season_start_year(curr_season) if curr_season else 2026
    today = date.today().isoformat()

    shows = [
        dict(s, blank_date_label=(
            "No date on record" if (season_start_year(s["season"]) is not None and season_start_year(s["season"]) < current_start) else "TBA"
        ))
        for s in raw_shows
    ]

    upcoming_shows = []
    past_shows = []
    for s in shows:
        s_start = season_start_year(s["season"])
        if (s["closing_date"] and s["closing_date"] >= today) or \
           (s["opening_date"] and s["opening_date"] >= today) or \
           (not s["opening_date"] and not s["closing_date"] and s_start is not None and s_start >= current_start):
            upcoming_shows.append(s)
        else:
            past_shows.append(s)

    # Sort upcoming chronologically (soonest first; TBA dates at end)
    upcoming_shows.sort(
        key=lambda s: (
            s["opening_date"] or s["closing_date"] or "9999-99-99",
            season_start_year(s["season"]) or 9999,
            s["society_name"],
        )
    )

    # Sort past productions reverse-chronologically (most recent first)
    past_shows.sort(
        key=lambda s: (
            season_start_year(s["season"]) or 0,
            s["opening_date"] or s["closing_date"] or "0000-00-00",
            s["society_name"],
        ),
        reverse=True,
    )

    # The rest of this title's stagings: the ones with no show page of their
    # own to link to. Split on that, not on an era - a skeleton shows row from
    # 12/13 belongs in the table above because it has a real page, and a
    # production known only from a 2025 award record belongs here rather than
    # being filtered out of existence (which is what the old year < 23/24 cut
    # did, 404ing 16 real titles). season_start_year + 1 is historical_results'
    # own year column exactly - the rebuild's verification pass asserts that
    # relationship for every linked award record - so the displayed years are
    # unchanged from what this table showed before.
    historical = db.execute(
        f"""
        SELECT productions.season_start_year + 1 AS year, productions.society_name, productions.society_id
        FROM productions
        WHERE productions.title_key = ? AND {ON_RECORD_PRODUCTION}
          AND NOT EXISTS (SELECT 1 FROM shows
                           WHERE shows.production_id = productions.id
                             AND shows.moderation_status = 'approved')
        ORDER BY productions.season_start_year DESC
        """,
        (title_key,),
    ).fetchall()

    if not shows and not historical:
        abort(404)

    info = db.execute("SELECT * FROM show_info WHERE show = ?", (title,)).fetchone()

    # AIMS debut - the earliest production on record, whichever source it came
    # from, as a four-digit year. Taken off productions rather than compared
    # across two conventions (an award year on one side, a 'yy/yy' string
    # compared lexically on the other, which put a 1976 debut after a 2009
    # one). Stated as the season's ending year, the same convention the
    # archive table above and the awards archive itself use.
    debut_year = db.execute(
        f"SELECT MIN(season_start_year) + 1 FROM productions "
        f"WHERE title_key = ? AND {ON_RECORD_PRODUCTION}",
        (title_key,),
    ).fetchone()[0]
    debut_label = str(debut_year) if debut_year is not None else None

    # Gated on real award-archive engagement, not just "this title exists" -
    # a just-announced show with a shows row and no adjudication yet has
    # nothing a circuit-intelligence panel could say.
    prod_ids = production_ids_for_title(db, title)
    circuit = None
    tally = award_tally(db, prod_ids)
    if tally["nominations"]:
        regions, regions_unknown = regional_distribution(db, prod_ids)
        circuit = {
            "tally": tally,
            "best_overall_wins": best_overall_show_wins(db, prod_ids),
            "signature": signature_categories(db, prod_ids),
            "regions": regions,
            "regions_unknown": regions_unknown,
            "regions_total": sum(r["n"] for r in regions) + regions_unknown,
            "revival": revival_candidate(db, prod_ids, date.today().year),
        }

    wardrobe_items = db.execute(
        """
        SELECT wi.*, s.name AS society_name, s.region AS society_region
        FROM wardrobe_items wi
        JOIN societies s ON s.id = wi.society_id
        WHERE (
            LOWER(wi.show_title) = LOWER(?)
            OR LOWER(wi.title) LIKE LOWER(?)
        ) AND wi.status != 'delisted' AND s.hidden = 0
        ORDER BY (wi.status = 'available') DESC, wi.created_at DESC
        """,
        (title, f"%{title}%"),
    ).fetchall()

    return render_template(
        "title_detail.html", title=title, shows=shows,
        upcoming_shows=upcoming_shows, past_shows=past_shows,
        historical=historical, info=info,
        debut_label=debut_label, circuit=circuit,
        wardrobe_items=wardrobe_items, item_types=WARDROBE_ITEM_TYPES, terms_labels=WARDROBE_TERMS,
    )


@bp.route("/venues")
def venues_index():
    db = get_db()
    q = request.args.get("q", "").strip()
    region = request.args.get("region", "")
    if region not in REGIONS:
        region = ""
    # "unclassified" is a real, selectable answer rather than a hidden state -
    # a venue with no type is either genuinely unlooked-at or one of the
    # archive's place-name artifacts, and both are worth being able to find.
    venue_type = request.args.get("venue_type", "")
    if venue_type not in VENUE_TYPES and venue_type != "unclassified":
        venue_type = ""

    # Reads the venues table rather than grouping the free-text shows.venue
    # column: the same building is typed several different ways across the
    # archive ("Town Hall Theatre" eight ways), which used to split one venue
    # across several rows. A venue's spellings are mapped to it through
    # venue_aliases, and merging two of them is a moderator decision (see
    # /admin/venue-directory). historical_results has no venue column at all,
    # so this is still necessarily scoped to the shows table (05/06 on).
    query = """
        SELECT venues.*,
               COUNT(shows.id) AS n,
               COUNT(DISTINCT shows.society_id) AS soc_n,
               MIN(shows.season) AS first_season, MAX(shows.season) AS last_season
          FROM venues
          JOIN shows ON shows.venue_id = venues.id
          JOIN societies ON societies.id = shows.society_id
         WHERE shows.moderation_status = 'approved' AND NOT societies.hidden
    """
    params = []
    if q:
        escaped = escape_like(q)
        query += (" AND (venues.name LIKE ? ESCAPE '\\' OR venues.town LIKE ? ESCAPE '\\'"
                  " OR venues.county LIKE ? ESCAPE '\\')")
        params += [f"%{escaped}%"] * 3
    if region:
        query += " AND venues.region = ?"
        params.append(region)
    if venue_type == "unclassified":
        query += " AND (venues.venue_type IS NULL OR venues.venue_type = '')"
    elif venue_type:
        query += " AND venues.venue_type = ?"
        params.append(venue_type)
    # Most-used first, not alphabetical - the venue field still has real noise
    # in it (an anniversary note where a venue name should be, a bare county
    # name), and alphabetical order put exactly that at the very top. Sorting
    # by production count means the real, recognizable venues lead; the noise
    # is all still there, just no longer the first impression.
    query += " GROUP BY venues.id ORDER BY n DESC, venues.name COLLATE NOCASE"
    venues = db.execute(query, params).fetchall()

    total = len(venues)
    # Counted before pagination slices the list - this is "how many of the
    # filtered set are mapped", not "how many on this page happen to be" -
    # the latter was this line's original behaviour when mapped_count was
    # computed but never actually rendered anywhere (fixed 2026-08-25, the
    # first time a template used it).
    mapped_count = sum(1 for v in venues if v["latitude"] is not None and v["longitude"] is not None)

    per_page, page, total_pages = paginate_args(total)
    venues = venues[(page - 1) * per_page:page * per_page]

    return render_template(
        "venues_list.html", venues=venues, q=q, regions=REGIONS, selected_region=region,
        venue_types=VENUE_TYPES, selected_venue_type=venue_type,
        mapped_count=mapped_count,
        page=page, total_pages=total_pages, total=total, per_page=per_page, page_sizes=LIST_PAGE_SIZES,
    )


@bp.route("/venues/map")
def venues_map():
    """Real interactive map, real pin coordinates - the parked Leaflet
    prototype (mockups/ireland_theatre_map.html) used 9 entirely fabricated
    venues; this reuses its layout (sidebar + map, keyless CartoDB tiles)
    against every venue that actually has a lat/lon on record. Separate page
    rather than folded into /venues itself - a map needs the full unfiltered
    set to be useful (a filtered subset with 3 pins isn't), and loading
    Leaflet only where it's actually used keeps the plain card grid light."""
    db = get_db()
    venues = db.execute(
        """
        SELECT venues.*,
               COUNT(shows.id) AS n,
               COUNT(DISTINCT shows.society_id) AS soc_n
          FROM venues
          JOIN shows ON shows.venue_id = venues.id
          JOIN societies ON societies.id = shows.society_id
         WHERE shows.moderation_status = 'approved' AND NOT societies.hidden
           AND venues.latitude IS NOT NULL AND venues.longitude IS NOT NULL
         GROUP BY venues.id ORDER BY venues.name COLLATE NOCASE
        """
    ).fetchall()

    total_venues = db.execute(
        """
        SELECT COUNT(DISTINCT venues.id)
          FROM venues JOIN shows ON shows.venue_id = venues.id
          JOIN societies ON societies.id = shows.society_id
         WHERE shows.moderation_status = 'approved' AND NOT societies.hidden
        """
    ).fetchone()[0]

    # Resident societies per mapped venue - bulk query rather than N+1
    # (same reasoning as titles_list()'s tally/upcoming dicts above), and
    # only the venues actually on the map, not every society ever anywhere.
    residents = defaultdict(set)
    for r in db.execute(
        """
        SELECT DISTINCT shows.venue_id AS venue_id, societies.name AS society_name
          FROM shows JOIN societies ON societies.id = shows.society_id
         WHERE shows.moderation_status = 'approved' AND NOT societies.hidden
           AND shows.venue_id IS NOT NULL
        """
    ):
        residents[r["venue_id"]].add(r["society_name"])

    pins = [
        {
            "name": v["name"],
            "place": place_label(v["town"], v["county"]),
            "county": v["county"] or "",
            "region": v["region"] or "",
            "lat": v["latitude"], "lng": v["longitude"],
            "capacity": v["capacity"],
            "n": v["n"], "soc_n": v["soc_n"],
            "societies": sorted(residents.get(v["id"], ())),
            "url": url_for("public.venue_detail", venue=v["slug"]),
        }
        for v in venues
    ]

    counties = sorted({p["county"] for p in pins if p["county"]})
    regions_present = sorted({p["region"] for p in pins if p["region"]})

    return render_template(
        "venues_map.html", pins=pins, mapped_count=len(pins), total=total_venues,
        counties=counties, regions_present=regions_present,
    )


@bp.route("/venues/<path:venue>")
def venue_detail(venue):
    db = get_db()
    # `venue` is a slug now, but every previously-published /venues/<name> URL
    # used the raw venue string - those are still live links (and indexed), so
    # a name that resolves through venue_aliases redirects to its slug rather
    # than 404ing.
    row = db.execute("SELECT * FROM venues WHERE slug = ?", (venue,)).fetchone()
    if row is None:
        alias = db.execute(
            "SELECT venues.slug FROM venue_aliases JOIN venues ON venues.id = venue_aliases.venue_id "
            "WHERE venue_aliases.name_key = ?",
            (normalize_venue(venue),),
        ).fetchone()
        if alias is None:
            abort(404)
        return redirect(url_for("public.venue_detail", venue=alias["slug"]), code=301)

    shows = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.venue_id = ? AND shows.moderation_status = 'approved' AND NOT societies.hidden
        ORDER BY shows.season DESC, shows.opening_date DESC
        """,
        (row["id"],),
    ).fetchall()
    if not shows:
        abort(404)

    upcoming, past = [], []
    for s in shows:
        (upcoming if _is_upcoming(s) else past).append(s)

    residents = {}
    for s in shows:
        entry = residents.setdefault(
            s["society_id"], {"society_id": s["society_id"], "society_name": s["society_name"], "n": 0}
        )
        entry["n"] += 1
    resident_societies = sorted(residents.values(), key=lambda r: (-r["n"], r["society_name"]))

    seasons_seen = [s["season"] for s in shows]
    earliest = min(seasons_seen, key=season_start_year)
    latest = max(seasons_seen, key=season_start_year)
    span = earliest if earliest == latest else f"{earliest}–{latest}"

    # Every spelling this venue has been recorded under, so a page for a venue
    # whose name was corrected or merged still says what people will recognise.
    spellings = [
        r["venue"] for r in db.execute(
            "SELECT DISTINCT venue FROM shows WHERE venue_id = ? AND venue IS NOT NULL "
            "AND venue != ? ORDER BY venue",
            (row["id"], row["name"]),
        )
    ]
    return render_template(
        "venue_detail.html", venue=row, upcoming=upcoming, past=past, spellings=spellings,
        resident_societies=resident_societies, production_count=len(shows), span=span,
        seasons=len({s["season"] for s in shows}),
    )


@bp.route("/more")
def more():
    """Mobile-only "More" tab destination - everything that isn't one of the
    bottom bar's 5 main tabs. Renders fine at any width, just isn't linked
    from anywhere except the bottom bar (see base.html)."""
    return render_template("more.html")


@bp.route("/about")
def about():
    db = get_db()
    total_societies = db.execute("SELECT COUNT(*) FROM societies").fetchone()[0]
    # Same filter as /societies' default (anonymous) view - the number a
    # visitor actually finds if they click through, not the full archive
    # total (which includes Inactive/hidden societies kept for historical
    # record). See the 2026-08-05 site review: these two numbers used to
    # diverge with no explanation, reading as a mismatch rather than by design.
    active_societies = db.execute(
        "SELECT COUNT(*) FROM societies WHERE section != 'Inactive' AND NOT hidden"
    ).fetchone()[0]
    historical_from = db.execute("SELECT MIN(year) FROM historical_results").fetchone()[0]
    return render_template(
        "about.html", total_societies=total_societies, active_societies=active_societies,
        historical_from=historical_from,
    )


@bp.route("/faq")
def faq():
    db = get_db()
    entries = db.execute(
        "SELECT * FROM faq_entries WHERE status = 'published' ORDER BY sort_order, id"
    ).fetchall()
    return render_template("faq.html", entries=entries)


@bp.route("/suggest", methods=("GET", "POST"))
@limiter.limit("5 per minute")
def suggest():
    if request.method == "POST":
        # Honeypot - same pattern as the show submission form.
        if request.form.get("website", ""):
            return redirect(url_for("public.suggest_thanks"))

        message = request.form.get("message", "").strip()
        category = request.form.get("category", "")
        submitted_name = request.form.get("submitted_name", "").strip() or None
        contact = request.form.get("contact", "").strip() or None

        if not message:
            flash("Enter your suggestion before submitting.", "error")
            return render_template("suggest.html", form=request.form, categories=SUGGESTION_CATEGORIES)
        if category not in SUGGESTION_CATEGORIES:
            flash("Choose a type for your suggestion.", "error")
            return render_template("suggest.html", form=request.form, categories=SUGGESTION_CATEGORIES)

        get_db().execute(
            "INSERT INTO feature_suggestions (message, category, submitted_name, contact) VALUES (?, ?, ?, ?)",
            (message, category, submitted_name, contact),
        )
        get_db().commit()
        notify.send(
            f"New suggestion ({category})",
            f"From: {submitted_name or 'Anonymous'}\n\n{message}\n\n"
            f"Review it: {notify.link(url_for('admin.suggestions'))}",
        )
        return redirect(url_for("public.suggest_thanks"))

    # Cheap prefill for a link into this form (e.g. a society page's
    # "spot something wrong?" note) - only category/message, and only from
    # the fixed category list, so a crafted link can't inject anything
    # beyond what a user could type in by hand anyway.
    prefill = {}
    if request.args.get("category") in SUGGESTION_CATEGORIES:
        prefill["category"] = request.args["category"]
    if request.args.get("message"):
        prefill["message"] = request.args["message"]
    return render_template("suggest.html", form=prefill, categories=SUGGESTION_CATEGORIES)


@bp.route("/suggest/thanks")
def suggest_thanks():
    return render_template("suggest_thanks.html")


@bp.route("/suggestions")
def suggestions_board():
    db = get_db()
    # Lane order (not alphabetical): Planned -> In Progress -> Done reads as
    # a pipeline, "Not planned" as the reference tail - still shown so a
    # duplicate idea can be spotted before resubmitting. Ordered within each
    # lane by triaged_at (falls back to created_at for rows triaged before
    # that column existed) so the most recently-moved item floats to the top.
    rows = db.execute(
        """
        SELECT message, category, triage_status, admin_note FROM feature_suggestions
        WHERE triage_status IN ('Planned', 'In Progress', 'Done', 'Not planned')
        ORDER BY
            CASE triage_status WHEN 'Planned' THEN 0 WHEN 'In Progress' THEN 1 WHEN 'Done' THEN 2 WHEN 'Not planned' THEN 3 END,
            COALESCE(triaged_at, created_at) DESC
        """
    ).fetchall()
    lanes = {status: [] for status in ("Planned", "In Progress", "Done", "Not planned")}
    for row in rows:
        lanes[row["triage_status"]].append(row)
    # "Recently shipped" is the curated/manual changelog only now that a
    # finished suggestion is visible in its own Done lane above - showing
    # the same item in both places would just be clutter. This still covers
    # shipped work that didn't start as a suggestion (e.g. the nav rework).
    changelog = db.execute(
        "SELECT entry, created_at AS entry_date FROM changelog_entries ORDER BY created_at DESC"
    ).fetchall()
    return render_template("suggestions_board.html", lanes=lanes, changelog=changelog)


@bp.route("/watchlist")
def watchlist():
    return render_template("watchlist.html")


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename)


# --- Costumes, Props & Sets Exchange ---

@bp.route("/exchange")
def exchange_index():
    db = get_db()
    q = request.args.get("q", "").strip()
    item_type = request.args.get("type", "").strip()
    region = request.args.get("region", "").strip()
    terms = request.args.get("terms", "").strip()

    where_clauses = ["wi.status != 'delisted'", "s.hidden = 0"]
    params = []

    if q:
        match_query = build_phrase_query(q)
        if match_query:
            where_clauses.append("wi.id IN (SELECT rowid FROM wardrobe_items_fts WHERE wardrobe_items_fts MATCH ?)")
            params.append(match_query)
        else:
            where_clauses.append("(wi.title LIKE ? OR wi.show_title LIKE ? OR wi.description LIKE ?)")
            like_term = f"%{escape_like(q)}%"
            params.extend([like_term, like_term, like_term])

    if item_type and item_type in WARDROBE_ITEM_TYPES:
        where_clauses.append("wi.item_type = ?")
        params.append(item_type)

    if region and region in REGIONS:
        where_clauses.append("s.region = ?")
        params.append(region)

    if terms and terms in WARDROBE_TERMS:
        where_clauses.append("wi.terms = ?")
        params.append(terms)

    where_sql = " AND ".join(where_clauses)

    items = db.execute(
        f"""
        SELECT wi.*, s.name AS society_name, s.region AS society_region,
               s.logo_filename AS society_logo,
               (SELECT COUNT(*) FROM wardrobe_photos WHERE item_id = wi.id) AS photo_count
        FROM wardrobe_items wi
        JOIN societies s ON s.id = wi.society_id
        WHERE {where_sql}
        ORDER BY wi.created_at DESC
        """,
        params,
    ).fetchall()

    type_counts = dict(
        db.execute(
            """
            SELECT wi.item_type, COUNT(*) 
            FROM wardrobe_items wi 
            JOIN societies s ON s.id = wi.society_id 
            WHERE wi.status != 'delisted' AND s.hidden = 0 
            GROUP BY wi.item_type
            """
        ).fetchall()
    )
    total_count = sum(type_counts.values())

    return render_template(
        "exchange_index.html",
        items=items,
        q=q,
        selected_type=item_type,
        selected_region=region,
        selected_terms=terms,
        regions=REGIONS,
        item_types=WARDROBE_ITEM_TYPES,
        terms_labels=WARDROBE_TERMS,
        status_labels=WARDROBE_STATUSES,
        type_counts=type_counts,
        total_count=total_count,
    )


@bp.route("/exchange/<int:item_id>")
def exchange_detail(item_id):
    db = get_db()
    item = db.execute(
        """
        SELECT wi.*, s.name AS society_name, s.region AS society_region,
               s.logo_filename AS society_logo, s.website_url, s.facebook_url,
               s.instagram_url, s.about AS society_about
        FROM wardrobe_items wi
        JOIN societies s ON s.id = wi.society_id
        WHERE wi.id = ? AND wi.status != 'delisted' AND s.hidden = 0
        """,
        (item_id,),
    ).fetchone()
    if not item:
        abort(404)

    photos = db.execute(
        "SELECT * FROM wardrobe_photos WHERE item_id = ? ORDER BY display_order, id",
        (item_id,),
    ).fetchall()

    other_items = db.execute(
        """
        SELECT wi.*, s.name AS society_name, s.region AS society_region
        FROM wardrobe_items wi
        JOIN societies s ON s.id = wi.society_id
        WHERE wi.society_id = ? AND wi.id != ? AND wi.status != 'delisted'
        ORDER BY wi.created_at DESC LIMIT 3
        """,
        (item["society_id"], item_id),
    ).fetchall()

    # Contact details are for society-to-society use, not the open web. They
    # are stripped here rather than hidden in the template on purpose: a
    # template-only guard still ships the phone number and email inside the
    # HTML for anyone who views source, which is not "protected", it is just
    # less visible. What the browser never receives cannot be scraped.
    viewer_is_society = active_society_code() is not None
    item = dict(item)
    if not viewer_is_society:
        for field in ("contact_name", "contact_email", "contact_phone"):
            item[field] = None

    return render_template(
        "exchange_detail.html",
        item=item,
        viewer_is_society=viewer_is_society,
        photos=photos,
        other_items=other_items,
        item_types=WARDROBE_ITEM_TYPES,
        terms_labels=WARDROBE_TERMS,
        status_labels=WARDROBE_STATUSES,
    )

