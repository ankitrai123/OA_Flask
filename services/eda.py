"""Exploratory Data Analysis backing Slide 03. POS is the demand-level
source of truth throughout (see services.data_quality.defect_c_...); the
inventory log is used only for its own internal prep/spoilage relationship,
never compared against POS here. Kept separate from metrics.py, which stays
a plain groupby-to-JSON layer with no statistical framing of its own.
"""

import numpy as np
import pandas as pd
from scipy import stats

from services.data_loader import get_data
from services import basket_analysis, metrics

SUMMER_MONTHS = (4, 5, 6)


def _round(x, n=2):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    return round(x, n) if isinstance(x, float) else x


def revenue_mix(top_n=10):
    items = metrics.item_performance()
    total_revenue = sum(i["revenue"] for i in items) or 1

    cumulative = 0.0
    enriched = []
    for i in items:
        share = i["revenue"] / total_revenue * 100
        cumulative += share
        enriched.append({
            "item": i["Item_Name"],
            "category": i["Category"],
            "revenue_inr": i["revenue"],
            "qty": i["qty"],
            "profit_inr": i["profit"],
            "margin_pct": i["margin_pct"],
            "revenue_share_pct": _round(share),
            "cumulative_share_pct": _round(cumulative),
        })

    return {"items": enriched[:top_n], "total_items": len(enriched), "by_category": metrics.revenue_by_category()}


def _daily_qty_series():
    d = get_data()
    pos = d["pos"]
    full_range = pd.date_range(pos["Date"].min(), pos["Date"].max())
    daily = pos.groupby("Date")["Quantity"].sum().reindex(full_range, fill_value=0)
    return pos, full_range, daily


def _per_item_daily_matrix(pos, full_range):
    return pos.groupby(["Date", "Item_Name"])["Quantity"].sum().unstack(fill_value=0).reindex(full_range, fill_value=0)


def demand_distribution():
    pos, full_range, daily = _daily_qty_series()
    counts, edges = np.histogram(daily, bins=12)

    matrix = _per_item_daily_matrix(pos, full_range)
    per_item = []
    for item in matrix.columns:
        s = matrix[item]
        per_item.append({
            "item": item,
            "mean_daily_qty": _round(s.mean()),
            "std_daily_qty": _round(s.std()),
            "cv": _round(s.std() / s.mean(), 3) if s.mean() else None,
            "zero_qty_day_pct": _round((s == 0).mean() * 100),
        })

    return {
        "daily_overall": {
            "mean": _round(daily.mean()),
            "median": _round(daily.median()),
            "std": _round(daily.std()),
            "cv": _round(daily.std() / daily.mean(), 3),
            "histogram": {"bin_edges": [_round(e, 1) for e in edges], "counts": [int(c) for c in counts]},
        },
        "per_item": per_item,
    }


