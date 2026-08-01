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
