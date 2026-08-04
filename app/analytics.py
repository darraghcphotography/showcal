EXCLUDED_PREFIXES = ("/static/", "/uploads/", "/admin/")
EXCLUDED_PATHS = {"/robots.txt", "/sitemap.xml", "/export/shows.csv", "/manifest.webmanifest"}


def should_track_path(path):
    return not path.startswith(EXCLUDED_PREFIXES) and path not in EXCLUDED_PATHS


def should_track(request):
    return request.method == "GET" and should_track_path(request.path)


def record_pageview(db, path):
    db.execute(
        """
        INSERT INTO page_views (path, views, last_viewed) VALUES (?, 1, datetime('now'))
        ON CONFLICT(path) DO UPDATE SET views = views + 1, last_viewed = datetime('now')
        """,
        (path,),
    )
    db.commit()


def purge_excluded_pageviews(db):
    """Delete any already-recorded page_views for a path that's since been
    added to EXCLUDED_PATHS/EXCLUDED_PREFIXES - otherwise a path excluded
    today (e.g. /manifest.webmanifest) keeps whatever count it accumulated
    before the exclusion existed, forever, on the Traffic page. Called once
    at startup (see app/__init__.py) - cheap, and safe to run every time."""
    rows = db.execute("SELECT path FROM page_views").fetchall()
    stale = [r["path"] for r in rows if not should_track_path(r["path"])]
    if stale:
        db.executemany("DELETE FROM page_views WHERE path = ?", [(p,) for p in stale])
        db.commit()
