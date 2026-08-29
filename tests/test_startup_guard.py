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


def test_only_db_free_endpoints_skip_the_derived_table_check(app):
    """2026-08-29. A code review suggested exempting every feeds.* endpoint
    from keep_derived_tables_current(). That would be wrong: /sitemap.xml
    reads productions AND venues, and calendar.ics and export/shows.csv both
    open the database - exempting the blueprint wholesale would serve a stale
    sitemap after an import. Only the three that touch no data are exempt.
    """
    from app import NO_DB_ENDPOINTS

    assert "feeds.sitemap_xml" not in NO_DB_ENDPOINTS
    assert "feeds.calendar_ics" not in NO_DB_ENDPOINTS
    assert "feeds.export_shows_csv" not in NO_DB_ENDPOINTS
    assert {"static", "feeds.robots_txt", "feeds.manifest", "feeds.service_worker"} <= NO_DB_ENDPOINTS


def test_the_sitemap_still_reflects_a_fresh_import(client, db):
    """The guard the exemption above must not break: a title added straight to
    the database appears in the sitemap on the next request, because
    /sitemap.xml still gets its productions rebuild."""
    db.execute(
        "INSERT INTO societies (id, name, region, section) VALUES (700, 'Sitemap Society', 'Eastern', 'Gilbert')"
    )
    db.execute(
        "INSERT INTO historical_results (year, tier, category_name, result, show, society_name, society_id, source) "
        "VALUES (2019, 'Gilbert', 'Best Overall Show', 'Nominee', 'Freshly Imported', 'Sitemap Society', 700, 'manual')"
    )
    db.commit()

    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "Freshly%20Imported" in body or "Freshly Imported" in body
