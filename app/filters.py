import re
from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
DUBLIN = ZoneInfo("Europe/Dublin")

SHOW_INITIALS_STOPWORDS = {"the", "a", "an", "of", "and", "or", "in", "at", "on", "for", "to"}


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


def month_label(value):
    """'2026-09' -> 'September 2026', for the homepage's month headings.

    Same lenient fallback as irish_date: anything that isn't a clean yyyy-mm
    comes back untouched rather than raising, because this only ever runs on
    values already on their way to the page.
    """
    if not value:
        return value
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return value


def show_initials(value):
    """1-2 letter monogram for the homepage's poster-placeholder box (a show
    with no poster upload yet - see .whatson-poster.is-placeholder). Initials
    of the title's significant words, skipping small connecting words
    ("The Hired Man" -> "HM", not "TH") so the letters carry the title's real
    identity. A single-word title falls back to its own first two letters
    ("Oklahoma!" -> "OK") so the box always reads as two characters rather
    than one lonely one."""
    words = [w for w in re.findall(r"[A-Za-z0-9]+", value or "") if w.lower() not in SHOW_INITIALS_STOPWORDS]
    if not words:
        words = re.findall(r"[A-Za-z0-9]+", value or "")
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def maps_search_url(venue):
    """Google's free "Maps URL" text-search scheme - no API key or billing
    account needed (unlike the Maps Embed/Static/Geocoding APIs), and works
    fine on a bare town name as well as a full venue address."""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(venue)}"


def maps_directions_url(destination):
    """Directions to a place, same keyless Maps URL family as maps_search_url.

    On a phone this hands off to the native Maps app and offers turn-by-turn
    navigation, which a static map link can't - the one thing somebody looking
    up a venue on the way to a show actually wants.

    Takes text ("Moat Theatre, Naas") rather than coordinates on purpose: it
    then works for every venue, not just the ones with a pin on record, and
    Google shows a named destination instead of a bare lat/long.
    """
    return f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(destination)}"


def register(app):
    app.jinja_env.filters["irish_date"] = irish_date
    app.jinja_env.filters["irish_datetime"] = irish_datetime
    app.jinja_env.filters["date_range"] = date_range
    app.jinja_env.filters["month_label"] = month_label
    app.jinja_env.filters["show_initials"] = show_initials
    app.jinja_env.filters["maps_search_url"] = maps_search_url
    app.jinja_env.filters["maps_directions_url"] = maps_directions_url
    app.jinja_env.filters["destub"] = destub
