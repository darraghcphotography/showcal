"""Round 5 of the 2026-08-17 audit's plan: a public /adjudicators directory
and per-adjudicator reviews page, plus a "reviewed by" credit on a published-
review show page - see app/blueprints/public.py's adjudicators_list()/
adjudicator_detail()/show_detail()."""
from conftest import seed_society


def seed_adjudicator(db, name="Jane Smith", notes=None):
    db.execute("INSERT INTO adjudicators (name, notes) VALUES (?, ?)", (name, notes))
    db.commit()
    return db.execute("SELECT id FROM adjudicators WHERE name = ?", (name,)).fetchone()["id"]


def assign(db, season, section, adjudicator_id):
    db.execute(
        "INSERT INTO adjudicator_assignments (season, section, adjudicator_id) VALUES (?, ?, ?)",
        (season, section, adjudicator_id),
    )
    db.commit()


def test_adjudicators_list_excludes_unassigned(client, db):
    seed_adjudicator(db, name="Assigned Jane")
    unassigned_id = seed_adjudicator(db, name="Unassigned Jack")
    assigned_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Assigned Jane'").fetchone()["id"]
    assign(db, "23/24", "Gilbert", assigned_id)

    body = client.get("/adjudicators").get_data(as_text=True)
    assert "Assigned Jane" in body
    assert "Unassigned Jack" not in body


def test_adjudicator_detail_404_for_unknown_id(client):
    assert client.get("/adjudicators/999").status_code == 404


def test_adjudicator_detail_404_for_unassigned_adjudicator(client, db):
    unassigned_id = seed_adjudicator(db, name="Unassigned Jack")
    assert client.get(f"/adjudicators/{unassigned_id}").status_code == 404


def test_adjudicator_detail_shows_only_published_reviews(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "23/24", "Gilbert", jane_id)

    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    # Same season/tier but no review yet - must not appear.
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Scheduled Show', 'Scheduled')",
        (society_id,),
    )
    # Different tier, same season - must not appear.
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Sullivan', 'Cabaret', 'Published', 'https://example.com/other')",
        (society_id,),
    )
    db.commit()
    jane_id = db.execute("SELECT id FROM adjudicators WHERE name = 'Jane Smith'").fetchone()["id"]

    body = client.get(f"/adjudicators/{jane_id}").get_data(as_text=True)
    assert "Oliver!" in body
    assert "Scheduled Show" not in body
    assert "Cabaret" not in body


def test_adjudicator_detail_excludes_hidden_society(client, db):
    society_id = seed_society(db, id=1, name="Hidden Society", region="Eastern")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = ?", (society_id,))
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "23/24", "Gilbert", jane_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Secret Show', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()

    body = client.get(f"/adjudicators/{jane_id}").get_data(as_text=True)
    assert "Secret Show" not in body
    assert "No published reviews" in body


def test_show_page_credits_the_assigned_adjudicator(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    jane_id = seed_adjudicator(db, name="Jane Smith")
    assign(db, "23/24", "Gilbert", jane_id)
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Oliver!'").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by" in body.lower()
    assert "Jane Smith" in body


def test_show_page_no_credit_without_assignment(client, db):
    society_id = seed_society(db, id=1, name="Test Society", region="Eastern")
    db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_status, review_url) "
        "VALUES (?, '23/24', 'Eastern', 'Gilbert', 'Oliver!', 'Published', 'https://example.com/review')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows WHERE show = 'Oliver!'").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert "reviewed by" not in body.lower()


def test_adjudicators_link_present_in_footer_and_more_page(client):
    footer = client.get("/").get_data(as_text=True)
    assert 'href="/adjudicators"' in footer
    more_page = client.get("/more").get_data(as_text=True)
    assert 'href="/adjudicators"' in more_page


def test_sitemap_includes_adjudicators_page(client):
    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/adjudicators</loc>" in body
