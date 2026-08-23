"""The homepage leads with what's on, "Browse societies" lives on its own
/societies page, the nav is grouped rather than a flat row, and the site is
branded "DC Show Tracker".

Rebuilt 24 Aug 2026 around the site audit's bet 1: productions grouped by month
with their poster inline, the housekeeping notices moved below them, and the
whole page answering "what's on, where, when" before it explains itself.

"Submit a show" is still not a header destination for anonymous visitors - the
in-page CTA only appears once a society is logged in, pointing at their own live
add-show page rather than the one-off moderation-queue flow. It is in the
footer, though; see test_nav_matches_new_arrangement for why that changed."""
from conftest import seed_invite_code, seed_society


def unlock_society(client, code_id):
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id


def test_housekeeping_notices_sit_below_the_listings_but_not_last(client):
    """Both notices used to sit above the site's own title, so a first-time
    visitor read two pieces of admin before seeing a single production (site
    audit, finding 04). They're now below the listings.

    Deliberately a middle position, not a revert: 19 Aug 2026 feedback was that
    the "please suggest it" prompt was easy to miss as the very last thing on
    the page, so it still sits above "Recently shipped" rather than going back
    to the bottom."""
    body = client.get("/").get_data(as_text=True)
    listings_pos = body.index("<h1>What's on</h1>")
    suggest_pos = body.index("Please suggest it")
    login_ask_pos = body.index("he'll issue you a login code")

    assert listings_pos < login_ask_pos
    assert listings_pos < suggest_pos


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


def test_homepage_lists_upcoming_shows_with_their_poster_inline(client, db):
    """The separate poster strip above the listings became a thumbnail on the
    production's own row (site audit, bet 1). The image is decorative there -
    the show's name is already a link to the same place right beside it - so it
    carries an empty alt rather than repeating the title to a screen reader."""
    society_id = seed_society(db, id=1, name="Test Soc", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date, poster_filename) "
        "VALUES (?, '26/27', 'Eastern', 'Chicago', '2099-09-01', '2099-09-05', 'poster.jpg')",
        (society_id,),
    )
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "What's on" in body
    assert "Chicago" in body
    assert "poster.jpg" in body
    assert 'class="whatson-poster"' in body


def test_a_show_without_a_poster_still_renders_a_full_row(client, db):
    """Only a handful of upcoming shows have a poster, so no poster is the
    normal case - the row must not look like it's missing something."""
    society_id = seed_society(db, id=1, name="Test Soc", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date) "
        "VALUES (?, '26/27', 'Eastern', 'Chess', '2099-09-01', '2099-09-05')",
        (society_id,),
    )
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "Chess" in body
    assert "Test Soc" in body
    assert 'class="whatson-poster"' not in body


def test_listings_are_grouped_by_month(client, db):
    society_id = seed_society(db, id=1, name="Test Soc", region="Eastern")
    for show, opening in (("Chicago", "2099-09-01"), ("Chess", "2099-10-04")):
        db.execute(
            "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date) "
            "VALUES (?, '26/27', 'Eastern', ?, ?, ?)",
            (society_id, show, opening, opening),
        )
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "September 2099" in body
    assert "October 2099" in body
    assert body.index("September 2099") < body.index("October 2099")


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

    # Explore, including Venues and Adjudicators, which were footer-only.
    for label in ["All Shows", "Seasons", "Societies", "Venues", "Reviews", "Adjudicators"]:
        assert label in header
    for label in ["Awards", "Decades", "Statistics"]:
        assert label in header

    # The footer keeps its sitemap links even where the header duplicates them.
    for label in ["All Shows", "Seasons"]:
        assert label in footer

    # "/" IS the upcoming-productions list, and the brand logo already links
    # there - a third link to the same page earns nothing.
    assert "Upcoming shows" not in header
    assert "Upcoming Productions" not in header

    # "Submit a show" stays out of the header, but is back in the footer as of
    # 24 Aug 2026. It had been removed from both on the reasoning that an
    # anonymous visitor shouldn't be pushed at the invite-code flow - but the
    # site audit (finding 02) found the consequence: /more is linked only from
    # the mobile bottom bar, so on a desktop browser there was no path to it at
    # all, and the main thing a committee is meant to do here was invisible on a
    # laptop. The unlock page itself says how to get a code, so it's a
    # reasonable landing point rather than a dead end. Darragh's call, 24 Aug.
    assert "Submit a show" not in header
    assert "Submit a show" in footer

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
