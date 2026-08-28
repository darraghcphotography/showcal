"""F3 (small-items queue, plan item 8): a share affordance on show pages -
Web Share API with a copy-link fallback, CSS/inline-JS only, no third-party
widget. The inline script has to carry the CSP nonce (g.csp_nonce) or the
Content-Security-Policy in app/__init__.py blocks it outright."""
from conftest import seed_society


def test_share_button_renders_with_the_show_url(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'approved', 'import')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows").fetchone()["id"]

    body = client.get(f"/shows/{show_id}").get_data(as_text=True)
    assert 'id="share-button"' in body
    assert f"/shows/{show_id}" in body


def test_share_script_carries_the_csp_nonce(client, db):
    society_id = seed_society(db)
    db.execute(
        "INSERT INTO shows (society_id, season, region, show, moderation_status, source) "
        "VALUES (?, '24/25', 'Eastern', 'Oliver!', 'approved', 'import')",
        (society_id,),
    )
    db.commit()
    show_id = db.execute("SELECT id FROM shows").fetchone()["id"]

    resp = client.get(f"/shows/{show_id}")
    body = resp.get_data(as_text=True)
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "share-button" in body

    import re
    nonce = re.search(r"nonce-([A-Za-z0-9_-]+)", csp).group(1)
    assert f'nonce="{nonce}"' in body
