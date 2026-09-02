"""Regenerates the share card and the app icons from the current DC brand mark.

Three things went wrong at once and this fixes the asset half of them.

1. THE ICONS WERE STILL THE OLD LOGO. The header got a DC monogram on
   2026-08-30 (see base.html's inline .brand-icon SVG) but `favicon.svg` and
   every PNG under static/icons/ kept the previous gold "M". So the app icon,
   the browser tab and every link preview showed a mark the site no longer uses.

2. CLOUDFLARE WAS MANGLING THE SHARE IMAGE. `icon-512.png` was RGBA. Served
   over https, Cloudflare's image optimisation re-encoded it to RGB and
   composited the transparency against crimson - the corner pixel went from
   (11,15,20) to (200,16,46). Every WhatsApp preview was a gold M on a red
   field, which is what prompted this. Everything written here is **flat RGB
   with no alpha**, so there is nothing left to composite and no re-encode can
   change the colours.

3. A square icon is the wrong shape for a link preview anyway. WhatsApp,
   Facebook and Slack all want roughly 1.91:1; a square gets cropped or
   letterboxed. `og-card.png` is 1200x630.

The DC mark is redrawn here with the same geometry as the header SVG rather
than traced from a bitmap, so the two cannot drift apart silently.

Needs `fonttools` to read the site's own Archivo woff2 (deliberately NOT in
requirements.txt - this is a one-off asset build, not something the app does at
runtime). Falls back to a system grotesk with a warning if it is missing.

Usage:
    py -m pip install fonttools
    py scripts/build_brand_images.py
"""
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "app" / "static" / "icons"
FONTS = ROOT / "app" / "static" / "fonts"

# Straight off the site's own tokens (app/static/style.css).
INK = (9, 14, 21)          # --bg
SURFACE = (16, 25, 36)     # --surface
GOLD = (245, 158, 11)      # --gold
WHITE = (241, 245, 249)    # --fg
MUTED = (148, 163, 184)    # --muted


