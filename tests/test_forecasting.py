import json

from services import forecasting as fc


def test_per_item_significance_pattern():
    b = fc.get_demand_forecast_bundle()
    assert b["items"]["Cold Coffee"]["model_info"]["summer_significant"] is True
    assert b["items"]["Virgin Mojito"]["model_info"]["summer_significant"] is True
    assert b["items"]["Bbq Fried Wings 6 Pcs."]["model_info"]["summer_significant"] is False


def test_sparse_item_flagged():
    b = fc.get_demand_forecast_bundle()
    assert b["items"]["Chilli Baby Corn (dry)"]["model_info"]["sparse_data_flag"] is True


def test_rolling_origin_improvement_positive():
    v = fc.rolling_origin_validate("Cold Coffee")
    assert v["improvement_pct"] > 0


def test_forecast_band_ordering():
    f = fc.future_forecast("Cold Coffee")
    assert len(f["future"]["labels"]) == fc.FUTURE_HORIZON_DAYS
    for lo, med, hi in zip(f["future"]["lower"], f["future"]["median"], f["future"]["upper"]):
        assert lo <= med <= hi


def test_bundle_json_safe_no_private_keys():
    b = fc.get_demand_forecast_bundle()
    json.dumps(b)  # must not raise
    for item_data in b["items"].values():
        if item_data.get("status") == "supported":
            assert not any(k.startswith("_") for k in item_data["model_info"].keys())


def test_one_step_ahead_forecast_shape():
    r = fc.get_one_step_ahead_forecast("Cold Coffee")
    assert set(r.keys()) == {"item", "date", "mean", "std"}
    assert r["mean"] >= 0
    assert r["std"] > 0


def test_unknown_item_returns_none_not_raise():
    assert fc.fit_item_model("Not A Real Item") is None
