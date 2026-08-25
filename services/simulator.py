"""Monte Carlo what-if simulation.

Two scenario types, both bootstrap/Normal-sampling based rather than
assuming a closed-form distribution has to hold:

1. Prep scenario - "what if demand grows/gets more volatile, and we hold
   prep at X units/day" - bootstraps real historical daily demand for the
   item, scales it, and re-runs the newsvendor cost math from optimizer.py
   across simulated days to show the resulting cost/waste/stockout spread.

2. Supplier scenario - "what if lead time increases / we switch supplier" -
   a classic periodic-review (reorder-point, order-quantity) simulation
   using the EOQ policy from supply_optimization.py, so the two modules
   tell one consistent story rather than assuming unrelated numbers.
"""

import numpy as np

from services.data_loader import get_data
from services.item_economics import critical_ratio, margin as item_margin
from services.supply_optimization import DEFAULT_DEMAND_CV, SERVICE_LEVEL_Z, category_supply_stats, eoq_calculator

_RNG = np.random.default_rng(42)


def _percentiles(arr, ps=(10, 50, 90)):
    return {f"p{p}": round(float(np.percentile(arr, p)), 2) for p in ps}


def simulate_prep_scenario(item, demand_growth_pct=0, demand_vol_multiplier=1.0, prep_quantity=None, n_trials=2000, n_days=90):
    d = get_data()
    pos, inv = d["pos"], d["inventory"]

    item_rows = inv[inv["Item_Name"] == item]
    if item_rows.empty:
        return {"error": f"unknown item '{item}'"}

    cost = item_rows["Unit_Cost"].iloc[0]
    margin = item_margin(pos, item, cost)
    hist_demand = item_rows["Actual_Demand_Qty"].to_numpy()
    hist_mean = hist_demand.mean()

    if prep_quantity is None:
        cr = critical_ratio(pos, item, cost)
        prep_quantity = float(np.quantile(hist_demand, cr))

    sampled = _RNG.choice(hist_demand, size=(n_trials, n_days), replace=True).astype(float)
    scaled = hist_mean + (sampled - hist_mean) * demand_vol_multiplier
    demand = np.clip(scaled * (1 + demand_growth_pct / 100), 0, None)

    spoiled = np.maximum(prep_quantity - demand, 0)
    stockout = np.maximum(demand - prep_quantity, 0)
    daily_cost = spoiled * cost + stockout * margin

    total_cost_per_trial = daily_cost.sum(axis=1)
    waste_units_per_trial = spoiled.sum(axis=1)
    stockout_units_per_trial = stockout.sum(axis=1)
    fill_rate_per_trial = 1 - (stockout.sum(axis=1) / np.maximum(demand.sum(axis=1), 1e-9))
    stockout_day_rate_per_trial = (stockout > 0).mean(axis=1)

    return {
        "item": item,
        "inputs": {
            "demand_growth_pct": demand_growth_pct,
            "demand_vol_multiplier": demand_vol_multiplier,
            "prep_quantity": round(prep_quantity, 1),
            "n_trials": n_trials,
            "n_days": n_days,
        },
        "total_cost_inr": _percentiles(total_cost_per_trial),
        "waste_units": _percentiles(waste_units_per_trial),
        "stockout_units": _percentiles(stockout_units_per_trial),
        "fill_rate_pct": _percentiles(fill_rate_per_trial * 100),
        "stockout_day_rate_pct": _percentiles(stockout_day_rate_per_trial * 100),
        "cost_histogram": np.histogram(total_cost_per_trial, bins=20)[0].tolist(),
        "cost_histogram_edges": [round(float(v), 1) for v in np.histogram(total_cost_per_trial, bins=20)[1]],
        "note": (
            "Demand is bootstrap-resampled from your item's real historical daily demand "
            "(not assumed Normal), scaled by the growth/volatility inputs above, then run "
            "through the same newsvendor cost model as the prep optimizer."
        ),
    }


