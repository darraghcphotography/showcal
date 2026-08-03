# Roadmap

Tracks the current phase of work so a new session (after `/clear` or a fresh
start) can pick up where the last one left off without re-deriving context.
Update this file - don't just say the plan out loud in chat - whenever the
phase changes.

## Phase 0 - Incident response & hardening (done, 2026-08-03)
- Recovered from the broken `/data` mount that wiped the database (absolute
  volume path fix, `aims-backup` sidecar, HBS3 off-NAS backup, startup guard).
- Security/stability audit: response headers, rate limiting, DB index,
  confirmed no dead code / SQL injection / auth gaps.
- UX polish: favicon/manifest/404, responsive tables on mobile, compact
  dates, venue+Maps links, trophy case runner-up/third place.

## Phase 1 - Test suite (next)
No persisted tests exist - every check so far has been a one-off script,
verified once and thrown away. Build a small `pytest` suite covering the
things that would actually hurt if they broke silently:
- Auth gates (`login_required`/`admin_required`/`society_required`) actually
  block unauthenticated access.
- `import_csv.py` / `export_csv.py` round-trip (import then export produces
  the same data back out).
- The 27/28 unconfirmed-tier blanking rule in `import_csv.py`.
- The trophy-case query (win/runner-up/third-place counts).
- The startup guard (missing-db warning) and the mount-path assumption.

## Phase 2 - Data integrity sweep
- [Pending: run `export_csv.py` against production](see Claude's memory -
  "pending-csv-export-refresh") to pull the North Wexford tier fix (and
  anything else manually corrected since) back into the tracked CSVs.
- Audit for other societies with similarly stale/presumptive data.

## Phase 3 - Public launch
Before announcing this to AIMS societies/fans at large:
- Start a **fresh session** for this phase specifically.
- Have Claude interview you with `AskUserQuestion` about launch scope,
  onboarding at scale (how do all ~150 societies actually get invite codes -
  not just the ones who happen to ask), edge cases, and what "done" means.
- Write the outcome to `LAUNCH.md` as a real spec before implementing
  anything further.

## Phase 4 - Post-launch maintenance cadence
- Periodically verify the nightly backup (`aims-backup` sidecar) is still
  actually producing files, not just running.
- Revisit deferred items from the security audit: CSP (blocked on inline
  `onsubmit` handlers), real image-content validation for poster uploads
  (would need Pillow).

## Working agreements (from the 2026-08-03 process review)
- `/clear` (or a fresh session) between genuinely distinct workstreams -
  don't chain unrelated incidents/features/audits in one long thread.
- Mockup-first for anything visual - already working well, keep doing it.
- For a sweep touching many files (like Phase 0's audit), write the plan
  and get sign-off before editing, rather than fixing things as found.
- Lessons that matter beyond one session go in `docs/`, not just chat -
  already the habit for this repo, keep it up.
