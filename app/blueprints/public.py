import itertools
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import quote_plus

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for

from .. import notify, productions_build, venues_build
from ..auth import current_user
from ..calendar_links import google_calendar_url
from ..circuit_intelligence import (
    award_tally, best_overall_show_wins, production_ids_for_title,
    regional_distribution, revival_candidate, signature_categories,
)
from ..constants import REGIONS, SHOWS_COVERAGE_START_YEAR, SOCIETY_SECTIONS, SUGGESTION_CATEGORIES
from ..db import get_db
from ..rate_limit import limiter
from ..search import build_phrase_query, fts_match_ids
from ..season import current_season, historical_results_year, season_has_ended, season_range, season_start_year
from ..shows import is_upcoming as _is_upcoming
from ..similarity import normalize_title
from ..venues import normalize_venue

bp = Blueprint("public", __name__)

UPCOMING_LIMIT = 6
CHANGELOG_TEASER_LIMIT = 3

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


@bp.route("/")
def index():
    db = get_db()
    venues_build.ensure_current(db)

    upcoming_region = request.args.get("upcoming_region", "")
    upcoming_query = """
        SELECT shows.*, societies.name AS society_name, venues.slug AS venue_slug
        FROM shows JOIN societies ON societies.id = shows.society_id
        LEFT JOIN venues ON venues.id = shows.venue_id
        WHERE shows.moderation_status = 'approved'
          AND shows.show IS NOT NULL
          AND shows.opening_date >= ?
          AND shows.status IS NOT 'Cancelled'
          AND NOT societies.hidden
    """
    upcoming_params = [date.today().isoformat()]
    if upcoming_region in REGIONS:
        upcoming_query += " AND shows.region = ?"
        upcoming_params.append(upcoming_region)
    upcoming_query += " ORDER BY shows.opening_date LIMIT ?"
    upcoming_params.append(UPCOMING_LIMIT)
    upcoming = db.execute(upcoming_query, upcoming_params).fetchall()

    # Whichever of the upcoming shows above happen to have a poster - same
    # list, same region filter, same order, not a separate query. Keeps the
    # gallery honest: it can never show a show that isn't actually in the
    # "Upcoming shows" table right below it.
    poster_gallery = [show for show in upcoming if show["poster_filename"]]

    changelog_teaser = db.execute(
        "SELECT entry, date(created_at) AS entry_date FROM changelog_entries ORDER BY created_at DESC LIMIT ?",
        (CHANGELOG_TEASER_LIMIT,),
    ).fetchall()

    return render_template(
        "index.html",
        upcoming=upcoming,
        poster_gallery=poster_gallery,
        regions=REGIONS,
        upcoming_region=upcoming_region,
        changelog_teaser=changelog_teaser,
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
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
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
    productions_build.ensure_current(db)
    societies = []
    titles = []
    reviews = []
    awards = []
    if q:
        escaped = q.translate(_QUOTE_CHARS).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

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

        # Every matching title from either the current shows table or the
        # older awards archive, same shape as titles_list()'s own query -
        # deliberately one "Shows" result kind rather than a separate "Award"
        # one, since /titles/<title> already surfaces both a show's
        # production history and its awards together.
        titles = db.execute(
            """
            SELECT show, COUNT(*) AS n FROM (
                SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical'
                UNION ALL
                SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
            )
            WHERE show LIKE ? ESCAPE '\\'
            GROUP BY show ORDER BY show LIMIT ?
            """,
            (SHOWS_COVERAGE_START_YEAR, f"%{escaped}%", SEARCH_RESULT_LIMIT),
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
               societies.name AS society_name, NULL AS direct_adjudicator_id, 'link' AS source
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.review_status = 'Published' AND shows.review_url IS NOT NULL
          AND shows.review_url != '' AND shows.moderation_status = 'approved' AND NOT societies.hidden

        UNION ALL

        SELECT shows.id AS show_id, shows.show AS show, historical_reviews.season AS season,
               historical_reviews.tier AS tier, NULL AS review_url,
               societies.name AS society_name, historical_reviews.adjudicator_id AS direct_adjudicator_id,
               'full_text' AS source
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
        reviews = [
            r for r in reviews
            if needle in (r["show"] or "").lower() or needle in (r["society_name"] or "").lower()
        ]
    if season:
        reviews = [r for r in reviews if r["season"] == season]
    if tier:
        reviews = [r for r in reviews if r["tier"] == tier]
    if adjudicator_id:
        reviews = [r for r in reviews if r["adjudicator_id"] == adjudicator_id]

    # Grouped by season for plain browsing (no search text) - matches
    # adjudicator_detail() above; only meaningful once a search narrows the
    # list to something that could reasonably cross seasons/tiers on its own,
    # so a search result stays a single flat list instead.
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
        stats=stats, result_count=len(reviews),
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
    for a society with none). Built entirely from historical_results (the
    one results table spanning every season - see SHOWS_COVERAGE_START_YEAR)
    plus shows for the current-era production count and active-years set.
    Gilbert Grandmaster (3+ Best Overall Show wins in the Gilbert tier) was
    considered and parked, not built - Darragh's call, can activate later."""
    badges = []

    # Production count mirrors info.py's "Unified productions on record"
    # logic (built for the 20 Aug stats rebuild after a real 371-production
    # undercounting bug) at reduced precision: skips that logic's
    # skeleton-show-with-no-award-record reconciliation, since being off by
    # one or two productions at a threshold is low-stakes for a decorative
    # badge in a way it wasn't for the stats page itself.
    pre_2024_productions = db.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT year, show FROM historical_results "
        "WHERE society_id = ? AND year < ? AND show IS NOT NULL)",
        (society_id, SHOWS_COVERAGE_START_YEAR),
    ).fetchone()[0]
    recent_productions = db.execute(
        "SELECT COUNT(*) FROM shows WHERE society_id = ? AND show IS NOT NULL "
        "AND moderation_status = 'approved' AND source != 'historical'",
        (society_id,),
    ).fetchone()[0]
    total_productions = pre_2024_productions + recent_productions
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

    years = {r[0] for r in db.execute(
        "SELECT DISTINCT year FROM historical_results WHERE society_id = ? AND show IS NOT NULL", (society_id,)
    )}
    for r in db.execute(
        "SELECT DISTINCT season FROM shows WHERE society_id = ? AND show IS NOT NULL AND moderation_status = 'approved'",
        (society_id,),
    ):
        years.add(historical_results_year(r[0]))
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
    productions_build.ensure_current(db)
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
        SELECT shows.*,
               EXISTS(
                   SELECT 1 FROM historical_reviews
                   WHERE historical_reviews.show_id = shows.id AND historical_reviews.moderation_status = 'approved'
               ) AS has_historical_review
        FROM shows
        WHERE society_id = ? AND moderation_status = 'approved'
        ORDER BY season DESC, show
        """,
        (society_id,),
    ).fetchall()

    # Season strings sort correctly as text (see schema.sql's design note).
    # A future-season row with no title yet is just a "slotted, TBA" placeholder -
    # not worth a blank line in the history table. One that's already been
    # announced gets pulled out into its own "coming up" block instead of
    # blending into the history below it.
    current = current_season(db)
    future_shows = [s for s in shows if s["season"] > current and s["show"] is not None]
    shows = [s for s in shows if s["season"] <= current]

    # Pre-2024 award/nomination history from the AIMS awards archive - one row
    # per category (so a single production can appear several times, once per
    # category it was up for). show can be NULL here (person-level awards like
    # the Mary Kelly/Unsung Hero Award aren't tied to a specific production) -
    # those have nothing to group onto, so they're kept as their own list
    # rather than folded into the per-production timeline below. A row with
    # no category/result at all isn't an award record - it's a bare "this
    # production happened" entry (see admin.bulk_historical_productions) -
    # still gets its own timeline row, just with an empty awards list rather
    # than being split into a separate table (see ROADMAP, 20 Aug 2026 -
    # "integrate award wins/nominations into the show-history rows instead
    # of a separate table below").
    historical_rows = db.execute(
        """
        SELECT year, tier, category_name, result, show, nominee_name, role, reason
        FROM historical_results
        WHERE society_id = ?
        ORDER BY year DESC, show, category_name
        """,
        (society_id,),
    ).fetchall()
    person_awards = [r for r in historical_rows if r["show"] is None]

    productions = {}
    for r in historical_rows:
        if r["show"] is None:
            continue
        key = (r["year"], r["show"])
        production = productions.setdefault(key, {"year": r["year"], "tier": r["tier"], "show": r["show"], "awards": []})
        if not production["tier"]:
            production["tier"] = r["tier"]
        if r["category_name"] is not None or r["result"] is not None:
            production["awards"].append(r)
    historical_timeline = sorted(productions.values(), key=lambda p: (-p["year"], p["show"] or ""))

    # A compact "trophy case" summary - total wins, Best Overall Show wins
    # specifically, and the earliest year on record (from the awards archive,
    # falling back to the earliest season in shows if there's no archive
    # history at all).
    award_totals = db.execute(
        """
        SELECT COUNT(*), SUM(CASE WHEN category_name = 'Best Overall Show' THEN 1 ELSE 0 END), MIN(year)
        FROM historical_results WHERE society_id = ? AND result = 'Winner'
        """,
        (society_id,),
    ).fetchone()
    total_wins, best_show_wins, earliest_award_year = award_totals

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

    earliest_season = db.execute(
        "SELECT MIN(season) FROM shows WHERE society_id = ? AND show IS NOT NULL", (society_id,)
    ).fetchone()[0]
    active_since = earliest_award_year or (2000 + int(earliest_season[:2]) if earliest_season else None)

    badges = _society_badges(db, society_id)

    return render_template(
        "society_detail.html", society=society, shows=shows, future_shows=future_shows,
        historical_timeline=historical_timeline, person_awards=person_awards,
        total_wins=total_wins, best_show_wins=best_show_wins, active_since=active_since,
        best_show_second=best_show_second, best_show_third=best_show_third, society_code=society_code,
        society_login_url=society_login_url, badges=badges, current_season=current,
    )


@bp.route("/shows/<int:show_id>")
def show_detail(show_id):
    db = get_db()
    venues_build.ensure_current(db)
    productions_build.ensure_current(db)
    show = db.execute(
        """
        SELECT shows.*, societies.name AS society_name, venues.slug AS venue_slug
        FROM shows JOIN societies ON societies.id = shows.society_id
        LEFT JOIN venues ON venues.id = shows.venue_id
        WHERE shows.id = ? AND shows.moderation_status = 'approved'
        """,
        (show_id,),
    ).fetchone()
    if show is None:
        abort(404)

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
    # unlike the actual scheduled adjudication_date, this is fine to show
    # publicly since it's only ever arithmetic on a date the page already
    # displays, never AIMS's own internal scheduling info.
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
        if show["review_status"] != "Not adjudicated":
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

    # Pre-2024 award/nomination history for this exact production, from the
    # older AIMS awards archive (historical_results) - a separate table with
    # no foreign key to shows (it predates this site), so matched here by
    # (society, year, title) rather than joined directly. year is
    # historical_results' own year column, not season - see
    # historical_results_year. Exact-normalized match only (case/punctuation,
    # same as normalize_title everywhere else) - deliberately not fuzzy on a
    # public page; a genuine title mismatch belongs in the admin queue's own
    # history_match review step (see admin.categorize_pending_reviews),
    # which is exactly what that step exists to catch before a show ever
    # gets this far.
    award_history = []
    if show["show"] and show["season"]:
        target_norm = normalize_title(show["show"])
        candidate_rows = db.execute(
            """
            SELECT show, tier, category_name, result, nominee_name, role, reason
            FROM historical_results
            WHERE society_id = ? AND year = ? AND show IS NOT NULL
            """,
            (show["society_id"], historical_results_year(show["season"])),
        ).fetchall()
        award_history = [
            r for r in candidate_rows
            if normalize_title(r["show"]) == target_norm and (r["category_name"] is not None or r["result"] is not None)
        ]

    return render_template(
        "show_detail.html", show=show, is_upcoming=is_upcoming,
        gcal_show_url=gcal_show_url, adjudication_cutoff=adjudication_cutoff, reviewed_by=reviewed_by,
        historical_review=historical_review, award_history=award_history,
        season_ended=season_has_ended(db, show["season"]),
    )


TITLES_SORT_OPTIONS = {
    "title": "show COLLATE NOCASE",
    "most": "n DESC, show COLLATE NOCASE",
    "least": "n ASC, show COLLATE NOCASE",
}
# "stale" isn't a SQL ORDER BY - last-performed year comes from a separate
# lookup (see last_performed below), so it's sorted in Python after the fact.
TITLES_SORT_CHOICES = set(TITLES_SORT_OPTIONS) | {"stale"}


@bp.route("/titles")
def titles_list():
    db = get_db()
    productions_build.ensure_current(db)
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "title")
    if sort not in TITLES_SORT_CHOICES:
        sort = "title"

    query = """
        SELECT show, COUNT(*) AS n FROM (
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' AND source != 'historical'
            UNION ALL
            SELECT show FROM historical_results WHERE show IS NOT NULL AND year < ?
        )
    """
    params = [SHOWS_COVERAGE_START_YEAR]
    if q:
        query += " WHERE show LIKE ? ESCAPE '\\'"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    query += f" GROUP BY show ORDER BY {TITLES_SORT_OPTIONS[sort if sort != 'stale' else 'title']}"

    rows = db.execute(query, params).fetchall()

    manual_links = dict(db.execute("SELECT show, url FROM show_links").fetchall())
    has_info = {r[0] for r in db.execute("SELECT show FROM show_info").fetchall()}
    # Last performed - the true most recent year on record for a title from
    # either source, unfiltered by SHOWS_COVERAGE_START_YEAR (that filter
    # only exists above to avoid double-counting a production in both
    # tables; a recency question has no such double-counting problem).
    last_performed = dict(db.execute(
        """
        SELECT show, MAX(year) FROM (
            SELECT show, CAST(substr(opening_date, 1, 4) AS INTEGER) AS year
            FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved' AND opening_date IS NOT NULL
            UNION ALL
            SELECT show, year FROM historical_results WHERE show IS NOT NULL
        )
        GROUP BY show
        """
    ).fetchall())

    shows = [
        {
            "title": r["show"],
            "count": r["n"],
            "last_year": last_performed.get(r["show"]),
            "url": manual_links.get(r["show"]),
            "is_manual": r["show"] in manual_links,
            "has_info": r["show"] in has_info,
            "search_url": f"https://en.wikipedia.org/w/index.php?search={quote_plus(r['show'] + ' musical')}",
        }
        for r in rows
    ]

    if sort == "stale":
        shows.sort(key=lambda s: (s["last_year"] is None, s["last_year"] or 0))

    # Paged in Python rather than SQL: the "stale" sort above can only be
    # applied after last_performed is joined in, so the full list has to be
    # built either way. Same page-size/param convention as /awards.
    total = len(shows)
    per_page, page, total_pages = paginate_args(total)
    shows = shows[(page - 1) * per_page:page * per_page]

    return render_template(
        "titles_list.html", shows=shows, q=q, sort=sort,
        page=page, total_pages=total_pages, total=total,
        per_page=per_page, page_sizes=LIST_PAGE_SIZES,
    )


@bp.route("/titles/<path:title>")
def title_detail(title):
    db = get_db()
    productions_build.ensure_current(db)
    shows = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.show = ? AND shows.moderation_status = 'approved'
        ORDER BY shows.season DESC, societies.name
        """,
        (title,),
    ).fetchall()

    # Distinct (year, society) before 23/24 - historical_results has one row
    # per award category, not per production, so this collapses back to one
    # row per actual staging. Stops before SHOWS_COVERAGE_START_YEAR so a
    # 23/24+ production already listed above under "full detail" doesn't
    # also show up a second time down here.
    historical = db.execute(
        """
        SELECT DISTINCT year, society_name FROM historical_results
        WHERE show = ? AND year < ? ORDER BY year DESC
        """,
        (title, SHOWS_COVERAGE_START_YEAR),
    ).fetchall()

    if not shows and not historical:
        abort(404)

    info = db.execute("SELECT * FROM show_info WHERE show = ?", (title,)).fetchone()

    # AIMS debut - earliest record of this title, whichever source it comes
    # from. historical is already the pre-23/24 archive, so if it has any
    # rows its earliest (last, since it's sorted DESC) year always predates
    # anything in shows. Otherwise fall back to the earliest season string
    # among shows - lexical comparison matches chronological order for this
    # site's YY/YY+1 seasons, same assumption all_seasons sorting relies on.
    if historical:
        debut_label = str(historical[-1]["year"])
    elif shows:
        debut_label = f"{min(s['season'] for s in shows)} season"
    else:
        debut_label = None

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

    return render_template(
        "title_detail.html", title=title, shows=shows, historical=historical, info=info,
        debut_label=debut_label, circuit=circuit,
    )


