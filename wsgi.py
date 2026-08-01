"""Entry point for a production WSGI server (waitress, per the Dockerfile's
CMD). For local development use `flask run` instead (see README.md)."""
import os

from app import create_app

app = create_app()


class PrefixMiddleware:
    """Lets the app be mounted under a path prefix (e.g. /showcal) behind a
    reverse proxy or Cloudflare Tunnel path rule, with no route in the app
    itself needing to know about the prefix. Setting SCRIPT_NAME here is all
    that's needed - url_for() and every internal link already fold it in
    automatically, because that's what Werkzeug's URL generation is built to
    respect."""

    def __init__(self, wsgi_app, prefix):
        self.wsgi_app = wsgi_app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path.startswith(self.prefix):
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            environ["SCRIPT_NAME"] = self.prefix
        return self.wsgi_app(environ, start_response)


# Set URL_PREFIX (e.g. "/showcal") when the app is reachable at a sub-path of
# a domain rather than at the domain root. Leave unset for local dev.
_url_prefix = os.environ.get("URL_PREFIX", "").rstrip("/")
if _url_prefix:
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, _url_prefix)
