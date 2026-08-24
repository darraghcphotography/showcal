"""Second Act backlog item 7 ("measure the Shows A-Z page weight before
deciding whether to change it") measured real numbers against /titles: 386KB
uncompressed, nothing in the stack compressed a response, and a real "Slow
3G" profile (Lighthouse's own preset) took 8.2s to become interactive - 2.2s
on "Fast 3G". The actual fix turned out to be missing response compression,
not /titles needing lazy-loading or pagination - text compresses ~70-80%
with gzip/brotli, which alone closes most of that gap, site-wide."""
from pathlib import Path


def test_html_response_is_gzip_compressed_when_requested(client):
    resp = client.get("/titles", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("Content-Encoding") == "gzip"


def test_response_is_not_compressed_without_an_accept_encoding_header(client):
    """flask-compress only compresses when the client says it can decode it -
    a request with no Accept-Encoding (or one that doesn't list gzip/br)
    gets a plain response, same as before this was added."""
    resp = client.get("/titles", headers={"Accept-Encoding": ""})
    assert "Content-Encoding" not in resp.headers


def test_uploaded_image_is_not_recompressed(app, client):
    """Poster/logo files are already-compressed JPEG/PNG - flask-compress's
    default mimetype allowlist excludes image/* (recompressing would waste
    CPU for no size benefit), confirmed here against this app's own
    /uploads/<filename> route rather than just assuming the library default."""
    upload_dir = Path(app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "test-poster.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * 500)

    resp = client.get("/uploads/test-poster.jpg", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert "Content-Encoding" not in resp.headers