def simulate_supplier_scenario(
    category,
    annual_demand,
    holding_cost_per_unit_per_year,
    lead_time_override=None,
    demand_growth_pct=0,
    order_qty_override=None,
    service_level="95%",
    demand_cv=DEFAULT_DEMAND_CV,
    n_trials=1000,
    n_days=180,
):
    eoq = eoq_calculator(category, annual_demand, holding_cost_per_unit_per_year, service_level, demand_cv)
    if "error" in eoq:
        return eoq

    stats = category_supply_stats(category)
    lead_time = lead_time_override if lead_time_override is not None else stats["avg_lead_time_days"]
    order_qty = order_qty_override if order_qty_override is not None else eoq["eoq"]

    daily_mean = (annual_demand / 365) * (1 + demand_growth_pct / 100)
    daily_std = daily_mean * demand_cv
    z = SERVICE_LEVEL_Z.get(service_level, SERVICE_LEVEL_Z["95%"])
    # Recomputed fresh at the (possibly overridden) lead time — safety stock
    # scales with sqrt(lead time), so reusing the EOQ calculator's baseline
    # figure here would understate risk under a lead-time-shock scenario.
    safety_stock = z * daily_std * (lead_time ** 0.5)
    reorder_point = daily_mean * lead_time + safety_stock

    lead_time_int = max(1, round(lead_time))
    stockout_days = np.zeros(n_trials)
    total_holding = np.zeros(n_trials)
    total_orders = np.zeros(n_trials)
    unmet_units = np.zeros(n_trials)

    for trial in range(n_trials):
        inventory = reorder_point + order_qty
        pipeline = []  # list of [days_remaining, qty]
        day_stockouts = 0
        orders_placed = 0
        inv_area = 0.0
        unmet = 0.0

        daily_demand = np.clip(_RNG.normal(daily_mean, daily_std, size=n_days), 0, None)

        for day in range(n_days):
            arrivals = [q for rem, q in pipeline if rem <= 0]
            inventory += sum(arrivals)
            pipeline = [[rem - 1, q] for rem, q in pipeline if rem > 0]

            demand_today = daily_demand[day]
            if demand_today > inventory:
                unmet += demand_today - inventory
                day_stockouts += 1
                inventory = 0
            else:
                inventory -= demand_today

            inv_area += inventory

            if inventory <= reorder_point and not pipeline:
                pipeline.append([lead_time_int, order_qty])
                orders_placed += 1

        stockout_days[trial] = day_stockouts
        total_holding[trial] = (inv_area / n_days) * holding_cost_per_unit_per_year * (n_days / 365)
        total_orders[trial] = orders_placed
        unmet_units[trial] = unmet

    ordering_cost = total_orders * stats["avg_delivery_cost"]
    total_cost = total_holding + ordering_cost

    return {
        "category": category,
        "inputs": {
            "annual_demand": annual_demand,
            "holding_cost_per_unit_per_year": holding_cost_per_unit_per_year,
            "lead_time_days": lead_time,
            "demand_growth_pct": demand_growth_pct,
            "order_qty": round(order_qty, 1),
            "reorder_point": round(reorder_point, 1),
            "n_trials": n_trials,
            "n_days": n_days,
        },
        "stockout_days_pct_of_horizon": _percentiles(stockout_days / n_days * 100),
        "unmet_units": _percentiles(unmet_units),
        "orders_placed": _percentiles(total_orders),
        "total_cost_inr": _percentiles(total_cost),
        "holding_cost_inr": _percentiles(total_holding),
        "ordering_cost_inr": _percentiles(ordering_cost),
        "note": (
            "Periodic-review (reorder-point, order-quantity) simulation seeded with the EOQ "
            "policy from the supply optimizer. Demand is Normal(mean, mean*demand_cv) since "
            "ingredient-level daily demand isn't in the source data — override demand_cv if "
            "you have a better estimate for this category."
        ),
    }
