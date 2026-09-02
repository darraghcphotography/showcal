"""Paste-to-upload on the poster and logo forms (_paste_upload.html + the
handler in base.html).

Darragh's ask, 2026-09-02: chasing posters means finding one on a society's
Facebook page, and the file-picker route is save-to-Downloads, Choose file, find
it again. Copying the image and pressing Ctrl+V should be the whole job.

The interaction itself is browser-side and is exercised in
tests/test_paste_upload_browser.py. What is pinned here is the contract between
the two halves, which is where this would silently break:

  - the paste zone is actually rendered on the forms that need it, and points at
    a file input that exists on the same page;
  - a file named the way the pasted one is named survives the real upload path.
"""
import io

import pytest
from PIL import Image

from conftest import seed_invite_code, seed_society, seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _png_bytes(size=(300, 400)):
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 60, 120)).save(buf, format="PNG")
    buf.seek(0)
    return buf


@pytest.mark.parametrize("path, input_id", [
    ("/admin/societies/1/shows/new", "poster-input"),
    ("/admin/societies/1/edit", "logo-input"),
])
def test_the_paste_zone_points_at_an_input_that_exists(client, db, path, input_id):
    """The zone finds its input by id. A rename on one side and not the other
    leaves a hint on screen that silently does nothing."""
    seed_society(db, id=1)
    db.commit()
    login_as(client, seed_user(db))

    body = client.get(path).get_data(as_text=True)
    assert f'data-paste-for="{input_id}"' in body
    assert f'id="{input_id}"' in body


def test_a_society_gets_the_paste_zone_on_its_own_show_form(client, db):
    """The societies are the ones being asked for posters - this is the form
    the login codes exist to reach."""
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="AIMS-PASTE1", society_id=society_id)
    db.commit()
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id

    body = client.get("/society/shows/new").get_data(as_text=True)
    assert 'data-paste-for="poster-input"' in body
    assert 'id="poster-input"' in body


def test_a_pasted_filename_survives_the_real_upload_path(client, db):
    """The blob is named `pasted-<timestamp>.png` in the browser because the
    server derives the extension from the filename (app/uploads.py's
    ALLOWED_EXTENSIONS). The colons in an ISO timestamp are stripped for exactly
    this reason - this pins that the name the handler builds is one the upload
    path actually accepts."""
    society_id = seed_society(db)
    db.commit()
    login_as(client, seed_user(db))

    resp = client.post(
        f"/admin/societies/{society_id}/shows/new",
        data={
            "season": "26/27",
            "show": "Pasted Poster Show",
            "region": "Eastern",
            "poster": (_png_bytes(), "pasted-2026-09-02-17-04-11.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    row = db.execute(
        "SELECT poster_filename FROM shows WHERE show = 'Pasted Poster Show'"
    ).fetchone()
    assert row is not None, "the show was not created"
    assert row["poster_filename"], "the pasted-style filename was rejected by the upload path"


def test_the_handler_is_only_shipped_where_a_paste_zone_exists(client, db):
    """It is in base.html, so it loads on every page. It must bail immediately
    when there is nothing to paste into rather than binding a document-level
    paste listener on, say, the homepage."""
    body = client.get("/").get_data(as_text=True)
    # The script itself ships everywhere (it lives in base.html) and mentions
    # the attribute in its own selector, so this checks for the rendered zone.
    assert 'class="paste-zone"' not in body
    # The guard that makes shipping it everywhere safe.
    assert "querySelector('.paste-zone[data-paste-for]')" in body
