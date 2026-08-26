(function () {
  let forecastData = null;

  function renderKPIs(validationBundle) {
    const items = Object.values(forecastData.items).filter((i) => i.status === "supported");
    const sigCount = items.filter((i) => i.model_info.summer_significant).length;

    UI.renderKPIs("forecast-kpis", [
      { label: "Avg Improvement vs Naive", value: UI.fmtPct(validationBundle.cross_item_avg_improvement_pct), context: "rolling-origin RMSE, averaged across items" },
      { label: "Items Modeled", value: `${items.length} / 6`, context: "ARIMAX(0,1,1) + summer regressor" },
      { label: "Summer-Significant Items", value: `${sigCount} / ${items.length}`, context: "p < 0.05 on the summer coefficient" },
      { label: "Forecast Horizon", value: `${forecastData.forecast_horizon_days} days`, context: "beyond the last observed date" },
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
    const sparseText = mi.sparse_data_flag
      ? " This item has sparse historical data (many zero-demand days) — treat the forecast interval with extra caution."
      : "";
    document.getElementById("forecast-interpretation").textContent =
      `Summer regressor coefficient ${mi.summer_coef} (${UI.fmtPValue(mi.summer_pvalue)}) — ${sigText} for this item.${sparseText}`;

    document.getElementById("model-info-drawer").innerHTML = `
      <p><strong>Spec:</strong> ${mi.spec}<br>
      <strong>AIC:</strong> ${mi.aic}<br>
      <strong>Summer coefficient:</strong> ${mi.summer_coef} (${UI.fmtPValue(mi.summer_pvalue)})<br>
      <strong>Training window:</strong> ${mi.training_window.start} to ${mi.training_window.end} (${mi.training_window.n_days} days)<br>
      <strong>Converged:</strong> ${mi.converged ? "Yes" : "No"}<br>
      <strong>Zero-quantity days:</strong> ${UI.fmtPct(mi.zero_quantity_day_pct)}</p>
    `;
  }

  async function loadValidation(item) {
    const v = await Api.getJSON("/api/demand/validation");
    renderKPIs(v);

    DashCharts.groupedBar("chart-validation-error", v.fold_level_chart.labels, [
      { label: "ARIMAX RMSE", data: v.fold_level_chart.arimax_rmse },
      { label: "Naive RMSE", data: v.fold_level_chart.naive_rmse },
    ]);

    const itemValidation = v.items[item];
    if (itemValidation && itemValidation.status === "supported") {
      UI.renderTable("table-validation-folds", itemValidation.folds, (fold) => `
        <tr><td>${fold.fold}</td><td>${fold.cutoff_date}</td><td>${fold.arimax_rmse ?? "—"}</td><td>${fold.naive_rmse}</td></tr>
      `);
    }
  }

  async function loadDemandSensing() {
    forecastData = await Api.getJSON("/api/demand/forecast");
    const items = Object.keys(forecastData.items);

    const select = document.getElementById("forecast-item-select");
    select.innerHTML = items.map((i) => `<option value="${i}">${i}</option>`).join("");
    select.onchange = () => {
      renderForecastChart(select.value);
      loadValidation(select.value).catch((err) => console.error("Validation reload failed", err));
    };

    renderForecastChart(items[0]);
    await loadValidation(items[0]);
    Drawer.wire();
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 3 || loaded) return;
    loaded = true;
    loadDemandSensing().catch((err) => console.error("Slide 4 (Demand Sensing) failed to load", err));
  });
})();
