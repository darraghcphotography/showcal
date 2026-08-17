"""One-off generator for the PWA/home-screen icons under app/static/icons/,
redrawing the exact brand mark from app/static/favicon.svg (a 32x32 viewBox)
at higher resolution with Pillow. Nothing at runtime depends on Pillow -
only re-run this manually if the brand mark itself ever changes:

    py generate_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

RED = (200, 16, 46)    # #c8102e - the site's brand red
GOLD = (220, 184, 79)  # #dcb84f - the site's brand gold

OUT_DIR = Path(__file__).parent / "app" / "static" / "icons"

# Geometry copied straight from favicon.svg's 32x32 viewBox (the red circle
# itself is skipped - every icon here uses a solid square background
# instead, see _icon() below).
FLAG_LEFT = [(6, 5), (15, 5), (7, 14)]
FLAG_RIGHT = [(26, 5), (17, 5), (25, 14)]
CHECK_LINE = [(8, 27), (13, 22), (17, 24), (24, 16)]
DOT_CENTER = (24, 16)
DOT_R = 1.8
STROKE_W = 2.2


def _scaled(points, scale, offset):
    return [(x * scale + offset[0], y * scale + offset[1]) for x, y in points]


def _draw_mark(draw, scale, offset):
    draw.polygon(_scaled(FLAG_LEFT, scale, offset), fill=GOLD)
    draw.polygon(_scaled(FLAG_RIGHT, scale, offset), fill=GOLD)

    line = _scaled(CHECK_LINE, scale, offset)
    draw.line(line, fill=GOLD, width=round(STROKE_W * scale), joint="curve")
    # draw.line() doesn't round the two end caps the way joint="curve" rounds
    # internal joints - add them by hand to match the SVG's stroke-linecap.
    r = STROKE_W * scale / 2
    for x, y in (line[0], line[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=GOLD)

    cx, cy = offset[0] + DOT_CENTER[0] * scale, offset[1] + DOT_CENTER[1] * scale
    r = DOT_R * scale
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD)


def _icon(size, content_scale=1.0):
    """A solid red square (never transparent - iOS treats transparent PNG
    corners as black, and a solid background is also what guarantees an
    Android mask can never crop into empty space) with the gold mark drawn
    at content_scale of the canvas, centered."""
    img = Image.new("RGB", (size, size), RED)
    draw = ImageDraw.Draw(img)
    scale = size * content_scale / 32
    offset = ((size - 32 * scale) / 2, (size - 32 * scale) / 2)
    _draw_mark(draw, scale, offset)
    return img


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # "any" manifest icons - full-bleed, matching favicon.svg's own margins.
    _icon(192).save(OUT_DIR / "icon-192.png")
    _icon(512).save(OUT_DIR / "icon-512.png")

    # Maskable manifest icon - mark shrunk to ~70% so it stays inside
    # Android's ~80% safe zone regardless of which mask shape a launcher
    # applies (circle, squircle, rounded square, ...).
    _icon(512, content_scale=0.7).save(OUT_DIR / "icon-maskable-512.png")

    # Apple touch icon - iOS rounds the corners itself, so this must be a
    # plain, fully opaque square (never pre-rounded). Reuses the maskable
    # shrink for the same safe-margin reasoning.
    _icon(180, content_scale=0.7).save(OUT_DIR / "apple-touch-icon.png")

    print(f"Wrote icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png to {OUT_DIR}")


if __name__ == "__main__":
    main()
