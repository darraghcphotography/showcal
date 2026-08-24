"""Admin counts read the productions table (stage 2 of the migration).

Three places used to answer "does this need a review link?" separately - the
dashboard counter, the shows-list filter it links to, and the Reviews queue -
and disagreed (115, 115, 29 against real data). They share one definition now
(admin.NEEDS_REVIEW_WHERE), so the tests here mostly check that they agree.
"""
import re

from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def _add_show(db, season="24/25", show="Oliver!", **kw):
    cols = dict(
        society_id=kw.pop("society_id", 1), season=season, region=kw.pop("region", "Eastern"),
        show=show, source=kw.pop("source", "import"),
        moderation_status=kw.pop("moderation_status", "approved"),
    )
    cols.update(kw)
    names = ", ".join(cols)
    marks = ", ".join("?" * len(cols))
    return db.execute(f"INSERT INTO shows ({names}) VALUES ({marks})", list(cols.values())).lastrowid


def _counter(client, label="Shows missing a review link"):
    """A named number from the dashboard's "Missing data" table. The label
    sits inside an .admin-row-label span (with an on/off urgency dot) rather
    than directly in the <td> - see dashboard.html, Second Act backlog item 8."""
    body = client.get("/admin/").get_data(as_text=True)
    match = re.search(r"%s\s*</span>\s*</td>\s*<td>(\d+)</td>" % re.escape(label), body)
    assert match, f"no dashboard row labelled {label!r}"
    return int(match.group(1))


def _queue_show_ids(client):
    body = client.get("/admin/reviews-queue").get_data(as_text=True)
    return {int(n) for n in re.findall(r"/admin/reviews-queue/(\d+)/save", body)}


def _list_show_ids(client):
    body = client.get("/admin/shows?needs_review=1&season=all").get_data(as_text=True)
    return {int(n) for n in re.findall(r"/admin/shows/(\d+)/edit", body)}


def _setup(client, db):
    login_as(client, seed_user(db))
    seed_society(db)


def test_a_show_that_has_not_run_yet_does_not_need_a_review(client, db):
    """The old counter was season-based, so the whole current season counted -
    78 of its 115 were shows that hadn't happened."""
    _setup(client, db)
    _add_show(db, season="27/28", show="Wicked", opening_date="2099-01-01", closing_date="2099-01-05")
    db.commit()

    assert _counter(client) == 0
    assert _queue_show_ids(client) == set()
    assert _list_show_ids(client) == set()


def test_a_show_that_has_run_needs_a_review(client, db):
    _setup(client, db)
    show_id = _add_show(db, season="23/24", opening_date="2023-11-01", closing_date="2023-11-05")
    db.commit()

    assert _counter(client) == 1
    assert _queue_show_ids(client) == {show_id}
    assert _list_show_ids(client) == {show_id}


def test_an_undated_show_counts_once_its_season_is_over(client, db):
    """A show with no dates at all can't be date-tested. Its season having
    ended is the only evidence available, and dropping it outright would hide
    real work - there's a real 10/11 production in exactly this state."""
    _setup(client, db)
    _add_show(db, season="26/27", show="Current Season Show", opening_date="2026-11-01")
    old = _add_show(db, season="10/11", show="Old Undated Show")
    current = _add_show(db, season="26/27", show="Undated This Season")
    db.commit()

    assert _list_show_ids(client) == {old}
    assert current not in _list_show_ids(client)


def test_a_production_reviewed_in_the_archive_is_not_nagged_about(client, db):
    """A show whose write-up lives in the ShowTimes archive rather than as an
    aims.ie link doesn't need a link added. The Reviews queue already knew
    this; the dashboard counter and the shows-list filter did not."""
    _setup(client, db)
    show_id = _add_show(db, season="18/19", show="Cabaret",
                        opening_date="2019-03-01", closing_date="2019-03-05")
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, show_id, moderation_status) "
        "VALUES ('18/19', 'Cabaret', 'Test Society', 'A fine show.', ?, 'approved')",
        (show_id,),
    )
    db.commit()

    assert show_id not in _list_show_ids(client)
    assert _counter(client) == 0


