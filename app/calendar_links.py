"""Shared "add this to your calendar" link builders - just URLs, no auth and
no API integration with either provider. Used by the public show page (the
show's own dates) and the society's own edit-show page (the adjudication-forms
reminder, logged-in-only - see app/blueprints/society.py).

**These are two of four routes, not the whole answer.** Google and Outlook are
web calendars, so they take a URL that opens a pre-filled "new event" screen.
Apple Calendar has no such URL - and neither does any desktop client - so the
fourth route is the .ics file at `feeds.show_calendar_ics`, which is also what
an iPhone opens natively. A UI that offers only these two silently excludes
every Apple user, which is a large share of an Irish committee."""
from urllib.parse import urlencode

GOOGLE_CALENDAR_RENDER_URL = "https://calendar.google.com/calendar/render"
OUTLOOK_COMPOSE_URL = "https://outlook.live.com/calendar/0/deeplink/compose"


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


def outlook_calendar_url(text, start, end_exclusive, details="", location=""):
    """The same all-day event for Outlook on the web.

    Outlook wants ISO dates rather than Google's compact form, and it treats
    `enddt` as exclusive for an all-day event exactly as Google and RFC 5545
    do - so the same `end_exclusive` the caller already computed is correct
    here, and must not be adjusted."""
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "allday": "true",
        "subject": text,
        "startdt": start.isoformat(),
        "enddt": end_exclusive.isoformat(),
        "body": details,
    }
    if location:
        params["location"] = location
    return f"{OUTLOOK_COMPOSE_URL}?{urlencode(params)}"
