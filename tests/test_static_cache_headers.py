"""T3 (small-items queue): static assets were served with no Cache-Control
at all. asset_version (app/__init__.py, mtime-based) already busts the URL
on any real change, which is exactly what makes a long max-age here safe."""


def test_static_asset_has_a_long_cache_control_header(client):
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert "max-age=31536000" in resp.headers.get("Cache-Control", "")
