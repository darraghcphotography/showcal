"""How a production is identified, in one place.

Everything that has to decide "are these two records the same staging?" - the
backfill script, and eventually every page that counts productions - goes
through here, so the definition can't drift between callers the way it did
when each query hand-rolled its own union of shows and historical_results.

The natural key is (society_key, season_start_year, title_key):

  society_key       'id:<societies.id>' when the society is a real, matched
                    row, 'name:<normalized name>' when it isn't. 71 society
                    names in the awards archive are defunct or renamed and
                    have never matched a current row; they still staged real
                    productions, so they need to key on something. Prefixing
                    keeps the two forms from ever colliding.
  season_start_year The real four-digit year the season opened - never a
                    'yy/yy' string, which cannot tell 1912 from 2012.
  title_key         normalize_title() - the same lowercase/strip-punctuation
                    rule used everywhere else on the site, deliberately not
                    fuzzy (Frozen vs Frozen Jr. are different shows).

Verified against the real production database before being committed to:
under this key, no production maps to more than one shows row, no production
is reachable under both an id- and a name-form society key, and title
normalization merges exactly one pair of raw spellings ("Ghost the Musical" /
"Ghost: The Musical"), which is the same show.
"""

from .season import award_year_to_season_start, season_label, season_start_year
from .similarity import normalize_title


# A production the public site may count or list. The productions table is built
# from every shows row regardless of moderation_status (see productions_build.
# collect), so a pending or rejected submission has a production row too -
# filtering that out is the caller's job, and every public surface has to do it
# the same way or they will disagree again, which is the whole reason this table
# exists.
#
# An award record needs no status check: historical_results has no moderation
# gate, and a row only exists because AIMS published the result.
#
# "On record", not "has already happened". /titles has always counted an
# announced future show, and info.py's own happened_production predicate asks
# the narrower question (it takes a :today parameter). Deliberately two
# predicates, not one - don't merge them.
#
# Callers must refer to the table as `productions` (not an alias).
ON_RECORD_PRODUCTION = """
    (EXISTS (SELECT 1 FROM shows
              WHERE shows.production_id = productions.id
                AND shows.moderation_status = 'approved')
     OR EXISTS (SELECT 1 FROM historical_results
                 WHERE historical_results.production_id = productions.id))
"""


def society_key(society_id, society_name):
    """The society half of a production's identity. society_id wins whenever
    it's set; the normalized name is the fallback for an unmatched historical
    society."""
    if society_id:
        return f"id:{int(society_id)}"
    return f"name:{normalize_title(society_name or '')}"


def production_key(society_id, society_name, start_year, title):
    """Full natural key, or None if this record can't name a production -
    a shows row with no title yet ("society slotted, title TBA"), or an award
    record whose show column is blank."""
    title_key = normalize_title(title or "")
    if not title_key:
        return None
    return (society_key(society_id, society_name), int(start_year), title_key)


def key_from_show(row):
    """Natural key for a `shows` row. shows.season is safe to decode with
    season_start_year here because that table only ever holds modern seasons
    (05/06 onward) - the ambiguity that helper warns about is confined to
    award years, which don't come through this path."""
    return production_key(row["society_id"], None, season_start_year(row["season"]), row["show"])


def key_from_award_record(row):
    """Natural key for a `historical_results` row, straight off its real
    four-digit award year."""
    return production_key(
        row["society_id"], row["society_name"], award_year_to_season_start(row["year"]), row["show"]
    )


def season_for_key(key):
    """Display season string for a natural key."""
    return season_label(key[1])
