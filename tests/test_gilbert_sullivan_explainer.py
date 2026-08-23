"""2026-08-23 audit finding: "Gilbert" and "Sullivan" are used as a filter
label on five separate pages but explained nowhere except /about, which
almost nobody reads. Each page that offers a Gilbert/Sullivan filter now
carries one short hint line pointing at the real explanation rather than
assuming the term is self-evident."""


def test_awards_page_explains_gilbert_sullivan(client):
    body = client.get("/awards").get_data(as_text=True)
    assert "AIMS's two adjudication tiers" in body
    assert 'href="/about"' in body


def test_reviews_page_explains_gilbert_sullivan(client):
    body = client.get("/reviews").get_data(as_text=True)
    assert "AIMS's two adjudication tiers" in body


def test_season_page_explains_gilbert_sullivan(client):
    body = client.get("/season").get_data(as_text=True)
    assert "AIMS's two adjudication tiers" in body


def test_societies_page_explains_gilbert_sullivan(client):
    body = client.get("/societies").get_data(as_text=True)
    assert "AIMS's two adjudication tiers" in body
