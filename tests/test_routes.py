NEW_GET_ROUTES = [
    "/api/overview", "/api/data-quality", "/api/eda",
    "/api/demand/forecast", "/api/demand/validation",
    "/api/prep/newsvendor", "/api/prep/compare",
]

UNTOUCHED_GET_ROUTES = [
    "/api/metrics/overview", "/api/metrics/sales", "/api/metrics/inventory", "/api/metrics/supply",
    "/api/optimizer/prep", "/api/optimizer/pricing", "/api/optimizer/procurement",
    "/api/basket-analysis", "/api/supply/categories",
]


def test_new_routes_return_200(client):
    for path in NEW_GET_ROUTES:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.get_json() is not None, path


def test_untouched_routes_still_work(client):
    for path in UNTOUCHED_GET_ROUTES:
        r = client.get(path)
        assert r.status_code == 200, path


def test_prep_newsvendor_post_missing_item(client):
    r = client.post("/api/prep/newsvendor", json={})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_prep_newsvendor_post_unknown_item(client):
    r = client.post("/api/prep/newsvendor", json={"item": "Not A Real Item"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_prep_newsvendor_post_valid_item(client):
    r = client.post("/api/prep/newsvendor", json={"item": "Cold Coffee"})
    assert r.status_code == 200
    body = r.get_json()
    assert "recommended_qty" in body


def test_sales_no_longer_has_hourly_pattern(client):
    r = client.get("/api/metrics/sales")
    assert "hourly_pattern" not in r.get_json()


def test_old_forecast_route_removed(client):
    r = client.get("/api/forecast")
    assert r.status_code == 404


def test_agent_insights_still_works(client):
    r = client.get("/api/agent/insights")
    assert r.status_code == 200
