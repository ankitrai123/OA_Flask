"""Demand Sensing (Slide 03): ARIMAX(0,1,1) + summer-season exogenous
regressor on log-transformed weekly demand - matching the reference
capstone's exact specification ("ARIMAX(0,1,1) on log demand + Summer
flag"). Only in log space does the fitted coefficient exponentiate into a
clean multiplicative uplift (e.g. exp(0.65) approx 1.9x), and only at
weekly aggregation does the RMSE/AIC scale match a weekly prep-planning
decision - a daily-raw fit (this module's previous spec) answers a
different, harder-to-interpret question.

This deliberately does NOT forecast the inventory log's Actual_Demand_Qty
column, which an even earlier version of this module did. That column and
what POS transactions actually show sold per item per day are, empirically,
uncorrelated (r=-0.02 - see services.data_quality.defect_c_...) and cannot
be treated as the same demand series. POS is the source of truth here;
everywhere in this module sources demand through get_item_daily_demand /
get_item_weekly_log_demand so nothing forecasts the wrong signal again.

Two parallel model tracks live in this module, deliberately not merged:
  - WEEKLY (log-space): fit_item_weekly_model / rolling_origin_validate_weekly
    / naive_split_validate_weekly / future_forecast_weekly. This is Q1's
    headline, validated answer - what Slide 03 displays.
  - DAILY (raw, unchanged from before this recalibration): fit_item_model /
    rolling_origin_validate / get_one_step_ahead_forecast. This keeps
    powering services.newsvendor's day-to-day dynamic prep quantity, which
    is a daily decision a weekly aggregate can't directly answer. Kept
    running exactly as before so newsvendor.py needs no changes.
"""

import threading

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from services.data_loader import get_data

ORDER = (0, 1, 1)
SUMMER_MONTHS = (4, 5, 6)
MIN_TRAIN_DAYS = 365
VALIDATION_HORIZON_DAYS = 14
VALIDATION_N_FOLDS = 5
FUTURE_HORIZON_DAYS = 14
CI_ALPHA = 0.20  # 80% interval

WEEK_RULE = "W-SUN"
MIN_TRAIN_WEEKS = 52
VALIDATION_HORIZON_WEEKS = 8
FUTURE_HORIZON_WEEKS = 12
NAIVE_SPLIT_TEST_FRACTION = 0.2

_lock = threading.Lock()
_cache = {}
_weekly_lock = threading.Lock()
_weekly_cache = {}


def _round(x, n=2):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    return round(x, n) if isinstance(x, float) else x


def get_item_daily_demand(item):
    """POS Quantity summed per calendar day for one item, 0-filled across
    every day in the POS date range. The single source of demand truth
    every other module (simulator, newsvendor) should read through."""
    d = get_data()
    pos = d["pos"]
    item_pos = pos[pos["Item_Name"] == item]
    full_range = pd.date_range(pos["Date"].min(), pos["Date"].max(), freq="D")
    daily = item_pos.groupby("Date")["Quantity"].sum().reindex(full_range, fill_value=0)
    daily.index.freq = "D"
    return daily


def get_item_weekly_log_demand(item):
    """POS Quantity summed per calendar week (W-SUN), log1p-transformed -
    the series the weekly ARIMAX model in this module fits on. log1p (not
    log) is safe even in weeks with zero units."""
    daily = get_item_daily_demand(item)
    weekly = daily.resample(WEEK_RULE).sum()
    weekly.index.freq = pd.tseries.frequencies.to_offset(WEEK_RULE)
    return np.log1p(weekly)


def _summer_dummy(index):
    return pd.Series(index.month.isin(SUMMER_MONTHS).astype(int), index=index, name="summer")


