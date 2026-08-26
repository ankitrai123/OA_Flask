"""Newsvendor prep-quantity model (Slide 05).

Cu = contribution margin (understock/stockout cost - the margin lost when
demand exceeds prep). Co = unit cost (overstock/spoilage cost; salvage is
0 in this data). Critical ratio CR = Cu / (Cu + Co).

Builds on services.optimizer.optimize_prep() (kept as-is, not duplicated)
and services.item_economics rather than reinventing that math.

KEY DESIGN DECISION (see the project's Data Quality slide, Defect C):
the inventory log's Actual_Demand_Qty and POS-derived demand are
empirically uncorrelated (r=-0.02) - not two views of the same series.
So compare_prep_policies() below NEVER compares its two panels to each
other: "inventory_log_policies" (current judgment vs static newsvendor,
both on the inventory log's own internal scale - exactly what
optimizer.optimize_prep() already validly computes) and
"dynamic_newsvendor_pos_scale" (ARIMAX-driven, POS scale, compared only
against a POS-scale naive baseline) are structurally separate. Comparing
them directly would be exactly the kind of fabricated number this project
must avoid.

Framing rule enforced throughout: results are "cost avoided relative to a
historical/naive counterfactual", never "savings we generated".
"""

import numpy as np
from scipy.stats import norm

from services.data_loader import get_data
from services.item_economics import avg_realized_price, margin as item_margin
from services import forecasting, optimizer, simulator


def _known_items():
    d = get_data()
    return set(d["pos"]["Item_Name"].unique())


def newsvendor_inputs(item):
    """Cu, Co, CR, and the observed price/cost they're built from - the
    numbers the Methodology drawer quotes."""
    if item not in _known_items():
        return {"error": f"unknown item '{item}'"}

    d = get_data()
    inv, pos = d["inventory"], d["pos"]
    item_inv = inv[inv["Item_Name"] == item]
    cost = float(item_inv["Unit_Cost"].iloc[0]) if not item_inv.empty else float(pos[pos["Item_Name"] == item]["Unit_Cost"].iloc[0])
    price = float(avg_realized_price(pos, item))
    margin = float(item_margin(pos, item, cost))
    cr = margin / (margin + cost) if (margin + cost) else 0.5

    return {
        "item": item,
        "unit_cost_inr": round(cost, 2),
        "contribution_margin_inr": round(margin, 2),
        "critical_ratio": round(cr, 4),
        "avg_realized_price_inr": round(price, 2),
    }


def _optimal_quantity(cr, demand_forecast):
    """demand_forecast is either an array of historical/sample demand
    values (-> empirical CR-th quantile) or a {"mean","std"} dict from
    ARIMAX (-> the standard newsvendor closed form under a Normal
    approximation, Q* = mean + std * Phi^-1(CR))."""
    if isinstance(demand_forecast, dict):
        return float(demand_forecast["mean"] + demand_forecast["std"] * norm.ppf(cr))
    return float(np.quantile(np.asarray(demand_forecast, dtype=float), cr))


def _expected_costs(recommended_qty, demand_forecast, cu, co, n_mc=20000):
    """Expected spoilage/stockout cost at a given prep quantity. For an
    array, the direct historical expectation; for a {"mean","std"} dict, a
    seeded Monte Carlo draw (kept separate from simulator.py's own RNG)."""
    if isinstance(demand_forecast, dict):
        rng = np.random.default_rng(7)
        draws = np.clip(rng.normal(demand_forecast["mean"], demand_forecast["std"], n_mc), 0, None)
    else:
        draws = np.asarray(demand_forecast, dtype=float)

    spoilage = np.maximum(recommended_qty - draws, 0)
    stockout = np.maximum(draws - recommended_qty, 0)
    return float(spoilage.mean() * co), float(stockout.mean() * cu)


