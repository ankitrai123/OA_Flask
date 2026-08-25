"""Shared per-item economics used by the optimizer, forecasting, and simulator
modules, so the margin/critical-ratio definition can't drift between them."""


def avg_realized_price(pos, item):
    p = pos[pos["Item_Name"] == item]
    return (p["Unit_Price"] - p["Discount_Applied"]).mean()


def margin(pos, item, cost):
    return max(avg_realized_price(pos, item) - cost, 1e-6)


def critical_ratio(pos, item, cost):
    """Newsvendor critical ratio: understock cost (margin) vs overstock cost (unit cost)."""
    m = margin(pos, item, cost)
    return m / (m + cost)
