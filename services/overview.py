"""Executive Overview (Slide 01) composition layer. Pulls from the other
service modules; invents nothing. Findings whose module doesn't exist yet
(inventory/reorder, procurement - both Milestone 2) return an explicit
not-supported status rather than a guessed number.
"""

from services.data_loader import get_data
from services import automation, forecasting, newsvendor, procurement, safety_stock


def executive_kpis():
    """8 KPI tiles, each with value+label+context - never a bare number."""
    d = get_data()
    pos, inv, sup = d["pos"], d["inventory"], d["supply"]

    # The POS extract spans 2 full calendar years (2023-2024). "Annual Revenue"
    # must be a per-year rate, not the raw 2-year sum - dividing by the number
    # of distinct calendar years spanned is the disclosed, reproducible method
    # (years_spanned=2 here, matching the reference analysis's own annualized
    # figure). Bills/lines below are extract-size counts, not rates, so they
    # are NOT annualized - they're reported as the full 2-year totals, same as
    # the reference analysis.
    years_spanned = int(pos["Date"].dt.year.nunique())
    total_revenue_2yr = float(pos["Total_Amount"].sum())
    total_profit_2yr = float(pos["Profit"].sum())
    annual_revenue = total_revenue_2yr / years_spanned
    annual_profit = total_profit_2yr / years_spanned
    gross_margin_pct = total_profit_2yr / total_revenue_2yr * 100 if total_revenue_2yr else 0
    orders = int(pos["Transaction_ID"].nunique())
    order_lines = int(len(pos))
    spoilage_cost = float(inv["Spoilage_Cost"].sum())

    return {
        "annual_revenue": {
            "value": round(annual_revenue, 2),
            "label": "Annual Revenue",
            "context": f"~₹{round(annual_revenue / 52):,.0f}/week - annualized from {years_spanned} years, {pos['Date'].min().strftime('%b %Y')} - {pos['Date'].max().strftime('%b %Y')}",
        },
        "gross_margin": {
            "value": round(gross_margin_pct, 2),
            "label": "Gross Margin",
            "context": f"₹{round(annual_profit):,.0f} profit on ₹{round(annual_revenue):,.0f} revenue/yr",
        },
        "orders": {
            "value": orders,
            "label": "Orders / Bills",
            "context": f"{order_lines:,} order lines across {orders:,} bills",
        },
        "order_lines": {
            "value": order_lines,
            "label": "Order Lines",
            "context": f"avg {round(order_lines / orders, 2)} items/bill" if orders else "n/a",
        },
        "spoilage_cost": {
            "value": round(spoilage_cost, 2),
            "label": "Spoilage Cost",
            "context": "2024 inventory log, all items (see Defect C for scope)",
        },
        "shortage_days": {
            "value": round(float((inv["Actual_Demand_Qty"] > inv["Forecasted_Prep_Qty"]).mean() * 100), 2),
            "label": "Prep Shortfall Days",
            "context": "% of item-days where actual demand exceeded the kitchen's own prep plan (inventory log, 2024)",
        },
        "num_items": {
            "value": int(pos["Item_Name"].nunique()),
            "label": "Number of Items",
            "context": "menu items analyzed - not the full menu (see Limitations)",
        },
        "num_suppliers": {
            "value": int(sup["Supplier"].nunique()),
            "label": "Number of Suppliers",
            "context": f"across {sup['Ingredient_Category'].nunique()} ingredient categories",
        },
    }


def decision_pipeline_status():
    """Demand -> Forecast -> Prep -> Inventory -> Reorder -> Supplier
    Allocation stage list with a per-stage build status - reference data,
    not a derived statistic, so later milestones flip a flag here rather
    than editing frontend markup."""
    return {
        "stages": [
            {"stage": "Demand", "status": "built", "note": "POS transactions, 2 years"},
            {"stage": "Forecast", "status": "built", "note": "ARIMAX(0,1,1) + summer regressor"},
            {"stage": "Prep", "status": "built", "note": "Newsvendor critical-ratio model"},
            {"stage": "Inventory", "status": "built", "note": "Safety stock / reorder point, decomposed by supplier"},
            {"stage": "Reorder", "status": "built", "note": "Rule-based trigger, backtested"},
            {"stage": "Supplier Allocation", "status": "built", "note": "Linear programming + TOPSIS"},
        ],
    }


