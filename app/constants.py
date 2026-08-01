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
