"""T2 (small-items queue): requirements-dev.txt pulled in requirements.txt's
Pillow==12.3.0 via -r, then re-pinned it to Pillow==11.1.0 - so the test
suite (which exercises the upload decoder) never actually ran against the
version production installs. Guards against the dev pin coming back."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pillow_pin(path):
    for line in path.read_text().splitlines():
        if line.strip().lower().startswith("pillow"):
            return line.strip()
    return None


def test_dev_requirements_does_not_repin_pillow():
    assert _pillow_pin(REPO_ROOT / "requirements-dev.txt") is None
