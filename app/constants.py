"""Shared vocabulary that mirrors the CHECK constraints in schema.sql.

Kept in one place so templates/routes build filter dropdowns from the same
list the database enforces - if you ever add a region or tier, this is one
of two places to update (the other is schema.sql).
"""
import re

# ISO date, as every date-typed form field on the site submits it (an
# <input type="date">'s own wire format).
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REGIONS = ["Eastern", "Western", "Northern", "South-West", "South-East", "Midlands"]

# Full set of society tiers, including states that never apply to a single show.
SOCIETY_SECTIONS = ["Gilbert", "Sullivan", "Non-AIMS", "Inactive"]

# Tiers a single show can be produced under (a society is never "Inactive" *as* a show).
SHOW_SECTIONS = ["Gilbert", "Sullivan", "Non-AIMS"]

REVIEW_STATUSES = ["Published", "Scheduled", "Not adjudicated", "None"]

# photo_submissions.kind - what a member says they've sent in, in the order the
# submit form offers them: Past Productions Listing, Past Show Poster, Other.
# Older rows predating this split carry 'review', 'programme_cover', 'production_photo',
# so ALL_PHOTO_KIND_LABELS preserves them for admin views.
PHOTO_KIND_LABELS = {
    "programme_history": "Past Productions Listing",
    "poster": "Past Show Poster",
    "other": "Other",
}

ALL_PHOTO_KIND_LABELS = {
    **PHOTO_KIND_LABELS,
    "review": "Newspaper clipping (Legacy)",
    "programme_cover": "Programme cover (Legacy)",
    "production_photo": "Cast / production photo (Legacy)",
}

# venues.venue_type - what kind of building it is, as opposed to
# AUDITORIUM_TYPES (app/blueprints/admin/venues.py), which is the shape of the
# room. Deliberately coarse: these are the distinctions a society actually
# cares about when scanning the directory ("is this a real theatre or a parish
# hall?"), and a finer split would need judgement calls the venue's own name
# can't settle. Most rows were classified from that name by
# classify_venue_types.py; NULL means nobody has looked yet.
VENUE_TYPES = ["Theatre", "Arts Centre", "School or College", "Community or Parish Hall", "Other"]

# Result values as they appear in historical_results (AIMS awards archive).
AWARD_RESULTS = ["Winner", "Second Place", "Third Place", "Nominee"]

# shows.csv's own coverage begins at season 23/24, i.e. award-archive Year
# 2024 (historical_results.year N corresponds to show season (N-1)/N). Any
# query that treats a historical_results row as equivalent to a shows-table
# row - counting/listing a production, not showing award-category detail -
# must stay below this year to avoid counting/listing a 23/24+ show twice.
SHOWS_COVERAGE_START_YEAR = 2024

