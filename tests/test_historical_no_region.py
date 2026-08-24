""""No region" is a settled answer, not a skip. AIMS itself is a national body
rather than a society, and a few defunct touring names give no location clue
anywhere - leaving them in the queue asks a question with no answer.

Deliberately a separate no_region flag rather than a sentinel in
confirmed_region: that column feeds /stats' region breakdown and
productions.region (see schema.sql), so an "Unknown" written there would
surface publicly as though it were a region.
"""
from conftest import seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add(db, name, suggested=None):
    db.execute(
        "INSERT INTO historical_society_regions (society_name, suggested_region, note) VALUES (?, ?, ?)",
        (name, suggested, "test"),
    )
    db.commit()


def test_marking_no_region_clears_it_from_the_queue(client, db):
    login_as(client, seed_user(db))
    _add(db, "AIMS")

    assert "AIMS" in client.get("/admin/historical-societies").get_data(as_text=True)

    client.post("/admin/historical-societies/bulk",
                data={"name_0": "AIMS", "region_0": "__none__"})

    body = client.get("/admin/historical-societies").get_data(as_text=True)
    assert "No unconfirmed historical societies left to review." in body


def test_no_region_leaves_confirmed_region_null(client, db):
    """The whole point of the separate flag - nothing downstream should start
    treating this name as having a region."""
    login_as(client, seed_user(db))
    _add(db, "Take Four")

    client.post("/admin/historical-societies/bulk",
                data={"name_0": "Take Four", "region_0": "__none__"})

    row = db.execute(
        "SELECT confirmed_region, no_region FROM historical_society_regions WHERE society_name = 'Take Four'"
    ).fetchone()
    assert row["confirmed_region"] is None
    assert row["no_region"] == 1


def test_dashboard_counter_agrees_with_the_page(client, db):
    """Same shape of bug as the review-link and missing-dates counters: the
    counter and the page it links to must exclude the same rows."""
    login_as(client, seed_user(db))
    _add(db, "AIMS")
    _add(db, "Genuinely Unknown Society")

    client.post("/admin/historical-societies/bulk",
                data={"name_0": "AIMS", "region_0": "__none__"})

    dashboard = client.get("/admin/").get_data(as_text=True)
    # The label can also appear in the "quick win" banner above the table
    # (if this happens to be the smallest nonzero count on the page), so
    # scope to the "Missing data" table first. The label itself sits inside
    # an .admin-row-label span (with an on/off urgency dot) rather than
    # directly in the <td> - see dashboard.html, Second Act backlog item 8.
    missing_data_table = dashboard.split("Missing data</h2>")[1]
    row = missing_data_table.split(
        "Historical societies with a region awaiting confirmation"
    )[1].split("</tr>")[0]
    assert "<td>1</td>" in row

    page = client.get("/admin/historical-societies").get_data(as_text=True)
    assert "Genuinely Unknown Society" in page
    # Match the row cell, not the bare word - "AIMS" appears in the site's own
    # meta description on every page.
    assert "<td>AIMS</td>" not in page


def test_a_real_region_still_confirms_normally(client, db):
    login_as(client, seed_user(db))
    _add(db, "Bangor Operatic Society", suggested="Northern")

    client.post("/admin/historical-societies/bulk",
                data={"name_0": "Bangor Operatic Society", "region_0": "Northern"})

    row = db.execute(
        "SELECT confirmed_region, no_region FROM historical_society_regions "
        "WHERE society_name = 'Bangor Operatic Society'"
    ).fetchone()
    assert row["confirmed_region"] == "Northern"
    assert row["no_region"] == 0
