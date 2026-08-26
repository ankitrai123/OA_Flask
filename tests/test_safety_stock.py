from services import safety_stock as ss


def test_between_supplier_variance_is_dominant():
    r = ss.between_supplier_lead_time_variance_share()
    assert r["between_supplier_variance_share_pct"] > 50


def test_decomposed_range_matches_reference_analysis():
    # The reference analysis reports "5 to 36 units" for the decomposed,
    # item-specific safety stock - our own recomputation should land close.
    b = ss.safety_stock_bundle()
    rng = b["decomposed_safety_stock_range_units"]
    assert 3 <= rng["min"] <= 8
    assert 30 <= rng["max"] <= 40


def test_pooled_comparator_flattens_across_items():
    # The whole point of Q3A: pooling ignores each item's real supplier, so
    # the "wrong" pooled figure should differ meaningfully from at least one
    # of the decomposed per-supplier figures for every item.
    b = ss.safety_stock_bundle()
    for item, v in b["items"].items():
        pooled = v["pooled_wrong_comparator"]["safety_stock_units"]
        decomposed_vals = [r["safety_stock_units"] for r in v["decomposed_by_supplier"]]
        assert any(abs(pooled - dv) > 1 for dv in decomposed_vals)


def test_service_level_increases_safety_stock():
    low = ss.item_safety_stock("Chicken Pepper Bbq Pizza (Medium)", service_level="90%")
    high = ss.item_safety_stock("Chicken Pepper Bbq Pizza (Medium)", service_level="99%")
    low_ss = low["decomposed_by_supplier"][0]["safety_stock_units"]
    high_ss = high["decomposed_by_supplier"][0]["safety_stock_units"]
    assert high_ss > low_ss


def test_unknown_item_returns_error():
    assert "error" in ss.item_safety_stock("Not A Real Item")


def test_category_mapping_covers_all_six_items():
    assert len(ss.ITEM_TO_CATEGORY) == 6
