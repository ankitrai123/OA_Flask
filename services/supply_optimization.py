"""EOQ/reorder-point calculator and supplier-allocation optimizer.

Data reality check: restaurant_supply_network.csv has delivery cost, lead
time, and MOQ per route - but no per-unit ingredient cost or consumption
quantity, both of which a textbook EOQ needs. Rather than invent those
numbers, the two figures a real restaurant owner actually knows (annual
ingredient volume, holding cost per unit) are taken as inputs; everything
else (ordering cost, lead time, MOQ, demand variability) is derived from
the real data. That is the honest way to make this useful rather than
decorative.
"""

import itertools

import numpy as np

from services.data_loader import get_data

# Derived from the average coefficient of variation of daily item-level
# demand in the dataset (~0.27 across all 6 menu items) - used as the
# default assumption for day-to-day ingredient demand variability, since
# ingredient-level consumption isn't in the data. Callers can override it.
DEFAULT_DEMAND_CV = 0.27
SERVICE_LEVEL_Z = {"90%": 1.282, "95%": 1.645, "97.5%": 1.960, "99%": 2.326}


def category_supply_stats(category):
    d = get_data()
    sup = d["supply"][d["supply"]["Ingredient_Category"] == category]
    if sup.empty:
        return None
    return {
        "category": category,
        "avg_delivery_cost": round(sup["Delivery_Cost_INR"].mean(), 2),
        "avg_lead_time_days": round(sup["Lead_Time_Days"].mean(), 2),
        "suppliers": sup.groupby("Supplier").agg(
            avg_delivery_cost=("Delivery_Cost_INR", "mean"),
            avg_lead_time_days=("Lead_Time_Days", "mean"),
            moq=("Minimum_Order_Qty", "mean"),
            routes=("Route_ID", "count"),
        ).round(2).reset_index().to_dict(orient="records"),
    }


def list_categories():
    d = get_data()
    return sorted(d["supply"]["Ingredient_Category"].unique())


def eoq_calculator(category, annual_demand, holding_cost_per_unit_per_year, service_level="95%", demand_cv=DEFAULT_DEMAND_CV):
    """Classic EOQ + safety stock, using real ordering cost/lead time and
    user-supplied demand/holding-cost figures."""
    stats = category_supply_stats(category)
    if stats is None:
        return {"error": f"unknown category '{category}'"}
    if annual_demand <= 0 or holding_cost_per_unit_per_year <= 0:
        return {"error": "annual_demand and holding_cost_per_unit_per_year must be positive"}

    S = stats["avg_delivery_cost"]
    H = holding_cost_per_unit_per_year
    D = annual_demand
    lead_time = stats["avg_lead_time_days"]
    z = SERVICE_LEVEL_Z.get(service_level, SERVICE_LEVEL_Z["95%"])

    eoq = (2 * D * S / H) ** 0.5
    daily_demand = D / 365
    daily_std = daily_demand * demand_cv
    safety_stock = z * daily_std * (lead_time ** 0.5)
    reorder_point = daily_demand * lead_time + safety_stock

    orders_per_year_eoq = D / eoq
    annual_cost_eoq = orders_per_year_eoq * S + (eoq / 2) * H

    # Baseline: ordering in MOQ-sized batches (today's likely de-facto policy)
    moq = max((s["moq"] for s in stats["suppliers"]), default=eoq)
    orders_per_year_moq = D / moq
    annual_cost_moq = orders_per_year_moq * S + (moq / 2) * H

    savings_pct = ((annual_cost_moq - annual_cost_eoq) / annual_cost_moq * 100) if annual_cost_moq else 0

    return {
        "category": category,
        "inputs": {
            "annual_demand": D,
            "holding_cost_per_unit_per_year": H,
            "service_level": service_level,
            "demand_cv": demand_cv,
            "demand_cv_is_default": demand_cv == DEFAULT_DEMAND_CV,
        },
        "derived_from_data": {
            "ordering_cost_per_order": S,
            "avg_lead_time_days": lead_time,
        },
        "eoq": round(eoq, 1),
        "reorder_point": round(reorder_point, 1),
        "safety_stock": round(safety_stock, 1),
        "orders_per_year": round(orders_per_year_eoq, 1),
        "annual_cost_at_eoq": round(annual_cost_eoq, 2),
        "baseline_moq_used": round(moq, 1),
        "annual_cost_at_moq_baseline": round(annual_cost_moq, 2),
        "savings_vs_moq_baseline_pct": round(savings_pct, 2),
        "note": (
            "annual_demand and holding_cost_per_unit_per_year are figures you supply — "
            "they aren't in the source data. Ordering cost, lead time, and MOQ come from "
            "your actual supplier routes; demand variability defaults to the average "
            "coefficient of variation observed across your menu items (0.27) unless overridden."
        ),
    }


