"""Executive Overview (Slide 01) composition layer. Pulls from the other
service modules; invents nothing. Findings whose module doesn't exist yet
(inventory/reorder, procurement - both Milestone 2) return an explicit
not-supported status rather than a guessed number.
"""

from services.data_loader import get_data
from services import forecasting, newsvendor


def executive_kpis():
    """8 KPI tiles, each with value+label+context - never a bare number."""
    d = get_data()
    pos, inv, sup = d["pos"], d["inventory"], d["supply"]

    total_revenue = float(pos["Total_Amount"].sum())
    total_profit = float(pos["Profit"].sum())
    gross_margin_pct = total_profit / total_revenue * 100 if total_revenue else 0
    orders = int(pos["Transaction_ID"].nunique())
    order_lines = int(len(pos))
    spoilage_cost = float(inv["Spoilage_Cost"].sum())

    return {
        "annual_revenue": {
            "value": round(total_revenue, 2),
            "label": "Annual Revenue",
            "context": f"{pos['Date'].min().strftime('%b %Y')} - {pos['Date'].max().strftime('%b %Y')}",
        },
        "gross_margin": {
            "value": round(gross_margin_pct, 2),
            "label": "Gross Margin",
            "context": f"₹{round(total_profit):,.0f} profit on ₹{round(total_revenue):,.0f} revenue",
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
            "status": "not_supported",
            "label": "Shortage Days",
            "reason": (
                "A true stockout/shortage day needs a running-inventory reorder-point model "
                "(Milestone 2). Not conflated with the inventory log's internal prep-shortfall "
                "figure, a different concept shown on the EDA slide."
            ),
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
            {"stage": "Inventory", "status": "planned", "note": "Safety stock / reorder point"},
            {"stage": "Reorder", "status": "planned", "note": "Rule-based trigger"},
            {"stage": "Supplier Allocation", "status": "planned", "note": "Linear programming + TOPSIS"},
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

    findings.append({
        "topic": "inventory_reorder_implication",
        "status": "not_supported",
        "reason": "Item-specific safety stock and reorder points need Milestone 2's Inventory & Replenishment module.",
    })
    findings.append({
        "topic": "procurement_implication",
        "status": "not_supported",
        "reason": "Supplier allocation (LP) and multi-criteria ranking (TOPSIS) need Milestone 2's Procurement module.",
    })

    return {"findings": findings}


def get_executive_overview_bundle():
    """Backing function for GET /api/overview."""
    return {
        "kpis": executive_kpis(),
        "decision_pipeline": decision_pipeline_status(),
        "decision_summary": executive_decision_summary(),
    }
