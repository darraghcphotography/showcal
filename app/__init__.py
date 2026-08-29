import mimetypes
import os
import secrets
from pathlib import Path

from flask import Flask, g, request
from flask_compress import Compress
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db as db_module
from . import productions_build, venues_build
from .rate_limit import limiter

BASE_DIR = Path(__file__).resolve().parent.parent
csrf = CSRFProtect()
compress = Compress()

# The container's Python has no .webp entry in its mimetypes table at all
# (confirmed on production, 2026-08-24: mimetypes.guess_type('x.webp') ->
# (None, None)) - every poster save_poster produces is WebP now, and
# send_from_directory (public.uploaded_file) falls back to
# application/octet-stream without this, which every browser refuses to
# render as an image behind this app's own X-Content-Type-Options: nosniff
# header. Registered at import time, once, rather than per-request.
mimetypes.add_type("image/webp", ".webp")


def create_app(test_config=None):
    app = Flask(__name__)

    # Cloudflare Tunnel terminates TLS and forwards to the container over
    # plain HTTP, so without this every url_for(..., _external=True) call
    # (sitemap.xml, robots.txt, the .ics feed, og:image tags) built its URL
    # as http:// - wrong scheme, and in practice a broken link-preview image
    # on any platform that refuses to embed a plain-http image. Trusting
    # exactly one hop's X-Forwarded-Proto (not -Host or -For) is the minimal
    # fix - safe to apply unconditionally, since with no such header present
    # (local `flask run`, or the test client) it's a no-op.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-insecure-change-me"),
        DATABASE=os.environ.get("AIMS_DB_PATH", str(BASE_DIR / "aims.db")),
        SCHEMA_PATH=str(BASE_DIR / "schema.sql"),
        SOCIETY_CORRECTIONS_PATH=str(BASE_DIR / "society_gate_suggestions.json"),
        UPLOAD_DIR=os.environ.get("AIMS_UPLOAD_DIR", str(BASE_DIR / "uploads")),
        MAX_CONTENT_LENGTH=40 * 1024 * 1024,  # 40 MB - a programme's worth of pages, about a dozen phone photos in one photo submission
        # Secure only in Docker/production (signalled by AIMS_DB_PATH being
        # set, per docker-compose.yml - local dev per docs/deployment.md
        # never sets it) - the site is HTTPS-only there via Cloudflare
        # Tunnel. Local `flask run` stays plain http, where a Secure cookie
        # would never be sent back by the browser at all, breaking login.
        SESSION_COOKIE_SECURE=bool(os.environ.get("AIMS_DB_PATH")),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        # Safe to cache long - static/<path> URLs already carry
        # asset_version (below, mtime-based) as a query string, so a real
        # change always gets a new URL rather than relying on this expiring.
        SEND_FILE_MAX_AGE_DEFAULT=31536000,
    )
    if test_config:
        app.config.update(test_config)

    if app.config["SECRET_KEY"] == "dev-insecure-change-me" and not app.debug and not app.testing:
        app.logger.warning(
            "SECRET_KEY is not set - using an insecure default. "
            "Set the SECRET_KEY environment variable before deploying."
        )

    # AIMS_DB_PATH is only ever set in Docker/production (see SESSION_COOKIE_SECURE
    # above) - a missing database file there means either a genuinely brand-new
    # deployment, or the data volume isn't mounted where the app expects it and
    # a fresh empty database is about to get created in its place (exactly what
    # silently wiped this app's entire history once already - see docs/deployment.md).
    # Nothing below this can tell those two cases apart, so just log loudly and
    # let a human decide, rather than quietly serving an empty site.
    if os.environ.get("AIMS_DB_PATH") and not app.testing and not Path(app.config["DATABASE"]).exists():
        app.logger.warning(
            "No database file found at %s before this startup. If aims-web has "
            "run here before, this almost certainly means the data volume isn't "
            "mounted correctly - STOP and check it (see docs/deployment.md) "
            "before this instance serves real traffic.",
            app.config["DATABASE"],
        )

    db_module.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    # Measured 2026-08-24 against /titles (300 titles, the site's heaviest
    # list page): 386KB uncompressed (286KB HTML + 66KB CSS + 34KB font),
    # nothing in the stack compresses a response - not waitress, no reverse
    # proxy in front. On a real "Slow 3G" profile (400Kbps/400ms RTT,
    # Lighthouse's own preset) that page took 8.2s to become interactive,
    # against 2.2s on "Fast 3G". Text compresses ~70-80% with gzip/brotli,
    # so this alone should close most of that gap site-wide, for every page,
    # not just this one - the actual fix for the "page weight" backlog item
    # (Second Act item 7) turned out to be missing compression, not /titles
    # needing lazy-loading or pagination.
    compress.init_app(app)

    from . import filters
    filters.register(app)

    # Safe to run on every startup: schema.sql uses CREATE ... IF NOT EXISTS,
    # and column migrations only add a column when it's actually missing.
    with app.app_context():
        db_module.init_schema()
        from . import analytics
        analytics.purge_excluded_pageviews(db_module.get_db())

        # The productions table is derived from shows/historical_results/
        # historical_reviews, so a deploy that changes how it's derived - or an
        # import script that rewrote rows outside the app - has to be picked up
        # without anyone remembering to run something. Cheap: a rebuild with
        # nothing to do writes nothing and takes ~50ms at this data's size.
        from . import productions_build, venues_build
        productions_build.build(db_module.get_db())
        venues_build.build(db_module.get_db())
        db_module.get_db().commit()

        # Publish any new CHANGELOG.md entries - skipped under pytest so a
        # test asserting an empty changelog_entries table isn't broken by
        # whatever happens to be in the real file (see test_suggestions_roadmap.py).
        if not app.testing:
            from . import changelog_sync
            changelog_sync.sync(db_module.get_db(), BASE_DIR / "CHANGELOG.md")

    from .blueprints.public import bp as public_bp
    from .blueprints.submit import bp as submit_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.info import bp as info_bp
    from .blueprints.feeds import bp as feeds_bp
    from .blueprints.society import bp as society_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(submit_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(info_bp)
    app.register_blueprint(feeds_bp)
    app.register_blueprint(society_bp)

    from . import auth

    # Cache-busting for static/style.css: a version string baked from the
    # file's own mtime, appended as a query string on the <link> tag. Changes
    # automatically on every deploy (the file gets a fresh mtime when the
    # image is rebuilt), so browsers and Cloudflare's edge cache always fetch
    # the new CSS instead of serving a stale copy under the same URL.
    try:
        asset_version = str(int((BASE_DIR / "app" / "static" / "style.css").stat().st_mtime))
    except OSError:
        asset_version = "1"

    # When this process started - a redeploy restarts the container, so this
    # is an accurate "deployed at" for the Roadmap page's "Recently shipped"
    # section without needing to track deploys separately. Explicitly UTC
    # (not datetime.now(), which is the container's own clock - usually UTC
    # in Docker, but not guaranteed) so it matches every other timestamp in
    # the app (SQLite's datetime('now')) and displays correctly through the
    # irish_datetime filter's UTC -> Europe/Dublin conversion.
    from datetime import datetime as _datetime, timezone as _timezone
    deployed_at = _datetime.now(_timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def csp_nonce():
        """The current request's CSP nonce, generated on first use.

        A fresh per-request token, not a fixed one - a nonce that never
        changed would let an attacker who once got a script injected reuse
        that same nonce on every future request.

        Lazy rather than only set in the before_request below, because that
        handler does not always get to run. Flask-WTF's CSRF check is
        registered as a before_request when csrf.init_app() is called, which
        happens earlier in this function than the decorator below - so on a
        POST with a missing or expired CSRF token it aborts first and every
        later before_request is skipped. That left both consumers of the
        nonce raising AttributeError: the after_request security headers,
        and then the 500 handler's own template render, so a stale form
        (left open past the token's lifetime - an ordinary thing for a user
        to do) produced an unhandled 500 whose error page also failed to
        render. Found 2026-08-29.
        """
        nonce = g.get("csp_nonce")
        if nonce is None:
            nonce = secrets.token_urlsafe(16)
            g.csp_nonce = nonce
        return nonce

    @app.before_request
    def set_csp_nonce():
        # Generated up front on the normal path (not lazily inside
        # set_security_headers below) so inject_globals() can hand it to
        # templates in time for their <script nonce="..."> tags.
        csp_nonce()

    @app.before_request
    def keep_derived_tables_current():
        """Rebuild productions/venues if their sources have moved, before any
        view runs.

        These used to be per-route calls, and that made correctness a thing you
        had to remember: a route reading production_id or venue_id without one
        doesn't error, it silently under-reports. Sixteen call sites across six
        modules, and every new route was another chance to forget. Stated once
        here it can't be forgotten instead.

        The cost of the no-op case is why this is affordable: both freshness
        checks are a single fingerprint query, measured at 0.26ms each on the
        real database. Static files skip it because they touch no data at all.
        """
        if request.endpoint == "static":
            return
        db = db_module.get_db()
        productions_build.ensure_current(db)
        venues_build.ensure_current(db)

    @app.context_processor
    def inject_globals():
        return {
            "current_user": auth.current_user(),
            "society_session": auth.active_society_code(),
            "asset_version": asset_version,
            "deployed_at": deployed_at,
            "csp_nonce": csp_nonce(),
        }

    from urllib.parse import urlparse

    from flask import flash, redirect, request, url_for

    @app.errorhandler(413)
    def too_large(e):
        flash("That upload is too large - photos together must be under 40 MB.", "error")
        # request.referrer is a client-supplied header - redirecting straight
        # to it is an open redirect (a crafted Referer pointing off-site would
        # send this app's own visitors there). Only follow it if it actually
        # points back at this site; otherwise fall back to the homepage, same
        # as when there's no referrer at all.
        target = request.referrer
        if target and urlparse(target).netloc != urlparse(request.host_url).netloc:
            target = None
        return redirect(target or url_for("public.index")), 302

    from flask import render_template

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    from . import analytics

    @app.after_request
    def track_pageview(response):
        if response.status_code == 200 and analytics.should_track(request):
            analytics.record_pageview(db_module.get_db(), request.path)
        return response

    is_production = bool(os.environ.get("AIMS_DB_PATH"))

    @app.after_request
    def set_security_headers(response):
        # nosniff matters most for /uploads/<filename> - without it, an
        # older browser can content-sniff a crafted "poster.jpg" as HTML
        # despite the image/* Content-Type, regardless of the extension
        # allowlist in uploads.py. X-Frame-Options blocks clickjacking a
        # moderator into an invisible iframe over /admin.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Sends the full referring URL to same-origin links/uploads, but only
        # the bare origin (no path/query) cross-origin - a show/society page's
        # URL isn't sensitive, but no reason to leak the full path to a
        # third-party image host etc.
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # No browser feature here needs geolocation/camera/mic/payment access.
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=(), payment=()")
        # script-src is nonce-gated (every <script> tag carries the same
        # per-request g.csp_nonce set in set_csp_nonce() above) rather than
        # 'unsafe-inline', so an injected <script> - the actual XSS risk -
        # can't execute even if it slips past Jinja's autoescaping somehow.
        # style-src still allows 'unsafe-inline' - the site's handful of
        # inline style="..." attributes (some with a dynamically-computed
        # width, e.g. the venues page's progress bar) aren't a nonce-able
        # shape, and a CSS-only injection is a much smaller risk than script.
        # /venues/map is the one page on the site that needs a third-party
        # resource at all - Leaflet's JS/CSS from unpkg (SRI-pinned on the
        # <script>/<link> tags themselves as a second layer) and CartoDB's
        # tile images. Vendoring Leaflet into /static instead of a CDN would
        # avoid this entirely, but there's no safe way here to fetch and
        # verify an exact binary-correct copy of a minified JS library to
        # commit - a CDN with SRI hashes both loads and verifies it in one
        # step. Scoped to just this route rather than loosened site-wide, so
        # everywhere else keeps the fully strict policy.
        if request.endpoint == "public.venues_map":
            script_src = f"'self' 'nonce-{csp_nonce()}' https://unpkg.com"
            style_src = "'self' 'unsafe-inline' https://unpkg.com"
            img_src = "'self' data: https://*.basemaps.cartocdn.com"
        else:
            script_src = f"'self' 'nonce-{csp_nonce()}'"
            style_src = "'self' 'unsafe-inline'"
            img_src = "'self' data:"
        response.headers.setdefault("Content-Security-Policy", (
            "default-src 'self'; "
            f"script-src {script_src}; "
            f"style-src {style_src}; "
            f"img-src {img_src}; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "object-src 'none'"
        ))
        if is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    return app