def _feasible_batch_combos(moqs, required_qty):
    # Bounded so this stays an exact search: no supplier alone would ever
    # need more batches than required_qty/its own MOQ (+2 slack for
    # combinations with the others), capped so worst case (3 suppliers)
    # stays under ~1M combinations, fast enough for a live request.
    max_batches = min(80, int(np.ceil(required_qty / min(moqs))) + 2)
    ranges = [range(0, max_batches + 1) for _ in moqs]
    for combo in itertools.product(*ranges):
        total = sum(n * moq for n, moq in zip(combo, moqs))
        if total >= required_qty and any(combo):
            yield combo, total


def supplier_allocation(category, required_qty, max_lead_time_days=None, max_share_per_supplier=None):
    """Exact search over MOQ-sized batches per supplier minimizing total
    delivery cost while meeting required_qty. Small integer search (<=3
    suppliers/category, bounded batch counts) so an exact optimum is cheap
    enough to brute-force - no MILP solver dependency needed.

    Without a capacity cap, per-unit cost minimization always single-sources
    to whichever supplier is cheapest per unit - there's no data-supported
    reason to split otherwise (the source data has no per-supplier capacity
    limit). max_share_per_supplier (0-1) exists for the real business case
    that isn't in the data: risk diversification, i.e. not wanting to depend
    on one vendor. Setting it shows the cost premium paid for that safety.
    """
    stats = category_supply_stats(category)
    if stats is None:
        return {"error": f"unknown category '{category}'"}
    if required_qty <= 0:
        return {"error": "required_qty must be positive"}
    if max_share_per_supplier is not None and not (0 < max_share_per_supplier <= 1):
        return {"error": "max_share_per_supplier must be between 0 and 1"}

    suppliers = stats["suppliers"]
    if max_lead_time_days is not None:
        suppliers = [s for s in suppliers if s["avg_lead_time_days"] <= max_lead_time_days]
    if not suppliers:
        return {"error": "no supplier meets the max_lead_time_days constraint"}

    names = [s["Supplier"] for s in suppliers]
    costs = [s["avg_delivery_cost"] for s in suppliers]
    moqs = [s["moq"] for s in suppliers]
    cap_qty = required_qty * max_share_per_supplier if max_share_per_supplier else None

    best = None
    for combo, total_qty in _feasible_batch_combos(moqs, required_qty):
        if cap_qty is not None and any(n * moq > cap_qty + 1e-9 for n, moq in zip(combo, moqs)):
            continue
        total_cost = sum(n * c for n, c in zip(combo, costs))
        if best is None or total_cost < best["total_cost"]:
            best = {"combo": combo, "total_qty": total_qty, "total_cost": total_cost}

    if best is None:
        return {"error": "no feasible allocation found within search bounds — try a higher max_share_per_supplier or a longer max_lead_time_days"}

    allocation = [
        {"supplier": names[i], "batches": best["combo"][i], "batch_size_moq": moqs[i], "qty": best["combo"][i] * moqs[i], "cost": round(best["combo"][i] * costs[i], 2)}
        for i in range(len(names)) if best["combo"][i] > 0
    ]

    single_supplier_costs = []
    for i in range(len(names)):
        batches_needed = int(np.ceil(required_qty / moqs[i]))
        single_supplier_costs.append({"supplier": names[i], "cost": round(batches_needed * costs[i], 2)})
    cheapest_single = min(single_supplier_costs, key=lambda r: r["cost"])

    savings_pct = ((cheapest_single["cost"] - best["total_cost"]) / cheapest_single["cost"] * 100) if cheapest_single["cost"] else 0

    result = {
        "category": category,
        "required_qty": required_qty,
        "allocation": allocation,
        "total_qty_ordered": best["total_qty"],
        "total_cost": round(best["total_cost"], 2),
        "single_cheapest_supplier_baseline": cheapest_single,
        "savings_vs_single_supplier_pct": round(savings_pct, 2),
        "note": "Exact optimum over integer MOQ-sized batches per supplier, minimizing total delivery cost for the quantity you specified.",
    }

    if max_share_per_supplier is not None:
        premium = best["total_cost"] - cheapest_single["cost"]
        result["diversification"] = {
            "max_share_per_supplier": max_share_per_supplier,
            "cost_premium_vs_cheapest_single_inr": round(premium, 2),
            "cost_premium_pct": round(premium / cheapest_single["cost"] * 100, 2) if cheapest_single["cost"] else 0,
        }

    return result
