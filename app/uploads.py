import io
import os
import uuid

from PIL import Image

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

# Posters render at most 240 CSS px wide anywhere on the site (.poster, the
# show-detail hero and the poster gallery - see style.css) - 600px comfortably
# covers that at 2x/retina in either orientation. Measured 2026-08-24: posters
# were serving at original upload size, one alone 1.36MB rendered 54px wide on
# the homepage - this is the actual fix, not lazy-loading or pagination.
MAX_POSTER_DIMENSION = 600
WEBP_QUALITY = 82


def _extension(filename):
    if "." not in filename:
        return None
    return filename.rsplit(".", 1)[1].lower()


def _resized_webp_bytes(fileobj, ext):
    """Downscales an image to fit MAX_POSTER_DIMENSION and re-encodes it as
    WebP, returning (bytes, 'webp'). Never upscales - a poster already
    smaller than the bound is only re-encoded, not enlarged.

    Animated GIFs are returned unchanged as ('gif' passthrough) - re-encoding
    would need per-frame handling Pillow doesn't do for free, and a real
    theatre poster is never animated, so it's not worth the complexity for
    what amounts to a hypothetical case.
    """
    fileobj.seek(0)
    img = Image.open(fileobj)
    if ext == "gif" and getattr(img, "is_animated", False):
        fileobj.seek(0)
        return fileobj.read(), "gif"

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if img.mode in ("P", "LA") and "transparency" in img.info else "RGB")
    img.thumbnail((MAX_POSTER_DIMENSION, MAX_POSTER_DIMENSION), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY)
    return buf.getvalue(), "webp"


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
        raise ValueError("Poster must be a JPG, PNG, WEBP, or GIF image.")

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

    Deliberately NOT resized like save_poster - this is source material a
    moderator reads to fill in real data (extract_historical_reviews.py's
    kind of raw scan), not something rendered at a fixed on-page size, so
    downscaling it would only throw away detail a moderator might need to
    read (a name, a small print run credit)."""
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a photo to upload.")

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Photo must be a JPG, PNG, WEBP, or GIF image.")

    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return filename