# The oldest season the archive covers as a *circuit* rather than as a few
# societies' own back catalogues. Everything from 76/77 on runs to 28-37
# productions a season and comes from the AIMS awards archive proper;
# everything before it is 98 productions across 51 seasons, 1-4 each, from
# exactly three societies (Wexford Light Opera, Roscrea, Carrick-on-Suir)
# whose own production histories were backfilled - real productions that
# should count, but a row saying "1954: 2 productions" would read as a fact
# about AIMS rather than about how far three societies' records go. /stats
# folds everything below this into one labelled summary row instead.
ARCHIVE_CIRCUIT_START_YEAR = 1976

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
# society-level by cross-checking against society_name population.
#
# "Best Choreography" and "Best Choreographer" were merged into one entry
# here for years (db_names carrying both) on the assumption they were the
# same award under two historical names - WRONG, corrected 19 Aug 2026:
# checked year-by-year and both ran in parallel, as clearly distinct
# categories, every single year from 2019 through 2025 (never a rename -
# a renamed award doesn't coexist with its own "old name" for 7 straight
# years). Reverted to two separate entries below.
#
# Three renames ARE confirmed clean (the category simply stops appearing
# under one name and starts under another, never both in the same year) -
# merged via db_names, with a "note" surfaced on the Explorer result so a
# 48-year history doesn't silently read as brand new:
#   - Best Chorus (1977-2025) -> Best Choral Singing (2026-)
#   - Adjudicator's Special Award (1977-2000, and again 2023-2025) ->
#     "Spirit of AIMS/Adjudicator's Special Award" (2001-2022, a real
#     printed category name for two decades, missed by the first pass at
#     this lineage since only the outer two names were checked) ->
#     Spirit of AIMS (2026-)
# Best Choreography (1977-2025) -> Best Moment of Theatre (2026-) is
# deliberately NOT merged - the award's meaning changed (no longer
# dance-specific), so Darragh's call was to cross-link but count
# separately. Best Choreographer (2019-2026) is untouched by any of this -
# a separate, still-running person award throughout.
AWARD_CATEGORIES = [
    {"key": "Best Overall Show", "group": "Show", "person": False, "db_names": ["Best Overall Show"]},
    {"key": "Best Technical (Lighting, Sets & Sound)", "group": "Show", "person": False, "db_names": ["Best Technical (Lighting, Sets & Sound)"]},
    {"key": "Best Visual (Costumes, Props, Make-Up & Hair)", "group": "Show", "person": False, "db_names": ["Best Visual (Costumes, Props, Make-Up & Hair)"]},
    {"key": "Best Programme", "group": "Show", "person": False, "db_names": ["Best Programme"]},
    {"key": "Best House Management", "group": "Show", "person": False, "db_names": ["Best House Management"]},
    {
        "key": "Best Choral Singing", "group": "Show", "person": False,
        "db_names": ["Best Chorus", "Best Choral Singing"],
        "note": 'Renamed from "Best Chorus" for the 2025/26 season - counted continuously across both names.',
    },
    {"key": "Best Ensemble", "group": "Show", "person": False, "db_names": ["Best Ensemble"]},
    {"key": "Best Gilbert & Sullivan/Pre 1935 Show/Modern Opera", "group": "Show", "person": False, "db_names": ["Best Gilbert & Sullivan/Pre 1935 Show/Modern Opera"]},
    {"key": "Best Lighting", "group": "Show", "person": False, "db_names": ["Best Lighting"]},
    {"key": "Best Sets", "group": "Show", "person": False, "db_names": ["Best Sets"]},
    {"key": 'Best Show "All Amateur Cast"', "group": "Show", "person": False, "db_names": ['Best Show "All Amateur Cast"']},
    {
        "key": "Best Moment of Theatre", "group": "Show", "person": False, "db_names": ["Best Moment of Theatre"],
        "note": 'New for the 2025/26 season - formerly "Best Choreography" (see that entry under Production '
                "team), but counted separately: this one has no individual nominee on any of its 10 records "
                "so far, confirming the award's meaning genuinely changed (no longer dance-specific), not just its name.",
    },
    {
        "key": "Spirit of AIMS", "group": "Show", "person": False,
        "db_names": ["Adjudicator's Special Award", "Spirit of AIMS/Adjudicator's Special Award", "Spirit of AIMS"],
        "note": 'Renamed from "Adjudicator\'s Special Award" for the 2025/26 season (printed as "Spirit of AIMS/'
                'Adjudicator\'s Special Award" 2001-2022) - counted continuously across all three names.',
    },
    {"key": "Best Director", "group": "Production team", "person": True, "db_names": ["Best Director"]},
    {"key": "Best Musical Director", "group": "Production team", "person": True, "db_names": ["Best Musical Director"]},
    {
        "key": "Best Choreography", "group": "Production team", "person": True, "db_names": ["Best Choreography"],
        "note": 'Retired after the 2024/25 season - continues as "Best Moment of Theatre" (see that entry '
                "under Show), but that award's meaning changed (no longer dance-specific), so its history "
                "starts fresh rather than inheriting this one's.",
    },
    {"key": "Best Choreographer", "group": "Production team", "person": True, "db_names": ["Best Choreographer"]},
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
