"""/export/shows.csv's id, society_id and poster_url columns - what the aims.ie
review publisher keys on to take region and poster from ShowCal (2026-11-19)."""
import csv
import io

from conftest import seed_society


def _rows(client):
    body = client.get("/export/shows.csv").get_data(as_text=True)
    return list(csv.DictReader(io.StringIO(body)))


def _insert(db, society_id, show, poster=None, status="approved"):
    cur = db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, poster_filename, moderation_status) "
        "VALUES (?, '26/27', 'Northern', 'Sullivan', ?, ?, ?)",
        (society_id, show, poster, status),
    )
    db.commit()
    return cur.lastrowid


def test_export_carries_ids_and_absolute_poster_url(client, db, monkeypatch):
    monkeypatch.setattr("app.notify.SITE_URL", "https://darraghc.ie/showcal")
    society_id = seed_society(db)
    with_poster = _insert(db, society_id, "Gypsy", poster="gypsy.jpg")
    without = _insert(db, society_id, "Little Shop of Horrors")

    rows = {r["show"]: r for r in _rows(client)}
    assert rows["Gypsy"]["id"] == str(with_poster)
    assert rows["Gypsy"]["society_id"] == str(society_id)
    assert rows["Gypsy"]["region"] == "Northern"
    assert rows["Gypsy"]["poster_url"] == "https://darraghc.ie/showcal/uploads/gypsy.jpg"
    assert rows["Little Shop of Horrors"]["id"] == str(without)
    assert rows["Little Shop of Horrors"]["poster_url"] == ""


def test_new_columns_are_appended_after_the_old_ones(client):
    header = client.get("/export/shows.csv").get_data(as_text=True).splitlines()[0]
    assert header.startswith("season,region,section,society,show,")
    assert header.endswith(",ticket_url,id,society_id,poster_url")


def test_pending_submissions_still_never_exported(client, db):
    society_id = seed_society(db)
    _insert(db, society_id, "Secret Show", status="pending")
    assert all(r["show"] != "Secret Show" for r in _rows(client))
