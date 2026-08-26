from services import data_quality as dq


def test_defect_a_discount_calc():
    r = dq.defect_a_discount_calc()
    assert r["match_pct"] == 100.0
    assert r["naive_formula_mismatch_pct"] > 0


def test_defect_b_synthetic_timestamp():
    r = dq.defect_b_synthetic_timestamp()
    for window in r["windows_tested"]:
        assert window["pct_outside"] > 30


def test_defect_c_uncorrelated():
    r = dq.defect_c_inventory_vs_pos_demand()
    assert abs(r["correlation"]) < 0.1


def test_defect_d_duplicates_found():
    r = dq.defect_d_duplicate_route_id()
    assert r["affected_rows"] > 0
    assert r["duplicate_route_ids_found"] > 0


def test_scorecard_has_all_four_defects():
    sc = dq.data_quality_scorecard()
    assert len(sc["defects"]) == 4
    assert {d["defect"] for d in sc["defects"]} == {"A", "B", "C", "D"}
    assert set(sc["taxonomy"].keys()) == {"observed", "derived", "assumption", "unsupported"}


def test_data_sources_summary_three_sources():
    r = dq.data_sources_summary()
    assert len(r["sources"]) == 3
