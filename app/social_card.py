"""The shareable show card - a PNG a society can post to its own Instagram.

**This is not the link preview.** `og-card.png` (see `scripts/build_brand_images.py`)
is what WhatsApp renders when someone *pastes a ShowCal link*; that already
worked. This is different: an image a society downloads and *posts*, carrying
their own show. It is the only thing on the board that gives a society
something instead of asking them for something, which is the point - 175 of 194
societies have never uploaded a poster, and "upload your poster and get a card
you can post" is a reason to.

Three shapes, because the platforms genuinely differ and a wrong aspect ratio
gets centre-cropped by each of them differently:

    post    1200x630   link previews, Facebook, X
    square  1080x1080  an Instagram feed post
    story    1080x1920  Instagram/Facebook stories

WHY PILLOW AND NOT A CANVAS IN THE BROWSER. The card has a URL, so it can be
linked, hotlinked into a message, or handed to a society over WhatsApp without
them visiting the site at all. A canvas would save the server some work and
lose all of that.

FONTS. Pillow cannot read woff2, and `fonttools` is deliberately not a runtime
dependency (see `scripts/build_brand_images.py`), so the two Archivo weights
the site already ships are committed alongside them as .ttf. There is no
regular weight in the repo - the site loads 700 and 800 only - so small text
here is 700 rather than a fake-regular substitute. On the card that reads as
deliberate; do not "fix" it by adding a system font, which will differ between
your machine and the container.
"""
import io
import re
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parent / "static" / "fonts"

# The site's own tokens (app/static/style.css, dark theme) - the card has to
# look like the page it came from.
INK = (9, 14, 21)
SURFACE = (16, 25, 36)
PANEL = (20, 36, 58)
GOLD = (245, 158, 11)
FG = (241, 245, 249)
MUTED = (148, 163, 184)

SIZES = {
    "post": (1200, 630),
    "square": (1080, 1080),
    "story": (1080, 1920),
}
DEFAULT_SIZE = "post"

# Everything is drawn at 2x and resampled once. Pillow does not antialias text
# edges or rounded rectangles well at final size, and the countdown numeral is
# large enough that the stepping shows.
SS = 2


def _font(weight, px):
    return ImageFont.truetype(str(FONTS / f"archivo-{weight}.ttf"), px)


