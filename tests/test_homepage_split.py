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
    listings_pos = body.index("What's on</h1>")
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


def _seed_undated_poster_show(db, title="Chess"):
    society_id = seed_society(db, id=1, name="Test Soc", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, opening_date, closing_date) "
        "VALUES (?, '26/27', 'Eastern', ?, '2099-09-01', '2099-09-05')",
        (society_id, title),
    )
    db.commit()
    return society_id


def test_a_show_without_a_poster_gets_a_playbill(client, db):
    """No poster is the NORMAL case - 55 of 67 upcoming productions have none -
    so this box is most of what the homepage renders, and it must not look like
    something failed to load. It used to be two initials on a gradient; it is
    now a playbill set from the show's own title (2026-09-02)."""
    _seed_undated_poster_show(db)

    body = client.get("/").get_data(as_text=True)
    assert 'class="whatson-poster is-playbill"' in body

    # It has to carry real content, not just a nicer background.
    playbill = body[body.index("is-playbill"):body.index("whatson-body")]
    assert "Chess" in playbill
    assert "September 2099" in playbill


def test_the_playbill_does_not_repeat_the_card_body(client, db):
    """The first cut carried the society and the run dates on the playbill as
    well, which read fine in isolation and badly in place - the body repeats
    both a couple of centimetres below, so every card said everything twice.
    A poster's job here is to be the title; the body carries the facts."""
    _seed_undated_poster_show(db)

    body = client.get("/").get_data(as_text=True)
    playbill = body[body.index("is-playbill"):body.index("whatson-body")]

    assert "Test Soc" not in playbill
    assert "1–5 Sep" not in playbill and "Sep 2099" not in playbill
    # ...and the body still carries both, so nothing was lost.
    card_body = body[body.index("whatson-body"):]
    assert "Test Soc" in card_body
    assert "Sep 2099" in card_body


def test_the_add_a_poster_ask_is_not_shown_to_the_public(client, db):
    """A visitor has nothing to act on, and 55 of 67 cards carrying "add your
    poster" would advertise the gap rather than close it."""
    _seed_undated_poster_show(db)

    body = client.get("/").get_data(as_text=True)
    assert "Add your poster" not in body


def test_the_owning_society_does_see_the_add_a_poster_ask(client, db):
    """...but the committee member signed in and looking at their own show is
    exactly the person who can fix it."""
    from conftest import seed_invite_code

    society_id = _seed_undated_poster_show(db)
    code_id = seed_invite_code(db, code="AIMS-SOC001", society_id=society_id)
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id

    body = client.get("/").get_data(as_text=True)
    assert "Add your poster" in body


def test_another_society_does_not_see_the_ask_on_someone_elses_show(client, db):
    from conftest import seed_invite_code

    _seed_undated_poster_show(db)
    other_id = seed_society(db, id=2, name="Other Soc", region="Western")
    code_id = seed_invite_code(db, code="AIMS-SOC002", society_id=other_id)
    with client.session_transaction() as sess:
        sess["society_code_id"] = code_id

    body = client.get("/").get_data(as_text=True)
    assert "Add your poster" not in body


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


def test_homepage_does_not_print_the_changelog(client, db):
    """Changed 2026-08-29. The homepage used to end with a "Recently shipped"
    block listing the three most recent changelog entries. This is the page a
    member lands on to find out what is on; a release log is not that, and at
    its worst it printed developer wording about text comparisons and season
    strings. The Roadmap page carries it, and is linked from here instead."""
    db.execute("INSERT INTO changelog_entries (entry) VALUES ('Shipped the new roadmap page.')")
    db.commit()

    body = client.get("/").get_data(as_text=True)
    assert "Shipped the new roadmap page." not in body
    assert "Recently shipped" not in body
    # Still reachable in one click, just not inlined.
    assert "/suggestions" in body


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
    """The header is Home plus three grouped menus: What's On, Societies, Archive.
    Reorganized 3 Sep 2026 per the nav proposal to eliminate the 8-item grab-bag."""
    body = client.get("/").get_data(as_text=True)
    header = body.split("</header>")[0]
    footer = body.split("<footer")[1]

    assert ">Home</a>" in header
    # The menu triggers, specifically - not just the words appearing somewhere.
    for label in ["What's On", "Societies", "Archive"]:
        assert '{}<span class="nav-chevron"'.format(label) in header

    # Key destinations in header
    for label in ["Season Calendar", "Theatres &amp; Venues", "Costumes &amp; Props", "Directory by Region", "Musicals Repertoire"]:
        assert label in header
    for label in ["AIMS Awards Archive", "Decades &amp; Trends", "Circuit Statistics", "Adjudications &amp; Reviews"]:
        assert label in header

    # The footer keeps its sitemap links even where the header duplicates them.
    for label in ["Musicals Repertoire", "Seasons"]:
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
    assert nav.count("<details") == 3
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
