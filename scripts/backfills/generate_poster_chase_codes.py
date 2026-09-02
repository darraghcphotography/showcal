"""Mints a society login code for each chaseable production that has none.

A society cannot upload its poster without a login code, and 15 of the 17
productions opening inside the poster chase window belong to societies with no
active code. That is the real bottleneck: sending a "please add your poster"
message to a society that has no way to add one wastes the message and teaches
them the next one is safe to ignore.

Scoped to exactly the set `/admin/missing-posters` presents as work - approved,
titled, upcoming, no poster, opening within POSTER_CHASE_DAYS - and skips any
society that already has an active code. A society with two chaseable shows gets
one code, not two.

WHY THESE EXPIRE, when the admin "Generate code" button's do not
--------------------------------------------------------------
`admin.generate_society_code` inserts with no `expires_at`, which is how the
2026-09-01 security audit found 17 of 21 active codes never expiring. A society
code is not read-only: it edits that society's shows and uploads posters. Minting
15 more permanent credentials to fix a poster gap would take that 17 to 32 and
make an open finding materially worse.

These expire at the end of the current AIMS season instead. That is the natural
boundary for the thing they are being issued for - a season's productions - and
it is explainable to a committee in one line: "this works for the 26/27 season."
A society that wants ongoing access should come through the magic-link flow,
which is the intended front door.

Nothing here is emailed or published. It prints a distribution list for Darragh
to send himself.

Usage:
    py scripts/backfills/generate_poster_chase_codes.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python \\
        scripts/backfills/generate_poster_chase_codes.py --db /data/aims.db --dry-run
"""
import argparse
import secrets
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

# Same window the chasing list and the dashboard counter use.
POSTER_CHASE_DAYS = 93

CREATED_BY = "poster-chase script"


def _repo_root():
    if __file__ in ("<stdin>", "-"):
        return Path.cwd()
    return Path(__file__).resolve().parents[2]


def _season_end(today):
    """Last day of the AIMS season `today` falls in.

    The season runs mid-June to early May (see app/season.py). Anything from
    mid-May onward belongs to the season starting that year, so it ends in May
    of the following year; anything before belongs to the season that ends this
    May. The 31st is deliberately generous - the point is a boundary a committee
    recognises, not a precise adjudication deadline.
    """
    end_year = today.year + 1 if today.month >= 6 else today.year
    return date(end_year, 5, 31)


def _load_word_lists():
    """The generator lives in the app package, which is importable in the
    container and from the repo root. Imported lazily so --help works anywhere.
    """
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from app.invite_words import ADJECTIVES, NOUNS

    # CODE_DIGITS moved into invite_words.py in the same commit as this script,
    # so a deployed container has both or neither - they cannot arrive apart.
    # The fallback is for the other way of running this: piping the file
    # straight into `docker exec -i ... python -` from a working tree that is
    # ahead of the deploy, which is how it was first run and how it will be run
    # again whenever something needs doing before GitOps has caught up. The
    # value is the one that constant has always had, and the app's own tests
    # pin the code format, so drift would fail loudly rather than silently
    # minting codes in the wrong shape.
    try:
        from app.invite_words import CODE_DIGITS
    except ImportError:
        CODE_DIGITS = 4
    return ADJECTIVES, NOUNS, CODE_DIGITS


def _generate_code(db, adjectives, nouns, digits):
    """Same shape as admin.auth._generate_invite_code - adjective-noun-NNNN,
    checked for collision. Not imported from there because that module pulls in
    Flask request context."""
    while True:
        number = secrets.randbelow(10 ** digits)
        code = f"{secrets.choice(adjectives)}-{secrets.choice(nouns)}-{number:0{digits}d}"
        if not db.execute(
            "SELECT 1 FROM invite_codes WHERE code = ? COLLATE NOCASE", (code,)
        ).fetchone():
            return code


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(_repo_root() / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    parser.add_argument("--days", type=int, default=POSTER_CHASE_DAYS,
                        help=f"chase window in days (default {POSTER_CHASE_DAYS})")
    args = parser.parse_args()

    today = date.today()
    chase_until = (today + timedelta(days=args.days)).isoformat()
    expires_at = _season_end(today).isoformat()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        """
        SELECT societies.id AS society_id, societies.name AS society_name,
               shows.show, shows.opening_date, shows.closing_date
          FROM shows JOIN societies ON societies.id = shows.society_id
         WHERE shows.moderation_status = 'approved'
           AND shows.show IS NOT NULL
           AND shows.poster_filename IS NULL
           AND shows.opening_date IS NOT NULL
           AND shows.opening_date >= :today
           AND shows.opening_date <= :chase_until
           AND NOT EXISTS (
                 SELECT 1 FROM invite_codes
                  WHERE invite_codes.society_id = societies.id
                    AND invite_codes.is_active = 1
                    AND (invite_codes.expires_at IS NULL OR invite_codes.expires_at >= :today))
         ORDER BY shows.opening_date
        """,
        {"today": today.isoformat(), "chase_until": chase_until},
    ).fetchall()

    # One code per society, even where they have two chaseable productions.
    by_society = {}
    for r in rows:
        by_society.setdefault(r["society_id"], []).append(r)

    if not by_society:
        print("Every society with a production in the chase window already has an active code.")
        db.close()
        return

    print(f"Chase window: {today} to {chase_until} ({args.days} days)")
    print(f"Codes will expire: {expires_at} (end of the current AIMS season)")
    print(f"{len(by_society)} societ{'y' if len(by_society) == 1 else 'ies'} need a code, "
          f"covering {len(rows)} production{'' if len(rows) == 1 else 's'}.\n")

    adjectives, nouns, digits = _load_word_lists()
    issued = []
    for society_id, shows in by_society.items():
        code = _generate_code(db, adjectives, nouns, digits)
        db.execute(
            "INSERT INTO invite_codes (code, label, society_id, is_active, expires_at, created_by) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (code, f"Poster chase {today.isoformat()}", society_id, expires_at, CREATED_BY),
        )
        issued.append((shows[0]["society_name"], code, shows))

    print("-" * 78)
    for society_name, code, shows in issued:
        titles = ", ".join(f"{s['show']} ({s['opening_date']})" for s in shows)
        print(f"{society_name}")
        print(f"  code: {code}")
        print(f"  for:  {titles}")
    print("-" * 78)

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back. The codes above were NOT created and are "
              "not reusable - a real run mints different ones.")
    else:
        db.commit()
        print(f"\nWritten. {len(issued)} code(s) created, expiring {expires_at}.")
    db.close()


if __name__ == "__main__":
    main()
