from datetime import date, timedelta


CONGESTION_THRESHOLD = 4


def season_weeks(rows):
    """Group a season's shows by the ISO week of their opening date, flagging
    a week "congested" per section - Gilbert and Sullivan judged separately,
    each at 4+ non-cancelled shows actually *running* (not just opening) at
    any point in it, a still-running show from the week before counts too.
    Per-section, not combined: an adjudicator only needs to reach every show
    in their own section, so 2 Gilbert + 2 Sullivan in the same week isn't a
    real clash for either of them, even though it's 4 shows total."""
    parsed = []
    for row in rows:
        if not row["opening_date"]:
            continue
        opening = date.fromisoformat(row["opening_date"])
        closing = date.fromisoformat(row["closing_date"]) if row["closing_date"] else opening
        parsed.append((row, opening, closing))

    buckets = {}
    for row, opening, closing in parsed:
        buckets.setdefault(opening.isocalendar()[:2], []).append(row)

    def section_overlap(section, start, end):
        return sum(
            1 for r, o, c in parsed
            if r["status"] != "Cancelled" and r["section"] == section and o <= end and c >= start
        )

    weeks = []
    for iso_year, iso_week in sorted(buckets):
        start = date.fromisocalendar(iso_year, iso_week, 1)
        end = start + timedelta(days=6)
        shows = buckets[(iso_year, iso_week)]

        gilbert_shows = [r for r in shows if r["section"] == "Gilbert"]
        sullivan_shows = [r for r in shows if r["section"] == "Sullivan"]
        other_shows = [r for r in shows if r["section"] not in ("Gilbert", "Sullivan")]

        gilbert_open = sum(1 for r in gilbert_shows if r["status"] != "Cancelled")
        sullivan_open = sum(1 for r in sullivan_shows if r["status"] != "Cancelled")
        gilbert_overlap = section_overlap("Gilbert", start, end)
        sullivan_overlap = section_overlap("Sullivan", start, end)
        gilbert_congested = gilbert_overlap >= CONGESTION_THRESHOLD
        sullivan_congested = sullivan_overlap >= CONGESTION_THRESHOLD

        congestion_notes = []
        if gilbert_congested:
            congestion_notes.append({
                "label": "Gilbert", "overlap": gilbert_overlap, "carryover": gilbert_overlap - gilbert_open,
            })
        if sullivan_congested:
            congestion_notes.append({
                "label": "Sullivan", "overlap": sullivan_overlap, "carryover": sullivan_overlap - sullivan_open,
            })

        other_open = sum(1 for r in other_shows if r["status"] != "Cancelled")

        weeks.append({
            "start": start,
            "end": end,
            "gilbert": gilbert_shows,
            "sullivan": sullivan_shows,
            "other": other_shows,
            "open_count": gilbert_open + sullivan_open + other_open,
            "gilbert_open": gilbert_open,
            "sullivan_open": sullivan_open,
            "gilbert_overlap": gilbert_overlap,
            "sullivan_overlap": sullivan_overlap,
            "gilbert_congested": gilbert_congested,
            "sullivan_congested": sullivan_congested,
            "congested": gilbert_congested or sullivan_congested,
            "congestion_notes": congestion_notes,
            "month_key": start.strftime("%Y-%m"),
            "month_label": start.strftime("%B %Y"),
        })
    return weeks


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


def historical_results_season(year):
    """Inverse of historical_results_year - the 'yy/yy' season string a given
    historical_results.year belongs to."""
    return f"{(year - 1) % 100:02d}/{year % 100:02d}"


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
