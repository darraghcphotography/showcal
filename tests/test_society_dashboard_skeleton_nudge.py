"""A skeleton show (source='historical', created just to host a ShowTimes
review with no real details) is already editable through the normal
dashboard/edit-show flow - no restriction on source anywhere in
app/blueprints/society.py. The only real gap was discoverability: nothing
told a society that entry was theirs to fill in. This is that nudge."""
from conftest import seed_invite_code, seed_society


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def test_skeleton_show_with_no_venue_gets_the_nudge(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, '15/16', 'Eastern', 'Seussical', 'historical', 'approved')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    body = client.get("/society/").get_data(as_text=True)
    assert "Has a review - add details" in body
    assert ">Add details<" in body


def test_skeleton_show_nudge_disappears_once_venue_is_filled_in(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC002", society_id=society_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status, venue) "
        "VALUES (?, '15/16', 'Eastern', 'Seussical', 'historical', 'approved', 'The Helix')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    body = client.get("/society/").get_data(as_text=True)
    assert "Has a review - add details" not in body
    assert ">Edit<" in body


def test_normal_submitted_show_never_gets_the_nudge(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC003", society_id=society_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, source, moderation_status) "
        "VALUES (?, '25/26', 'Eastern', 'Oliver!', 'submission', 'approved')",
        (society_id,),
    )
    db.commit()
    unlock_society(client, code_id)

    body = client.get("/society/").get_data(as_text=True)
    assert "Has a review - add details" not in body
