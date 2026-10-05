"""Headline figures that more than one public page quotes.

Each of these used to be worked out (or typed in) separately on every page that
mentioned it, and they drifted: the More page said 194 societies, /stats said
196, /societies found 143, and the awards archive was said to start in 1977,
1910 or 1912 depending on where you read it (site audit, 2026-10-05). A visitor
comparing two pages took that as the data being unreliable. One function per
figure, read live from the database, means a page can't quote a number another
page contradicts.

Two society totals are kept on purpose, because they answer different
questions:

  * every society on record - what /stats and /about count, including
    Inactive and hidden ones, which stay in the historical record (see the
    `hidden` column in schema.sql);
  * societies a visitor can find - /societies' default anonymous view, i.e.
    not Inactive and not hidden. This is the number to quote next to a link
    to /societies, so a click-through finds exactly that many.
"""
from .season import season_for_date, season_start_year


def society_total(db):
    """Every society on record, Inactive and hidden included."""
    return db.execute("SELECT COUNT(*) FROM societies").fetchone()[0]


def listed_society_count(db):
    """Societies /societies lists to a visitor by default."""
    return db.execute(
        "SELECT COUNT(*) FROM societies WHERE section != 'Inactive' AND NOT hidden"
    ).fetchone()[0]


def first_award_year(db):
    """Earliest year in the AIMS awards archive, or None if it is empty."""
    return db.execute("SELECT MIN(year) FROM historical_results").fetchone()[0]


def first_dated_season(db):
    """The season the show-by-show catalogue first has real dates for, e.g.
    '05/06'. Earlier seasons exist only as season lists and the awards
    archive, without dates, venues or production teams."""
    first = db.execute(
        "SELECT MIN(opening_date) FROM shows "
        "WHERE opening_date IS NOT NULL AND moderation_status = 'approved'"
    ).fetchone()[0]
    return season_for_date(first) if first else None


def first_venue_season(db):
    """The earliest season any show is linked to a venue on record."""
    seasons = [
        row[0]
        for row in db.execute(
            "SELECT DISTINCT season FROM shows "
            "WHERE venue_id IS NOT NULL AND season LIKE '__/__' "
            "AND moderation_status = 'approved'"
        )
        if row[0][:2].isdigit()
    ]
    return min(seasons, key=season_start_year) if seasons else None
