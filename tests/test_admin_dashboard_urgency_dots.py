"""Second Act backlog item 8: the admin dashboard's on/off urgency dot
(.admin-dot-on/.admin-dot-off) used to appear on only 2 of ~12 rows -
extended to every row except the ones that structurally can't reach zero
(currently just "Award records with no society match" - mostly genuinely
defunct societies), which are split into their own dot-less "Won't reach
zero" group instead of living inside "Possible errors to check" (a
permanent amber dot there would be a standing false alarm)."""
from conftest import seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_every_missing_data_and_errors_row_has_a_dot(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)

    body = client.get("/admin/").get_data(as_text=True)
    missing_data_and_errors = body.split("Missing data</h2>")[1].split("Won't reach zero</h2>")[0]

    for label in [
        "Shows missing a review link",
        "Active societies missing a default venue",
        "Shows missing a date",
        "Historical societies with a region awaiting confirmation",
        "Possible duplicate titles",
        "Duplicate historical productions",
        "Orphaned title data",
        "Skeleton shows whose title doesn't line up with the awards archive",
    ]:
        row = missing_data_and_errors.split(label)[1].split("</tr>")[0]
        section_before_label = missing_data_and_errors.split(label)[0]
        # A dot for this row is the one immediately preceding the label text.
        assert "admin-dot" in section_before_label.rsplit("<tr>", 1)[-1], f"{label!r} has no dot"


def test_unmatched_award_societies_split_into_its_own_group(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db, name="Test Society")
    login_as(client, admin_id)

    # A row with society_name set but no society_id match.
    db.execute(
        "INSERT INTO historical_results (year, show, society_name, society_id, source) "
        "VALUES (1994, 'Chess', 'Defunct Society', NULL, 'manual')"
    )
    db.commit()

    body = client.get("/admin/").get_data(as_text=True)
    assert '<h2 class="admin-group-label">Won\'t reach zero</h2>' in body

    wont_reach_zero = body.split("Won't reach zero</h2>")[1]
    assert "Award records with no society match" in wont_reach_zero
    # Deliberately no urgency dot on this group - see module docstring.
    row = wont_reach_zero.split("Award records with no society match")[0]
    assert "admin-dot" not in row.rsplit("<tr>", 1)[-1]

    # And it's gone from "Possible errors to check", not duplicated there.
    possible_errors = body.split("Possible errors to check</h2>")[1].split("Won't reach zero</h2>")[0]
    assert "Award records with no society match" not in possible_errors


def test_dot_toggles_on_and_off_with_the_count(client, db):
    admin_id = seed_user(db)
    society_id = seed_society(db)
    login_as(client, admin_id)

    body = client.get("/admin/").get_data(as_text=True)
    missing_data = body.split("Missing data</h2>")[1].split("Possible errors")[0]
    row = missing_data.split("Shows missing a date")[0]
    assert "admin-dot-off" in row.rsplit("<tr>", 1)[-1]

    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'import', 'approved')",
        (society_id,),
    )
    db.commit()

    body2 = client.get("/admin/").get_data(as_text=True)
    missing_data2 = body2.split("Missing data</h2>")[1].split("Possible errors")[0]
    row2 = missing_data2.split("Shows missing a date")[0]
    assert "admin-dot-on" in row2.rsplit("<tr>", 1)[-1]
