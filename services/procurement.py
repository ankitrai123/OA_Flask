"""Procurement - LP Allocation & TOPSIS Sensitivity (Q3B, Slide 06).

Two independent methods answer "when and from whom to replenish", on
purpose, so neither one alone is presented as the single answer:

1. A linear program (scipy.optimize.linprog, method="highs") allocates
   weekly category-level purchase quantities across the 3 suppliers at
   least cost, subject to a per-supplier CAPACITY constraint. The dual
   value of a binding capacity constraint (its "shadow price") is the
   marginal cost of that supplier's capacity ceiling - what you'd save per
   extra unit they could deliver.

2. TOPSIS ranks the suppliers serving each category under three weighting
   scenarios (cost-heavy, lead-time-heavy, balanced) - deliberately run as
   a sensitivity check, not a single score, because the ranking changes
   with the weights (verified below), so no supplier is "the best" in any
   weighting-independent sense.

CAPACITY IS NOT IN THE SOURCE DATA. restaurant_supply_network.csv has
delivery cost, lead time, and MOQ per route - no capacity column at all
(confirmed by inspecting every column). Capacity is therefore an explicit,
user-adjustable ASSUMPTION input, never fabricated from the data. The
defaults below are illustrative starting points, not a claim about what
any supplier can actually deliver - replace them with real capacity
figures when you have them. Required weekly quantity per category IS
derived from real data: each item's own POS daily demand (via
forecasting.get_item_daily_demand), summed to weekly, aggregated by the
item->ingredient-category assumption already used in services.safety_stock
(kept as the single source of that mapping, not re-declared here).
"""

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from services.data_loader import get_data
from services import forecasting
from services.safety_stock import ITEM_TO_CATEGORY

DEFAULT_CAPACITY = {
    "City Central Market": 250,
    "Local Farm Co.": 150,
    "Metro Wholesale": 300,
}

TOPSIS_WEIGHT_SCENARIOS = {
    "cost_heavy": {"unit_cost": 0.6, "lead_time": 0.2, "moq": 0.2},
    "lead_time_heavy": {"unit_cost": 0.2, "lead_time": 0.6, "moq": 0.2},
    "balanced": {"unit_cost": 0.34, "lead_time": 0.33, "moq": 0.33},
}


def _round(x, n=2):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    return round(x, n) if isinstance(x, float) else x


def _unit_cost_matrix():
    """Delivery_Cost_INR / Minimum_Order_Qty, averaged per route - the same
    per-unit price basis Defect D's audit uses. Returns {(supplier, category): cost}."""
    d = get_data()
    sup = d["supply"]
    grouped = sup.groupby(["Supplier", "Ingredient_Category"]).apply(
        lambda g: float((g["Delivery_Cost_INR"] / g["Minimum_Order_Qty"]).mean())
    )
    return grouped.to_dict()


def required_weekly_qty_by_category():
    """Real weekly quantity required per ingredient category, derived from
    each mapped item's own POS-derived daily demand (mean * 7), summed
    across every item assigned to that category."""
    totals = {}
    for item, category in ITEM_TO_CATEGORY.items():
        daily_mean = float(forecasting.get_item_daily_demand(item).mean())
        totals[category] = totals.get(category, 0.0) + daily_mean * 7
    return {c: _round(v) for c, v in totals.items()}


