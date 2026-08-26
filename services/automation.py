"""Automation - Reorder Trigger (Q4, Slide 08).

There is no real-time inventory feed in this data - only historical daily
logs - so this module does not claim to run a live system. It specifies a
rule precisely enough that it COULD be automated (an RPA-style trigger, per
the reference analysis's "rule-based reorder trigger on corrected reorder
points"), and backtests that exact rule against the item's real historical
demand so its behavior is demonstrated, not just asserted:

  RULE: each day, IF projected inventory position <= the item's Reorder
  Point (from services.safety_stock, at the recommended supplier) THEN
  place an order of order_qty units from that supplier, arriving after
  their lead time.

This is a specification + a mechanical backtest, not a forecast of future
reorders - it answers "how often would this rule have fired, given what
this item's demand actually looked like."
"""

import numpy as np

from services.data_loader import get_data
from services import forecasting
from services.safety_stock import ITEM_TO_CATEGORY, item_safety_stock


def _round(x, n=2):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    return round(x, n) if isinstance(x, float) else x


def reorder_rule(item):
    """The specified rule for one item: its ROP, recommended supplier, lead
    time, and a default order quantity (that supplier's own MOQ for this
    item's assumed category - a real, data-grounded default, not a demand
    forecast)."""
    if item not in ITEM_TO_CATEGORY:
        return {"error": f"unknown item '{item}'"}

    ss = item_safety_stock(item)
    recommended_name = ss["recommended_supplier"]
    recommended_row = next(r for r in ss["decomposed_by_supplier"] if r["supplier"] == recommended_name)

    d = get_data()
    sup = d["supply"]
    moq_rows = sup[(sup["Supplier"] == recommended_name) & (sup["Ingredient_Category"] == ss["assumed_ingredient_category"])]
    order_qty = float(moq_rows["Minimum_Order_Qty"].mean()) if not moq_rows.empty else recommended_row["reorder_point_units"]

    return {
        "item": item,
        "assumed_ingredient_category": ss["assumed_ingredient_category"],
        "recommended_supplier": recommended_name,
        "reorder_point_units": recommended_row["reorder_point_units"],
        "lead_time_days": recommended_row["lead_time_mean_days"],
        "order_qty_units": _round(order_qty),
        "order_qty_source": "recommended supplier's own Minimum_Order_Qty for this category",
        "rule_statement": (
            f"IF projected inventory position for {item} <= {recommended_row['reorder_point_units']} units "
            f"THEN order {_round(order_qty)} units from {recommended_name} "
            f"(arrives in ~{recommended_row['lead_time_mean_days']} days)."
        ),
    }


def backtest_reorder_rule(item, initial_position=None):
    """Mechanical simulation of the rule above over the item's real
    POS-derived daily demand: starts at a full position (ROP + order_qty),
    decrements by each day's real demand, and places a reorder (arriving
    after lead time) whenever position drops to/below ROP. Reports how many
    times the rule fired and the resulting stockout-day rate - an honest
    demonstration of the rule's behavior on real history, not a claim about
    the future."""
    rule = reorder_rule(item)
    if "error" in rule:
        return rule

    rop = rule["reorder_point_units"]
    order_qty = rule["order_qty_units"]
    lead_time = max(1, round(rule["lead_time_days"]))

    demand = forecasting.get_item_daily_demand(item).to_numpy()
    n_days = len(demand)
    position = initial_position if initial_position is not None else rop + order_qty

    pipeline = []  # list of [days_remaining, qty]
    triggers = 0
    stockout_days = 0
    trigger_log = []

    for day in range(n_days):
        arrivals = [q for rem, q in pipeline if rem <= 0]
        position += sum(arrivals)
        pipeline = [[rem - 1, q] for rem, q in pipeline if rem > 0]

        position -= demand[day]
        if position < 0:
            stockout_days += 1
            position = 0

        if position <= rop and not pipeline:
            pipeline.append([lead_time, order_qty])
            triggers += 1
            if len(trigger_log) < 10:
                trigger_log.append({"day_index": day, "position_at_trigger": _round(position, 1)})

    return {
        "item": item,
        "rule": rule,
        "backtest_horizon_days": int(n_days),
        "triggers_fired": triggers,
        "avg_days_between_triggers": _round(n_days / triggers) if triggers else None,
        "stockout_days": int(stockout_days),
        "stockout_day_pct": _round(stockout_days / n_days * 100),
        "sample_triggers": trigger_log,
        "note": (
            "A mechanical backtest of the stated rule against this item's real historical daily "
            "demand - not a live system (there is no real-time inventory feed in this data) and not "
            "a forecast of future reorder timing."
        ),
    }


def automation_bundle():
    """Backing function for GET /api/automation."""
    items_out = {item: backtest_reorder_rule(item) for item in ITEM_TO_CATEGORY}
    total_triggers = sum(v["triggers_fired"] for v in items_out.values())
    return {
        "items": items_out,
        "total_triggers_across_items": total_triggers,
    }
