from datetime import datetime


def irish_date(value):
    """Format an ISO yyyy-mm-dd string as dd-mm-yyyy for display.

    Leaves anything that isn't a clean ISO date untouched (blank, None, or
    already-human text like an adjudication month name) rather than raising -
    this filter only ever runs on data meant for reading, never on values fed
    back into an <input type="date">.
    """
    if not value:
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return value


def date_range(opening, closing):
    """Compact human range for two ISO yyyy-mm-dd dates, e.g. "2-5 Sep 2026"
    or "30 Sep - 3 Oct 2026" - drops the repeated month/year when both ends
    share them, since spelling out "Sep 2026" twice for a 3-day run wastes
    width without adding information. Falls back gracefully for partial/odd
    input rather than raising, same spirit as irish_date above."""
    if not opening:
        return ""
    try:
        start = datetime.strptime(opening, "%Y-%m-%d")
    except ValueError:
        return opening

    if not closing:
        return f"From {start.day} {start.strftime('%b %Y')}"
    try:
        end = datetime.strptime(closing, "%Y-%m-%d")
    except ValueError:
        return f"{start.day} {start.strftime('%b %Y')}"

    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {start.strftime('%b %Y')}"
    if start.year == end.year:
        return f"{start.day} {start.strftime('%b')} – {end.day} {end.strftime('%b %Y')}"
    return f"{start.day} {start.strftime('%b %Y')} – {end.day} {end.strftime('%b %Y')}"


def register(app):
    app.jinja_env.filters["irish_date"] = irish_date
    app.jinja_env.filters["date_range"] = date_range
