"""Every remaining place that builds an absolute URL, after the feeds fix.

The Cloudflare Tunnel terminates TLS and hands the origin a plain HTTP request
with **no `X-Forwarded-Proto`**, so `ProxyFix(x_proto=1)` has nothing to promote
and `url_for(..., _external=True)` honestly reports `http://`. This has now been
found and fixed three separate times:

  1. 2026-09-02 - `og:url` / `og:image` (test_share_preview.py)
  2. 2026-09-04 - sitemap.xml, robots.txt, calendar.ics (test_round1_foundation.py)
  3. 2026-09-04 - the four sites below, found by grepping for the pattern during
     a backlog audit rather than by anything failing.

The third round is the reason this file exists. Each fix closed the sites it
knew about and left the others, because `_external=True` reads as correct and
nothing fails visibly. These tests assert the *absence* of the pattern's effect
at each remaining site, so a fourth round cannot happen quietly.

The worst two were the magic-link emails: a society approved for access was sent
an `http://` link to click. It redirects, so nobody would report it - it just
looks wrong to a committee member, and some mail scanners rewrite or strip plain
-http links entirely.
"""
from conftest import seed_society, seed_user

SITE = "https://darraghc.ie"


def _approve_a_request(client, db, monkeypatch):
    """Drive the real approval flow far enough to capture the emailed link."""
    sent = {}

    def fake_send(subject, body, to=None):
        sent["body"] = body
        return True

    monkeypatch.setattr("app.notify.SITE_URL", SITE)
    monkeypatch.setattr("app.blueprints.admin.access_requests.notify.send", fake_send)
    return sent


def test_the_magic_link_emailed_to_a_society_is_https(client, db, monkeypatch):
    """The one that actually reached a person. An approved society got an
    http:// link in their inbox."""
    sent = _approve_a_request(client, db, monkeypatch)
    user_id = seed_user(db, role="admin")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    society_id = seed_society(db, name="Test Society")
    # token_hash is NOT NULL even while pending - the real request route fills
    # it with a throwaway, and approval replaces it with the token it actually
    # emails. Mirrored here rather than reaching through the rate-limited form.
    from app.auth import generate_magic_token, hash_magic_token

    db.execute(
        "INSERT INTO society_access_requests (society_id, requester_name, requester_email, "
        "requester_role, token_hash, status) VALUES (?, 'A Person', 'person@example.com', "
        "'Committee', ?, 'pending')",
        (society_id, hash_magic_token(generate_magic_token())),
    )
    db.commit()
    req_id = db.execute("SELECT id FROM society_access_requests").fetchone()["id"]

    client.post(f"/admin/access-requests/{req_id}/approve", data={}, follow_redirects=True)

    body = sent.get("body", "")
    assert body, "no email was sent, so this test proves nothing - check the approval route"
    assert "http://" not in body, f"an http:// magic link was emailed:\n{body}"
    assert SITE in body


def test_the_add_to_google_calendar_link_carries_an_https_url(client, db, monkeypatch):
    """The event details Google stores contain a link back to the show. It was
    http://, so every calendar entry created from the site held one."""
    monkeypatch.setattr("app.notify.SITE_URL", SITE)
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status) VALUES (?, '26/27', 'Eastern', 'Chess', '2099-09-01', "
        "'2099-09-05', 'approved')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Chess'").fetchone()["id"]

    html = client.get(f"/shows/{show_id}").get_data(as_text=True)

    # The URL is query-encoded inside the Google Calendar link.
    assert "http%3A%2F%2F" not in html, "an http:// URL is encoded into the calendar link"
    assert "https%3A%2F%2Fdarraghc.ie" in html


def test_the_share_button_shares_an_https_url(client, db, monkeypatch):
    """`navigator.share` sends whatever `data-url` holds. A cast sharing its own
    show to WhatsApp was sharing an http:// link - the site's most natural
    growth loop, advertising the wrong scheme."""
    monkeypatch.setattr("app.notify.SITE_URL", SITE)
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status) VALUES (?, '26/27', 'Eastern', 'Chess', '2099-09-01', "
        "'2099-09-05', 'approved')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Chess'").fetchone()["id"]

    html = client.get(f"/shows/{show_id}").get_data(as_text=True)
    marker = 'id="share-button"'
    assert marker in html
    button = html[html.index(marker):html.index(marker) + 400]
    assert 'data-url="http://' not in button, f"share button still shares http://\n{button}"
    assert f'data-url="{SITE}' in button


def test_no_template_or_route_reintroduces_external_true():
    """The pattern itself, not its symptoms. `_external=True` looks correct and
    is not, so the only durable guard is that it does not come back.

    `app/__init__.py` is exempt: it is where the explanation lives, and the
    mentions there are prose in a docstring, not calls."""
    import pathlib

    offenders = []
    for path in pathlib.Path("app").rglob("*"):
        if path.suffix not in (".py", ".html") or path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            if "_external=True" not in line:
                continue
            # A comment warning about it is the point, not a violation.
            stripped = line.strip()
            if stripped.startswith("#") or "can't be trusted" in line:
                continue
            offenders.append(f"{path}:{n}: {stripped}")

    assert not offenders, (
        "url_for(..., _external=True) reports http:// behind the Cloudflare "
        "Tunnel. Use notify.link(url_for(...)) in Python or the absolute_url() "
        "Jinja global in a template:\n" + "\n".join(offenders)
    )
