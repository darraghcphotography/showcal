"""Shared "Add to Google Calendar" link builder - just a URL, no Google
auth/API integration. Used by the public show page (the show's own dates)
and the society's own edit-show page (the adjudication-forms reminder,
logged-in-only - see app/blueprints/society.py)."""
from urllib.parse import urlencode

GOOGLE_CALENDAR_RENDER_URL = "https://calendar.google.com/calendar/render"


def google_calendar_url(text, start, end_exclusive, details="", location=""):
    """All-day event link. `end_exclusive` is the day *after* the event ends
    (Google's own convention, same as the .ics feed's DTEND)."""
    params = {
        "action": "TEMPLATE",
        "text": text,
        "dates": f"{start.strftime('%Y%m%d')}/{end_exclusive.strftime('%Y%m%d')}",
        "details": details,
    }
    if location:
        params["location"] = location
    return f"{GOOGLE_CALENDAR_RENDER_URL}?{urlencode(params)}"
