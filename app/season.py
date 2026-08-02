from datetime import date


def next_season(season):
    start, end = (int(part) for part in season.split("/"))
    return f"{(start + 1) % 100:02d}/{(end + 1) % 100:02d}"


def current_season(db):
    """The season presently being produced: the most recent season with a
    real (non-placeholder) show already on record. Falls back to a guess
    from today's date only if the table is ever completely empty."""
    row = db.execute(
        "SELECT season FROM shows WHERE show IS NOT NULL AND opening_date IS NOT NULL "
        "ORDER BY season DESC LIMIT 1"
    ).fetchone()
    if row:
        return row["season"]
    yy = date.today().year % 100
    return f"{yy:02d}/{(yy + 1) % 100:02d}"


def season_range(db):
    """Every season from the earliest year in the awards archive through
    next season, most recent first - for a full historical-entry dropdown
    (a society login adding decades of back catalogue), unlike the tight
    current/next-season-only list the public one-off submission form uses.
    """
    earliest_year = db.execute("SELECT MIN(year) FROM historical_results").fetchone()[0]
    current = current_season(db)
    last_season = next_season(current)
    start_year = (earliest_year - 1) if earliest_year else int(current[:2]) + 2000

    seasons = []
    year = start_year
    while True:
        season = f"{year % 100:02d}/{(year + 1) % 100:02d}"
        seasons.append(season)
        if season == last_season:
            break
        year += 1
    return list(reversed(seasons))
