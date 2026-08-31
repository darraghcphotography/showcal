"""Comprehensive tests for the nationwide Costumes, Props & Sets Exchange feature."""
import io
import pytest
from app import create_app
from app.db import get_db, init_schema


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test_aims.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    app = create_app({
        "TESTING": True,
        "DATABASE": str(db_path),
        "SCHEMA_PATH": "schema.sql",
        "UPLOAD_DIR": str(upload_dir),
        "SECRET_KEY": "test-key-for-testing",
        "RATELIMIT_ENABLED": False,
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        init_schema()
        db = get_db()
        # Seed societies
        db.execute(
            "INSERT INTO societies (id, name, region, section, lifecycle_status) VALUES (1, 'Trim Musical Society', 'Midlands', 'Gilbert', 'Active')"
        )
        db.execute(
            "INSERT INTO societies (id, name, region, section, lifecycle_status) VALUES (2, 'Rathmines & Rathgar Musical Society', 'Eastern', 'Gilbert', 'Active')"
        )
        db.execute(
            "INSERT INTO societies (id, name, region, section, hidden, lifecycle_status) VALUES (3, 'Secret Society', 'Eastern', 'Gilbert', 1, 'Active')"
        )
        # Seed invite codes for society login
        db.execute(
            "INSERT INTO invite_codes (id, code, society_id, is_active) VALUES (1, 'TRIM-LOGIN', 1, 1)"
        )
        db.execute(
            "INSERT INTO invite_codes (id, code, society_id, is_active) VALUES (2, 'RANDR-LOGIN', 2, 1)"
        )
        db.commit()

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def login_as_society(client, code="TRIM-LOGIN"):
    return client.post("/society/login", data={"code": code}, follow_redirects=True)


# --- 1. Authentication & Vault Access Tests ---

def test_vault_requires_login(client):
    """Unauthenticated users attempting to access /society/vault are redirected to login."""
    res = client.get("/society/vault")
    assert res.status_code == 302
    assert "/society/login" in res.headers["Location"]


def test_society_can_view_empty_vault(client):
    """Logged in society sees the empty state with listing prompt."""
    login_as_society(client)
    res = client.get("/society/vault")
    assert res.status_code == 200
    assert "Your Society Vault is Empty" in res.get_data(as_text=True)
    assert "Community Notice &amp; Guidelines" in res.get_data(as_text=True)


# --- 2. Add, Edit, Status Toggle, & Delete Flow ---

def test_add_vault_item_flow(client):
    """Society can create a new wardrobe listing with disclaimer agreement and photo upload."""
    login_as_society(client)

    # 1. Missing disclaimer acknowledgment fails
    res = client.post(
        "/society/vault/new",
        data={
            "title": "Ancestors Ensemble Costumes",
            "item_type": "costume_full_set",
            "terms": "hire",
            "status": "available",
        },
        follow_redirects=True,
    )
    assert "Please confirm the community guideline" in res.get_data(as_text=True)

    # 2. Valid submission succeeds
    buf = io.BytesIO()
    from PIL import Image as PILImage
    PILImage.new("RGB", (50, 50), color="blue").save(buf, format="PNG")
    buf.seek(0)
    valid_photo = (buf, "costume.png")

    res = client.post(
        "/society/vault/new",
        data={
            "title": "Ancestors Ensemble Costumes",
            "item_type": "costume_full_set",
            "show_title": "The Addams Family",
            "description": "22 full outfits with wigs and makeup references.",
            "sizing_quantity": "Adult 8-18 (12 female, 10 male)",
            "terms": "hire",
            "status": "available",
            "contact_name": "Mary Kelly",
            "contact_email": "wardrobe@trimms.com",
            "contact_phone": "0871234567",
            "agree_terms": "1",
            "photos": [valid_photo],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "Listed &#39;Ancestors Ensemble Costumes&#39; in your society&#39;s vault!" in res.get_data(as_text=True)

    # Check database record
    with client.application.app_context():
        db = get_db()
        item = db.execute("SELECT * FROM wardrobe_items WHERE society_id = 1").fetchone()
        assert item is not None
        assert item["title"] == "Ancestors Ensemble Costumes"
        assert item["item_type"] == "costume_full_set"
        assert item["show_title"] == "The Addams Family"
        assert item["terms"] == "hire"
        assert item["status"] == "available"
        assert item["primary_photo"] is not None


def test_cross_society_isolation(client):
    """Society A cannot edit or delete Society B's wardrobe items."""
    # Society 1 creates an item
    login_as_society(client, code="TRIM-LOGIN")
    client.post(
        "/society/vault/new",
        data={
            "title": "Trim Prop",
            "item_type": "prop",
            "terms": "loan",
            "status": "available",
            "agree_terms": "1",
        },
        follow_redirects=True,
    )

    with client.application.app_context():
        db = get_db()
        item = db.execute("SELECT id FROM wardrobe_items WHERE title = 'Trim Prop'").fetchone()
        item_id = item["id"]

    # Society 2 logs in and attempts to access/edit/delete Society 1's item
    login_as_society(client, code="RANDR-LOGIN")
    
    edit_res = client.get(f"/society/vault/{item_id}/edit")
    assert edit_res.status_code == 404

    post_edit = client.post(f"/society/vault/{item_id}/edit", data={"title": "Hacked Title"})
    assert post_edit.status_code == 404

    delete_res = client.post(f"/society/vault/{item_id}/delete")
    assert delete_res.status_code == 302
    
    # Verify item was not deleted
    with client.application.app_context():
        db = get_db()
        assert db.execute("SELECT id FROM wardrobe_items WHERE id = ?", (item_id,)).fetchone() is not None


def test_vault_toggle_status_and_delete(client):
    """Society can toggle status between available and on_loan, and delete items."""
    login_as_society(client)
    client.post(
        "/society/vault/new",
        data={
            "title": "Chandelier Set Piece",
            "item_type": "set_piece",
            "terms": "hire",
            "status": "available",
            "agree_terms": "1",
        },
        follow_redirects=True,
    )

    with client.application.app_context():
        db = get_db()
        item_id = db.execute("SELECT id FROM wardrobe_items WHERE title = 'Chandelier Set Piece'").fetchone()["id"]

    # Toggle to on_loan
    res = client.post(f"/society/vault/{item_id}/status", data={"status": "on_loan"}, follow_redirects=True)
    assert res.status_code == 200
    assert "Status updated to &#39;Currently On Loan&#39;." in res.get_data(as_text=True)

    # Delete item
    del_res = client.post(f"/society/vault/{item_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert "Item removed from your vault." in del_res.get_data(as_text=True)

    with client.application.app_context():
        db = get_db()
        assert db.execute("SELECT id FROM wardrobe_items WHERE id = ?", (item_id,)).fetchone() is None


# --- 3. Public Directory & Search Tests ---

def test_public_exchange_listing_and_filtering(client):
    """Public /exchange displays items, supports category & region filters, and excludes delisted/hidden."""
    with client.application.app_context():
        db = get_db()
        # Active Trim item
        db.execute(
            """
            INSERT INTO wardrobe_items (society_id, show_title, title, item_type, description, terms, status)
            VALUES (1, 'Les Misérables', 'French Barricade Pieces', 'set_piece', 'Sturdy wooden barricade modules', 'hire', 'available')
            """
        )
        # Active R&R item
        db.execute(
            """
            INSERT INTO wardrobe_items (society_id, show_title, title, item_type, description, terms, status)
            VALUES (2, 'The Mikado', 'Japanese Kimonos and Fans', 'costume_full_set', 'Silk embroidered kimonos', 'hire', 'available')
            """
        )
        # Delisted item (should not show)
        db.execute(
            """
            INSERT INTO wardrobe_items (society_id, title, item_type, terms, status)
            VALUES (1, 'Broken Prop', 'prop', 'hire', 'delisted')
            """
        )
        # Hidden society item (should not show)
        db.execute(
            """
            INSERT INTO wardrobe_items (society_id, title, item_type, terms, status)
            VALUES (3, 'Secret Wardrobe', 'costume_full_set', 'hire', 'available')
            """
        )
        db.commit()

    # 1. Main directory has both active items and disclaimer
    res = client.get("/exchange")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "French Barricade Pieces" in html
    assert "Japanese Kimonos and Fans" in html
    assert "Broken Prop" not in html
    assert "Secret Wardrobe" not in html
    assert "Community Notice &amp; Guidelines" in html
    assert "ShowCal operates solely as an informal introduction directory" in html

    # 2. Filter by category
    cat_res = client.get("/exchange?type=set_piece")
    assert cat_res.status_code == 200
    cat_html = cat_res.get_data(as_text=True)
    assert "French Barricade Pieces" in cat_html
    assert "Japanese Kimonos and Fans" not in cat_html

    # 3. Filter by region
    region_res = client.get("/exchange?region=Eastern")
    assert region_res.status_code == 200
    reg_html = region_res.get_data(as_text=True)
    assert "Japanese Kimonos and Fans" in reg_html
    assert "French Barricade Pieces" not in reg_html

    # 4. Search query
    search_res = client.get("/exchange?q=Barricade")
    assert search_res.status_code == 200
    s_html = search_res.get_data(as_text=True)
    assert "French Barricade Pieces" in s_html
    assert "Japanese Kimonos and Fans" not in s_html


# --- 4. Public Item Detail & Disclaimer Tests ---

def test_public_exchange_detail_view(client):
    """Item detail page renders item info, society details, mailto contact, and disclaimer."""
    with client.application.app_context():
        db = get_db()
        cur = db.execute(
            """
            INSERT INTO wardrobe_items (
                society_id, show_title, title, item_type, description,
                sizing_quantity, terms, status, contact_name, contact_email, contact_phone
            ) VALUES (
                1, 'The Addams Family', 'Ancestors Wardrobe (22 Outfits)', 'costume_full_set',
                'Detailed gothic monochrome costumes in good condition.',
                'Adults sizes 8-16', 'hire', 'available', 'Mary Kelly', 'wardrobe@trimms.com', '0871234567'
            )
            """
        )
        item_id = cur.lastrowid
        db.commit()

    res = client.get(f"/exchange/{item_id}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Ancestors Wardrobe (22 Outfits)" in html
    assert "The Addams Family" in html
    assert "Trim Musical Society" in html
    assert "Mary Kelly" in html
    assert "0871234567" in html
    assert "mailto:wardrobe@trimms.com" in html
    assert "Community Disclaimer" in html
    assert "ShowCal provides this listing as an introductory guideline only" in html


def test_public_exchange_detail_404_for_delisted(client):
    """Delisted or nonexistent items return 404."""
    with client.application.app_context():
        db = get_db()
        cur = db.execute(
            "INSERT INTO wardrobe_items (society_id, title, item_type, terms, status) VALUES (1, 'Hidden Item', 'prop', 'hire', 'delisted')"
        )
        item_id = cur.lastrowid
        db.commit()

    assert client.get(f"/exchange/{item_id}").status_code == 404
    assert client.get("/exchange/99999").status_code == 404


# --- 5. Society & Title Detail Cross-Links Tests ---

def test_society_detail_displays_active_wardrobe_strip(client):
    """Society detail page includes compact strip for active wardrobe items and stat tile."""
    with client.application.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO wardrobe_items (
                society_id, show_title, title, item_type, terms, status
            ) VALUES (1, 'We Will Rock You', 'Bohemian Rocker Jackets', 'costume_full_set', 'hire', 'available')
            """
        )
        db.commit()

    res = client.get("/societies/1")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Costumes, Props &amp; Sets for Hire / Loan" in html
    assert "Bohemian Rocker Jackets" in html
    assert "Item for Hire" in html


def test_title_detail_displays_matching_show_wardrobe_strip(client):
    """Title detail page renders matching costumes & props for that show."""
    with client.application.app_context():
        db = get_db()
        # Seed a show for We Will Rock You
        db.execute(
            """
            INSERT INTO shows (
                society_id, season, show, region, section, moderation_status, source
            ) VALUES (1, '24/25', 'We Will Rock You', 'Midlands', 'Gilbert', 'approved', 'submission')
            """
        )
        db.execute(
            """
            INSERT INTO wardrobe_items (
                society_id, show_title, title, item_type, terms, status
            ) VALUES (1, 'We Will Rock You', 'Galileo Laser Guitar Prop', 'prop', 'hire', 'available')
            """
        )
        db.commit()

    res = client.get("/titles/We%20Will%20Rock%20You")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Costumes, Props &amp; Sets for this Show" in html
    assert "Galileo Laser Guitar Prop" in html
    assert "Trim Musical Society" in html

