"""/about's society count - shows both the full archive total and the
number actually browsable on /societies (Inactive/hidden excluded), so the
two numbers don't read as an unexplained mismatch (see the 2026-08-05 site
review)."""
from conftest import seed_society


def test_about_page_shows_total_and_active_counts(client, db):
    seed_society(db, id=1, name="Active Society", section="Gilbert")
    seed_society(db, id=2, name="Retired Society", section="Inactive")
    seed_society(db, id=3, name="Asked Not To Be Mentioned", section="Gilbert")
    db.execute("UPDATE societies SET hidden = 1 WHERE id = 3")
    db.commit()

    body = client.get("/about").get_data(as_text=True)
    assert "3 societies" in body
    assert "1 currently active" in body
