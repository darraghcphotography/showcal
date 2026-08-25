"""/titles rights-status and licensing-house filters (public.py's
titles_list()), added 2026-08-25 - "no one goes alphabetically" was Darragh's
own framing, so the letter index stays as a jump-nav but rights availability
and licensing house become real quick-filter/dropdown options, same shape as
the existing on-stage/revival/rare-gems chips."""
from conftest import seed_society


def seed_show(db, **kw):
    fields = {
        "society_id": 1, "season": "25/26", "show": "Test Show", "region": "Eastern",
        "section": "Gilbert", "moderation_status": "approved", "source": "import",
    }
    fields.update(kw)
    cols = ", ".join(fields)
    db.execute(
        f"INSERT INTO shows ({cols}) VALUES ({', '.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    db.commit()


def seed_show_info(db, show, rights_status=None, licensing_house=None):
    db.execute(
        "INSERT INTO show_info (show, rights_status, licensing_house) VALUES (?, ?, ?)",
        (show, rights_status, licensing_house),
    )
    db.commit()


def test_rights_status_chip_filters_to_matching_titles(client, db):
    """"Most-staged, archive-wide" staples strip always shows the top titles
    regardless of the active filter, so a plain "in body" check would false-
    positive on any title small enough to still make that top-8 list -
    counting occurrences (staples-only vs. staples + a real title-card)
    distinguishes an actually-filtered-in title from one merely name-dropped
    in the staples strip."""
    seed_society(db)
    seed_show(db, show="Available Show", opening_date="2025-09-01")
    seed_show(db, show="Restricted Show", opening_date="2025-09-02")
    seed_show_info(db, "Available Show", rights_status="Available")
    seed_show_info(db, "Restricted Show", rights_status="Restricted")

    body = client.get("/titles?filter=available").get_data(as_text=True)
    assert body.count("Available Show") == 2  # staples strip + title-card
    assert body.count("Restricted Show") == 1  # staples strip only, no card

    body = client.get("/titles?filter=restricted").get_data(as_text=True)
    assert body.count("Restricted Show") == 2
    assert body.count("Available Show") == 1


def test_rights_status_chip_counts_are_correct(client, db):
    seed_society(db)
    seed_show(db, show="A", opening_date="2025-09-01")
    seed_show(db, show="B", opening_date="2025-09-02")
    seed_show(db, show="C", opening_date="2025-09-03")
    seed_show_info(db, "A", rights_status="Available")
    seed_show_info(db, "B", rights_status="Available")
    seed_show_info(db, "C", rights_status="Contact publisher")

    body = client.get("/titles").get_data(as_text=True)
    assert 'Rights available <span class="n">2</span>' in body
    assert 'Contact publisher <span class="n">1</span>' in body
    assert 'Restricted <span class="n">0</span>' in body


def test_a_title_with_no_rights_status_is_excluded_from_every_rights_chip(client, db):
    seed_society(db)
    seed_show(db, show="No Info Show", opening_date="2025-09-01")
    # deliberately no show_info row at all

    for flt in ("available", "contact", "restricted"):
        body = client.get(f"/titles?filter={flt}").get_data(as_text=True)
        assert body.count("No Info Show") <= 1  # staples only, never also a title-card


def test_licensing_house_dropdown_filters_and_combines_with_a_chip(client, db):
    seed_society(db)
    seed_show(db, show="MTI Onstage", opening_date="2026-11-01")  # future = "on stage"
    seed_show(db, show="Concord Onstage", opening_date="2026-11-05")
    seed_show_info(db, "MTI Onstage", rights_status="Available", licensing_house="MTI Europe")
    seed_show_info(db, "Concord Onstage", rights_status="Available", licensing_house="Concord Theatricals")

    house_only = client.get("/titles?house=MTI+Europe").get_data(as_text=True)
    assert house_only.count("MTI Onstage") == 2
    assert house_only.count("Concord Onstage") == 1

    # Combines with a chip filter rather than replacing it.
    combined = client.get("/titles?house=MTI+Europe&filter=available").get_data(as_text=True)
    assert combined.count("MTI Onstage") == 2
    assert combined.count("Concord Onstage") == 1


def test_licensing_house_dropdown_lists_only_real_distinct_houses(client, db):
    seed_society(db)
    seed_show(db, show="A", opening_date="2025-09-01")
    seed_show(db, show="B", opening_date="2025-09-02")
    seed_show_info(db, "A", licensing_house="MTI Europe")
    seed_show_info(db, "B", licensing_house="MTI Europe")  # duplicate house, should appear once

    body = client.get("/titles").get_data(as_text=True)
    assert body.count('value="MTI Europe"') == 1


def test_clearing_the_house_filter_keeps_an_active_chip_filter(client, db):
    seed_society(db)
    seed_show(db, show="Available Show", opening_date="2025-09-01")
    seed_show_info(db, "Available Show", rights_status="Available", licensing_house="MTI Europe")

    body = client.get("/titles?house=MTI+Europe&filter=available").get_data(as_text=True)
    # The "clear search" link should drop house but keep the active chip filter.
    assert 'href="/titles?filter=available"' in body
