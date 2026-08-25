"""Login brute-force protection, shared across blueprints.

Kept in its own module (like db.py) so app/__init__.py and the blueprints
that apply @limiter.limit(...) can both import it without a circular import.
In-memory storage is fine here - a single waitress process, no need for
Redis for a handful of login routes - it just resets on container restart.
"""
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _rate_limit_key():
    """The real client IP, not the cloudflared tunnel container's - deployment
    is behind Cloudflare Tunnel (see docker-compose.yml), and ProxyFix is only
    configured with x_proto=1 (for correct https:// URL generation), not
    x_for=1, so request.remote_addr is the tunnel container's own address.
    Without this every visitor would share one rate-limit bucket: one bad
    actor tripping /admin/login's 10/min limit would 429 everyone else too.
    CF-Connecting-IP is Cloudflare's own header, set by their edge and not
    forgeable by the client - safe to trust here unlike a bare X-Forwarded-For,
    which a client could set directly if the tunnel container is ever bypassed."""
    return request.headers.get("CF-Connecting-IP") or get_remote_address()


limiter = Limiter(key_func=_rate_limit_key)