def calculate_newsvendor(item, demand_forecast=None, spoilage_cost_override=None, stockout_cost_override=None, service_level_override=None):
    """Core newsvendor calculation, decoupled from *how* demand was
    estimated. demand_forecast: an array (historical/user samples), a
    {"mean","std"} dict (ARIMAX), or None (falls back to
    forecasting.get_item_daily_demand(item))."""
    if item not in _known_items():
        return {"error": f"unknown item '{item}'"}

    inputs = newsvendor_inputs(item)
    co = spoilage_cost_override if spoilage_cost_override is not None else inputs["unit_cost_inr"]
    cu = stockout_cost_override if stockout_cost_override is not None else inputs["contribution_margin_inr"]

    if service_level_override is not None:
        cr = service_level_override / 100 if service_level_override > 1 else service_level_override
    else:
        cr = cu / (cu + co) if (cu + co) else 0.5

    if demand_forecast is None:
        demand_forecast = forecasting.get_item_daily_demand(item).to_numpy()
        demand_source = "historical"
    elif isinstance(demand_forecast, dict):
        demand_source = "arimax"
    else:
        demand_source = "user_override"

    recommended_qty = _optimal_quantity(cr, demand_forecast)
    spoilage_cost, stockout_cost = _expected_costs(recommended_qty, demand_forecast, cu, co)

    return {
        "item": item,
        "cu_inr": round(float(cu), 2),
        "co_inr": round(float(co), 2),
        "critical_ratio": round(float(cr), 4),
        "recommended_qty": round(recommended_qty, 1),
        "demand_source": demand_source,
        "expected_spoilage_cost_inr": round(spoilage_cost, 2),
        "expected_stockout_cost_inr": round(stockout_cost, 2),
        "expected_total_cost_inr": round(spoilage_cost + stockout_cost, 2),
    }


def compare_prep_policies(item):
    """Structurally-split three-way comparison - see module docstring for
    why the two panels are never compared to each other."""
    if item not in _known_items():
        return {"error": f"unknown item '{item}'"}

    prep_by_item = {r["item"]: r for r in optimizer.optimize_prep()}
    row = prep_by_item.get(item)

    if row is None:
        inventory_log_policies = {"status": "not_supported", "reason": "item not found in the inventory log"}
    else:
        inventory_log_policies = {
            "scope_note": (
                "Both figures computed on the inventory log's own internal scale "
                "(Forecasted_Prep_Qty vs Actual_Demand_Qty) - a valid self-consistent "
                "comparison, but not on the same scale as POS-derived demand (see Defect C)."
            ),
            "current_judgment": {"avg_qty": row["current_avg_prep_qty"], "annual_cost_inr": row["current_annual_cost"]},
            "static_newsvendor": {
                "avg_qty": row["recommended_avg_prep_qty"],
                "annual_cost_inr": row["projected_annual_cost"],
                "cost_avoided_vs_current_judgment_inr": row["projected_savings_inr"],
                "cost_avoided_vs_current_judgment_pct": row["projected_savings_pct"],
            },
        }

    osa = forecasting.get_one_step_ahead_forecast(item)
    if osa is None:
        dynamic_newsvendor_pos_scale = {
            "status": "not_supported",
            "reason": "ARIMAX model unavailable for this item (insufficient history, or the fit did not converge)",
        }
    else:
        inputs = newsvendor_inputs(item)
        cr = inputs["critical_ratio"]
        cu, co = inputs["contribution_margin_inr"], inputs["unit_cost_inr"]

        arimax_forecast = {"mean": osa["mean"], "std": osa["std"]}
        recommended_qty = _optimal_quantity(cr, arimax_forecast)
        rec_spoil, rec_stockout = _expected_costs(recommended_qty, arimax_forecast, cu, co)
        annual_cost_at_recommended = (rec_spoil + rec_stockout) * 365

        hist_arr = forecasting.get_item_daily_demand(item).to_numpy()
        naive_baseline_qty = float(np.quantile(hist_arr, cr))
        naive_spoil, naive_stockout = _expected_costs(naive_baseline_qty, hist_arr, cu, co)
        annual_cost_at_naive = (naive_spoil + naive_stockout) * 365

        cost_avoided = annual_cost_at_naive - annual_cost_at_recommended
        cost_avoided_pct = cost_avoided / annual_cost_at_naive * 100 if annual_cost_at_naive else 0

        dynamic_newsvendor_pos_scale = {
            "scope_note": (
                "Computed on POS-derived demand (the corrected scale) and compared only "
                "against a POS-scale naive baseline (the same critical ratio applied to the raw "
                "historical quantile, no ARIMAX signal) - never against the inventory-log "
                "'current judgment' figure above, because the two scales are empirically "
                "uncorrelated (Defect C)."
            ),
            "recommended_qty": round(recommended_qty, 1),
            "naive_baseline_qty": round(naive_baseline_qty, 1),
            "annual_cost_at_recommended_inr": round(annual_cost_at_recommended, 2),
            "annual_cost_at_naive_baseline_inr": round(annual_cost_at_naive, 2),
            "cost_avoided_vs_naive_baseline_inr": round(cost_avoided, 2),
            "cost_avoided_vs_naive_baseline_pct": round(cost_avoided_pct, 2),
        }

    return {
        "item": item,
        "inventory_log_policies": inventory_log_policies,
        "dynamic_newsvendor_pos_scale": dynamic_newsvendor_pos_scale,
        "framing_note": (
            "'Cost avoided' describes a projection against a historical/naive counterfactual, "
            "not a booked saving. The inventory-log and POS-scale panels are never compared to "
            "each other directly - see Defect C."
        ),
    }


