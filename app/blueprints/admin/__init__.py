"""Moderator/admin area: dashboard, moderation queues, and CRUD for
societies, shows, venues, awards, adjudicators, and the historical-reviews
archive.

Split from a single 3,300+ line admin.py into this package, one module per
concern (see each submodule's own docstring/comments for what it owns).
`bp` is defined here and shared by every submodule; submodules are imported
below purely for their route-registration side effects (each one does
`from . import bp` and then `@bp.route(...)`), the standard Flask pattern
for a blueprint split across files.

A few names are re-exported here for callers outside this package that
import them by dotted path from `app.blueprints.admin` directly (tests, and
app/__init__.py's own blueprint registration) - see each import below for
which submodule actually owns the definition.
"""

from flask import Blueprint

bp = Blueprint("admin", __name__, url_prefix="/admin")

from . import auth  # noqa: E402,F401
from . import historical_reviews  # noqa: E402,F401
from . import dashboard  # noqa: E402,F401
from . import shows  # noqa: E402,F401
from . import invite_codes  # noqa: E402,F401
from . import societies  # noqa: E402,F401
from . import venues  # noqa: E402,F401
from . import misc  # noqa: E402,F401
from . import duplicates  # noqa: E402,F401
from . import reviews  # noqa: E402,F401
from . import awards  # noqa: E402,F401
from . import adjudicators  # noqa: E402,F401
from . import photo_submissions  # noqa: E402,F401
from . import logo_candidates  # noqa: E402,F401
from . import faq  # noqa: E402,F401
from . import historical_society_links  # noqa: E402,F401

# Re-exported: tests/test_adjudicators.py imports this by dotted path.
from .adjudicators import _adjudicator_grid_seasons  # noqa: E402,F401

# Re-exported: tests/test_historical_reviews.py imports these by dotted path.
from .historical_reviews import SOCIETY_DISTINCTIVE_THRESHOLD, _society_distinctive_score  # noqa: E402,F401
