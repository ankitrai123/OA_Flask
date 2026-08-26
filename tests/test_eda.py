from services import eda


def test_demand_distribution_six_items():
    r = eda.demand_distribution()
    assert len(r["per_item"]) == 6


def test_seasonality_significance_pattern():
    r = eda.seasonality()
    assert r["summer_vs_rest"]["significant"] is True
    assert r["summer_vs_rest"]["p_value"] < 0.001

    by_item = {x["item"]: x for x in r["per_item_summer_uplift"]}
    assert by_item["Cold Coffee"]["significant"] is True
    assert by_item["Virgin Mojito"]["significant"] is True
    assert by_item["Bbq Fried Wings 6 Pcs."]["significant"] is False


def test_weekday_seasonality_not_actionable():
    r = eda.seasonality()
    w = r["weekday_seasonality"]
    assert w["p_value"] < 0.06  # borderline-significant, matching the reference analysis's p=0.049
    assert w["actionable"] is False
    assert w["spread_pct_of_mean"] < 20


def test_hourly_pattern_inadmissible():
    r = eda.hourly_pattern_status()
    assert r["status"] == "inadmissible"


def test_revenue_mix_cumulative_share_reaches_100():
    r = eda.revenue_mix()
    assert r["items"][-1]["cumulative_share_pct"] <= 100.01
    assert r["total_items"] == 6


def test_spoilage_and_prep_bias_six_items():
    r = eda.spoilage_and_prep_bias()
    assert len(r["per_item"]) == 6


def test_menu_affinity_returns_rules():
    r = eda.menu_affinity_highlights(top_n=3)
    assert len(r["top_rules"]) <= 3


def test_eda_bundle_has_all_sections():
    b = eda.eda_bundle()
    assert set(b.keys()) == {
        "revenue_mix", "demand_distribution", "seasonality",
        "spoilage_and_prep_bias", "hourly_pattern_status", "menu_affinity",
    }
