"""Shared vocabulary that mirrors the CHECK constraints in schema.sql.

Kept in one place so templates/routes build filter dropdowns from the same
list the database enforces - if you ever add a region or tier, this is one
of two places to update (the other is schema.sql).
"""

REGIONS = ["Eastern", "Western", "Northern", "South-West", "South-East", "Midlands"]

# Full set of society tiers, including states that never apply to a single show.
SOCIETY_SECTIONS = ["Gilbert", "Sullivan", "Non-AIMS", "Inactive"]

# Tiers a single show can be produced under (a society is never "Inactive" *as* a show).
SHOW_SECTIONS = ["Gilbert", "Sullivan", "Non-AIMS"]

REVIEW_STATUSES = ["Published", "Scheduled", "Not adjudicated", "None"]

# Result values as they appear in historical_results (AIMS awards archive).
AWARD_RESULTS = ["Winner", "Second Place", "Third Place", "Nominee"]

# shows.csv's own coverage begins at season 23/24, i.e. award-archive Year
# 2024 (historical_results.year N corresponds to show season (N-1)/N). Any
# query that treats a historical_results row as equivalent to a shows-table
# row - counting/listing a production, not showing award-category detail -
# must stay below this year to avoid counting/listing a 23/24+ show twice.
SHOWS_COVERAGE_START_YEAR = 2024

# Amateur licensing status for show_info.rights_status - deliberately coarse,
# since this is a moderator's manual read of a rights holder's site (MTI,
# Concord Theatricals, etc.), not a live/automated availability check.
RIGHTS_STATUSES = ["Available", "Contact publisher", "Restricted"]

# feature_suggestions.category - chosen by the submitter on the /suggest form.
SUGGESTION_CATEGORIES = ["Idea/Feature", "Bug report", "Data error"]

# feature_suggestions.triage_status - moderator-set. Anything past 'New' is
# visible on the public /suggestions Roadmap page.
SUGGESTION_STATUSES = ["New", "Planned", "In Progress", "Done", "Not planned"]

# Award categories for the /stats "award category leaderboard" picker, in
# dropdown display order. "person": True means the meaningful winner is an
# individual (leaderboard groups/labels by historical_results.nominee_name);
# False means it's a society category (groups by society, labels by
# society_name) - checked against real data, not assumed from the column
# name: Best Technical/Visual/Programme/House Management all store a
# *society* name in nominee_name despite the column, and were confirmed
# society-level by cross-checking against society_name population. "Best
# Choreography" and "Best Choreographer" are the same award under two
# historical names (both in use 2019-2025, not a clean rename) - merged
# into one picker entry, db_names carries both so the query catches either.
AWARD_CATEGORIES = [
    {"key": "Best Overall Show", "group": "Show", "person": False, "db_names": ["Best Overall Show"]},
    {"key": "Best Technical (Lighting, Sets & Sound)", "group": "Show", "person": False, "db_names": ["Best Technical (Lighting, Sets & Sound)"]},
    {"key": "Best Visual (Costumes, Props, Make-Up & Hair)", "group": "Show", "person": False, "db_names": ["Best Visual (Costumes, Props, Make-Up & Hair)"]},
    {"key": "Best Programme", "group": "Show", "person": False, "db_names": ["Best Programme"]},
    {"key": "Best House Management", "group": "Show", "person": False, "db_names": ["Best House Management"]},
    {"key": "Best Chorus", "group": "Show", "person": False, "db_names": ["Best Chorus"]},
    {"key": "Best Ensemble", "group": "Show", "person": False, "db_names": ["Best Ensemble"]},
    {"key": "Best Gilbert & Sullivan/Pre 1935 Show/Modern Opera", "group": "Show", "person": False, "db_names": ["Best Gilbert & Sullivan/Pre 1935 Show/Modern Opera"]},
    {"key": "Best Choral Singing", "group": "Show", "person": False, "db_names": ["Best Choral Singing"]},
    {"key": "Best Lighting", "group": "Show", "person": False, "db_names": ["Best Lighting"]},
    {"key": "Best Sets", "group": "Show", "person": False, "db_names": ["Best Sets"]},
    {"key": 'Best Show "All Amateur Cast"', "group": "Show", "person": False, "db_names": ['Best Show "All Amateur Cast"']},
    {"key": "Best Moment of Theatre", "group": "Show", "person": False, "db_names": ["Best Moment of Theatre"]},
    {"key": "Spirit of AIMS", "group": "Show", "person": False, "db_names": ["Spirit of AIMS"]},
    {"key": "Spirit of AIMS/Adjudicator's Special Award", "group": "Show", "person": False, "db_names": ["Spirit of AIMS/Adjudicator's Special Award"]},
    {"key": "Adjudicator's Special Award", "group": "Show", "person": False, "db_names": ["Adjudicator's Special Award"]},
    {"key": "Best Director", "group": "Production team", "person": True, "db_names": ["Best Director"]},
    {"key": "Best Musical Director", "group": "Production team", "person": True, "db_names": ["Best Musical Director"]},
    {"key": "Best Choreography", "group": "Production team", "person": True, "db_names": ["Best Choreography", "Best Choreographer"]},
    {"key": "Best Stage Management", "group": "Production team", "person": True, "db_names": ["Best Stage Management"]},
    {"key": "Best Chorus Master/Mistress", "group": "Production team", "person": True, "db_names": ["Best Chorus Master/Mistress"]},
    {"key": "Best Actor", "group": "Cast", "person": True, "db_names": ["Best Actor"]},
    {"key": "Best Actor In A Supporting Role", "group": "Cast", "person": True, "db_names": ["Best Actor In A Supporting Role"]},
    {"key": "Best Actress", "group": "Cast", "person": True, "db_names": ["Best Actress"]},
    {"key": "Best Actress In A Supporting Role", "group": "Cast", "person": True, "db_names": ["Best Actress In A Supporting Role"]},
    {"key": "Best Comedian", "group": "Cast", "person": True, "db_names": ["Best Comedian"]},
    {"key": "Best Comedienne", "group": "Cast", "person": True, "db_names": ["Best Comedienne"]},
    {"key": "Best Male Singer", "group": "Cast", "person": True, "db_names": ["Best Male Singer"]},
    {"key": "Best Female Singer", "group": "Cast", "person": True, "db_names": ["Best Female Singer"]},
    {"key": "Best Overall Performance", "group": "Cast", "person": True, "db_names": ["Best Overall Performance"]},
    {"key": "Best Youth in an Adult Show", "group": "Cast", "person": True, "db_names": ["Best Youth in an Adult Show"]},
    {"key": "Mary Kelly/Unsung Hero Award", "group": "Cast", "person": True, "db_names": ["Mary Kelly/Unsung Hero Award"]},
]
AWARD_CATEGORY_BY_KEY = {c["key"]: c for c in AWARD_CATEGORIES}
DEFAULT_AWARD_CATEGORY = "Best Overall Show"

# Real historical_results.category_name values that are society-level (see
# the AWARD_CATEGORIES comment above for how "person" was determined) - used
# on the /awards browse table to hide the Nominee column for these rows,
# since nominee_name there actually just duplicates the Society column, not
# a real individual.
SOCIETY_AWARD_CATEGORY_NAMES = frozenset(
    name for c in AWARD_CATEGORIES if not c["person"] for name in c["db_names"]
)
