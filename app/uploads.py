import os
import uuid

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def _extension(filename):
    if "." not in filename:
        return None
    return filename.rsplit(".", 1)[1].lower()


def save_poster(file_storage, upload_dir):
    """Save an uploaded poster under a random filename (never the browser-supplied
    one - avoids path traversal and collisions) and return that filename, or
    None if no file was actually chosen.

    Raises ValueError with a user-facing message on an unsupported type.
    """
    if not file_storage or not file_storage.filename:
        return None

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Poster must be a JPG, PNG, WEBP, or GIF image.")

    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return filename


def save_photo_submission(file_storage, upload_dir):
    """Same as save_poster, but required rather than optional - a photo
    submission with no file attached isn't a submission. Raises ValueError
    with a user-facing message either way."""
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a photo to upload.")

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Photo must be a JPG, PNG, WEBP, or GIF image.")

    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return filename
