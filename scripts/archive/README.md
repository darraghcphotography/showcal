# Archived one-shot scripts

Scripts that ran once against production, did their job, and are kept for the
record rather than for re-running. Moved here (2026-08-24) so the repo root
holds only the scripts that are part of the operating manual (import/export,
enrichment, seeding - the ones CLAUDE.md and docs/deployment.md reference).

A script belongs here when: it has already run against production, nothing in
the app/docs/tests references it, and re-running it would be a no-op or need
rework anyway. When a future one-shot finishes its job, `git mv` it here.

- `backfill_2526_reviews.py` - one-time 25/26 review-status backfill (2026-08-20)
- `backfill_2627_venues.py` - one-time 26/27 venue backfill (2026-08-22)
- `fix_society_misattributions.py` / `_2.py` - the 2026-08-20 society
  misattribution correction pair (history and reasoning in ROADMAP_ARCHIVE.md)
