import os
from pathlib import Path

from flask import Flask
from flask_wtf import CSRFProtect

from . import db as db_module

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
    )
    if test_config:
        app.config.update(test_config)

    if app.config["SECRET_KEY"] == "dev-insecure-change-me" and not app.debug and not app.testing:
        app.logger.warning(
            "SECRET_KEY is not set - using an insecure default. "
            "Set the SECRET_KEY environment variable before deploying."
        )

    db_module.init_app(app)
    csrf.init_app(app)

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

    app.register_blueprint(public_bp)
    app.register_blueprint(submit_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(info_bp)

    from . import auth

    @app.context_processor
    def inject_globals():
        return {"current_user": auth.current_user()}

    from flask import flash, redirect, request, url_for

    @app.errorhandler(413)
    def too_large(e):
        flash("That file is too large - posters must be under 8 MB.", "error")
        return redirect(request.referrer or url_for("public.index")), 302

    return app