def simulate_newsvendor_whatif(item, demand_qty=None, spoilage_cost=None, stockout_cost=None, service_level=None, n_trials=2000, n_days=90):
    """Backs the interactive 'what if demand/costs change' simulator.
    demand_qty (if given) is a single user-typed scenario point, paired
    with the item's historical demand std to form an ARIMAX-shaped
    {"mean","std"} input so the same Normal-approximation math applies."""
    if item not in _known_items():
        return {"error": f"unknown item '{item}'"}

    hist_arr = forecasting.get_item_daily_demand(item).to_numpy()

    if demand_qty is not None:
        demand_forecast = {"mean": float(demand_qty), "std": float(hist_arr.std())}
        demand_growth_pct = (float(demand_qty) / hist_arr.mean() - 1) * 100 if hist_arr.mean() else 0
    else:
        demand_forecast = hist_arr
        demand_growth_pct = 0

    result = calculate_newsvendor(
        item,
        demand_forecast=demand_forecast,
        spoilage_cost_override=spoilage_cost,
        stockout_cost_override=stockout_cost,
        service_level_override=service_level,
    )
    if "error" in result:
        return result

    simulation = simulator.simulate_prep_scenario(
        item,
        demand_growth_pct=demand_growth_pct,
        prep_quantity=result["recommended_qty"],
        unit_cost_override=spoilage_cost,
        margin_override=stockout_cost,
        n_trials=n_trials,
        n_days=n_days,
    )

    return {**result, "simulation": simulation}


