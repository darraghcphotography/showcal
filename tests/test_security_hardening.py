"""Two findings from a 2026-08-25 security/architecture review, both fixed
the same day:

1. Rate-limiting keyed off request.remote_addr, but ProxyFix is only
   configured with x_proto=1 (for correct https:// URL generation) - not
   x_for=1 - and deployment is behind Cloudflare Tunnel (see
   docker-compose.yml), so every visitor's remote_addr was the tunnel
   container's own address. One bad actor tripping a login limit would 429
   every other visitor too. Fixed in app/rate_limit.py to prefer Cloudflare's
   own CF-Connecting-IP header, which their edge sets and a client can't
   forge (unlike a bare X-Forwarded-For).

2. The 413 (payload too large) handler redirected straight to
   request.referrer - a client-supplied header - which is a textbook open
   redirect: a crafted Referer pointing off-site would send this app's own
   visitors there. Fixed in app/__init__.py to only follow a same-origin
   referrer.
"""
from app.rate_limit import _rate_limit_key


def test_rate_limit_key_prefers_cf_connecting_ip(app):
    with app.test_request_context(headers={"CF-Connecting-IP": "203.0.113.7"}):
        assert _rate_limit_key() == "203.0.113.7"


def test_rate_limit_key_falls_back_to_remote_addr_without_the_header(app):
    with app.test_request_context(environ_overrides={"REMOTE_ADDR": "198.51.100.9"}):
        assert _rate_limit_key() == "198.51.100.9"


def test_413_redirects_to_a_same_origin_referrer(client):
    oversized = b"x" * (41 * 1024 * 1024)
    resp = client.post(
        "/submit/photo",
        data={"photo": (__import__("io").BytesIO(oversized), "photo.jpg")},
        headers={"Referer": "http://localhost/submit/photo"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "http://localhost/submit/photo"


def test_413_does_not_follow_an_off_site_referrer(client):
    oversized = b"x" * (41 * 1024 * 1024)
    resp = client.post(
        "/submit/photo",
        data={"photo": (__import__("io").BytesIO(oversized), "photo.jpg")},
        headers={"Referer": "https://evil.example/phishing"},
    )
    assert resp.status_code == 302
    assert "evil.example" not in resp.headers["Location"]


def test_413_falls_back_to_homepage_with_no_referrer(client):
    oversized = b"x" * (41 * 1024 * 1024)
    resp = client.post(
        "/submit/photo",
        data={"photo": (__import__("io").BytesIO(oversized), "photo.jpg")},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] in ("/", "http://localhost/")


def test_a_csrf_failure_is_a_clean_400_not_a_500(app):
    """Found 2026-08-29 while reviewing something else.

    Flask-WTF registers its CSRF check as a before_request when
    csrf.init_app() runs, which is earlier in create_app() than the
    @app.before_request that generated the CSP nonce. So on a POST with a
    missing/expired token it aborted first, every later before_request was
    skipped, and the nonce was never set - which then raised AttributeError
    in the after_request security headers AND again in the 500 handler's own
    template render. A stale form left open past its token lifetime (an
    ordinary thing for a user to do) produced an unhandled 500 whose error
    page could not render either. The nonce is generated lazily now.
    """
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()

    resp = client.post("/admin/login", data={"username": "x", "password": "y"})

    assert resp.status_code == 400
    assert "Content-Security-Policy" in resp.headers
    assert "nonce-" in resp.headers["Content-Security-Policy"]
