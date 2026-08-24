"""A poster is always WebP now (app/uploads.py's save_poster) - found in
production 2026-08-24 that the container's Python has no .webp entry in its
mimetypes table at all (mimetypes.guess_type returns (None, None)), so
public.uploaded_file's send_from_directory served every poster as
application/octet-stream. Combined with this app's own
X-Content-Type-Options: nosniff header, no browser would render it as an
image. app/__init__.py registers the type at import time - this just checks
it actually sticks."""
import mimetypes


def test_webp_mimetype_is_registered():
    assert mimetypes.guess_type("poster.webp")[0] == "image/webp"


def test_uploaded_webp_file_serves_with_correct_content_type(client, app):
    upload_dir = app.config["UPLOAD_DIR"]
    import os
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, "test.webp"), "wb") as f:
        f.write(b"fake webp bytes")

    resp = client.get("/uploads/test.webp")
    assert resp.status_code == 200
    assert resp.content_type == "image/webp"