def get_prep_policy_aggregate_comparison():
    """Q2's headline: Current judgment vs a Static (one blanket quantity
    for every item) vs Dynamic (each item's own newsvendor-optimal
    quantity) prep policy, scored on the inventory log's own internal
    scale (366 days) and summed across all 6 items into one annual cost
    figure per policy - the "fixed quantity is worse than tailoring per
    item" result. All three stay on the inventory-log scale throughout
    (never mixed with POS-scale figures - see Defect C), which is exactly
    why this is a *separate*, additional aggregate view, not a replacement
    for compare_prep_policies()'s per-item Panel A/B split above, which
    stays exactly as built.

    Current and Dynamic reuse services.optimizer.optimize_prep() as-is:
    - "Current" = the kitchen's own current_annual_cost (its actual
      judgment-based prep quantity, scored against real Actual_Demand_Qty).
    - "Dynamic" = optimize_prep()'s own bias-corrected, item-specific
      critical-ratio quantity (projected_annual_cost) - tailored per item.
    "Static" is the one genuinely new policy: a single order-up-to
    quantity - the pooled demand quantile at the mean critical ratio
    across items - applied identically to every item regardless of its
    own scale, deliberately a "one target fits none" strawman.
    """
    d = get_data()
    pos, inv = d["pos"], d["inventory"]
    prep_rows = optimizer.optimize_prep()
    if not prep_rows:
        return {"status": "not_supported", "reason": "prep optimizer returned no items"}

    items = sorted(_known_items())
    per_item_info = {}
    for item in items:
        item_inv = inv[inv["Item_Name"] == item]
        if item_inv.empty:
            continue
        cost = float(item_inv["Unit_Cost"].iloc[0])
        margin = float(item_margin(pos, item, cost))
        cr = margin / (margin + cost) if (margin + cost) else 0.5
        per_item_info[item] = {"cost": cost, "margin": margin, "cr": cr, "demand": item_inv["Actual_Demand_Qty"].to_numpy()}

    if not per_item_info:
        return {"status": "not_supported", "reason": "no items found in the inventory log"}

    current_total = sum(r["current_annual_cost"] for r in prep_rows)
    dynamic_total = sum(r["projected_annual_cost"] for r in prep_rows)

    pooled_demand = np.concatenate([v["demand"] for v in per_item_info.values()])
    mean_cr = float(np.mean([v["cr"] for v in per_item_info.values()]))
    static_qty = float(np.quantile(pooled_demand, mean_cr))

    static_total = 0.0
    for v in per_item_info.values():
        spoiled = np.maximum(static_qty - v["demand"], 0).sum() * v["cost"]
        stockout = np.maximum(v["demand"] - static_qty, 0).sum() * v["margin"]
        static_total += spoiled + stockout

    cr_values = [round(r["critical_ratio"], 3) for r in prep_rows]
    static_vs_dynamic_pct = (static_total - dynamic_total) / dynamic_total * 100 if dynamic_total else 0

    return {
        "status": "supported",
        "scope_note": (
            "All three policies are scored entirely on the inventory log's own internal scale "
            "(Actual_Demand_Qty, 366 days) - never mixed with POS-scale figures elsewhere on this "
            "console (see Defect C)."
        ),
        "current": {"annual_cost_inr": round(current_total, 2), "description": "The kitchen's actual day-to-day prep judgment"},
        "static": {
            "annual_cost_inr": round(static_total, 2),
            "order_up_to_qty": round(static_qty, 1),
            "description": "One single order-up-to quantity applied identically to every item, ignoring each item's own scale and critical ratio",
        },
        "dynamic": {
            "annual_cost_inr": round(dynamic_total, 2),
            "description": "Each item's own bias-corrected, critical-ratio-tailored prep quantity",
        },
        "static_worse_than_dynamic_pct": round(static_vs_dynamic_pct, 1),
        "critical_ratio_range": {"min": min(cr_values), "max": max(cr_values)},
        "interpretation": (
            f"A single fixed prep quantity across all items costs {round(static_vs_dynamic_pct)}% more "
            f"than tailoring per item, because each item's critical ratio differs "
            f"({min(cr_values)}-{max(cr_values)}) and the café's own current judgment is already close "
            "to its item-specific optimum. This is a cost avoided by not standardizing, not a saving "
            "found by a new policy."
        ),
    }


def get_newsvendor_bundle():
    """Backing function for GET /api/prep/newsvendor (all items)."""
    return {"items": {item: newsvendor_inputs(item) for item in sorted(_known_items())}}


def get_prep_compare_bundle():
    """Backing function for GET /api/prep/compare (all items)."""
    return {"items": {item: compare_prep_policies(item) for item in sorted(_known_items())}}
