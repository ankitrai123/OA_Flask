import numpy as np

from services import newsvendor as nv

ITEMS = [
    "Cold Coffee", "Virgin Mojito", "Chicken Pepper Bbq Pizza (Medium)",
    "Bbq Fried Wings 6 Pcs.", "Chicken Lollipop 6pcs", "Chilli Baby Corn (dry)",
]


def test_critical_ratio_bounds():
    for item in ITEMS:
        r = nv.newsvendor_inputs(item)
        assert 0 <= r["critical_ratio"] <= 1


def test_calculate_newsvendor_matches_quantile():
    arr = np.array([10, 20, 30, 40, 50], dtype=float)
    result = nv.calculate_newsvendor("Cold Coffee", demand_forecast=arr, spoilage_cost_override=10, stockout_cost_override=30)
    cr = 30 / (30 + 10)
    expected_qty = round(float(np.quantile(arr, cr)), 1)
    assert result["recommended_qty"] == expected_qty
    assert result["critical_ratio"] == round(cr, 4)


def test_higher_stockout_cost_raises_recommended_qty():
    base = nv.calculate_newsvendor("Cold Coffee")
    higher = nv.calculate_newsvendor("Cold Coffee", stockout_cost_override=base["cu_inr"] * 3)
    assert higher["critical_ratio"] > base["critical_ratio"]
    assert higher["recommended_qty"] > base["recommended_qty"]


def test_defect_c_structural_separation():
    """The single most important honesty constraint in this milestone:
    the two demand scales are never compared to each other."""
    for item in ITEMS:
        r = nv.compare_prep_policies(item)
        dynamic = r["dynamic_newsvendor_pos_scale"]
        assert "cost_avoided_vs_current_judgment_inr" not in dynamic
        assert "cost_avoided_vs_current_judgment_pct" not in dynamic


def test_unknown_item_returns_error_not_raise():
    assert "error" in nv.calculate_newsvendor("Not A Real Item")
    assert "error" in nv.compare_prep_policies("Not A Real Item")
    assert "error" in nv.simulate_newsvendor_whatif("Not A Real Item")
    assert "error" in nv.newsvendor_inputs("Not A Real Item")
