from datetime import date, timedelta


CONGESTION_THRESHOLD = 4


def season_weeks(rows):
    """Group a season's shows by the ISO week of their opening date, flagging
    a week "congested" per section - Gilbert and Sullivan judged separately,
    each at 4+ shows actually *running* (not just opening) at any point in
    it, a still-running show from the week before counts too. Per-section,
    not combined: an adjudicator only needs to reach every show in their own
    section, so 2 Gilbert + 2 Sullivan in the same week isn't a real clash
    for either of them, even though it's 4 shows total."""
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
            if r["section"] == section and o <= end and c >= start
        )

    weeks = []
    for iso_year, iso_week in sorted(buckets):
        start = date.fromisocalendar(iso_year, iso_week, 1)
        end = start + timedelta(days=6)
        shows = buckets[(iso_year, iso_week)]

        gilbert_shows = [r for r in shows if r["section"] == "Gilbert"]
        sullivan_shows = [r for r in shows if r["section"] == "Sullivan"]
        other_shows = [r for r in shows if r["section"] not in ("Gilbert", "Sullivan")]

        gilbert_open = len(gilbert_shows)
        sullivan_open = len(sullivan_shows)
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

        other_open = len(other_shows)

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
    the first.

    ONLY safe for a season string that came from the shows table (05/06
    onward). It hard-codes the 2000s and cannot express an award year before
    2001 - '99/00' comes back as 2100, and the awards archive really does
    reach back to 1912. Anything spanning the full archive must use
    award_year_to_season_start / season_start_to_award_year below and carry a
    four-digit year, never a 'yy/yy' string. See the productions table in
    schema.sql for why this distinction has teeth: routing pre-2001 award
    years through here is what hid 823 real productions from /stats."""
    return 2000 + int(season[:2]) + 1


def historical_results_season(year):
    """Inverse of historical_results_year - the 'yy/yy' season string a given
    historical_results.year belongs to. Lossy for the same reason: 1912 and
    2012 both come back as '11/12'. Display only."""
    return f"{(year - 1) % 100:02d}/{year % 100:02d}"


def award_year_to_season_start(year):
    """historical_results.year -> the real four-digit year that season opened
    (2024 -> 2023, 1912 -> 1911). Exact and unambiguous in both directions,
    unlike anything that round-trips through a two-digit season string."""
    return year - 1


def season_start_to_award_year(start_year):
    """Inverse of award_year_to_season_start."""
    return start_year + 1


def season_label(start_year):
    """Display 'yy/yy' for a real four-digit season start year (2023 ->
    '23/24', 1911 -> '11/12'). One-way on purpose: two seasons a century
    apart share a label, so a label is never an identity - see the
    productions table."""
    return f"{start_year % 100:02d}/{(start_year + 1) % 100:02d}"


def season_start_year(season):
    """Real four-digit start year for a 'yy/yy' season string, so seasons can
    be compared across the 1999/2000 rollover. Plain string comparison is
    unsafe once the archive reaches back past 2000 - '76/77' sorts *after*
    '09/10' as text despite being 33 years earlier, which is exactly the bug
    that silently duplicated every season in the adjudicator grid (Round 25).

    The pivot at 50 fits the shows table's real range (05/06 to 27/28) and
    stays correct until 2050, but it is NOT a general decoder for the awards
    archive: that starts in 1912, so '11/12' is genuinely ambiguous and this
    resolves it to 2011. Use it on a shows.season value; for anything derived
    from historical_results.year, carry the four-digit year instead."""
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
