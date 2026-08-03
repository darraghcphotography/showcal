"""The missing-db startup guard in app/__init__.py: AIMS_DB_PATH is only ever
set in Docker/production, so a missing database file there almost always
means the /data volume isn't mounted where the app expects it (the exact
failure mode that silently wiped the database once already - see
docs/deployment.md). The guard should warn loudly in that case, and stay
silent for local dev (no AIMS_DB_PATH) or when the file is genuinely there.
"""
import logging

from app import create_app


def test_warns_when_aims_db_path_set_and_file_missing(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("AIMS_DB_PATH", str(tmp_path / "aims.db"))
    db_path = tmp_path / "aims.db"

    with caplog.at_level(logging.WARNING):
        create_app({"DATABASE": str(db_path), "SECRET_KEY": "test-secret"})

    assert any("data volume isn't mounted" in r.message for r in caplog.records)


def test_no_warning_when_db_file_already_exists(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("AIMS_DB_PATH", str(tmp_path / "aims.db"))
    db_path = tmp_path / "aims.db"
    db_path.touch()

    with caplog.at_level(logging.WARNING):
        create_app({"DATABASE": str(db_path), "SECRET_KEY": "test-secret"})

    assert not any("data volume isn't mounted" in r.message for r in caplog.records)


def test_no_warning_in_local_dev_without_aims_db_path(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("AIMS_DB_PATH", raising=False)
    db_path = tmp_path / "aims.db"  # deliberately does not exist

    with caplog.at_level(logging.WARNING):
        create_app({"DATABASE": str(db_path), "SECRET_KEY": "test-secret"})

    assert not any("data volume isn't mounted" in r.message for r in caplog.records)
