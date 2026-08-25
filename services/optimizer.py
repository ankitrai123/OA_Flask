"""Three standard, explainable optimizers built on top of the raw data.

1. Prep / waste optimizer  -> classic newsvendor (order-up-to) model.
2. Pricing optimizer       -> empirical discount-bucket margin analysis.
3. Procurement optimizer   -> weighted least-cost supplier scoring.
"""

import numpy as np
import pandas as pd

from services.data_loader import get_data


def _round(x, n=2):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    return round(x, n) if isinstance(x, float) else x


def optimize_prep():
    """Newsvendor bias-correction: how much to shift the *existing* daily
    prep forecast per item, not replace it.

    The kitchen's day-to-day forecast already tracks actual demand closely
    (observed correlation ~0.85-0.88), so throwing it away for one flat
    order-up-to quantity would discard real signal. Instead we find the
    constant additive shift to that forecast whose residual distribution
    hits the newsvendor critical ratio:

      CR = Cu / (Cu + Co),  Cu = contribution margin (understock cost),
                            Co = unit cost (overstock/spoilage cost, salvage is 0)
      shift = CR-th quantile of (Actual_Demand_Qty - Forecasted_Prep_Qty)

    This is the in-sample cost-minimizing shift given the current forecast,
    so it can only break even or improve on it (adj = 0 means the existing
    forecast is already well-calibrated for that item).
    """
    d = get_data()
    pos = d["pos"]
    inv = d["inventory"]

    price_cost = pos.groupby("Item_Name").agg(
        avg_realized_price=("Unit_Price", lambda s: (s - pos.loc[s.index, "Discount_Applied"]).mean()),
    )

    results = []
    for item, day in inv.groupby("Item_Name"):
        cost = day["Unit_Cost"].iloc[0]
        avg_price = price_cost.loc[item, "avg_realized_price"] if item in price_cost.index else cost * 1.5
        margin = max(avg_price - cost, 1e-6)
        cr = margin / (margin + cost)

        forecast = day["Forecasted_Prep_Qty"].to_numpy()
        demand = day["Actual_Demand_Qty"].to_numpy()
        residual = demand - forecast

        adjustment = round(float(np.quantile(residual, cr)))
        new_forecast = np.maximum(forecast + adjustment, 0)

        current_spoiled_cost = (day["Spoiled_Qty"] * cost).sum()
        current_understock_cost = np.maximum(demand - forecast, 0).sum() * margin
        current_total_cost = current_spoiled_cost + current_understock_cost

        new_spoiled = np.maximum(new_forecast - demand, 0)
        new_understock = np.maximum(demand - new_forecast, 0)
        new_total_cost = new_spoiled.sum() * cost + new_understock.sum() * margin

        savings = current_total_cost - new_total_cost
        savings_pct = (savings / current_total_cost * 100) if current_total_cost else 0

        results.append({
            "item": item,
            "current_avg_prep_qty": _round(forecast.mean()),
            "recommended_adjustment": adjustment,
            "recommended_avg_prep_qty": _round(new_forecast.mean()),
            "critical_ratio": _round(cr, 3),
            "current_annual_cost": _round(current_total_cost),
            "projected_annual_cost": _round(new_total_cost),
            "projected_savings_inr": _round(savings),
            "projected_savings_pct": _round(savings_pct),
        })

    return sorted(results, key=lambda r: -r["projected_savings_inr"])


_PRICING_NOTE = (
    "Based on realized transaction lines: average order quantity does not rise "
    "with discount depth in this data, so deeper discounts show up as margin "
    "given away rather than a proven volume driver. Treat 'projected savings' "
    "below as a halved-discretionary-discounting scenario, not a demand forecast."
)


