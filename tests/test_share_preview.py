"""Open Graph tags and the share card (base.html + app.absolute_url).

Darragh sent a photo of a WhatsApp preview showing a gold "M" on a crimson
field. Three separate faults, found 2026-09-02:

  1. `og:image` pointed at `icons/icon-512.png`, which was still the OLD logo -
     the header switched to a DC monogram on 2026-08-30 and the icons never
     followed.

  2. That PNG was RGBA. Served over https, Cloudflare's image optimisation
     re-encoded it to RGB and composited the transparency against crimson: the
     corner pixel went from (11,15,20) to (200,16,46). That is the red. The
     share card is flat RGB now, so there is no alpha left to composite.

  3. Every absolute URL on the page said **http://**. The Cloudflare Tunnel
     terminates TLS and hands the origin a plain request with no
     `X-Forwarded-Proto`, so `ProxyFix(x_proto=1)` has nothing to promote and
     `url_for(_external=True)` / `request.url` honestly report http.

The first two are asset problems and are tested by inspecting the files. The
third is the one that would come back, because `_external=True` looks correct.
"""
from PIL import Image

from conftest import seed_society

CARD = "app/static/og-card.png"
ICONS = [
    "app/static/icons/icon-512.png",
    "app/static/icons/icon-192.png",
    "app/static/icons/apple-touch-icon.png",
    "app/static/icons/icon-maskable-512.png",
]


def test_the_share_card_is_flat_rgb_so_nothing_can_composite_it():
    """The whole cause of the red preview. An alpha channel is an invitation
    for a CDN to re-encode and pick its own background."""
    im = Image.open(CARD)
    assert im.mode == "RGB", f"{CARD} is {im.mode} - an optimiser will flatten it against something"
    assert "transparency" not in im.info


def test_every_app_icon_is_flat_rgb_too():
    for path in ICONS:
        im = Image.open(path)
        assert im.mode == "RGB", f"{path} is {im.mode}"


def test_the_share_card_is_the_shape_a_link_preview_wants():
    """1.91:1. A square gets cropped or letterboxed, differently by each of
    WhatsApp, Facebook and Slack."""
    im = Image.open(CARD)
    assert im.size == (1200, 630)


def test_the_card_is_on_brand_and_not_the_old_red_mangle():
    im = Image.open(CARD)
    corner = im.getpixel((2, 2))
    assert corner == (9, 14, 21), f"card background is {corner}, expected the site's --bg"
    # The specific crimson the broken version was composited against.
    assert corner != (200, 16, 46)


def test_og_tags_use_https_not_the_scheme_the_origin_was_spoken_to_on(client, monkeypatch):
    """The fault that will come back: `_external=True` looks right and is not.
    With SITE_URL set - which is how production runs - every absolute URL on the
    page has to use it."""
    monkeypatch.setattr("app.notify.SITE_URL", "https://darraghc.ie")

    body = client.get("/").get_data(as_text=True)
    head = body[:body.index("</head>")]

    assert 'content="http://' not in head, "an http:// absolute URL is still being advertised"
    assert 'property="og:image" content="https://darraghc.ie/static/og-card.png"' in head
    assert 'property="og:url" content="https://darraghc.ie/"' in head


def test_the_card_carries_its_dimensions(client, monkeypatch):
    """WhatsApp lays the preview out before the image finishes downloading;
    without these it guesses, and a guess it gets wrong is a preview that
    reflows or drops."""
    monkeypatch.setattr("app.notify.SITE_URL", "https://darraghc.ie")
    head = client.get("/").get_data(as_text=True)

    assert 'property="og:image:width" content="1200"' in head
    assert 'property="og:image:height" content="630"' in head
    assert 'property="og:image:type" content="image/png"' in head


def test_a_show_with_a_poster_shares_the_poster_not_the_card(client, db, monkeypatch):
    """The point of a per-show preview - and it has to be absolute too."""
    monkeypatch.setattr("app.notify.SITE_URL", "https://darraghc.ie")
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, "
        "moderation_status, poster_filename) VALUES (?, '26/27', 'Eastern', 'Chess', "
        "'2099-09-01', '2099-09-05', 'approved', 'poster.webp')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Chess'").fetchone()["id"]

    head = client.get(f"/shows/{show_id}").get_data(as_text=True)
    head = head[:head.index("</head>")]
    assert "poster.webp" in head
    assert 'content="http://' not in head


def test_without_site_url_the_tags_still_come_out_absolute(client):
    """Local dev has no SITE_URL. A relative og:image is simply ignored by every
    scraper, so the fallback has to still produce an absolute address."""
    head = client.get("/").get_data(as_text=True)
    head = head[:head.index("</head>")]
    assert 'property="og:image" content="http://localhost/static/og-card.png"' in head


def test_the_favicon_is_the_same_mark_as_the_header():
    """These drifted for three days - the header was a DC monogram while the tab
    icon was still the previous "M"."""
    favicon = open("app/static/favicon.svg", encoding="utf-8").read()
    header = open("app/templates/base.html", encoding="utf-8").read()
    # The D's path is the identifying part of the mark.
    assert "M7 8h6a7 7 0 0 1 0 14H7V8z" in favicon
    assert "M7 8h6a7 7 0 0 1 0 14H7V8z" in header