def _fit(draw, text, weight, start_px, max_width, min_px):
    """Largest size at or below `start_px` where `text` fits `max_width`.

    Titles run from "Hair" to "Everybody's Talking About Jamie", so a fixed
    size either wastes the card or overflows it. Returns the font and the
    measured width."""
    px = start_px
    while px > min_px:
        font = _font(weight, px)
        width = draw.textlength(text, font=font)
        if width <= max_width:
            return font, width
        px -= max(2, px // 24)
    font = _font(weight, min_px)
    return font, draw.textlength(text, font=font)


def _wrap(draw, text, font, max_width):
    """Greedy word wrap. A word longer than the line is left to overflow
    rather than hyphenated - it cannot happen with a show title, and a bad
    hyphenation looks worse than the rare wide line."""
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and draw.textlength(candidate, font=font) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def _qr_matrix(data):
    """A QR code as a list of rows of booleans, via `segno`.

    Kept behind a function so the import failure has one place to happen: the
    card still renders without it, minus the QR, rather than 500ing. A society
    posting to Instagram cannot include a clickable link, so the QR is the only
    route from the post back to the show - but a card with no QR still beats no
    card at all."""
    try:
        import segno
    except ImportError:  # pragma: no cover - segno is in requirements.txt
        return None
    qr = segno.make(data, error="m")
    return [[bool(c) for c in row] for row in qr.matrix]


def _draw_qr(img, data, x, y, box_px, quiet=2):
    matrix = _qr_matrix(data)
    if not matrix:
        return False
    n = len(matrix) + quiet * 2
    cell = max(1, box_px // n)
    side = cell * n
    d = ImageDraw.Draw(img)
    # A white quiet zone is part of the spec, not decoration - scanners need it.
    d.rectangle([x, y, x + side, y + side], fill=(255, 255, 255))
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if on:
                cx = x + (c + quiet) * cell
                cy = y + (r + quiet) * cell
                d.rectangle([cx, cy, cx + cell - 1, cy + cell - 1], fill=INK)
    return True


def _poster_panel(box, poster_path, title):
    """The show's own poster, cover-cropped to `box`; a typeset playbill when
    there isn't one.

    The placeholder deliberately mirrors the site's own missing-poster playbill
    rather than being a grey rectangle - a society with no poster still gets a
    card worth posting, and it is the same design they already see on their
    own page."""
    w, h = box
    if poster_path:
        try:
            with Image.open(poster_path) as src:
                src = src.convert("RGB")
                scale = max(w / src.width, h / src.height)
                resized = src.resize((max(1, round(src.width * scale)),
                                      max(1, round(src.height * scale))), Image.LANCZOS)
                left = (resized.width - w) // 2
                top = (resized.height - h) // 2
                return resized.crop((left, top, left + w, top + h))
        except (OSError, ValueError):
            pass  # unreadable file - fall through to the playbill

    panel = Image.new("RGB", (w, h), PANEL)
    d = ImageDraw.Draw(panel)
    label = _font(700, max(11, int(w * 0.045)))
    text = "AIMS PRODUCTION"
    d.text(((w - d.textlength(text, font=label)) / 2, h * 0.16), text,
           font=label, fill=GOLD)

    # Shrink until the block fits on BOTH axes. Checking the line count alone
    # is not enough: a single unbreakable word ("EVERYBODY'S") can be wider
    # than the panel while still producing few enough lines, and because the
    # text is centred it then clips at both ends - the first version of this
    # rendered "VERYBODY'".
    limit = w * 0.82
    body_px = int(w * 0.16)
    while body_px > 14:
        font = _font(800, body_px)
        lines = _wrap(d, title.upper(), font, limit)
        widest = max((d.textlength(line, font=font) for line in lines), default=0)
        if len(lines) <= 4 and widest <= limit:
            break
        body_px = int(body_px * 0.9)
    font = _font(800, body_px)
    lines = _wrap(d, title.upper(), font, limit)

    line_h = body_px * 1.06
    block = line_h * len(lines)
    y = (h - block) / 2
    for line in lines:
        d.text(((w - d.textlength(line, font=font)) / 2, y), line, font=font, fill=FG)
        y += line_h

    rule_w = w * 0.22
    rule_y = h * 0.82
    d.rectangle([(w - rule_w) / 2, rule_y, (w + rule_w) / 2, rule_y + max(2, h * 0.005)],
                fill=GOLD)
    return panel


def _date_line(opening, closing):
    """"10-13 September 2026", or "10 September 2026" for a single night."""
    if not opening:
        return ""
    start = date.fromisoformat(opening)
    end = date.fromisoformat(closing) if closing else start
    if end <= start:
        return start.strftime("%-d %B %Y") if _supports_dash() else start.strftime("%d %B %Y").lstrip("0")
    if (start.month, start.year) == (end.month, end.year):
        return f"{start.day}-{end.day} {end.strftime('%B %Y')}"
    if start.year == end.year:
        return f"{start.day} {start.strftime('%B')} - {end.day} {end.strftime('%B %Y')}"
    return f"{start.day} {start.strftime('%B %Y')} - {end.day} {end.strftime('%B %Y')}"


def _supports_dash():
    try:
        date(2026, 9, 1).strftime("%-d")
        return True
    except ValueError:  # Windows
        return False


def _days_to(opening, today=None):
    if not opening:
        return None
    delta = (date.fromisoformat(opening) - (today or date.today())).days
    return delta if delta >= 0 else None


def render_card(show, size=DEFAULT_SIZE, poster_path=None, url=None, today=None):
    """`show` is a mapping with show, society_name, opening_date, closing_date
    and venue. Returns PNG bytes.

    **Type is sized against the text column, not the canvas height.** Keying it
    to height is the obvious thing and it is wrong: the story shape is 1920
    tall, so every size trebled, the countdown landed on top of the venue line
    and the QR caption ran off the right edge. The column a line sits in is
    what actually constrains it."""
    w, h = SIZES.get(size, SIZES[DEFAULT_SIZE])
    W, H = w * SS, h * SS
    img = Image.new("RGB", (W, H), INK)

    margin = int(W * 0.065)
    tall = H > W * 1.2
    if tall:
        # Poster across the top, everything else beneath it.
        img.paste(_poster_panel((W, int(H * 0.50)), poster_path, show["show"]), (0, 0))
        text_x, text_top = margin, int(H * 0.555)
        text_w = W - margin * 2
    else:
        # Poster down the left, text beside it.
        img.paste(_poster_panel((int(W * 0.34), H), poster_path, show["show"]), (0, 0))
        text_x, text_top = int(W * 0.40), int(H * 0.14)
        text_w = W - text_x - margin

    d = ImageDraw.Draw(img)

    # One unit, so every size is a ratio of the measure it sits in.
    u = text_w
    society_px = max(12, int(u * 0.046))
    meta_px = max(12, int(u * 0.043))
    count_px = max(18, int(u * 0.115))
    label_px = max(10, int(u * 0.030))
    qr_box = int(u * 0.21)

    # The footer is measured and reserved BEFORE the text is laid out, so the
    # two cannot collide - which is exactly what happened on the story shape.
    days = _days_to(show["opening_date"], today)
    cap_text = "SCAN FOR DATES"
    cap_font, cap_w = _fit(d, cap_text, 700, max(9, int(u * 0.023)), qr_box, 8)
    foot_h = qr_box + int(cap_font.size * 1.6)
    foot_top = H - margin - foot_h

    # --- text block ---
    y = text_top
    society = (show["society_name"] or "").upper()
    soc_font, _ = _fit(d, society, 700, society_px, text_w, 11)
    d.text((text_x, y), society, font=soc_font, fill=GOLD)
    y += soc_font.size * 1.65

    meta_lines = [ln for ln in (_date_line(show["opening_date"], show["closing_date"]),
                                show["venue"] or "") if ln]
    meta_h = len(meta_lines) * meta_px * 1.42 + u * 0.03
    title_room = foot_top - y - meta_h - u * 0.04

    # Shrink until the title fits on BOTH axes and inside the room left for it.
    # Line count alone is not enough: one unbreakable word ("EVERYBODY'S") can
    # be wider than the column while still producing few enough lines, and the
    # first version of this rendered it as "VERYBODY'".
    title_px = int(u * 0.155)
    while title_px > 16:
        title_font = _font(800, title_px)
        lines = _wrap(d, show["show"], title_font, text_w)
        widest = max((d.textlength(ln, font=title_font) for ln in lines), default=0)
        if (widest <= text_w and len(lines) <= 4
                and len(lines) * title_px * 1.05 <= title_room):
            break
        title_px = int(title_px * 0.9)
    title_font = _font(800, title_px)
    lines = _wrap(d, show["show"], title_font, text_w)
    for line in lines:
        d.text((text_x, y), line, font=title_font, fill=FG)
        y += title_px * 1.05

    y += u * 0.03
    for line in meta_lines:
        fitted, _ = _fit(d, line, 700, meta_px, text_w, 10)
        d.text((text_x, y), line, font=fitted, fill=MUTED)
        y += fitted.size * 1.42

    # --- footer: countdown left, QR right, on one baseline ---
    qr_x = W - margin - qr_box
    if days is not None:
        n_font = _font(800, count_px)
        d.text((text_x, foot_top), str(days), font=n_font, fill=GOLD)
        label = "DAY TO OPENING" if days == 1 else "DAYS TO OPENING"
        label_font, _ = _fit(d, label, 700, label_px, qr_x - text_x - margin, 9)
        d.text((text_x, foot_top + count_px * 1.10), label, font=label_font, fill=MUTED)

    if url and _draw_qr(img, url, qr_x, foot_top, qr_box):
        # Centred under the QR and never wider than it.
        d.text((qr_x + (qr_box - cap_w) / 2, foot_top + qr_box + cap_font.size * 0.45),
               cap_text, font=cap_font, fill=MUTED)

    img = img.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    # Flat RGB, no alpha - Cloudflare's image optimisation composites
    # transparency against its own background, which is how every WhatsApp
    # preview once became a gold M on a crimson field.
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def card_filename(show):
    bits = f"{show['show']}-{show['society_name']}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", bits).strip("-")
    return f"{slug or 'showcal'}-card.png"
