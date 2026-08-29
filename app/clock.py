"""The current UTC time, in the exact shape this app stores it.

`datetime.utcnow()` is deprecated and scheduled for removal from Python; CI
warns on every run (2026-08-29). The obvious replacement is not equivalent:

    datetime.utcnow().isoformat()              -> '2026-08-29T10:22:31.618294'
    datetime.now(timezone.utc).isoformat()     -> '2026-08-29T10:22:31.618294+00:00'

That suffix would change every moderated_at / updated_at value written from
here on, and those strings are parsed strictly on the way back out (see
filters.irish_datetime, which uses an exact strptime format and falls back to
printing the raw string when it does not match). Dropping tzinfo keeps the
stored format byte-identical to everything already in the database, which is
the point: this is a deprecation fix, not a data migration.
"""
from datetime import datetime, timezone


def utcnow():
    """Timezone-aware now, in UTC. Use this for arithmetic or comparison."""
    return datetime.now(timezone.utc)


def utcnow_iso():
    """Now as the naive UTC ISO string this app stores in TEXT columns."""
    return utcnow().replace(tzinfo=None).isoformat()


def utcnow_compact():
    """Now as a compact UTC stamp, e.g. for an iCalendar DTSTAMP."""
    return utcnow().strftime("%Y%m%dT%H%M%SZ")
