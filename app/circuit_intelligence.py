"""How a title's real staging history reads back as a few facts a visitor
would actually want: how often it wins, which award it's known for, how far
it's traveled across the AIMS regions, and whether it's gone quiet long
enough to be worth a society picking back up.

Everything here is "Source C" from SHOW_ENRICHMENT_PROPOSAL.md - free to
build because it's just queries against data already on record
(productions/historical_results), unlike the proposal's other two sources
(Wikidata matching, licensing-house specs) which need external research.

Every function takes a title's production ids, from production_ids_for_title
- the productions table (see app/productions_build.py) is the single
definition of "which stagings are the same show," so nothing here re-derives
title identity on its own.
"""

from .constants import AWARD_CATEGORIES, REGIONS
from .similarity import normalize_title

# category_name -> canonical AWARD_CATEGORIES key, folding a confirmed rename
# (e.g. "Best Chorus" -> "Best Choral Singing") so a title's wins under an old
# name aren't split off from the same wins under its current one - the same
# db_names list info.py's own award leaderboard already uses, for the
# identical reason.
_CANONICAL_CATEGORY = {name: c["key"] for c in AWARD_CATEGORIES for name in c["db_names"]}

# Judgment calls, checked against the real archive rather than guessed - see
# the module's own README note in ROADMAP.md for the numbers behind them.
# Same footing as public.py's BADGE_*_MIN constants: a real threshold, worth
# revisiting if the data or the site's audience changes, not a magic number.
REVIVAL_MIN_PRODUCTIONS = 8
REVIVAL_MIN_GAP_YEARS = 10
REVIVAL_MAX_GAP_YEARS = 30
SIGNATURE_MIN_WINS = 2


def production_ids_for_title(db, title):
    """Every production of this title, by its normalized identity - the same
    title_key productions_build.py itself groups on, so this can never
    disagree with what the productions table calls the same show."""
    key = normalize_title(title)
    if not key:
        return []
    return [r["id"] for r in db.execute("SELECT id FROM productions WHERE title_key = ?", (key,))]


def award_tally(db, production_ids):
    """Total AIMS award-category entries and how many were wins, across the
    full archive (not just 23/24+) - historical_results.production_id links
    every era's award records to their production regardless of date."""
    if not production_ids:
        return {"nominations": 0, "wins": 0}
    placeholders = ",".join("?" * len(production_ids))
    row = db.execute(
        f"""
        SELECT COUNT(*) AS nominations,
               SUM(CASE WHEN result = 'Winner' THEN 1 ELSE 0 END) AS wins
        FROM historical_results
        WHERE production_id IN ({placeholders}) AND category_name IS NOT NULL
        """,
        production_ids,
    ).fetchone()
    return {"nominations": row["nominations"], "wins": row["wins"] or 0}


def best_overall_show_wins(db, production_ids):
    """Year + society for every Best Overall Show win - joined through
    productions for the society's current name, not the raw archive spelling
    historical_results carries."""
    if not production_ids:
        return []
    placeholders = ",".join("?" * len(production_ids))
    return db.execute(
        f"""
        SELECT historical_results.year AS year, productions.society_name AS society_name
        FROM historical_results
        JOIN productions ON productions.id = historical_results.production_id
        WHERE historical_results.production_id IN ({placeholders})
          AND historical_results.category_name = 'Best Overall Show'
          AND historical_results.result = 'Winner'
        ORDER BY historical_results.year
        """,
        production_ids,
    ).fetchall()


def signature_categories(db, production_ids, min_wins=SIGNATURE_MIN_WINS):
    """Category/ies this title has won most often. A genuine tie is returned
    as a tie, never arbitrarily broken - real on this archive: 56% of titles
    with any win at all have a joint-top category (checked 2026-08-23).
    Returns [] rather than calling a single win "signature" - one win isn't
    a defining category, see min_wins."""
    if not production_ids:
        return []
    placeholders = ",".join("?" * len(production_ids))
    raw = db.execute(
        f"""
        SELECT category_name, COUNT(*) AS wins FROM historical_results
        WHERE production_id IN ({placeholders}) AND result = 'Winner' AND category_name IS NOT NULL
        GROUP BY category_name
        """,
        production_ids,
    ).fetchall()
    folded = {}
    for r in raw:
        key = _CANONICAL_CATEGORY.get(r["category_name"], r["category_name"])
        folded[key] = folded.get(key, 0) + r["wins"]
    if not folded:
        return []
    top = max(folded.values())
    if top < min_wins:
        return []
    return sorted(
        [{"category": k, "wins": v} for k, v in folded.items() if v == top],
        key=lambda x: x["category"],
    )


def regional_distribution(db, production_ids):
    """Production count per region, all 6 REGIONS always present (0 if none
    on record), plus a separate count for productions whose society never
    resolved to a region (a defunct/unconfirmed historical society - see
    productions.region's own NULL case). Returns (rows, unknown_count)."""
    counts = {r: 0 for r in REGIONS}
    unknown = 0
    if production_ids:
        placeholders = ",".join("?" * len(production_ids))
        for row in db.execute(
            f"SELECT region, COUNT(*) AS n FROM productions WHERE id IN ({placeholders}) GROUP BY region",
            production_ids,
        ):
            if row["region"] in counts:
                counts[row["region"]] = row["n"]
            else:
                unknown += row["n"]
    return [{"region": r, "n": counts[r]} for r in REGIONS], unknown


def _is_revival_candidate(production_count, gap_years):
    """Pure threshold check, factored out so the matrix of edge cases is
    testable without seeding a database. Both bounds matter: fewer than
    REVIVAL_MIN_PRODUCTIONS is a one-off, not proven popularity (the naive
    "last staged 1948" trap the enrichment proposal itself flags); a gap past
    REVIVAL_MAX_GAP_YEARS reads as genuinely retired rather than due."""
    if production_count < REVIVAL_MIN_PRODUCTIONS:
        return False
    return REVIVAL_MIN_GAP_YEARS <= gap_years <= REVIVAL_MAX_GAP_YEARS


def revival_candidate(db, production_ids, current_year):
    """None unless this title's own production history makes it a real
    revival candidate - per-title, not a cross-title showcase. See
    _is_revival_candidate for the threshold."""
    if not production_ids:
        return None
    placeholders = ",".join("?" * len(production_ids))
    last_year = db.execute(
        f"SELECT MAX(season_start_year) FROM productions WHERE id IN ({placeholders})", production_ids
    ).fetchone()[0]
    if last_year is None:
        return None
    gap = current_year - last_year
    if not _is_revival_candidate(len(production_ids), gap):
        return None
    return {"last_year": last_year, "gap_years": gap, "production_count": len(production_ids)}