def load_font(weight, size):
    """The site's own Archivo, via fonttools, or a system grotesk if it is not
    installed. Never silently substitutes without saying so."""
    woff = FONTS / f"archivo-{weight}.woff2"
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(woff)
        f.flavor = None
        buf = io.BytesIO()
        f.save(buf)
        buf.seek(0)
        return ImageFont.truetype(buf, size)
    except ImportError:
        print("  ! fonttools not installed - falling back to a system font, so the "
              "wordmark will not be Archivo. pip install fonttools for the real thing.")
        for name in ("segoeuib.ttf", "arialbd.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()


def draw_mark(img, cx, cy, size, stroke):
    """The DC monogram: a gold D, a white C, and a gold dot.

    Same geometry as the 32x32 SVG in base.html, scaled - the header path is
    `M7 8h6a7 7 0 0 1 0 14H7V8z` for the D, an arc from (25,10) for the C, and
    a dot at (21,7) r1.5.
    """
    d = ImageDraw.Draw(img)
    u = size / 32.0  # one SVG unit

    def px(x, y):
        return (cx - size / 2 + x * u, cy - size / 2 + y * u)

    w = max(2, int(stroke))

    # D - vertical stem plus a bowl.
    x0, y0 = px(7, 8)
    x1, y1 = px(7, 22)
    d.line([x0, y0, x1, y1], fill=GOLD, width=w)
    bowl = [*px(6, 8), *px(20, 22)]
    d.arc(bowl, start=-90, end=90, fill=GOLD, width=w)
    d.line([*px(7, 8), *px(13, 8)], fill=GOLD, width=w)
    d.line([*px(7, 22), *px(13, 22)], fill=GOLD, width=w)

    # C - an open arc, deliberately in white so the two letters separate.
    c_box = [*px(17, 8), *px(31, 22)]
    d.arc(c_box, start=35, end=325, fill=WHITE, width=max(2, int(w * 0.88)))

    # The dot.
    r = 1.6 * u
    dx, dy = px(21, 7)
    d.ellipse([dx - r, dy - r, dx + r, dy + r], fill=GOLD)


# Pillow has no antialiasing on arcs or thick strokes, so everything is drawn
# at 4x and resampled down. Without it the D's bowl is visibly stepped at any
# size an app icon is actually shown at.
SS = 4


def build_icon(size, path, rounded=True, bg=INK):
    """A square app icon. Flat RGB - see the module docstring."""
    big = size * SS
    img = Image.new("RGB", (big, big), bg)
    if rounded:
        d = ImageDraw.Draw(img)
        pad = big * 0.06
        d.rounded_rectangle(
            [pad, pad, big - pad, big - pad],
            radius=big * 0.20, outline=GOLD, width=max(2, int(big * 0.012)),
        )
    draw_mark(img, big / 2, big / 2, big * 0.58, stroke=big * 0.055)
    img = img.resize((size, size), Image.LANCZOS)
    img.save(path, format="PNG", optimize=True)
    print(f"  {path.relative_to(ROOT)}  {size}x{size} RGB")


def build_og_card(path):
    """1200x630 - the ratio WhatsApp, Facebook and Slack all render without
    cropping. A 512 square gets letterboxed or centre-cropped by each of them
    differently, which is how you end up with a preview nobody designed."""
    W, H = 1200, 630
    # The whole card is drawn at SS and resampled once. Compositing a
    # separately-downsampled mark onto a full-size canvas left a visible seam
    # where its bounding box crossed the panel edge.
    img = Image.new("RGB", (W * SS, H * SS), INK)
    d = ImageDraw.Draw(img)

    # A quiet panel so the card is not a flat rectangle, and a gold rule that
    # matches the underline the site puts beneath every h1.
    d.rectangle([64 * SS, 64 * SS, (W - 64) * SS, (H - 64) * SS], fill=SURFACE)

    draw_mark(img, 190 * SS, (H / 2 - 26) * SS, 190 * SS, stroke=11 * SS)

    title = load_font(800, 78 * SS)
    sub = load_font(700, 31 * SS)
    tag = load_font(700, 25 * SS)

    x = 320 * SS
    d.text((x, 214 * SS), "DC Show Tracker", font=title, fill=WHITE)
    d.line([x, 316 * SS, x + 96 * SS, 316 * SS], fill=GOLD, width=5 * SS)
    d.text((x, 344 * SS), "Irish amateur musical theatre", font=sub, fill=GOLD)
    d.text((x, 392 * SS), "Show history, upcoming productions", font=tag, fill=MUTED)
    d.text((x, 428 * SS), "and the AIMS awards archive", font=tag, fill=MUTED)

    img = img.resize((W, H), Image.LANCZOS)
    img.save(path, format="PNG", optimize=True)
    print(f"  {path.relative_to(ROOT)}  {W}x{H} RGB")


def main():
    if not ICONS.exists():
        print(f"No {ICONS} - run this from a checkout.", file=sys.stderr)
        return 1

    print("Writing brand images (flat RGB, no alpha):")
    build_og_card(ICONS.parent / "og-card.png")
    build_icon(512, ICONS / "icon-512.png")
    build_icon(192, ICONS / "icon-192.png")
    build_icon(180, ICONS / "apple-touch-icon.png")
    # Maskable icons are cropped to a circle by Android, so no border and the
    # mark sits inside the 80% safe zone.
    img = Image.new("RGB", (512 * SS, 512 * SS), INK)
    draw_mark(img, 256 * SS, 256 * SS, 512 * SS * 0.46, stroke=512 * SS * 0.045)
    img = img.resize((512, 512), Image.LANCZOS)
    img.save(ICONS / "icon-maskable-512.png", format="PNG", optimize=True)
    print(f"  {(ICONS / 'icon-maskable-512.png').relative_to(ROOT)}  512x512 RGB (maskable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