@bp.route("/venues")
def venues_index():
    db = get_db()
    venues_build.ensure_current(db)
    q = request.args.get("q", "").strip()
    region = request.args.get("region", "")
    if region not in REGIONS:
        region = ""

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
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query += (" AND (venues.name LIKE ? ESCAPE '\\' OR venues.town LIKE ? ESCAPE '\\'"
                  " OR venues.county LIKE ? ESCAPE '\\')")
        params += [f"%{escaped}%"] * 3
    if region:
        query += " AND venues.region = ?"
        params.append(region)
    # Most-used first, not alphabetical - the venue field still has real noise
    # in it (an anniversary note where a venue name should be, a bare county
    # name), and alphabetical order put exactly that at the very top. Sorting
    # by production count means the real, recognizable venues lead; the noise
    # is all still there, just no longer the first impression.
    query += " GROUP BY venues.id ORDER BY n DESC, venues.name COLLATE NOCASE"
    venues = db.execute(query, params).fetchall()

    total = len(venues)
    per_page, page, total_pages = paginate_args(total)
    venues = venues[(page - 1) * per_page:page * per_page]

    mapped = [v for v in venues if v["latitude"] is not None and v["longitude"] is not None]
    return render_template(
        "venues_list.html", venues=venues, q=q, regions=REGIONS, selected_region=region,
        mapped_count=len(mapped),
        page=page, total_pages=total_pages, total=total, per_page=per_page, page_sizes=LIST_PAGE_SIZES,
    )


@bp.route("/venues/<path:venue>")
def venue_detail(venue):
    db = get_db()
    venues_build.ensure_current(db)
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

    return render_template("suggest.html", form={}, categories=SUGGESTION_CATEGORIES)


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


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename)
