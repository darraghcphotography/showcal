from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
DUBLIN = ZoneInfo("Europe/Dublin")


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


def irish_datetime(value):
    """Format a full 'YYYY-MM-DD HH:MM:SS' UTC timestamp (e.g. a SQLite
    datetime('now') column, or __init__.py's deployed_at - both explicitly
    UTC) as 'd Mon YYYY, HH:MM' Irish local time. Actually converts via
    zoneinfo rather than just reformatting the string as-is - Europe/Dublin
    alternates between GMT and BST, so a fixed offset would be wrong half
    the year, and the previous version applied no offset at all (silently
    displayed raw UTC as if it were already Irish time - off by exactly the
    BST offset every summer). Same lenient-fallback spirit as irish_date
    above, since this runs on data meant for reading, not fed back into a form."""
    if not value:
        return value
    try:
        dt_utc = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        return dt_utc.astimezone(DUBLIN).strftime("%d %b %Y, %H:%M")
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


def destub(value):
    """Six historical_results rows (a legacy import predating the CSV
    pipeline, not the tracked awards CSV or today's admin form) stored the
    literal string 'None' - or for one row, 'NULL' - instead of a real
    blank, in reason/role/nominee_name. A plain `{% if %}`/`or '&mdash;'`
    check treats those as present, since they're non-empty strings, so the
    public /awards page rendered an italic "None" note and "(None)" next to
    a nominee. Normalizes both sentinels to a real blank so the existing
    checks already do the right thing - defends against a future import
    reintroducing the same sentinel, not just today's 6 known rows."""
    if value in ("None", "NULL"):
        return None
    return value


def maps_search_url(venue):
    """Google's free "Maps URL" text-search scheme - no API key or billing
    account needed (unlike the Maps Embed/Static/Geocoding APIs), and works
    fine on a bare town name as well as a full venue address."""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(venue)}"


def register(app):
    app.jinja_env.filters["irish_date"] = irish_date
    app.jinja_env.filters["irish_datetime"] = irish_datetime
    app.jinja_env.filters["date_range"] = date_range
    app.jinja_env.filters["maps_search_url"] = maps_search_url
    app.jinja_env.filters["destub"] = destub
