"""Pageviews are recorded per day and split into people vs bots.

page_views on its own is one running counter per path since tracking started,
which cannot answer either question actually asked of it: is the site growing,
and how much of this is a crawler. That mattered concretely - /shows/<id> looked
like the busiest section of the site when 955 of those paths had been hit
exactly twice each by a sitemap sweep, and a product decision was nearly taken
off that number (2026-09-06).
"""
from app import analytics
from conftest import seed_user

BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def test_a_real_browser_is_not_a_bot():
    assert analytics.is_bot(BROWSER) is False
    assert analytics.is_bot(IPHONE) is False


def test_known_crawlers_are_bots():
    for ua in [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
        "facebookexternalhit/1.1",
        "python-requests/2.31.0",
        "curl/8.4.0",
        "Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/120.0.0.0",
    ]:
        assert analytics.is_bot(ua) is True, ua


def test_a_missing_user_agent_counts_as_a_bot():
    """Every real browser sends one; a blank UA is a script that did not bother."""
    assert analytics.is_bot(None) is True
    assert analytics.is_bot("") is True


def test_bot_matching_ignores_case():
    assert analytics.is_bot("SomeCrawler/1.0") is True


def test_a_view_lands_on_the_right_side_of_the_split(client, db):
    client.get("/", headers={"User-Agent": BROWSER})
    client.get("/", headers={"User-Agent": "Googlebot/2.1"})
    client.get("/", headers={"User-Agent": BROWSER})

    rows = dict(
        db.execute(
            "SELECT is_bot, views FROM page_views_daily WHERE path = '/'"
        ).fetchall()
    )
    assert rows[0] == 2
    assert rows[1] == 1


def test_the_all_time_counter_still_counts_everything(client, db):
    """page_views is deliberately left unfiltered so its totals stay comparable
    with every figure quoted before the split existed."""
    client.get("/", headers={"User-Agent": BROWSER})
    client.get("/", headers={"User-Agent": "Googlebot/2.1"})

    total = db.execute("SELECT views FROM page_views WHERE path = '/'").fetchone()[0]
    assert total == 2


def test_repeat_views_accumulate_on_one_row_per_day(client, db):
    for _ in range(3):
        client.get("/season", headers={"User-Agent": BROWSER})

    rows = db.execute(
        "SELECT day, views FROM page_views_daily WHERE path = '/season' AND is_bot = 0"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["views"] == 3


def test_excluded_paths_are_purged_from_the_daily_table_too(client, db):
    """purge_excluded_pageviews cleaned page_views only; a path excluded after
    the fact would otherwise keep its daily rows on the Traffic page forever."""
    db.execute(
        "INSERT INTO page_views_daily (path, day, is_bot, views) "
        "VALUES ('/static/style.css', '2026-09-01', 0, 40)"
    )
    db.commit()

    analytics.purge_excluded_pageviews(db)

    assert db.execute(
        "SELECT COUNT(*) FROM page_views_daily WHERE path = '/static/style.css'"
    ).fetchone()[0] == 0


def test_traffic_page_shows_the_split(client, db):
    seed_user(db, username="mod", password="password123")
    client.get("/", headers={"User-Agent": BROWSER})
    client.get("/", headers={"User-Agent": "Googlebot/2.1"})
    client.post("/admin/login", data={"username": "mod", "password": "password123"},
                follow_redirects=True)

    body = client.get("/admin/traffic").get_data(as_text=True)
    assert "views by people" in body
    assert "views by bots" in body
    # And it says what it can actually speak for, so the first fortnight after
    # deploy does not read as a collapse in traffic.
    assert "Daily figures start" in body


def test_traffic_page_survives_an_empty_daily_table(client, db):
    """The window is all zeros on the day this deploys - the chart must not
    divide by a busiest-day of zero."""
    seed_user(db, username="mod", password="password123")
    client.post("/admin/login", data={"username": "mod", "password": "password123"},
                follow_redirects=True)

    resp = client.get("/admin/traffic")
    assert resp.status_code == 200
    assert "Nothing recorded yet" in resp.get_data(as_text=True)