def fit_item_model(item):
    """Fits ARIMAX(0,1,1)+summer regressor on the item's full daily
    series. Returns None - not a fabricated model - if there's too little
    history or the optimizer fails; callers must render 'not supported'
    for None, never proceed with a guessed number."""
    series = get_item_daily_demand(item)
    if len(series) < MIN_TRAIN_DAYS:
        return None

    summer = _summer_dummy(series.index)
    try:
        res = SARIMAX(series, exog=summer, order=ORDER, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    except Exception:
        return None

    converged = getattr(res, "mle_retvals", {}).get("converged", True) if hasattr(res, "mle_retvals") else True
    if not converged:
        return None
    zero_pct = float((series == 0).mean() * 100)

    return {
        "item": item,
        "spec": f"SARIMAX{ORDER} + summer regressor",
        "aic": _round(res.aic),
        "summer_coef": _round(res.params["summer"], 3),
        "summer_pvalue": _round(res.pvalues["summer"], 6),
        "summer_significant": bool(res.pvalues["summer"] < 0.05),
        "training_window": {
            "start": series.index.min().strftime("%Y-%m-%d"),
            "end": series.index.max().strftime("%Y-%m-%d"),
            "n_days": int(len(series)),
        },
        "converged": bool(converged),
        "zero_quantity_day_pct": _round(zero_pct),
        "sparse_data_flag": bool(zero_pct > 25),
        "_fitted_model": res,
        "_series": series,
    }


def rolling_origin_validate(item):
    """5-fold expanding-window backtest: each fold refits ARIMAX fresh at
    its own cutoff (no leakage) and forecasts VALIDATION_HORIZON_DAYS
    ahead. Baseline = flat mean of the trailing 7 days at each cutoff.
    Returns None if the series is too short for one full fold."""
    series = get_item_daily_demand(item)
    n = len(series)
    if n < MIN_TRAIN_DAYS + VALIDATION_HORIZON_DAYS:
        return None

    summer = _summer_dummy(series.index)
    fold_starts = np.linspace(MIN_TRAIN_DAYS, n - VALIDATION_HORIZON_DAYS, VALIDATION_N_FOLDS, dtype=int)

    folds = []
    for i, start in enumerate(fold_starts):
        train_y, test_y = series.iloc[:start], series.iloc[start:start + VALIDATION_HORIZON_DAYS]
        train_x, test_x = summer.iloc[:start], summer.iloc[start:start + VALIDATION_HORIZON_DAYS]

        try:
            fold_res = SARIMAX(train_y, exog=train_x, order=ORDER, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
            fc = fold_res.forecast(steps=VALIDATION_HORIZON_DAYS, exog=test_x)
            arimax_rmse = float(np.sqrt(np.mean((fc.values - test_y.values) ** 2)))
        except Exception:
            arimax_rmse = None

        naive = np.full(VALIDATION_HORIZON_DAYS, train_y.iloc[-7:].mean())
        naive_rmse = float(np.sqrt(np.mean((naive - test_y.values) ** 2)))

        folds.append({
            "fold": i + 1,
            "cutoff_date": series.index[start].strftime("%Y-%m-%d"),
            "arimax_rmse": _round(arimax_rmse) if arimax_rmse is not None else None,
            "naive_rmse": _round(naive_rmse),
        })

    valid_arimax = [f["arimax_rmse"] for f in folds if f["arimax_rmse"] is not None]
    if not valid_arimax:
        return None

    arimax_mean = float(np.mean(valid_arimax))
    naive_mean = float(np.mean([f["naive_rmse"] for f in folds]))
    improvement_pct = (naive_mean - arimax_mean) / naive_mean * 100 if naive_mean else 0

    return {
        "item": item,
        "n_folds": VALIDATION_N_FOLDS,
        "horizon_days": VALIDATION_HORIZON_DAYS,
        "method_description": (
            f"{VALIDATION_N_FOLDS}-fold expanding-window rolling-origin validation, "
            f"{VALIDATION_HORIZON_DAYS}-day horizon per fold, refit fresh at each cutoff (no "
            "leakage). Baseline: flat mean of the trailing 7 days at each cutoff."
        ),
        "folds": folds,
        "arimax_mean_rmse": _round(arimax_mean),
        "naive_mean_rmse": _round(naive_mean),
        "improvement_pct": _round(improvement_pct),
        "interpretation": (
            "The model is useful because it improves forecast error under rolling-origin "
            "validation, not merely because it fits the historical data."
        ),
    }


def fit_item_weekly_model(item):
    """Fits ARIMAX(0,1,1)+summer on the item's log1p weekly series - Q1's
    headline model. Returns None (not a fabricated model) if there's too
    little weekly history or the optimizer fails."""
    log_weekly = get_item_weekly_log_demand(item)
    if len(log_weekly) < MIN_TRAIN_WEEKS:
        return None

    summer = _summer_dummy(log_weekly.index)
    try:
        res = SARIMAX(log_weekly, exog=summer, order=ORDER, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    except Exception:
        return None

    converged = getattr(res, "mle_retvals", {}).get("converged", True) if hasattr(res, "mle_retvals") else True
    if not converged:
        return None

    coef = float(res.params["summer"])
    return {
        "item": item,
        "spec": f"SARIMAX{ORDER} on log(1+weekly demand) + summer regressor",
        "aic": _round(res.aic),
        "summer_log_coef": _round(coef, 3),
        "summer_multiplier": _round(float(np.exp(coef)), 3),
        "summer_pvalue": _round(res.pvalues["summer"], 6),
        "summer_significant": bool(res.pvalues["summer"] < 0.05),
        "training_window": {
            "start": log_weekly.index.min().strftime("%Y-%m-%d"),
            "end": log_weekly.index.max().strftime("%Y-%m-%d"),
            "n_weeks": int(len(log_weekly)),
        },
        "converged": bool(converged),
        "_fitted_model": res,
        "_log_series": log_weekly,
    }


def rolling_origin_validate_weekly(item):
    """5-fold expanding-window backtest at weekly (log-space fit, natural-
    units RMSE) granularity: each fold refits fresh at its own cutoff (no
    leakage) and forecasts VALIDATION_HORIZON_WEEKS ahead. Baseline: flat
    mean of the trailing 4 weeks at each cutoff, also in natural units."""
    log_weekly = get_item_weekly_log_demand(item)
    n = len(log_weekly)
    if n < MIN_TRAIN_WEEKS + VALIDATION_HORIZON_WEEKS:
        return None

    summer = _summer_dummy(log_weekly.index)
    fold_starts = np.linspace(MIN_TRAIN_WEEKS, n - VALIDATION_HORIZON_WEEKS, VALIDATION_N_FOLDS, dtype=int)

    folds = []
    for i, start in enumerate(fold_starts):
        train_y, test_y = log_weekly.iloc[:start], log_weekly.iloc[start:start + VALIDATION_HORIZON_WEEKS]
        train_x, test_x = summer.iloc[:start], summer.iloc[start:start + VALIDATION_HORIZON_WEEKS]
        test_natural = np.expm1(test_y.values)

        try:
            fold_res = SARIMAX(train_y, exog=train_x, order=ORDER, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
            fc_log = fold_res.forecast(steps=VALIDATION_HORIZON_WEEKS, exog=test_x)
            fc_natural = np.clip(np.expm1(fc_log.values), 0, None)
            arimax_rmse = float(np.sqrt(np.mean((fc_natural - test_natural) ** 2)))
        except Exception:
            arimax_rmse = None

        naive_natural = np.full(VALIDATION_HORIZON_WEEKS, np.expm1(train_y.iloc[-4:]).mean())
        naive_rmse = float(np.sqrt(np.mean((naive_natural - test_natural) ** 2)))

        folds.append({
            "fold": i + 1,
            "cutoff_date": log_weekly.index[start].strftime("%Y-%m-%d"),
            "arimax_rmse": _round(arimax_rmse) if arimax_rmse is not None else None,
            "naive_rmse": _round(naive_rmse),
        })

    valid_arimax = [f["arimax_rmse"] for f in folds if f["arimax_rmse"] is not None]
    if not valid_arimax:
        return None

    arimax_mean = float(np.mean(valid_arimax))
    naive_mean = float(np.mean([f["naive_rmse"] for f in folds]))
    improvement_pct = (naive_mean - arimax_mean) / naive_mean * 100 if naive_mean else 0

    return {
        "item": item,
        "n_folds": VALIDATION_N_FOLDS,
        "horizon_weeks": VALIDATION_HORIZON_WEEKS,
        "method_description": (
            f"{VALIDATION_N_FOLDS}-fold expanding-window rolling-origin validation, "
            f"{VALIDATION_HORIZON_WEEKS}-week horizon per fold, refit fresh at each cutoff (no "
            "leakage), RMSE scored in natural (not log) units. Baseline: flat mean of the "
            "trailing 4 weeks at each cutoff."
        ),
        "folds": folds,
        "arimax_mean_rmse": _round(arimax_mean),
        "naive_mean_rmse": _round(naive_mean),
        "improvement_pct": _round(improvement_pct),
        "interpretation": (
            "The model is useful because it improves forecast error under rolling-origin "
            "validation, not merely because it fits the historical data."
        ),
    }


def naive_split_validate_weekly(item):
    """A single 80/20 train/test split - deliberately the naive comparator
    to rolling_origin_validate_weekly, not a replacement for it. A single
    holdout window can land anywhere in the calendar; if it happens to miss
    the summer months entirely, it will understate the model's real value.
    Showing both side by side is the point, not just the rolling-origin
    number alone."""
    log_weekly = get_item_weekly_log_demand(item)
    n = len(log_weekly)
    split = int(n * (1 - NAIVE_SPLIT_TEST_FRACTION))
    if split < MIN_TRAIN_WEEKS or (n - split) < 4:
        return None

    summer = _summer_dummy(log_weekly.index)
    train_y, test_y = log_weekly.iloc[:split], log_weekly.iloc[split:]
    train_x, test_x = summer.iloc[:split], summer.iloc[split:]
    test_natural = np.expm1(test_y.values)

    try:
        res = SARIMAX(train_y, exog=train_x, order=ORDER, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        fc_natural = np.clip(np.expm1(res.forecast(steps=len(test_y), exog=test_x).values), 0, None)
        arimax_rmse = float(np.sqrt(np.mean((fc_natural - test_natural) ** 2)))
    except Exception:
        return None

    naive_natural = np.full(len(test_y), np.expm1(train_y.iloc[-4:]).mean())
    naive_rmse = float(np.sqrt(np.mean((naive_natural - test_natural) ** 2)))
    improvement_pct = (naive_rmse - arimax_rmse) / naive_rmse * 100 if naive_rmse else 0
    test_has_summer = bool(test_x.sum() > 0)

    return {
        "item": item,
        "test_weeks": int(len(test_y)),
        "test_window": {
            "start": test_y.index.min().strftime("%Y-%m-%d"),
            "end": test_y.index.max().strftime("%Y-%m-%d"),
        },
        "test_window_contains_summer": test_has_summer,
        "arimax_rmse": _round(arimax_rmse),
        "naive_rmse": _round(naive_rmse),
        "improvement_pct": _round(improvement_pct),
        "interpretation": (
            "A single train/test split can understate the model's real value if the held-out "
            "window happens to contain little or no summer signal - which is exactly why "
            "rolling-origin validation (5 folds, sampled across the full 2-year history) is "
            "used as the headline number instead of this single split."
        ),
    }


def _ensure_cache():
    if not _cache:
        with _lock:
            if not _cache:
                d = get_data()
                items = sorted(d["pos"]["Item_Name"].unique())
                per_item, unsupported = {}, []
                for item in items:
                    fit = fit_item_model(item)
                    if fit is None:
                        unsupported.append({"item": item, "reason": "insufficient history or the model failed to converge"})
                        per_item[item] = {"fit": None, "validation": None}
                        continue
                    per_item[item] = {"fit": fit, "validation": rolling_origin_validate(item)}
                _cache["items"] = per_item
                _cache["unsupported_items"] = unsupported


def _get_all_models():
    _ensure_cache()
    return _cache["items"]


def _get_unsupported_items():
    _ensure_cache()
    return _cache["unsupported_items"]


def _public_fit(fit):
    return None if fit is None else {k: v for k, v in fit.items() if not k.startswith("_")}


def future_forecast(item, horizon_days=FUTURE_HORIZON_DAYS):
    """History (last 90 days) + in-sample fitted values over that same
    window + future point forecast/CI via get_forecast().conf_int()."""
    bundle = _get_all_models().get(item)
    if bundle is None or bundle["fit"] is None:
        return None

    res, series = bundle["fit"]["_fitted_model"], bundle["fit"]["_series"]
    future_dates = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    future_summer = _summer_dummy(future_dates)

    fc = res.get_forecast(steps=horizon_days, exog=future_summer)
    ci = fc.conf_int(alpha=CI_ALPHA)
    median = fc.predicted_mean

    history_window = series.iloc[-90:]
    fitted_window = res.fittedvalues.iloc[-90:]

    return {
        "item": item,
        "history": {
            "labels": [d.strftime("%Y-%m-%d") for d in history_window.index],
            "actual": [_round(v, 1) for v in history_window],
        },
        "fitted": {
            "labels": [d.strftime("%Y-%m-%d") for d in fitted_window.index],
            "value": [_round(max(v, 0), 1) for v in fitted_window],
        },
        "future": {
            "labels": [d.strftime("%Y-%m-%d") for d in future_dates],
            "median": [_round(max(v, 0), 1) for v in median],
            "lower": [_round(max(v, 0), 1) for v in ci.iloc[:, 0]],
            "upper": [_round(max(v, 0), 1) for v in ci.iloc[:, 1]],
            "ci_level_pct": round((1 - CI_ALPHA) * 100),
        },
    }


def get_one_step_ahead_forecast(item):
    """Tomorrow's ARIMAX point forecast + standard error - the exact
    (mean, std) pair services.newsvendor's dynamic-newsvendor arm uses."""
    bundle = _get_all_models().get(item)
    if bundle is None or bundle["fit"] is None:
        return None

    res, series = bundle["fit"]["_fitted_model"], bundle["fit"]["_series"]
    next_date = series.index.max() + pd.Timedelta(days=1)
    next_summer = _summer_dummy(pd.DatetimeIndex([next_date], freq="D"))

    fc = res.get_forecast(steps=1, exog=next_summer)
    return {
        "item": item,
        "date": next_date.strftime("%Y-%m-%d"),
        "mean": _round(max(float(fc.predicted_mean.iloc[0]), 0)),
        "std": _round(float(fc.se_mean.iloc[0])),
    }


def _ensure_weekly_cache():
    if not _weekly_cache:
        with _weekly_lock:
            if not _weekly_cache:
                d = get_data()
                items = sorted(d["pos"]["Item_Name"].unique())
                per_item, unsupported = {}, []
                for item in items:
                    fit = fit_item_weekly_model(item)
                    if fit is None:
                        unsupported.append({"item": item, "reason": "insufficient weekly history or the model failed to converge"})
                        per_item[item] = {"fit": None, "validation": None, "naive_split": None}
                        continue
                    per_item[item] = {
                        "fit": fit,
                        "validation": rolling_origin_validate_weekly(item),
                        "naive_split": naive_split_validate_weekly(item),
                    }
                _weekly_cache["items"] = per_item
                _weekly_cache["unsupported_items"] = unsupported


def _get_all_weekly_models():
    _ensure_weekly_cache()
    return _weekly_cache["items"]


def _get_unsupported_weekly_items():
    _ensure_weekly_cache()
    return _weekly_cache["unsupported_items"]


def future_forecast_weekly(item, horizon_weeks=FUTURE_HORIZON_WEEKS):
    """History (last 26 weeks) + in-sample fitted values over that same
    window + future point forecast/CI, all inverse-transformed (expm1) back
    to natural weekly-unit scale via get_forecast().conf_int()."""
    bundle = _get_all_weekly_models().get(item)
    if bundle is None or bundle["fit"] is None:
        return None

    res, log_series = bundle["fit"]["_fitted_model"], bundle["fit"]["_log_series"]
    future_dates = pd.date_range(log_series.index.max() + pd.Timedelta(weeks=1), periods=horizon_weeks, freq=WEEK_RULE)
    future_summer = _summer_dummy(future_dates)

    fc = res.get_forecast(steps=horizon_weeks, exog=future_summer)
    ci_log = fc.conf_int(alpha=CI_ALPHA)
    median_log = fc.predicted_mean

    history_window = log_series.iloc[-26:]
    fitted_window = res.fittedvalues.iloc[-26:]

    return {
        "item": item,
        "history": {
            "labels": [d.strftime("%Y-%m-%d") for d in history_window.index],
            "actual": [_round(max(v, 0), 1) for v in np.expm1(history_window)],
        },
        "fitted": {
            "labels": [d.strftime("%Y-%m-%d") for d in fitted_window.index],
            "value": [_round(max(v, 0), 1) for v in np.expm1(fitted_window)],
        },
        "future": {
            "labels": [d.strftime("%Y-%m-%d") for d in future_dates],
            "median": [_round(max(v, 0), 1) for v in np.expm1(median_log)],
            "lower": [_round(max(v, 0), 1) for v in np.expm1(ci_log.iloc[:, 0])],
            "upper": [_round(max(v, 0), 1) for v in np.expm1(ci_log.iloc[:, 1])],
            "ci_level_pct": round((1 - CI_ALPHA) * 100),
        },
    }


def get_demand_forecast_bundle():
    """Backing function for GET /api/demand/forecast - Q1's headline
    weekly, log-space ARIMAX+summer model (see module docstring)."""
    items_out = {}
    for item, bundle in _get_all_weekly_models().items():
        if bundle["fit"] is None:
            reason = next((u["reason"] for u in _get_unsupported_weekly_items() if u["item"] == item), "insufficient data")
            items_out[item] = {"status": "not_supported", "reason": reason}
            continue
        items_out[item] = {
            "status": "supported",
            "model_info": _public_fit(bundle["fit"]),
            "forecast": future_forecast_weekly(item),
        }

    return {
        "order": list(ORDER),
        "summer_months": list(SUMMER_MONTHS),
        "forecast_horizon_weeks": FUTURE_HORIZON_WEEKS,
        "items": items_out,
        "unsupported_items": _get_unsupported_weekly_items(),
    }


def get_demand_validation_bundle():
    """Backing function for GET /api/demand/validation: the rolling-origin
    result (headline) alongside the naive single 80/20 split (the deck's
    'the 80/20 split shows only ~6%' contrast point), plus a fold-level
    'Baseline vs ARIMAX Forecast Error' series averaged across items."""
    all_models = _get_all_weekly_models()
    items_out, improvements = {}, []

    for item, bundle in all_models.items():
        if bundle["validation"] is None:
            items_out[item] = {"status": "not_supported"}
            continue
        items_out[item] = {
            "status": "supported",
            "rolling_origin": bundle["validation"],
            "naive_80_20_split": bundle["naive_split"],
        }
        improvements.append(bundle["validation"]["improvement_pct"])

    fold_avg_arimax, fold_avg_naive = [], []
    for i in range(VALIDATION_N_FOLDS):
        a_vals = [
            b["validation"]["folds"][i]["arimax_rmse"] for b in all_models.values()
            if b["validation"] and b["validation"]["folds"][i]["arimax_rmse"] is not None
        ]
        n_vals = [b["validation"]["folds"][i]["naive_rmse"] for b in all_models.values() if b["validation"]]
        fold_avg_arimax.append(_round(np.mean(a_vals)) if a_vals else None)
        fold_avg_naive.append(_round(np.mean(n_vals)) if n_vals else None)

    return {
        "items": items_out,
        "cross_item_avg_improvement_pct": _round(np.mean(improvements)) if improvements else None,
        "fold_level_chart": {
            "labels": [f"Fold {i + 1}" for i in range(VALIDATION_N_FOLDS)],
            "arimax_rmse": fold_avg_arimax,
            "naive_rmse": fold_avg_naive,
        },
        "methodology_note": (
            "Rolling-origin validation (5 expanding-window folds sampled across the full "
            "2-year history) is the headline result. A naive single 80/20 train/test split "
            "is shown alongside it because a single holdout window can land anywhere in the "
            "calendar - if it happens to miss the summer months, it understates the model's "
            "real value. See each item's naive_80_20_split.test_window_contains_summer."
        ),
    }