def test_a_pending_archive_review_does_not_count_as_reviewed(client, db):
    _setup(client, db)
    show_id = _add_show(db, season="18/19", opening_date="2019-03-01", closing_date="2019-03-05")
    db.execute(
        "INSERT INTO historical_reviews (season, show_raw, society_raw, review_text, show_id, moderation_status) "
        "VALUES ('18/19', 'Oliver!', 'Test Society', 'text', ?, 'pending')",
        (show_id,),
    )
    db.commit()

    assert _list_show_ids(client) == {show_id}


def test_not_adjudicated_is_left_out(client, db):
    _setup(client, db)
    _add_show(db, season="23/24", show="Not Judged", opening_date="2023-11-01",
              closing_date="2023-11-05", review_status="Not adjudicated")
    db.commit()

    assert _counter(client) == 0


def test_a_show_that_already_has_a_link_is_left_out(client, db):
    _setup(client, db)
    _add_show(db, season="23/24", opening_date="2023-11-01", closing_date="2023-11-05",
              review_status="Published", review_url="https://aims.ie/review/1")
    db.commit()

    assert _counter(client) == 0


def test_the_counter_and_the_page_it_links_to_agree(client, db):
    _setup(client, db)
    ids = set()
    for season, opening in [("23/24", "2023-11-01"), ("22/23", "2022-11-01"), ("21/22", "2021-11-01")]:
        ids.add(_add_show(db, season=season, show=f"Show {season}", opening_date=opening,
                          closing_date=opening))
    _add_show(db, season="27/28", show="Not Yet", opening_date="2099-01-01", closing_date="2099-01-05")
    db.commit()

    assert _counter(client) == 3
    assert _list_show_ids(client) == ids
    assert _queue_show_ids(client) == ids


# ---------------------------------------------------------------- duplicates

def test_a_bulk_added_row_duplicating_a_skeleton_show_is_flagged(client, db):
    """The old check compared the show's opening *calendar year* to the award
    year - never true for a skeleton show, which has no dates at all. Nine
    real duplicates sat unflagged behind that."""
    _setup(client, db)
    _add_show(db, season="16/17", show="Oliver!", source="historical")
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, society_id, source) "
        "VALUES (2017, 'Oliver!', 'Test Society', 1, 'manual')"
    )
    db.commit()

    body = client.get("/admin/data-quality").get_data(as_text=True)
    assert body.count("/delete") == 1
    assert "Oliver!" in body


def test_an_autumn_show_duplicating_a_bulk_added_row_is_flagged(client, db):
    """Same blind spot from the other direction: a show opening in the autumn
    of season N/N+1 has opening year N, but its award year is N+1."""
    _setup(client, db)
    _add_show(db, season="16/17", show="Oliver!", opening_date="2016-11-01", closing_date="2016-11-05")
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, society_id, source) "
        "VALUES (2017, 'Oliver!', 'Test Society', 1, 'manual')"
    )
    db.commit()

    assert client.get("/admin/data-quality").get_data(as_text=True).count("/delete") == 1


def test_a_real_award_record_is_never_flagged_as_a_duplicate(client, db):
    """Only bare rows (no category, no result) are duplicates of a staging -
    an actual award record says something the shows row doesn't."""
    _setup(client, db)
    _add_show(db, season="16/17", show="Oliver!", opening_date="2016-11-01", closing_date="2016-11-05")
    db.execute(
        "INSERT INTO historical_results (year, category_name, result, show, society_name, society_id, source) "
        "VALUES (2017, 'Best Overall Show', 'Winner', 'Oliver!', 'Test Society', 1, 'manual')"
    )
    db.commit()

    assert client.get("/admin/data-quality").get_data(as_text=True).count("/delete") == 0


def test_a_different_season_is_not_a_duplicate(client, db):
    _setup(client, db)
    _add_show(db, season="16/17", show="Oliver!", opening_date="2016-11-01", closing_date="2016-11-05")
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, society_id, source) "
        "VALUES (2019, 'Oliver!', 'Test Society', 1, 'manual')"
    )
    db.commit()

    assert client.get("/admin/data-quality").get_data(as_text=True).count("/delete") == 0
