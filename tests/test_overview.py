from services import overview


def test_shortage_days_not_supported():
    k = overview.executive_kpis()
    assert k["shortage_days"]["status"] == "not_supported"


def test_all_kpis_present():
    k = overview.executive_kpis()
    assert set(k.keys()) == {
        "annual_revenue", "gross_margin", "orders", "order_lines",
        "spoilage_cost", "shortage_days", "num_items", "num_suppliers",
    }


def test_decision_summary_four_findings_two_supported():
    s = overview.executive_decision_summary()
    findings = s["findings"]
    assert len(findings) == 4
    assert len([f for f in findings if f["status"] == "supported"]) == 2
    assert len([f for f in findings if f["status"] == "not_supported"]) == 2


def test_decision_pipeline_six_stages():
    p = overview.decision_pipeline_status()
    assert len(p["stages"]) == 6
