"""Reported 2026-08-29: adding a poster from a show's own page (Home -> show ->
"Edit this show" -> save) landed on /admin/shows, a different page listing
different shows, with the one just edited nowhere in sight. An edit form now
carries the page it was opened from and returns there (app/redirects.py).
"""
from conftest import seed_invite_code, seed_society, seed_user

from app.redirects import safe_return_path


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def seed_show(db, **kw):
    fields = {
        "society_id": 1, "season": "25/26", "show": "Test Show", "region": "Eastern",
        "section": "Gilbert", "moderation_status": "approved", "source": "import",
    }
    fields.update(kw)
    cols = ", ".join(fields)
    db.execute(
        f"INSERT INTO shows ({cols}) VALUES ({', '.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    db.commit()
    return db.execute("SELECT id FROM shows ORDER BY id DESC LIMIT 1").fetchone()["id"]


def _form_fields(show_id, **kw):
    fields = {
        "season": "25/26", "region": "Eastern", "section": "Gilbert",
        "show": "Test Show", "review_status": "None",
    }
    fields.update(kw)
    return fields


def test_the_edit_form_carries_the_page_it_was_opened_from(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    body = client.get(
        f"/admin/shows/{show_id}/edit",
        headers={"Referer": f"http://localhost/shows/{show_id}"},
    ).get_data(as_text=True)

    assert f'name="next" value="/shows/{show_id}"' in body


def test_saving_returns_to_that_page_rather_than_the_admin_list(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    resp = client.post(
        f"/admin/shows/{show_id}/edit",
        data=_form_fields(show_id, next=f"/shows/{show_id}"),
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/shows/{show_id}"


def test_saving_without_a_next_still_falls_back_to_the_admin_list(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    resp = client.post(f"/admin/shows/{show_id}/edit", data=_form_fields(show_id))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/shows")


def test_an_offsite_next_is_ignored(client, db):
    """A crafted ?next= must never turn a moderator's save into an off-site
    redirect - the fallback is used instead."""
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    for hostile in ("https://evil.example/steal", "//evil.example/steal", "javascript:alert(1)"):
        resp = client.post(
            f"/admin/shows/{show_id}/edit", data=_form_fields(show_id, next=hostile)
        )
        assert resp.headers["Location"].endswith("/admin/shows"), hostile


def test_a_referer_from_another_site_does_not_set_next(client, db):
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    body = client.get(
        f"/admin/shows/{show_id}/edit",
        headers={"Referer": "https://evil.example/bait"},
    ).get_data(as_text=True)

    assert 'name="next"' not in body


def test_the_form_never_points_back_at_itself(client, db):
    """Re-rendering after a validation error sets the Referer to the edit page
    itself; saving must not then bounce straight back to the form."""
    admin_id = seed_user(db)
    seed_society(db)
    show_id = seed_show(db)
    login_as(client, admin_id)

    body = client.get(
        f"/admin/shows/{show_id}/edit",
        headers={"Referer": f"http://localhost/admin/shows/{show_id}/edit"},
    ).get_data(as_text=True)

    assert 'name="next"' not in body


def test_safe_return_path_accepts_only_same_site_paths():
    assert safe_return_path("/shows/12") == "/shows/12"
    assert safe_return_path("/societies/tullamore?season=25%2F26") == "/societies/tullamore?season=25%2F26"
    assert safe_return_path("//evil.example") is None
    assert safe_return_path("https://evil.example") is None
    assert safe_return_path("shows/12") is None
    assert safe_return_path("") is None
    assert safe_return_path(None) is None


def test_a_society_login_gets_the_same_treatment(client, db):
    """The same helper backs /society/shows/<id>/edit, whose default was the
    society dashboard - equally wrong when the edit was opened from the
    society's own public page."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    show_id = seed_show(db, society_id=society_id)
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id

    resp = client.post(
        f"/society/shows/{show_id}/edit",
        data={"season": "25/26", "section": "Gilbert", "show": "Test Show",
              "next": f"/shows/{show_id}"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/shows/{show_id}"
