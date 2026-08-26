"""Aggregation functions that turn the raw dataframes into chart/KPI-ready JSON."""

import numpy as np

from services.data_loader import get_data


def _round(x, n=2):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    return round(x, n) if isinstance(x, float) else x


def kpi_overview():
    d = get_data()
    pos = d["pos"]
    inv = d["inventory"]

    total_revenue = pos["Total_Amount"].sum()
    total_profit = pos["Profit"].sum()
    avg_margin_pct = (total_profit / total_revenue) * 100 if total_revenue else 0

    total_waste_units = int(inv["Spoiled_Qty"].sum())
    total_waste_cost = inv["Spoilage_Cost"].sum()

    by_year = pos.groupby(pos["Date"].dt.year)["Total_Amount"].sum()
    years = sorted(by_year.index)
    yoy_growth_pct = None
    if len(years) >= 2:
        prev, curr = by_year[years[-2]], by_year[years[-1]]
        yoy_growth_pct = ((curr - prev) / prev) * 100 if prev else None

    return {
        "total_revenue": _round(total_revenue),
        "total_profit": _round(total_profit),
        "avg_margin_pct": _round(avg_margin_pct),
        "total_transactions": int(pos["Transaction_ID"].nunique()),
        "total_waste_units": total_waste_units,
        "total_waste_cost": _round(total_waste_cost),
        "yoy_revenue_growth_pct": _round(yoy_growth_pct) if yoy_growth_pct is not None else None,
        "date_range": {
            "start": pos["Date"].min().strftime("%Y-%m-%d"),
            "end": pos["Date"].max().strftime("%Y-%m-%d"),
        },
    }


def revenue_trend(freq="ME"):
    d = get_data()
    pos = d["pos"]
    g = pos.set_index("Date").resample(freq).agg(revenue=("Total_Amount", "sum"), profit=("Profit", "sum"))
    return {
        "labels": [ts.strftime("%Y-%m") for ts in g.index],
        "revenue": [_round(v) for v in g["revenue"]],
        "profit": [_round(v) for v in g["profit"]],
    }


def revenue_by_category():
    d = get_data()
    pos = d["pos"]
    g = pos.groupby("Category")["Total_Amount"].sum().sort_values(ascending=False)
    return {"labels": list(g.index), "values": [_round(v) for v in g]}


def item_performance():
    d = get_data()
    pos = d["pos"]
    g = pos.groupby(["Item_Name", "Category"]).agg(
        revenue=("Total_Amount", "sum"),
        qty=("Quantity", "sum"),
        profit=("Profit", "sum"),
    ).reset_index()
    g["margin_pct"] = (g["profit"] / g["revenue"]) * 100
    g = g.sort_values("revenue", ascending=False)
    return g.assign(
        revenue=g["revenue"].round(2),
        profit=g["profit"].round(2),
        margin_pct=g["margin_pct"].round(2),
    ).to_dict(orient="records")


def hourly_pattern():
    """Not surfaced anywhere in the UI - the Time column is synthetic/
    near-uniform (see services.data_quality.defect_b_synthetic_timestamp),
    so time-of-day analysis is inadmissible. Kept for completeness/tests."""
    d = get_data()
    pos = d["pos"]
    g = pos.groupby("Hour").agg(transactions=("Transaction_ID", "count"), revenue=("Total_Amount", "sum"))
    g = g.reindex(range(24), fill_value=0)
    return {
        "labels": [f"{h:02d}:00" for h in g.index],
        "transactions": [int(v) for v in g["transactions"]],
        "revenue": [_round(v) for v in g["revenue"]],
    }


def waste_by_item():
    d = get_data()
    inv = d["inventory"]
    g = inv.groupby("Item_Name").agg(
        avg_waste_pct=("Waste_Pct", "mean"),
        total_spoiled_qty=("Spoiled_Qty", "sum"),
        total_spoilage_cost=("Spoilage_Cost", "sum"),
    ).reset_index().sort_values("avg_waste_pct", ascending=False)
    return g.assign(
        avg_waste_pct=g["avg_waste_pct"].round(2),
        total_spoilage_cost=g["total_spoilage_cost"].round(2),
    ).to_dict(orient="records")


def forecast_vs_actual():
    d = get_data()
    inv = d["inventory"]
    g = inv.set_index("Date").resample("ME").agg(
        forecasted=("Forecasted_Prep_Qty", "sum"),
        actual=("Actual_Demand_Qty", "sum"),
    )
    return {
        "labels": [ts.strftime("%Y-%m") for ts in g.index],
        "forecasted": [int(v) for v in g["forecasted"]],
        "actual": [int(v) for v in g["actual"]],
    }


def supplier_comparison():
    d = get_data()
    sup = d["supply"]
    g = sup.groupby(["Ingredient_Category", "Supplier"]).agg(
        avg_delivery_cost=("Delivery_Cost_INR", "mean"),
        avg_lead_time=("Lead_Time_Days", "mean"),
        avg_moq=("Minimum_Order_Qty", "mean"),
        routes=("Route_ID", "count"),
    ).reset_index()
    return g.assign(
        avg_delivery_cost=g["avg_delivery_cost"].round(2),
        avg_lead_time=g["avg_lead_time"].round(2),
        avg_moq=g["avg_moq"].round(1),
    ).to_dict(orient="records")
