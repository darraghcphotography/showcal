import io
import os
import uuid

import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()

# iPhones (and many Androids) save camera photos as HEIC/HEIF by default -
# accepted here even though no browser renders it directly (found 2026-08-24:
# a real phone upload to /submit/photo failed outright), so both save
# functions below always convert it to something every browser can display.
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "heic", "heif"}

# Posters render at most 240 CSS px wide anywhere on the site (.poster, the
# show-detail hero and the poster gallery - see style.css) - 600px comfortably
# covers that at 2x/retina in either orientation. Measured 2026-08-24: posters
# were serving at original upload size, one alone 1.36MB rendered 54px wide on
# the homepage - this is the actual fix, not lazy-loading or pagination.
MAX_POSTER_DIMENSION = 600
WEBP_QUALITY = 82
JPEG_QUALITY = 90


def _extension(filename):
    if "." not in filename:
        return None
    return filename.rsplit(".", 1)[1].lower()


def _open_image(fileobj):
    """Image.open, but HEIC/HEIF is decoded via pillow_heif's registered
    opener - stock Pillow can't read it at all without this."""
    fileobj.seek(0)
    return Image.open(fileobj)


def _resized_webp_bytes(fileobj, ext):
    """Downscales an image to fit MAX_POSTER_DIMENSION and re-encodes it as
    WebP, returning (bytes, 'webp'). Never upscales - a poster already
    smaller than the bound is only re-encoded, not enlarged.

    Animated GIFs are returned unchanged as ('gif' passthrough) - re-encoding
    would need per-frame handling Pillow doesn't do for free, and a real
    theatre poster is never animated, so it's not worth the complexity for
    what amounts to a hypothetical case.
    """
    img = _open_image(fileobj)
    if ext == "gif" and getattr(img, "is_animated", False):
        fileobj.seek(0)
        return fileobj.read(), "gif"

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if img.mode in ("P", "LA") and "transparency" in img.info else "RGB")
    img.thumbnail((MAX_POSTER_DIMENSION, MAX_POSTER_DIMENSION), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY)
    return buf.getvalue(), "webp"


# The real image formats we'll store, mapped to the extension we save them
# under. Keyed on what Pillow actually decoded, never on the uploaded
# filename - see _viewable_bytes.
_PASSTHROUGH_FORMATS = {"jpeg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}


def _viewable_bytes(fileobj):
    """Passes a browser-renderable format straight through unchanged; a
    HEIC/HEIF source (no browser renders that directly - see ALLOWED_
    EXTENSIONS) is re-encoded to full-resolution JPEG instead, no resizing,
    so a moderator can actually see it in the admin queue.

    The passthrough branch still decodes the file first even though it then
    discards the decoded image and writes the original bytes. That decode is
    the only thing standing between a moderator and an arbitrary file: unlike
    save_poster (where the resize re-encodes, so a lie about the format can't
    survive), nothing here would otherwise look inside the file at all, and a
    filename extension is a claim by the uploader rather than evidence. Without
    it, HTML or SVG named .jpg is stored and later served into the admin queue.

    Dispatch is on the format Pillow actually decoded, not the claimed
    extension, so a mislabelled-but-genuine image (a HEIC shot named .jpg, a
    PNG saved as .jpeg - both common straight off a phone) is saved correctly
    under its real extension instead of being rejected.
    """
    img = _open_image(fileobj)
    img.load()  # force a full decode; truncated or non-image data raises here
    fmt = (img.format or "").lower()

    if fmt in _PASSTHROUGH_FORMATS:
        fileobj.seek(0)
        return fileobj.read(), _PASSTHROUGH_FORMATS[fmt]
    if fmt not in ("heif", "heic"):
        raise ValueError("Unsupported image format: %s" % (img.format or "unknown"))

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if img.mode == "RGBA":
        img = img.convert("RGB")  # JPEG has no alpha channel
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue(), "jpg"


def save_poster(file_storage, upload_dir):
    """Save an uploaded poster under a random filename (never the browser-supplied
    one - avoids path traversal and collisions) and return that filename, or
    None if no file was actually chosen. Resized and re-encoded as WebP on the
    way in (see _resized_webp_bytes) - the saved filename's extension reflects
    that, not whatever was uploaded.

    Raises ValueError with a user-facing message on an unsupported type.
    """
    if not file_storage or not file_storage.filename:
        return None

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Poster must be a JPG, PNG, WEBP, GIF, or HEIC image.")

    try:
        data, out_ext = _resized_webp_bytes(file_storage.stream, ext)
    except Exception:
        # A real theatre poster is a real JPEG/PNG. This only fires on a
        # corrupt file or a wrong-extension upload (a renamed .txt, a broken
        # download) - Pillow's own exception types vary by what's wrong, so
        # catching broadly and turning it into the same user-facing error as
        # an unsupported type (rather than a 500) is the right trade here.
        raise ValueError("That file doesn't look like a valid image - try a different one.")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{out_ext}"
    with open(os.path.join(upload_dir, filename), "wb") as f:
        f.write(data)
    return filename


def save_photo_submission(file_storage, upload_dir):
    """Same as save_poster, but required rather than optional - a photo
    submission with no file attached isn't a submission. Raises ValueError
    with a user-facing message either way.

    Not resized like save_poster - this is source material a moderator reads
    to fill in real data (extract_historical_reviews.py's kind of raw scan),
    not something rendered at a fixed on-page size, so downscaling it would
    only throw away detail a moderator might need to read (a name, a small
    print run credit). A HEIC/HEIF upload is still re-encoded to JPEG (see
    _viewable_bytes) - full resolution, format only - since no browser can
    display HEIC directly and the admin queue needs to actually show it.

    The extension check below is only a cheap early reject on an uploader's
    claim; _viewable_bytes is what actually proves the file is an image, and
    decides the extension it's saved under."""
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a photo to upload.")

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Photo must be a JPG, PNG, WEBP, GIF, or HEIC image.")

    try:
        data, out_ext = _viewable_bytes(file_storage.stream)
    except Exception:
        raise ValueError("That file doesn't look like a valid image - try a different one.")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{out_ext}"
    with open(os.path.join(upload_dir, filename), "wb") as f:
        f.write(data)
    return filename