def seasonality():
    pos, full_range, daily = _daily_qty_series()
    matrix = _per_item_daily_matrix(pos, full_range)

    monthly = daily.groupby(daily.index.month).mean()
    monthly_index = monthly / daily.mean() * 100

    is_summer = daily.index.month.isin(SUMMER_MONTHS)
    summer_vals, rest_vals = daily[is_summer], daily[~is_summer]
    t_stat, p_value = stats.ttest_ind(summer_vals, rest_vals, equal_var=False)

    per_item_results = []
    for item in matrix.columns:
        s = matrix[item]
        s_summer, s_rest = s[is_summer], s[~is_summer]
        t, p = stats.ttest_ind(s_summer, s_rest, equal_var=False)
        uplift = (s_summer.mean() / s_rest.mean() - 1) * 100 if s_rest.mean() else None
        per_item_results.append({
            "item": item,
            "summer_mean": _round(s_summer.mean()),
            "rest_mean": _round(s_rest.mean()),
            "uplift_pct": _round(uplift) if uplift is not None else None,
            "t_stat": _round(t, 3),
            "p_value": _round(p, 6),
            "significant": bool(p < 0.05),
        })

    driving_items = [r["item"] for r in per_item_results if r["significant"] and (r["uplift_pct"] or 0) > 20]

    # Weekly (day-of-week) seasonality: one-way ANOVA of total daily quantity
    # grouped by weekday - tests whether a weekly (s=7) seasonal cycle would
    # be worth modeling alongside the annual summer effect.
    dow_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_names = daily.index.day_name()
    dow_groups = [daily[dow_names == d].to_numpy() for d in dow_labels]
    f_stat, dow_p = stats.f_oneway(*dow_groups)
    dow_means = {d: float(daily[dow_names == d].mean()) for d in dow_labels}
    dow_spread_pct = (max(dow_means.values()) - min(dow_means.values())) / daily.mean() * 100

    return {
        "summer_months": list(SUMMER_MONTHS),
        "monthly_index": {"labels": [f"{m:02d}" for m in monthly_index.index], "index": [_round(v) for v in monthly_index]},
        "summer_vs_rest": {
            "summer_mean": _round(summer_vals.mean()),
            "rest_mean": _round(rest_vals.mean()),
            "uplift_pct": _round((summer_vals.mean() / rest_vals.mean() - 1) * 100),
            "t_stat": _round(t_stat, 3),
            "p_value": _round(p_value, 6),
            "significant": bool(p_value < 0.05),
        },
        "per_item_summer_uplift": sorted(per_item_results, key=lambda r: -(r["uplift_pct"] or 0)),
        "weekday_seasonality": {
            "method": "One-way ANOVA of total daily POS quantity, grouped by day of week",
            "labels": dow_labels,
            "means": {d: _round(v) for d, v in dow_means.items()},
            "f_stat": _round(float(f_stat), 3),
            "p_value": _round(float(dow_p), 4),
            "spread_pct_of_mean": _round(dow_spread_pct),
            "significant_at_05": bool(dow_p < 0.05),
            "actionable": False,
            "interpretation": (
                f"A weekly cycle is borderline-significant (p={_round(float(dow_p), 3)}) with only a "
                f"~{_round(dow_spread_pct)}% spread between the busiest and quietest day - too weak and "
                "too marginal to justify a weekly seasonal term (e.g. SARIMA with s=7) on top of the much "
                "stronger, clearly significant annual summer effect. Demand Sensing carries only the "
                "annual Summer regressor."
            ),
        },
        "interpretation": (
            f"The Apr-Jun uplift is real and highly significant in aggregate, but concentrated almost "
            f"entirely in {', '.join(driving_items) if driving_items else 'no single item'} - food "
            "items show little to no seasonal effect. Treat 'summer' as a beverage-specific pattern, "
            "not a uniform menu-wide seasonal multiplier."
        ),
    }


def spoilage_and_prep_bias():
    d = get_data()
    inv = d["inventory"]

    rows = []
    for item, g in inv.groupby("Item_Name"):
        avg_forecast, avg_actual, avg_spoiled = g["Forecasted_Prep_Qty"].mean(), g["Actual_Demand_Qty"].mean(), g["Spoiled_Qty"].mean()
        prep_bias_pct = (avg_forecast - avg_actual) / avg_actual * 100 if avg_actual else 0
        rows.append({
            "item": item,
            "avg_forecasted_prep_qty": _round(avg_forecast),
            "avg_actual_demand_qty": _round(avg_actual),
            "avg_spoiled_qty": _round(avg_spoiled),
            "prep_bias_pct": _round(prep_bias_pct),
            "avg_waste_pct": _round(g["Waste_Pct"].mean()),
        })

    return {
        "per_item": sorted(rows, key=lambda r: -r["prep_bias_pct"]),
        "scope_note": (
            "Computed entirely within the inventory log's own internal relationship "
            "(Forecasted_Prep_Qty vs Actual_Demand_Qty vs Spoiled_Qty) - valid for prep/spoilage "
            "behavior, not as a demand-level statistic (see Defect C)."
        ),
    }


def hourly_pattern_status():
    return {
        "status": "inadmissible",
        "reason": (
            "Transaction timestamps are near-uniformly distributed across all 24 hours (see Defect "
            "B) - not a real trading pattern. Time-of-day analysis is not shown."
        ),
        "see_also": "/api/data-quality",
    }


def menu_affinity_highlights(top_n=3):
    result = basket_analysis.get_association_rules()
    return {
        "top_rules": result.get("rules", [])[:top_n],
        "basket_count": result.get("basket_count", 0),
        "note": result.get("note", ""),
    }


def eda_bundle():
    return {
        "revenue_mix": revenue_mix(),
        "demand_distribution": demand_distribution(),
        "seasonality": seasonality(),
        "spoilage_and_prep_bias": spoilage_and_prep_bias(),
        "hourly_pattern_status": hourly_pattern_status(),
        "menu_affinity": menu_affinity_highlights(),
    }
