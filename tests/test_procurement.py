from services import procurement as proc


def test_allocation_lp_feasible_with_defaults():
    r = proc.allocation_lp()
    assert "error" not in r
    assert r["total_weekly_cost_inr"] > 0
    assert len(r["allocation"]) > 0


def test_allocation_lp_meets_required_qty_per_category():
    r = proc.allocation_lp()
    required = r["required_weekly_qty"]
    supplied = {}
    for row in r["allocation"]:
        supplied[row["category"]] = supplied.get(row["category"], 0) + row["qty"]
    for category, qty in required.items():
        assert supplied.get(category, 0) >= qty - 0.5


def test_allocation_lp_infeasible_when_capacity_too_low():
    r = proc.allocation_lp(capacity={"City Central Market": 1, "Local Farm Co.": 1, "Metro Wholesale": 1})
    assert "error" in r


def test_binding_supplier_has_nonzero_shadow_price():
    r = proc.allocation_lp()
    assert len(r["binding_suppliers"]) > 0
    for supplier in r["binding_suppliers"]:
        assert r["shadow_prices"][supplier]["shadow_price_inr_per_unit"] > 0
    for supplier, v in r["shadow_prices"].items():
        if supplier not in r["binding_suppliers"]:
            assert v["shadow_price_inr_per_unit"] == 0


def test_topsis_rankings_flip_with_weighting():
    # The reference analysis's own conclusion: "no single winner claimed" -
    # verify our own computation shows the same weight-sensitivity, not
    # just assert it in prose.
    t = proc.topsis_sensitivity()
    assert any(v["rankings_flip_with_weighting"] for v in t["by_category"].values())


def test_topsis_covers_all_four_categories():
    t = proc.topsis_sensitivity()
    assert len(t["by_category"]) == 4
