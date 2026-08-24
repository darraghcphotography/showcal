"""save_poster resizes/re-encodes to WebP on the way in (app/uploads.py) -
measured 2026-08-24: posters were serving at original upload size, one alone
1.36MB rendered 54px wide on the homepage. Covers the real resize path with
actual image bytes (no existing test exercised that before this), and the
error path for a file that isn't a real image.

Also covers HEIC/HEIF - a real phone upload to /submit/photo failed outright
(2026-08-24) because iPhones save camera photos in that format by default,
which wasn't accepted at all, and isn't renderable by any browser even where
it is accepted - both save functions now convert it to something every
browser can display."""
import io

from PIL import Image
from werkzeug.datastructures import FileStorage

from app.uploads import MAX_POSTER_DIMENSION, save_photo_submission, save_poster


def _fake_image_file(name="poster.jpg", size=(1200, 1800), fmt="JPEG"):
    buf = io.BytesIO()
    Image.new("RGB", size, color=(200, 50, 50)).save(buf, format=fmt)
    buf.seek(0)
    return FileStorage(stream=buf, filename=name)


def test_save_poster_downscales_and_converts_to_webp(tmp_path):
    filename = save_poster(_fake_image_file(size=(1200, 1800)), str(tmp_path))
    assert filename.endswith(".webp")
    with Image.open(tmp_path / filename) as img:
        assert max(img.size) <= MAX_POSTER_DIMENSION


def test_save_poster_never_upscales_a_small_image(tmp_path):
    filename = save_poster(_fake_image_file(size=(100, 150)), str(tmp_path))
    with Image.open(tmp_path / filename) as img:
        assert img.size == (100, 150)


def test_save_poster_rejects_a_corrupt_file(tmp_path):
    bad_file = FileStorage(stream=io.BytesIO(b"not actually an image"), filename="poster.jpg")
    try:
        save_poster(bad_file, str(tmp_path))
        assert False, "expected ValueError"
    except ValueError as e:
        assert "doesn't look like a valid image" in str(e)


def test_save_poster_returns_none_with_no_file(tmp_path):
    assert save_poster(None, str(tmp_path)) is None


def test_save_photo_submission_keeps_original_size_and_format(tmp_path):
    filename = save_photo_submission(_fake_image_file(size=(2000, 3000)), str(tmp_path))
    assert filename.endswith(".jpg")
    with Image.open(tmp_path / filename) as img:
        assert img.size == (2000, 3000)


def test_save_poster_accepts_heic_and_converts_to_webp(tmp_path):
    filename = save_poster(_fake_image_file(name="IMG_1234.HEIC", size=(1200, 1800), fmt="HEIF"), str(tmp_path))
    assert filename.endswith(".webp")
    with Image.open(tmp_path / filename) as img:
        assert max(img.size) <= MAX_POSTER_DIMENSION


def test_save_photo_submission_accepts_heic_and_converts_to_jpeg(tmp_path):
    filename = save_photo_submission(
        _fake_image_file(name="IMG_1234.heic", size=(2000, 3000), fmt="HEIF"), str(tmp_path)
    )
    assert filename.endswith(".jpg")
    with Image.open(tmp_path / filename) as img:
        assert img.format == "JPEG"
        assert img.size == (2000, 3000)  # full resolution, not resized