def allocation_lp(capacity=None):
    """Solves the least-cost weekly allocation LP. capacity: optional dict
    overriding DEFAULT_CAPACITY for any subset of suppliers (an Assumption
    input from the analyst)."""
    cap = {**DEFAULT_CAPACITY, **(capacity or {})}
    unit_cost = _unit_cost_matrix()
    required = required_weekly_qty_by_category()

    pairs = list(unit_cost.keys())
    costs = np.array([unit_cost[p] for p in pairs])
    suppliers = sorted({s for s, _ in pairs})
    categories = sorted({c for _, c in pairs})
    n = len(pairs)

    a_ub, b_ub = [], []
    for s in suppliers:
        a_ub.append([1.0 if p[0] == s else 0.0 for p in pairs])
        b_ub.append(cap.get(s, 0.0))
    n_cap_rows = len(suppliers)
    for c in categories:
        a_ub.append([-1.0 if p[1] == c else 0.0 for p in pairs])
        b_ub.append(-required.get(c, 0.0))

    res = linprog(costs, A_ub=a_ub, b_ub=b_ub, bounds=[(0, None)] * n, method="highs")
    if not res.success:
        return {
            "error": (
                "No feasible allocation under the given capacity - total capacity is below total "
                "required quantity. Raise one or more supplier capacities."
            ),
            "capacity_used": cap,
            "required_weekly_qty": required,
        }

    allocation = [
        {"supplier": pairs[i][0], "category": pairs[i][1], "qty": _round(res.x[i], 1), "unit_cost_inr": _round(costs[i], 2), "cost_inr": _round(res.x[i] * costs[i], 2)}
        for i in range(n) if res.x[i] > 1e-6
    ]

    marginals = res.ineqlin.marginals
    shadow_prices = {}
    for i, s in enumerate(suppliers):
        used = sum(a["qty"] for a in allocation if a["supplier"] == s)
        binding = abs(used - cap.get(s, 0.0)) < 1e-6 and cap.get(s, 0.0) > 0
        shadow_prices[s] = {
            "capacity": cap.get(s, 0.0),
            "qty_used": _round(used, 1),
            "binding": bool(binding),
            "shadow_price_inr_per_unit": _round(abs(marginals[i]), 2) if binding else 0,
        }

    total_qty = sum(required.values())
    total_cost = float(res.fun)
    revenue = float(get_data()["pos"]["Total_Amount"].sum())

    return {
        "capacity_used": cap,
        "capacity_is_assumption": True,
        "required_weekly_qty": required,
        "allocation": allocation,
        "total_weekly_cost_inr": _round(total_cost),
        "total_weekly_qty": _round(total_qty),
        "shadow_prices": shadow_prices,
        "binding_suppliers": [s for s, v in shadow_prices.items() if v["binding"]],
        "note": (
            "Solved via linear programming (scipy.optimize.linprog, method='highs') minimizing "
            "total delivery cost subject to meeting each category's real required weekly quantity "
            "and each supplier's assumed capacity. A supplier whose capacity constraint is binding "
            "has a nonzero shadow price - the marginal cost of that ceiling, i.e. what one more unit "
            "of their capacity would be worth."
        ),
    }


def _topsis(matrix, weights_dict, criteria_order):
    weights = np.array([weights_dict[c] for c in criteria_order])
    values = matrix[criteria_order].to_numpy(dtype=float)
    norms = np.sqrt((values ** 2).sum(axis=0))
    norms[norms == 0] = 1
    normalized = values / norms
    weighted = normalized * weights
    # every criterion here (cost, lead time, MOQ) is "lower is better"
    ideal_best = weighted.min(axis=0)
    ideal_worst = weighted.max(axis=0)
    d_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))
    closeness = d_worst / np.where((d_best + d_worst) == 0, 1, d_best + d_worst)
    return closeness


def topsis_sensitivity():
    """Ranks each category's serving suppliers under 3 weighting scenarios.
    Returns, per category, the ranking under each scenario and whether the
    top-ranked supplier changes across them."""
    d = get_data()
    sup = d["supply"]
    criteria_order = ["unit_cost", "lead_time", "moq"]

    results = {}
    for category, g in sup.groupby("Ingredient_Category"):
        rows = []
        for supplier, rows_df in g.groupby("Supplier"):
            rows.append({
                "supplier": supplier,
                "unit_cost": float((rows_df["Delivery_Cost_INR"] / rows_df["Minimum_Order_Qty"]).mean()),
                "lead_time": float(rows_df["Lead_Time_Days"].mean()),
                "moq": float(rows_df["Minimum_Order_Qty"].mean()),
            })
        matrix = pd.DataFrame(rows).set_index("supplier")

        scenario_rankings = {}
        for scenario, weights in TOPSIS_WEIGHT_SCENARIOS.items():
            closeness = _topsis(matrix, weights, criteria_order)
            ranked = sorted(zip(matrix.index, closeness), key=lambda x: -x[1])
            scenario_rankings[scenario] = [{"supplier": s, "closeness": _round(float(c), 3)} for s, c in ranked]

        top_suppliers = {scenario: rows[0]["supplier"] for scenario, rows in scenario_rankings.items()}
        rankings_flip = len(set(top_suppliers.values())) > 1

        results[category] = {
            "criteria": {"unit_cost": "lower is better", "lead_time": "lower is better", "moq": "lower is better (more flexible)"},
            "scenario_rankings": scenario_rankings,
            "top_supplier_by_scenario": top_suppliers,
            "rankings_flip_with_weighting": rankings_flip,
        }

    any_flip = any(v["rankings_flip_with_weighting"] for v in results.values())
    return {
        "weight_scenarios": TOPSIS_WEIGHT_SCENARIOS,
        "by_category": results,
        "interpretation": (
            "Supplier ranking changes with the weighting scenario in "
            f"{sum(v['rankings_flip_with_weighting'] for v in results.values())} of {len(results)} "
            "categories - no supplier is 'the best' independent of how cost is traded off against "
            "lead time; the ranking is only ever the best answer under a stated weighting."
            if any_flip else
            "Rankings are stable across all tested weighting scenarios for these categories."
        ),
    }


def procurement_bundle(capacity=None):
    """Backing function for GET/POST /api/procurement."""
    return {
        "lp_allocation": allocation_lp(capacity),
        "topsis_sensitivity": topsis_sensitivity(),
    }
