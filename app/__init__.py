import os
from pathlib import Path

from flask import Flask
from flask_wtf import CSRFProtect

from . import db as db_module
from .rate_limit import limiter

BASE_DIR = Path(__file__).resolve().parent.parent
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-insecure-change-me"),
        DATABASE=os.environ.get("AIMS_DB_PATH", str(BASE_DIR / "aims.db")),
        SCHEMA_PATH=str(BASE_DIR / "schema.sql"),
        UPLOAD_DIR=os.environ.get("AIMS_UPLOAD_DIR", str(BASE_DIR / "uploads")),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,  # 8 MB - generous for a poster photo, not for abuse
        # Secure only in Docker/production (signalled by AIMS_DB_PATH being
        # set, per docker-compose.yml - local dev per docs/deployment.md
        # never sets it) - the site is HTTPS-only there via Cloudflare
        # Tunnel. Local `flask run` stays plain http, where a Secure cookie
        # would never be sent back by the browser at all, breaking login.
        SESSION_COOKIE_SECURE=bool(os.environ.get("AIMS_DB_PATH")),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
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

    from . import filters
    filters.register(app)

    # Safe to run on every startup: schema.sql uses CREATE ... IF NOT EXISTS,
    # and column migrations only add a column when it's actually missing.
    with app.app_context():
        db_module.init_schema()

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

    @app.context_processor
    def inject_globals():
        return {
            "current_user": auth.current_user(),
            "society_session": auth.active_society_code(),
            "asset_version": asset_version,
        }

    from flask import flash, redirect, request, url_for

    @app.errorhandler(413)
    def too_large(e):
        flash("That file is too large - posters must be under 8 MB.", "error")
        return redirect(request.referrer or url_for("public.index")), 302

    from flask import render_template

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    from . import analytics

    @app.after_request
    def track_pageview(response):
        if response.status_code == 200 and analytics.should_track(request):
            analytics.record_pageview(db_module.get_db(), request.path)
        return response

    return app
