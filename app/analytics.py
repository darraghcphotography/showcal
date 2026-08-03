EXCLUDED_PREFIXES = ("/static/", "/uploads/", "/admin/")
EXCLUDED_PATHS = {"/robots.txt", "/sitemap.xml", "/export/shows.csv", "/manifest.webmanifest"}


def should_track(request):
    return (
        request.method == "GET"
        and not request.path.startswith(EXCLUDED_PREFIXES)
        and request.path not in EXCLUDED_PATHS
    )


def record_pageview(db, path):
    db.execute(
        """
        INSERT INTO page_views (path, views, last_viewed) VALUES (?, 1, datetime('now'))
        ON CONFLICT(path) DO UPDATE SET views = views + 1, last_viewed = datetime('now')
        """,
        (path,),
    )
    db.commit()
