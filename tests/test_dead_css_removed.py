"""V5 (small-items queue): .poster-gallery and its friends in style.css were
referenced only from an abandoned worktree, nowhere in the main tree - dead
weight in the file R8 (a separate, not-in-this-queue item) is about."""
from pathlib import Path

STYLE_CSS = Path(__file__).resolve().parent.parent / "app" / "static" / "style.css"


def test_poster_gallery_css_is_gone():
    assert ".poster-gallery" not in STYLE_CSS.read_text()
