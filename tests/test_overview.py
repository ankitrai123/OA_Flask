from services import overview


def test_shortage_days_is_scoped_prep_shortfall_metric():
    # Now that safety_stock/automation exist, "Prep Shortfall Days" is a
    # real, disclosed figure (inventory log: Actual_Demand_Qty >
    # Forecasted_Prep_Qty) - matches the reference analysis's own "27% of
    # days" finding - not the fabricated cross-scale claim this KPI must
    # never become (see Defect C).
    k = overview.executive_kpis()
    assert k["shortage_days"]["label"] == "Prep Shortfall Days"
    assert 20 < k["shortage_days"]["value"] < 35


def test_annual_revenue_is_annualized_not_two_year_total():
    # The POS extract spans 2 calendar years (2023-2024); summing
    # Total_Amount over the whole extract and calling it "Annual Revenue"
    # (the original bug) would give ~Rs78.8L, roughly double the true
    # per-year rate the label promises.
    k = overview.executive_kpis()
    assert 3_800_000 < k["annual_revenue"]["value"] < 4_100_000


def test_all_kpis_present():
    k = overview.executive_kpis()
    assert set(k.keys()) == {
        "annual_revenue", "gross_margin", "orders", "order_lines",
        "spoilage_cost", "shortage_days", "num_items", "num_suppliers",
    }


def test_decision_summary_four_findings_all_supported():
    # With safety_stock/procurement/automation now built, all 4 findings
    # are grounded in real computations - none are placeholder gaps anymore.
    s = overview.executive_decision_summary()
    findings = s["findings"]
    assert len(findings) == 4
    assert len([f for f in findings if f["status"] == "supported"]) == 4


def test_decision_pipeline_all_six_stages_built():
    p = overview.decision_pipeline_status()
    assert len(p["stages"]) == 6
    assert all(s["status"] == "built" for s in p["stages"])
