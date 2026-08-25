"""ML demand forecasting: gradient-boosted quantile regression per item.

A single global model (item is a feature, not a separate model per item —
366 obs/item is thin, pooling across all 6 items gives the trees more to
learn from) is trained at a small grid of quantiles. The item-specific
newsvendor critical ratio (from optimizer.py's logic) is then satisfied by
linearly interpolating between the two nearest trained quantiles, which
turns the forecast directly into a prescriptive "recommended prep qty" per
future day - the point of building this rather than a plain point forecast.

Honesty over polish: this is trained on 2024-only inventory logs (366
days x 6 items = 2,196 rows) and evaluated on a genuine time-based holdout
against a naive "same as last week" baseline, so the backtest numbers shown
are real out-of-sample performance, not curve-fit optimism.
"""

import threading

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from services.data_loader import get_data
from services.item_economics import critical_ratio

QUANTILES = [0.1, 0.25, 0.5, 0.6, 0.7, 0.75, 0.9]
TEST_DAYS = 45
FORECAST_HORIZON_DAYS = 14
FEATURE_COLS = ["day_of_week", "month", "is_weekend", "lag_1", "lag_7", "roll_mean_7", "roll_mean_14"]

_lock = threading.Lock()
_cache = {}


def _round(x, n=2):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    return round(x, n) if isinstance(x, float) else x


def _add_features(item_df):
    df = item_df.sort_values("Date").copy()
    df["day_of_week"] = df["Date"].dt.dayofweek
    df["month"] = df["Date"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["lag_1"] = df["Actual_Demand_Qty"].shift(1)
    df["lag_7"] = df["Actual_Demand_Qty"].shift(7)
    df["roll_mean_7"] = df["Actual_Demand_Qty"].shift(1).rolling(7).mean()
    df["roll_mean_14"] = df["Actual_Demand_Qty"].shift(1).rolling(14).mean()
    return df


def _build_dataset():
    d = get_data()
    inv = d["inventory"]
    items = sorted(inv["Item_Name"].unique())

    featured = pd.concat([_add_features(inv[inv["Item_Name"] == item]) for item in items], ignore_index=True)
    featured = pd.get_dummies(featured, columns=["Item_Name"], prefix="item")
    item_dummy_cols = [c for c in featured.columns if c.startswith("item_")]
    featured = featured.dropna(subset=FEATURE_COLS).reset_index(drop=True)
    return featured, item_dummy_cols, items


def _train():
    featured, item_dummy_cols, items = _build_dataset()
    cols = FEATURE_COLS + item_dummy_cols

    cutoff = featured["Date"].sort_values().unique()[-TEST_DAYS]
    train_df = featured[featured["Date"] < cutoff]
    test_df = featured[featured["Date"] >= cutoff]

    X_train, y_train = train_df[cols], train_df["Actual_Demand_Qty"]
    X_test, y_test = test_df[cols], test_df["Actual_Demand_Qty"]

    models = {}
    for q in QUANTILES:
        if q == 0.5:
            model = GradientBoostingRegressor(loss="squared_error", n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42)
        else:
            model = GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42)
        model.fit(X_train, y_train)
        models[q] = model

    median_pred_test = models[0.5].predict(X_test)
    mae = mean_absolute_error(y_test, median_pred_test)
    rmse = mean_squared_error(y_test, median_pred_test) ** 0.5

    naive_pred_test = test_df["lag_7"].to_numpy()
    naive_mae = mean_absolute_error(y_test, naive_pred_test)
    improvement_pct = (naive_mae - mae) / naive_mae * 100 if naive_mae else 0

    per_item = []
    for item in items:
        mask = test_df[f"item_{item}"] == 1
        if mask.sum() == 0:
            continue
        item_mae = mean_absolute_error(y_test[mask], median_pred_test[mask])
        per_item.append({"item": item, "test_mae": _round(item_mae), "test_days": int(mask.sum())})

    return {
        "models": models,
        "cols": cols,
        "item_dummy_cols": item_dummy_cols,
        "items": items,
        "featured": featured,
        "test_df": test_df,
        "median_pred_test": median_pred_test,
        "metrics": {
            "mae": _round(mae),
            "rmse": _round(rmse),
            "naive_baseline_mae": _round(naive_mae),
            "improvement_vs_naive_pct": _round(improvement_pct),
            "test_days": TEST_DAYS,
            "per_item": per_item,
        },
    }


def _get_trained():
    if not _cache:
        with _lock:
            if not _cache:
                _cache.update(_train())
    return _cache


def _interpolate_quantile(preds_by_q, target_q):
    qs = sorted(preds_by_q.keys())
    if target_q <= qs[0]:
        return preds_by_q[qs[0]]
    if target_q >= qs[-1]:
        return preds_by_q[qs[-1]]
    for lo, hi in zip(qs, qs[1:]):
        if lo <= target_q <= hi:
            w = (target_q - lo) / (hi - lo)
            return preds_by_q[lo] * (1 - w) + preds_by_q[hi] * w
    return preds_by_q[0.5]


def get_forecast():
    trained = _get_trained()
    d = get_data()
    pos, inv = d["pos"], d["inventory"]

    test_df = trained["test_df"]
    backtest_chart = {
        "labels": [dt.strftime("%Y-%m-%d") for dt in test_df["Date"]][-30:],
        "actual": [int(v) for v in test_df["Actual_Demand_Qty"]][-30:],
        "predicted": [_round(v, 1) for v in trained["median_pred_test"]][-30:],
    }

    future_dates = pd.date_range(inv["Date"].max() + pd.Timedelta(days=1), periods=FORECAST_HORIZON_DAYS)
    forecasts = {}

    for item in trained["items"]:
        cost = inv.loc[inv["Item_Name"] == item, "Unit_Cost"].iloc[0]
        cr = critical_ratio(pos, item, cost)

        history = inv[inv["Item_Name"] == item].sort_values("Date")[["Date", "Actual_Demand_Qty"]].copy()
        history = history.rename(columns={"Actual_Demand_Qty": "value"})

        rows = []
        for date in future_dates:
            recent = history["value"].tolist()
            row = {
                "day_of_week": date.dayofweek,
                "month": date.month,
                "is_weekend": int(date.dayofweek >= 5),
                "lag_1": recent[-1],
                "lag_7": recent[-7] if len(recent) >= 7 else recent[-1],
                "roll_mean_7": float(np.mean(recent[-7:])),
                "roll_mean_14": float(np.mean(recent[-14:])) if len(recent) >= 14 else float(np.mean(recent)),
            }
            for dummy_col in trained["item_dummy_cols"]:
                row[dummy_col] = 1 if dummy_col == f"item_{item}" else 0

            X_row = pd.DataFrame([row])[trained["cols"]]
            preds_by_q = {q: float(trained["models"][q].predict(X_row)[0]) for q in QUANTILES}
            median_val = max(preds_by_q[0.5], 0)

            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "median": _round(median_val, 1),
                "lower": _round(max(preds_by_q[0.1], 0), 1),
                "upper": _round(max(preds_by_q[0.9], 0), 1),
                "recommended_prep": round(max(_interpolate_quantile(preds_by_q, cr), 0)),
            })
            history = pd.concat([history, pd.DataFrame([{"Date": date, "value": median_val}])], ignore_index=True)

        forecasts[item] = {"critical_ratio": _round(cr, 3), "days": rows}

    return {
        "backtest_metrics": trained["metrics"],
        "backtest_chart": backtest_chart,
        "forecast_horizon_days": FORECAST_HORIZON_DAYS,
        "forecasts": forecasts,
    }
