"""C2 (small-items queue): DATE_RE was defined three times (society.py,
submit.py, admin/_shared.py) with the identical pattern. Moved to
app/constants.py as the one definition; the two admin submodules that
imported it via admin/_shared.py keep working through its re-export."""
from app.constants import DATE_RE
from app.blueprints.society import DATE_RE as society_date_re
from app.blueprints.submit import DATE_RE as submit_date_re
from app.blueprints.admin._shared import DATE_RE as shared_date_re
from app.blueprints.admin.shows import DATE_RE as shows_date_re
from app.blueprints.admin.misc import DATE_RE as misc_date_re


def test_all_date_re_imports_are_the_same_object():
    assert society_date_re is DATE_RE
    assert submit_date_re is DATE_RE
    assert shared_date_re is DATE_RE
    assert shows_date_re is DATE_RE
    assert misc_date_re is DATE_RE


def test_date_re_matches_iso_dates_only():
    assert DATE_RE.match("2026-08-28")
    assert not DATE_RE.match("28/08/2026")
    assert not DATE_RE.match("")
