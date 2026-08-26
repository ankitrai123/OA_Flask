import json

from services import forecasting as fc


def test_per_item_significance_pattern():
    b = fc.get_demand_forecast_bundle()
    assert b["items"]["Cold Coffee"]["model_info"]["summer_significant"] is True
    assert b["items"]["Virgin Mojito"]["model_info"]["summer_significant"] is True
    assert b["items"]["Bbq Fried Wings 6 Pcs."]["model_info"]["summer_significant"] is False


def test_weekly_log_model_multiplier_matches_coefficient():
    b = fc.get_demand_forecast_bundle()
    info = b["items"]["Cold Coffee"]["model_info"]
    assert info["summer_multiplier"] > 1.5  # a real, large summer uplift, not noise
    # summer_multiplier must be exp(summer_log_coef) - the whole point of fitting in log space
    assert abs(info["summer_multiplier"] - round(2.71828 ** info["summer_log_coef"], 3)) < 0.01


def test_rolling_origin_improvement_positive():
    v = fc.rolling_origin_validate("Cold Coffee")
    assert v["improvement_pct"] > 0


def test_rolling_origin_validate_weekly_improvement_positive():
    v = fc.rolling_origin_validate_weekly("Cold Coffee")
    assert v["improvement_pct"] > 0
    assert v["horizon_weeks"] == fc.VALIDATION_HORIZON_WEEKS


def test_naive_split_weekly_flags_missing_summer():
    # the last 20% of this 2-year series falls in Aug-Dec, which contains no
    # summer months - this is exactly the deck's "the 80/20 split understates
    # the gain" point, and must be visible in the flag, not silently hidden.
    v = fc.naive_split_validate_weekly("Cold Coffee")
    assert v["test_window_contains_summer"] is False


def test_demand_validation_bundle_has_both_methods():
    v = fc.get_demand_validation_bundle()
    item = v["items"]["Cold Coffee"]
    assert item["status"] == "supported"
    assert "rolling_origin" in item and "naive_80_20_split" in item
    assert item["rolling_origin"]["improvement_pct"] > item["naive_80_20_split"]["improvement_pct"]


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
