"""Installable-PWA basics: manifest icons, the service worker route, the
mobile-only "More" page, and that the bottom tab bar never renders on
admin/society pages (see base.html's mobile_chrome check)."""
import json

from conftest import seed_user


def test_manifest_has_any_and_maskable_icons(client):
    resp = client.get("/manifest.webmanifest")
    manifest = json.loads(resp.get_data(as_text=True))
    purposes = {icon.get("purpose") for icon in manifest["icons"] if "purpose" in icon}
    assert "any" in purposes
    assert "maskable" in purposes


def test_service_worker_served_at_root_with_js_mimetype(client):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.mimetype


def test_more_page_renders_and_links_resolve(client):
    body = client.get("/more").get_data(as_text=True)
    assert 'href="/awards"' in body
    assert 'href="/submit/unlock"' in body
    assert 'href="/suggest"' in body
    assert 'href="/society/login"' in body
    assert 'href="/admin/login"' in body
    assert 'href="/about"' in body


def test_bottom_tab_bar_present_on_public_page(client):
    body = client.get("/").get_data(as_text=True)
    assert 'class="bottom-tab-bar"' in body


def test_bottom_tab_bar_absent_on_admin_and_society_pages(client, db):
    seed_user(db, username="mod", password="password123")
    client.post("/admin/login", data={"username": "mod", "password": "password123"})

    admin_body = client.get("/admin/").get_data(as_text=True)
    assert 'class="bottom-tab-bar"' not in admin_body

    society_body = client.get("/society/login").get_data(as_text=True)
    assert 'class="bottom-tab-bar"' not in society_body