def executive_decision_summary():
    """4 findings: 2 supported (pulled from forecasting/newsvendor's real
    outputs), 2 not_supported (pending Milestone 2's inventory/procurement
    modules)."""
    findings = []

    validation = forecasting.get_demand_validation_bundle()
    improvement = validation.get("cross_item_avg_improvement_pct")
    if improvement is not None:
        findings.append({
            "topic": "demand_forecast_improvement",
            "status": "supported",
            "text": (
                f"ARIMAX demand sensing reduces rolling-origin forecast error by {improvement}% "
                "on average across items versus a naive trailing-week baseline."
            ),
        })
    else:
        findings.append({"topic": "demand_forecast_improvement", "status": "not_supported", "reason": "validation could not be computed"})

    prep_compare = newsvendor.get_prep_compare_bundle()
    avoided_pcts = [
        r["inventory_log_policies"]["static_newsvendor"]["cost_avoided_vs_current_judgment_pct"]
        for r in prep_compare["items"].values()
        if "static_newsvendor" in r.get("inventory_log_policies", {})
    ]
    if avoided_pcts:
        avg_avoided = sum(avoided_pcts) / len(avoided_pcts)
        findings.append({
            "topic": "prep_policy_implication",
            "status": "supported",
            "text": (
                f"A newsvendor-calibrated bias correction to the kitchen's existing daily prep "
                f"judgment avoids an average {round(avg_avoided, 2)}% of current spoilage/stockout "
                "cost across items, without discarding the kitchen's own day-to-day forecast."
            ),
        })
    else:
        findings.append({"topic": "prep_policy_implication", "status": "not_supported", "reason": "prep comparison could not be computed"})

    ss_bundle = safety_stock.safety_stock_bundle()
    ss_range = ss_bundle["decomposed_safety_stock_range_units"]
    variance_share = ss_bundle["between_supplier_variance"]["between_supplier_variance_share_pct"]
    if ss_range.get("min") is not None:
        findings.append({
            "topic": "inventory_reorder_implication",
            "status": "supported",
            "text": (
                f"Item-specific safety stock ranges {ss_range['min']}-{ss_range['max']} units at a 95% "
                f"service level, once decomposed by which supplier actually serves each item's category - "
                f"a single pooled figure would over-provision the smallest movers, since {variance_share}% "
                "of lead-time variance is a supplier-level property, not noise."
            ),
        })
    else:
        findings.append({"topic": "inventory_reorder_implication", "status": "not_supported", "reason": "safety-stock calculation could not be computed"})

    lp = procurement.allocation_lp()
    if "error" not in lp:
        binding = ", ".join(lp["binding_suppliers"]) or "none"
        findings.append({
            "topic": "procurement_implication",
            "status": "supported",
            "text": (
                f"Weekly least-cost allocation across suppliers is bound by assumed supplier capacity "
                f"(currently: {binding}), not lead time - and TOPSIS supplier ranking changes with how "
                "cost is weighted against lead time, so no supplier is 'the best' independent of that "
                "weighting (see Procurement)."
            ),
        })
    else:
        findings.append({"topic": "procurement_implication", "status": "not_supported", "reason": lp.get("error", "allocation could not be computed")})

    return {"findings": findings}


def get_executive_overview_bundle():
    """Backing function for GET /api/overview."""
    return {
        "kpis": executive_kpis(),
        "decision_pipeline": decision_pipeline_status(),
        "decision_summary": executive_decision_summary(),
    }
