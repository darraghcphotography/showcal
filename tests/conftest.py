import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
# The one-off and enrichment scripts moved out of the repo root into
# scripts/<group>/ on 2026-08-29. A couple of them hold logic worth testing
# directly (classify_venue_types.classify), so their directories stay
# importable by module name rather than every such test hand-rolling a path.
for _group in ("backfills", "enrichment", "maintenance"):
    sys.path.insert(0, str(_ROOT / "scripts" / _group))

from app import create_app
from app.db import get_db


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    })
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()
        get_db().commit()


def seed_society(db, id=1, name="Test Society", region="Eastern", section="Gilbert"):
    db.execute(
        "INSERT INTO societies (id, name, region, section) VALUES (?, ?, ?, ?)",
        (id, name, region, section),
    )
    db.commit()
    return id


def seed_user(db, username="mod", password="password123", role="moderator"):
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), role),
    )
    db.commit()
    return db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]


def seed_invite_code(db, code="AIMS-TEST01", society_id=None):
    db.execute(
        "INSERT INTO invite_codes (code, society_id) VALUES (?, ?)",
        (code, society_id),
    )
    db.commit()
    return db.execute("SELECT id FROM invite_codes WHERE code = ?", (code,)).fetchone()["id"]
