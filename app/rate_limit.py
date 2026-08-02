"""Login brute-force protection, shared across blueprints.

Kept in its own module (like db.py) so app/__init__.py and the blueprints
that apply @limiter.limit(...) can both import it without a circular import.
In-memory storage is fine here - a single waitress process, no need for
Redis for a handful of login routes - it just resets on container restart.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
