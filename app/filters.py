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


def register(app):
    app.jinja_env.filters["irish_date"] = irish_date
