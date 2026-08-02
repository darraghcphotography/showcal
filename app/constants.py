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
