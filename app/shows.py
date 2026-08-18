from datetime import date


def is_upcoming(show):
    """Whether a show row hasn't happened yet - same definition used for the
    public "upcoming" nudges (ticket/poster, calendar link) and a society's
    own adjudication-forms reminder, previously computed separately in each
    place with slightly different phrasing."""
    return (
        show["status"] != "Cancelled"
        and show["opening_date"] is not None
        and show["opening_date"] >= date.today().isoformat()
    )
