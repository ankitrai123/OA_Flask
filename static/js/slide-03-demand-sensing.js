(function () {
  let forecastData = null;

  function renderSeasonalityInsight(seasonality) {
    const sv = seasonality.summer_vs_rest;
    const wk = seasonality.weekday_seasonality;
    document.getElementById("seasonality-insight").innerHTML = `
      <span class="lead-label">Insight</span>
      Demand is seasonal, not weekly: Apr&ndash;Jun demand runs ${UI.fmtPct(sv.uplift_pct)} above the rest
      of the year in aggregate (${UI.fmtPValue(sv.p_value)}), concentrated almost entirely in the two
      beverage items. A weekly (day-of-week) cycle is only borderline-significant
      (${UI.fmtPValue(wk.p_value)}, ~${UI.fmtPct(wk.spread_pct_of_mean)} spread) and not worth modeling -
      so the ARIMAX model below carries an annual Summer regressor and no weekly (s=7) term.
    `;
  }

  function renderKPIs(validationBundle) {
    const items = Object.values(forecastData.items).filter((i) => i.status === "supported");
    const sigCount = items.filter((i) => i.model_info.summer_significant).length;

    UI.renderKPIs("forecast-kpis", [
      { label: "Avg Improvement vs Naive", value: UI.fmtPct(validationBundle.cross_item_avg_improvement_pct), context: "rolling-origin RMSE, averaged across items" },
      { label: "Items Modeled", value: `${items.length} / 6`, context: "ARIMAX(0,1,1) on log demand + summer regressor" },
      { label: "Summer-Significant Items", value: `${sigCount} / ${items.length}`, context: "p < 0.05 on the summer coefficient" },
      { label: "Forecast Horizon", value: `${forecastData.forecast_horizon_weeks} weeks`, context: "beyond the last observed week" },
    ]);
  }

  function renderForecastChart(item) {
    const entry = forecastData.items[item];
    document.getElementById("forecast-item-label").textContent = item;

    if (entry.status !== "supported") {
      document.getElementById("forecast-interpretation").textContent = entry.reason || "Not supported for this item.";
      document.getElementById("model-info-drawer").innerHTML = "Not supported for this item.";
      return;
    }

    const f = entry.forecast;
    DashCharts.forecastBand("chart-forecast-band", {
      historyLabels: f.history.labels, historyValues: f.history.actual,
      fittedValues: f.fitted.value,
      futureLabels: f.future.labels, futureMedian: f.future.median,
      futureLower: f.future.lower, futureUpper: f.future.upper,
    });

    const mi = entry.model_info;
    const sigText = mi.summer_significant ? "statistically significant" : "not statistically significant";
    document.getElementById("forecast-interpretation").textContent =
      `Summer regressor: log-coefficient ${mi.summer_log_coef} (→ ×${mi.summer_multiplier} multiplier), ` +
      `${UI.fmtPValue(mi.summer_pvalue)} — ${sigText} for this item.`;

    document.getElementById("model-info-drawer").innerHTML = `
      <p><strong>Spec:</strong> ${mi.spec}<br>
      <strong>AIC:</strong> ${mi.aic}<br>
      <strong>Summer log-coefficient:</strong> ${mi.summer_log_coef} (${UI.fmtPValue(mi.summer_pvalue)})<br>
      <strong>Summer multiplier:</strong> ×${mi.summer_multiplier} (exp of the log-coefficient)<br>
      <strong>Training window:</strong> ${mi.training_window.start} to ${mi.training_window.end} (${mi.training_window.n_weeks} weeks)<br>
      <strong>Converged:</strong> ${mi.converged ? "Yes" : "No"}</p>
    `;
  }

  async function loadValidation(item) {
    const v = await Api.getJSON("/api/demand/validation");

    DashCharts.groupedBar("chart-validation-error", v.fold_level_chart.labels, [
      { label: "ARIMAX RMSE", data: v.fold_level_chart.arimax_rmse },
      { label: "Naive RMSE", data: v.fold_level_chart.naive_rmse },
    ]);

    const itemValidation = v.items[item];
    if (itemValidation && itemValidation.status === "supported") {
      const ro = itemValidation.rolling_origin;
      const ns = itemValidation.naive_80_20_split;
      UI.renderTable("table-validation-folds", ro.folds, (fold) => `
        <tr><td>${fold.fold}</td><td>${fold.cutoff_date}</td><td>${fold.arimax_rmse ?? "—"}</td><td>${fold.naive_rmse}</td></tr>
      `);
      UI.renderMiniStats("validation-split-compare", [
        { label: "Rolling-Origin Improvement", value: UI.fmtPct(ro.improvement_pct), sub: "5 folds × 8 weeks (headline)" },
        { label: "Naive 80/20 Split Improvement", value: ns ? UI.fmtPct(ns.improvement_pct) : "—", sub: ns && !ns.test_window_contains_summer ? "test window has no summer" : "" },
      ]);
    }
    return v;
  }

  async function loadDemandSensing() {
    const [eda, fc] = await Promise.all([Api.getJSON("/api/eda"), Api.getJSON("/api/demand/forecast")]);
    forecastData = fc;
    renderSeasonalityInsight(eda.seasonality);

    const items = Object.keys(forecastData.items);
    const select = document.getElementById("forecast-item-select");
    select.innerHTML = items.map((i) => `<option value="${i}">${i}</option>`).join("");
    select.onchange = () => {
      renderForecastChart(select.value);
      loadValidation(select.value).then(renderKPIs).catch((err) => console.error("Validation reload failed", err));
    };

    renderForecastChart(items[0]);
    const v = await loadValidation(items[0]);
    renderKPIs(v);
    Drawer.wire();
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 2 || loaded) return;
    loaded = true;
    loadDemandSensing().catch((err) => console.error("Slide 3 (Demand Sensing) failed to load", err));
  });
})();
