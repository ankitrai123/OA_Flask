from services import automation


def test_reorder_rule_has_required_fields():
    r = automation.reorder_rule("Cold Coffee")
    assert r["reorder_point_units"] > 0
    assert r["order_qty_units"] > 0
    assert r["recommended_supplier"]


def test_backtest_fires_at_least_once_over_two_years():
    r = automation.backtest_reorder_rule("Cold Coffee")
    assert r["triggers_fired"] > 0
    assert r["backtest_horizon_days"] > 700


def test_backtest_stockout_rate_is_low_at_95pct_service_level():
    # ROP is set at a 95% service level (see safety_stock) - the backtest
    # should show a low, not near-zero-but-not-huge, stockout day rate.
    r = automation.backtest_reorder_rule("Cold Coffee")
    assert 0 <= r["stockout_day_pct"] < 15


def test_unknown_item_returns_error():
    assert "error" in automation.reorder_rule("Not A Real Item")


def test_automation_bundle_covers_all_six_items():
    b = automation.automation_bundle()
    assert len(b["items"]) == 6
    assert b["total_triggers_across_items"] > 0
