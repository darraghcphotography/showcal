from datetime import date


# Two different questions, and mixing them up is how a show running tonight
# vanished from the homepage (2026-09-11: Thurles Musical Society's Come From
# Away opened on the 10th, closed on the 12th, and was gone by the 11th).
#
#   is_upcoming - has it NOT OPENED yet? Lead-time questions: the adjudication
#                 forms reminder (6 weeks before opening), chasing a poster.
#   is_still_on - can someone STILL GO AND SEE IT? Anything offering the show
#                 to a visitor: the homepage, a ticket link, "on stage now".
#
# A show mid-run is the case that tells them apart: not upcoming, still on.


def is_upcoming(show):
    """Whether a show has not opened yet.

    For lead-time questions only - the adjudication forms reminder and poster
    chasing, both of which are about the weeks *before* opening night. Do not
    use this to decide whether to show a production to a visitor: it drops a
    show the morning after its first night. That is is_still_on."""
    return (
        show["opening_date"] is not None
        and show["opening_date"] >= date.today().isoformat()
    )


def is_still_on(show):
    """Whether someone can still go and see this show - it has not closed.

    Falls back to the opening date when no closing date is on record, so a
    one-night show is still on for the day it runs and gone the day after.
    Same rule as the Season page's `is_past` and the venue "next show" badge,
    which already had it right."""
    last_night = show["closing_date"] or show["opening_date"]
    return last_night is not None and last_night >= date.today().isoformat()


def still_on_sql(alias="shows"):
    """The is_still_on rule as a SQL condition, taking today's date as one `?`.

    One definition for queries too, so the WHERE clause and the Python check
    cannot drift apart - which is what produced the original bug."""
    return f"COALESCE({alias}.closing_date, {alias}.opening_date) >= ?"
