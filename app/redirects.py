"""Sending a moderator back where they came from after an edit.

Every admin edit form used to redirect to its own list page on save, so
following "Edit this show" from a show's public page (or from a society page)
dropped you into /admin/shows afterwards - a different page about different
shows, with the one you just edited nowhere in sight. These two helpers let a
form carry the page it was opened from and return there instead.

Deliberately path-only: an absolute URL, a protocol-relative one (//evil.tld)
or anything with a scheme is rejected outright rather than sanitised, so a
crafted ?next= can never turn a moderator's save into an off-site redirect.
"""
from urllib.parse import urlparse

from flask import request


def safe_return_path(candidate):
    """The candidate as a same-site path to redirect to, or None if it isn't one."""
    if not candidate:
        return None
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    return candidate


def return_to(default_url):
    """Where a form that was just submitted should send the user.

    Reads the form's own hidden `next` field first (set from `came_from()` when
    the form was rendered), then ?next= for a plain link, and falls back to the
    caller's own default - the list page these forms always used to return to.
    """
    for candidate in (request.form.get("next"), request.args.get("next")):
        target = safe_return_path(candidate)
        if target:
            return target
    return default_url


def came_from(default=None):
    """The page a form was opened from, for its hidden `next` field.

    Prefers an explicit ?next= (so a link can say where to come back to) over
    the Referer header, which browsers omit often enough that it can't be the
    only source. Returns `default` - normally None, meaning "use the route's
    own default" - when neither gives a usable same-site path.
    """
    explicit = safe_return_path(request.args.get("next"))
    if explicit:
        return explicit

    referrer = request.referrer
    if referrer:
        parsed = urlparse(referrer)
        # Only trust a Referer from this same host - a link from another site
        # to an edit form should not decide where saving it lands.
        if parsed.netloc == urlparse(request.url).netloc:
            path = parsed.path + (("?" + parsed.query) if parsed.query else "")
            # Never bounce back to the form itself (a re-render after a
            # validation error sets the Referer to this very page).
            if safe_return_path(path) and parsed.path != request.path:
                return path
    return default
