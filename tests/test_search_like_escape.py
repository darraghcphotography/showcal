"""C1 (small-items queue): the LIKE-escape line was copied verbatim in 9
places (public.py x4, info.py, admin/shows.py, admin/misc.py,
admin/societies.py, admin/awards.py). Extracted into app/search.py's
escape_like() - this pins its behaviour and that a LIKE-based fallback
search (used when the FTS index can't be) still finds a name containing a
literal %/_ /\\ once escaped."""
from app.search import escape_like
from conftest import seed_society


def test_escape_like_escapes_percent_underscore_and_backslash():
    assert escape_like("100%_done\\") == "100\\%\\_done\\\\"


def test_admin_societies_search_finds_a_name_with_a_percent_sign(client, db):
    from conftest import seed_user
    admin_id = seed_user(db)
    seed_society(db, id=1, name="100% Musical Society")
    seed_society(db, id=2, name="Unrelated Society")
    db.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
    body = client.get("/admin/societies?q=100%25").get_data(as_text=True)
    assert "100% Musical Society" in body
    assert "Unrelated Society" not in body
