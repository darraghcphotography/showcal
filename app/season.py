from datetime import date


def next_season(season):
    start, end = (int(part) for part in season.split("/"))
    return f"{(start + 1) % 100:02d}/{(end + 1) % 100:02d}"


def historical_results_year(season):
    """historical_results.year is the AIMS awards CSV's own "Year" column,
    not derived from season anywhere else in this codebase - confirmed
    empirically (323 exact (society, year, show) hits against a full pass
    over the historical-review queue using this convention, 0 hits using
    the other plausible one) that it's the *second* calendar year of the
    season string ('10/11' -> 2011, matching when that season's awards
    ceremony/the ShowTimes issue reporting on it actually happened), not
    the first."""
    return 2000 + int(season[:2]) + 1


def season_start_year(season):
    """Real four-digit start year for a 'yy/yy' season string, so seasons can
    be compared across the 1999/2000 rollover. Plain string comparison is
    unsafe once the archive reaches back past 2000 - '76/77' sorts *after*
    '09/10' as text despite being 33 years earlier, which is exactly the bug
    that silently duplicated every season in the adjudicator grid (Round 25).
    The pivot suits this dataset's real range (the awards archive starts 1977,
    shows run to 2027) and stays correct until 2050."""
    yy = int(season[:2])
    return (1900 + yy) if yy >= 50 else (2000 + yy)


def season_has_ended(db, season):
    """True if this season finished before the one currently being produced -
    i.e. anything still blank about it is missing from the record, not yet to
    be announced. Drives 'Not on record' vs 'TBA' wording."""
    if not season:
        return False
    try:
        return season_start_year(season) < season_start_year(current_season(db))
    except (ValueError, IndexError):
        return False


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
