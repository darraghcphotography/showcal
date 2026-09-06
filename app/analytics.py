EXCLUDED_PREFIXES = ("/static/", "/uploads/", "/admin/")
EXCLUDED_PATHS = {"/robots.txt", "/sitemap.xml", "/export/shows.csv", "/manifest.webmanifest"}

# Substrings that mark a user agent as a crawler, monitor or scripted fetch
# rather than a person. Matched case-insensitively against the whole UA string.
#
# This is a heuristic and it is worth being honest about what it does and does
# not catch. It catches every crawler that identifies itself, which - going by
# the traffic we already have - is most of ours: 955 /shows/<id> paths sat at
# exactly two views each, the signature of a well-behaved bot working through
# sitemap.xml. It does not catch anything that deliberately poses as a browser,
# and it never will, so read the "people" column as an upper bound with the
# obvious rubbish removed, not as a verified human count.
BOT_UA_MARKERS = (
    # Generic self-identification - covers the long tail of small crawlers.
    "bot", "crawl", "spider", "slurp", "scrape",
    # Search and AI crawlers big enough to matter to us by name.
    "bingpreview", "applebot", "yandex", "baidu", "duckduckbot", "gptbot",
    "ccbot", "bytespider", "facebookexternalhit", "meta-externalagent",
    "whatsapp", "ahrefs", "semrush", "mj12", "dotbot", "dataforseo",
    "serpstat", "screaming frog",
    # Scripted fetches and headless browsers.
    "python-requests", "python-urllib", "httpx", "aiohttp", "go-http-client",
    "java/", "okhttp", "curl/", "wget", "scrapy", "headlesschrome", "phantomjs",
    "puppeteer", "playwright", "lighthouse",
    # Uptime/monitoring pollers, which hit the same page forever.
    "uptimerobot", "pingdom", "statuscake", "site24x7", "newrelic", "datadog",
    # Feed readers - not a person browsing, and they poll on a timer.
    "feedfetcher", "feedly", "rss",
)


def is_bot(user_agent):
    """True if this user agent looks like a crawler rather than a person.

    A missing or empty user agent counts as a bot: every real browser sends
    one, so a blank UA is a script that did not bother."""
    if not user_agent:
        return True
    ua = user_agent.lower()
    return any(marker in ua for marker in BOT_UA_MARKERS)


def should_track_path(path):
    return not path.startswith(EXCLUDED_PREFIXES) and path not in EXCLUDED_PATHS


def should_track(request):
    return request.method == "GET" and should_track_path(request.path)


def record_pageview(db, path, user_agent=None):
    """Record one view of `path`, in both the all-time counter and the daily
    split. `user_agent` decides which side of the bot split the daily row lands
    on; page_views itself still counts everything, so its totals stay directly
    comparable with every figure quoted before this table existed."""
    db.execute(
        """
        INSERT INTO page_views (path, views, last_viewed) VALUES (?, 1, datetime('now'))
        ON CONFLICT(path) DO UPDATE SET views = views + 1, last_viewed = datetime('now')
        """,
        (path,),
    )
    db.execute(
        """
        INSERT INTO page_views_daily (path, day, is_bot, views)
        VALUES (?, date('now'), ?, 1)
        ON CONFLICT(path, day, is_bot) DO UPDATE SET views = views + 1
        """,
        (path, 1 if is_bot(user_agent) else 0),
    )
    db.commit()


def purge_excluded_pageviews(db):
    """Delete any already-recorded page_views for a path that's since been
    added to EXCLUDED_PATHS/EXCLUDED_PREFIXES - otherwise a path excluded
    today (e.g. /manifest.webmanifest) keeps whatever count it accumulated
    before the exclusion existed, forever, on the Traffic page. Called once
    at startup (see app/__init__.py) - cheap, and safe to run every time.

    Paths are read from both tables rather than page_views alone: the two are
    written together now, but a row can outlive its twin (page_views is pruned
    by hand from time to time, and the daily table only goes back as far as the
    deploy that added it), and a path this misses is never revisited."""
    rows = db.execute(
        """
        SELECT path FROM page_views
        UNION
        SELECT path FROM page_views_daily
        """
    ).fetchall()
    stale = [r["path"] for r in rows if not should_track_path(r["path"])]
    if stale:
        db.executemany("DELETE FROM page_views WHERE path = ?", [(p,) for p in stale])
        db.executemany("DELETE FROM page_views_daily WHERE path = ?", [(p,) for p in stale])
        db.commit()