def optimize_pricing():
    """Discount-leakage analysis per item.

    Rather than assume discounts causally drive volume (this transaction log
    can't show that - it has no controlled experiment, and average line
    quantity is flat across discount levels), this quantifies two things a
    restaurant can act on directly: how much margin each item gives away to
    discounting per year, and how much margin cushion (price-cost headroom)
    it has to absorb that. Bucketed profit-per-line is still returned for the
    chart - it visually shows margin eroding with discount depth at flat volume.
    """
    d = get_data()
    pos = d["pos"].copy()
    pos["discount_pct"] = pos["Discount_Applied"] / pos["Unit_Price"] * 100

    bins = [-0.01, 0, 10, 20, 100]
    labels = ["0%", "0-10%", "10-20%", "20%+"]
    pos["bucket"] = pd.cut(pos["discount_pct"], bins=bins, labels=labels)

    cushions = {}
    for item, g in pos.groupby("Item_Name"):
        price, cost = g["Unit_Price"].iloc[0], g["Unit_Cost"].iloc[0]
        cushions[item] = (price - cost) / price * 100
    median_cushion = float(np.median(list(cushions.values())))

    results = []
    for item, g in pos.groupby("Item_Name"):
        gross_revenue = (g["Unit_Price"] * g["Quantity"]).sum()
        discount_given = (g["Discount_Applied"] * g["Quantity"]).sum()
        leakage_pct = (discount_given / gross_revenue * 100) if gross_revenue else 0
        margin_cushion_pct = cushions[item]

        by_bucket = g.groupby("bucket", observed=True).agg(
            avg_profit_per_line=("Profit", "mean"),
            avg_qty_per_line=("Quantity", "mean"),
            lines=("Profit", "count"),
        )
        by_bucket = by_bucket[by_bucket["lines"] >= 5]

        priority = "Tighten discount approval first" if margin_cushion_pct < median_cushion else "Lower priority — healthy margin cushion"

        results.append({
            "item": item,
            "avg_discount_pct": _round(g["discount_pct"].mean()),
            "total_discount_given_inr": _round(discount_given),
            "discount_leakage_pct": _round(leakage_pct),
            "margin_cushion_pct": _round(margin_cushion_pct),
            "projected_savings_if_halved_inr": _round(discount_given * 0.5),
            "recommendation": priority,
            "note": _PRICING_NOTE,
            "buckets": {
                str(idx): {
                    "avg_profit_per_line": _round(row["avg_profit_per_line"]),
                    "avg_qty_per_line": _round(row["avg_qty_per_line"]),
                    "lines": int(row["lines"]),
                }
                for idx, row in by_bucket.iterrows()
            },
        })

    return sorted(results, key=lambda r: -r["total_discount_given_inr"])


def optimize_procurement():
    """Weighted least-cost supplier scoring per ingredient category.

    score = 0.6 * normalized(delivery_cost) + 0.4 * normalized(lead_time)
    Lower score wins. Weights favour cost since delivery cost varies more
    (and matters more to margin) than the 1-3 day lead-time spread here.
    """
    d = get_data()
    sup = d["supply"]

    results = []
    for category, g in sup.groupby("Ingredient_Category"):
        by_supplier = g.groupby("Supplier").agg(
            avg_cost=("Delivery_Cost_INR", "mean"),
            avg_lead_time=("Lead_Time_Days", "mean"),
            avg_moq=("Minimum_Order_Qty", "mean"),
            routes=("Route_ID", "count"),
        )

        cost_range = by_supplier["avg_cost"].max() - by_supplier["avg_cost"].min()
        lead_range = by_supplier["avg_lead_time"].max() - by_supplier["avg_lead_time"].min()
        cost_norm = (by_supplier["avg_cost"] - by_supplier["avg_cost"].min()) / cost_range if cost_range else 0
        lead_norm = (by_supplier["avg_lead_time"] - by_supplier["avg_lead_time"].min()) / lead_range if lead_range else 0
        by_supplier["score"] = 0.6 * cost_norm + 0.4 * lead_norm

        recommended = by_supplier["score"].idxmin()
        rec_row = by_supplier.loc[recommended]
        category_avg_cost = g["Delivery_Cost_INR"].mean()
        category_avg_lead = g["Lead_Time_Days"].mean()

        cost_savings_pct = ((category_avg_cost - rec_row["avg_cost"]) / category_avg_cost * 100) if category_avg_cost else 0
        leadtime_improvement_days = category_avg_lead - rec_row["avg_lead_time"]

        results.append({
            "category": category,
            "recommended_supplier": recommended,
            "recommended_avg_cost": _round(rec_row["avg_cost"]),
            "recommended_avg_lead_time": _round(rec_row["avg_lead_time"]),
            "category_avg_cost": _round(category_avg_cost),
            "category_avg_lead_time": _round(category_avg_lead),
            "cost_savings_pct": _round(cost_savings_pct),
            "leadtime_improvement_days": _round(leadtime_improvement_days),
            "suppliers": [
                {
                    "supplier": name,
                    "avg_cost": _round(row["avg_cost"]),
                    "avg_lead_time": _round(row["avg_lead_time"]),
                    "avg_moq": _round(row["avg_moq"], 1),
                    "routes": int(row["routes"]),
                    "score": _round(row["score"], 3),
                }
                for name, row in by_supplier.iterrows()
            ],
        })

    return sorted(results, key=lambda r: -r["cost_savings_pct"])
