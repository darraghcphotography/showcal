"""Round 3: the homepage keeps its poster gallery + Upcoming Shows content
(explicitly NOT replaced by a teaser - see index.html), "Browse societies"
moves out to its own /societies page, the nav is rebuilt around what
users actually asked for, and the site is rebranded to "DC Show Tracker".

"Submit a show" is deliberately absent from the nav/homepage for anonymous
visitors - it only appears once a society is logged in, pointing straight
at their own live add-show page, not the separate one-off/moderation-queue
flow (see base.html/index.html for why)."""
from conftest import seed_invite_code, seed_society


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def test_suggestions_banner_appears_near_the_top(client):
    """19 Aug 2026 feedback: the "please suggest it" prompt used to be the
    very last thing on the page, below Upcoming Shows and Recently
    Shipped - easy to miss. Moved up next to the existing top banner."""
    body = client.get("/").get_data(as_text=True)
    suggest_pos = body.index("Please suggest it")
    heading_pos = body.index("<h1>DC Show Tracker</h1>")
    assert suggest_pos < heading_pos


def test_societies_page_lists_and_filters_societies(client, db):
    seed_society(db, id=1, name="Eastern Soc", region="Eastern")
    seed_society(db, id=2, name="Western Soc", region="Western")
    db.commit()

    resp = client.get("/societies")
    body = resp.get_data(as_text=True)
    assert "Eastern Soc" in body and "Western Soc" in body

    resp = client.get("/societies?region=Eastern")
    body = resp.get_data(as_text=True)
    assert "Eastern Soc" in body
    assert "Western Soc" not in body


def test_homepage_no_longer_lists_societies(client, db):
    seed_society(db, id=1, name="Some Society", region="Eastern")
    db.commit()

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert "Some Society" not in body
    assert "Browse all societies" in body  # link out instead


def test_homepage_keeps_upcoming_shows_and_poster_gallery(client, db):
    society_id = seed_society(db, id=1, name="Test Soc", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, poster_filename) "
        "VALUES (?, '26/27', 'Eastern', 'Chicago', '2026-09-01', '2026-09-05', 'poster.jpg')",
        (society_id,),
    )
    db.commit()

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert "Upcoming shows" in body
    assert "Chicago" in body
    assert 'alt="Chicago poster"' in body


def test_homepage_shows_changelog_teaser(client, db):
    db.execute("INSERT INTO changelog_entries (entry) VALUES ('Shipped the new roadmap page.')")
    db.commit()

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert "Shipped the new roadmap page." in body


def test_submit_cta_hidden_for_anonymous_visitors(client, db):
    body = client.get("/").get_data(as_text=True)
    assert "Don't see your show listed?" not in body


def test_submit_cta_shown_for_logged_in_society_and_points_to_own_dashboard(client, db):
    society_id = seed_society(db)
    code_id = seed_invite_code(db, code="golden-heron", society_id=society_id)
    unlock_society(client, code_id)

    body = client.get("/").get_data(as_text=True)
    assert "Don't see your show listed?" in body
    assert 'href="/society/shows/new"' in body


def test_nav_matches_new_arrangement(client):
    """The header is Home plus two grouped menus (23 Aug 2026). The flat row
    of seven links wrapped at ordinary widths and had no room for Venues or
    Adjudicators, which is why both were footer-only and nobody found them."""
    body = client.get("/").get_data(as_text=True)
    header = body.split("</header>")[0]
    footer = body.split("<footer")[1]

    assert ">Home</a>" in header
    # The menu triggers, specifically - not just the words appearing somewhere.
    for label in ["Explore", "History"]:
        assert '{}<span class="nav-chevron"'.format(label) in header

    # Promoted out of the footer and into Explore.
    for label in ["Societies", "Venues", "Reviews", "Adjudicators"]:
        assert label in header
    for label in ["Awards", "Decades", "Statistics"]:
        assert label in header

    # Demoted to the footer, Darragh's call - the header carries what people
    # arrive looking for, the footer keeps everything reachable.
    for label in ["All Shows", "Seasons"]:
        assert label not in header
        assert label in footer

    # "/" IS the upcoming-productions list, and the brand logo already links
    # there - a third link to the same page earns nothing.
    assert "Upcoming shows" not in header
    assert "Upcoming Productions" not in header

    # "Submit a show" is deliberately not a standalone nav destination anymore
    assert "Submit a show" not in header
    assert "Submit a show" not in footer

    # 19 Aug 2026: "Season Archive" (header) vs "This season" (mobile tab bar)
    # read as opposite meanings for the same page - one name everywhere now.
    assert "Season Archive" not in header

    assert "Suggest a feature" not in header
    assert "Suggest a feature" in footer
    assert "Roadmap" in footer


def test_every_public_destination_is_still_reachable(client):
    """Regrouping the nav must not quietly strip a destination. Each of these
    was reachable from the chrome before the restructure and has to stay so,
    from the header, the footer, or /more."""
    chrome = client.get("/").get_data(as_text=True) + client.get("/more").get_data(as_text=True)
    for path in [
        "/", "/societies", "/titles", "/awards", "/stats", "/stats/trends",
        "/season", "/reviews", "/venues", "/adjudicators", "/about",
        "/suggest", "/suggestions",
    ]:
        assert 'href="{}"'.format(path) in chrome, "{} is no longer linked anywhere".format(path)


def test_the_menus_work_without_javascript(client):
    """The menus are native <details>, so they open and close on their own.
    The script only adds close-on-outside-click and Escape - if that's the
    only thing holding the nav together, the nav is broken for anyone whose
    JS hasn't loaded."""
    nav = client.get("/").get_data(as_text=True).split('<nav aria-label="Main">')[1].split("</nav>")[0]
    assert nav.count("<details") == 2
    assert "<summary" in nav
    assert "<script" not in nav


def test_site_is_rebranded(client):
    body = client.get("/").get_data(as_text=True)
    assert "DC Show Tracker" in body
    assert "Unofficial AIMS Show Tracker" not in body


def test_404_page_links_to_societies_list(client):
    resp = client.get("/this-page-does-not-exist")
    assert resp.status_code == 404
    assert '/societies"' in resp.get_data(as_text=True)
