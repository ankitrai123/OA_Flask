(function () {
  const fmtINR = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const fmtPct = (n, digits = 1) => (n === null || n === undefined ? "—" : `${Number(n).toFixed(digits)}%`);
  const fmtNum = (n, digits = 0) => Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: digits });

  async function getJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url} -> ${res.status}`);
    return res.json();
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `${url} -> ${res.status}`);
    return data;
  }

  function renderKPIs(containerId, tiles) {
    document.getElementById(containerId).innerHTML = tiles.map((t) => `
      <div class="kpi-tile">
        <div class="label">${t.label}</div>
        <div class="value">${t.value}</div>
      </div>
    `).join("");
  }

  function renderMiniStats(containerId, stats) {
    document.getElementById(containerId).innerHTML = stats.map((s) => `
      <div class="mini-stat">
        <div class="label">${s.label}</div>
        <div class="value">${s.value}</div>
        ${s.sub ? `<div class="sub">${s.sub}</div>` : ""}
      </div>
    `).join("");
  }

  // ---- Slide 6: Forecasting & Simulation ----

  let forecastData = null;

  function renderBacktestChart() {
    const bt = forecastData.backtest_chart;
    DashCharts.lineTrend("chart-backtest", bt.labels, [
      { label: "Actual", data: bt.actual },
      { label: "Predicted", data: bt.predicted },
    ]);
  }

  function renderFutureForecast(item) {
    const f = forecastData.forecasts[item];
    document.getElementById("forecast-item-label").textContent = item;
    const days = f.days;
    const seriesColor = DashCharts.SERIES[0];

    DashCharts.upsertChart("chart-forecast-future", {
      type: "line",
      data: {
        labels: days.map((d) => d.date.slice(5)),
        datasets: [
          { label: "Lower (10%)", data: days.map((d) => d.lower), borderColor: "transparent", backgroundColor: "transparent", pointRadius: 0, fill: false },
          { label: "Upper (90%)", data: days.map((d) => d.upper), borderColor: "transparent", backgroundColor: seriesColor + "26", pointRadius: 0, fill: "-1" },
          { label: "Median forecast", data: days.map((d) => d.median), borderColor: seriesColor, backgroundColor: seriesColor, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.2 },
          { label: `Recommended prep (CR ${f.critical_ratio})`, data: days.map((d) => d.recommended_prep), borderColor: DashCharts.SERIES[1], backgroundColor: DashCharts.SERIES[1], borderWidth: 2, borderDash: [4, 3], pointRadius: 0, fill: false, tension: 0.2 },
        ],
      },
      options: DashCharts.baseOptions({
        plugins: { legend: { display: true, position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10 } } },
        // Not a magnitude-comparison bar chart — forcing the zero baseline here
        // would flatten the forecast band into an unreadable sliver, since daily
        // demand for these items sits in a fairly narrow 20-45 unit range.
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: "#2c2c2a" }, beginAtZero: false },
        },
      }),
    });
  }

  async function loadForecastSlide() {
    forecastData = await getJSON("/api/forecast");
    const m = forecastData.backtest_metrics;

    renderKPIs("forecast-kpis", [
      { label: "Model MAE (units/day)", value: fmtNum(m.mae, 1) },
      { label: "Model RMSE", value: fmtNum(m.rmse, 1) },
      { label: "vs Naive Baseline", value: fmtPct(m.improvement_vs_naive_pct) + " better" },
      { label: "Forecast Horizon", value: `${forecastData.forecast_horizon_days} days` },
    ]);

    renderBacktestChart();

    const items = Object.keys(forecastData.forecasts);
    const select = document.getElementById("forecast-item-select");
    select.innerHTML = items.map((i) => `<option value="${i}">${i}</option>`).join("");
    select.onchange = () => renderFutureForecast(select.value);
    renderFutureForecast(items[0]);

    const simItemSelect = document.getElementById("sim-prep-item");
    simItemSelect.innerHTML = items.map((i) => `<option value="${i}">${i}</option>`).join("");

    const runBtn = document.getElementById("sim-prep-run");
    runBtn.disabled = false;
    runBtn.textContent = "Run Simulation";
  }

  function wireRangeLabel(rangeId, labelId, formatFn) {
    const range = document.getElementById(rangeId);
    const label = document.getElementById(labelId);
    range.addEventListener("input", () => { label.textContent = formatFn(range.value); });
  }

  async function runPrepSimulation() {
    const btn = document.getElementById("sim-prep-run");
    btn.disabled = true;
    try {
      const item = document.getElementById("sim-prep-item").value;
      const growth = Number(document.getElementById("sim-prep-growth").value);
      const vol = Number(document.getElementById("sim-prep-vol").value) / 100;

      const result = await postJSON("/api/simulator/prep", {
        item, demand_growth_pct: growth, demand_vol_multiplier: vol,
      });

      renderMiniStats("sim-prep-results", [
        { label: "Total Cost (median)", value: fmtINR(result.total_cost_inr.p50), sub: `p10 ${fmtINR(result.total_cost_inr.p10)} – p90 ${fmtINR(result.total_cost_inr.p90)}` },
        { label: "Waste Units", value: fmtNum(result.waste_units.p50), sub: `over ${result.inputs.n_days} days` },
        { label: "Stockout Units", value: fmtNum(result.stockout_units.p50) },
        { label: "Fill Rate", value: fmtPct(result.fill_rate_pct.p50) },
      ]);
      document.getElementById("sim-prep-note").textContent = result.note;
    } catch (err) {
      document.getElementById("sim-prep-note").textContent = `Simulation failed: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  async function runSupplierSimulation() {
    const btn = document.getElementById("sim-supplier-run");
    btn.disabled = true;
    try {
      const category = document.getElementById("sim-supplier-category").value;
      const annual_demand = Number(document.getElementById("sim-supplier-demand").value);
      const holding_cost_per_unit_per_year = Number(document.getElementById("sim-supplier-holding").value);
      const leadInput = document.getElementById("sim-supplier-leadtime").value;
      const demand_growth_pct = Number(document.getElementById("sim-supplier-growth").value);

      const result = await postJSON("/api/simulator/supplier", {
        category, annual_demand, holding_cost_per_unit_per_year, demand_growth_pct,
        lead_time_override: leadInput ? Number(leadInput) : null,
      });

      renderMiniStats("sim-supplier-results", [
        { label: "Stockout Days", value: fmtPct(result.stockout_days_pct_of_horizon.p50), sub: `p90 ${fmtPct(result.stockout_days_pct_of_horizon.p90)}` },
        { label: "Unmet Units", value: fmtNum(result.unmet_units.p50) },
        { label: "Total Cost (median)", value: fmtINR(result.total_cost_inr.p50) },
        { label: "Orders Placed", value: fmtNum(result.orders_placed.p50) },
      ]);
      document.getElementById("sim-supplier-note").textContent = `Lead time: ${result.inputs.lead_time_days}d · Reorder point: ${fmtNum(result.inputs.reorder_point,1)} · Order qty: ${fmtNum(result.inputs.order_qty,1)}. ${result.note}`;
    } catch (err) {
      document.getElementById("sim-supplier-note").textContent = `Simulation failed: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  async function initSimulationControls() {
    const categories = await getJSON("/api/supply/categories");
    document.getElementById("sim-supplier-category").innerHTML = categories.map((c) => `<option value="${c}">${c}</option>`).join("");

    wireRangeLabel("sim-prep-growth", "sim-prep-growth-val", (v) => `${v > 0 ? "+" : ""}${v}%`);
    wireRangeLabel("sim-prep-vol", "sim-prep-vol-val", (v) => `${(v / 100).toFixed(2)}x`);
    wireRangeLabel("sim-supplier-growth", "sim-supplier-growth-val", (v) => `${v > 0 ? "+" : ""}${v}%`);

    document.getElementById("sim-prep-run").addEventListener("click", runPrepSimulation);
    document.getElementById("sim-supplier-run").addEventListener("click", runSupplierSimulation);
  }

  let slide6Loaded = false;
  async function loadSlide6() {
    if (slide6Loaded) return;
    slide6Loaded = true;
    await initSimulationControls();
    await loadForecastSlide();
  }

  // ---- Slide 7: Menu & Supply Optimization ----

  async function loadBasketAnalysis() {
    const data = await getJSON("/api/basket-analysis");
    const rules = data.rules || [];

    const strongest = rules[0];
    renderKPIs("basket-kpis", [
      { label: "Association Rules Found", value: rules.length },
      { label: "Strongest Pair (Lift)", value: strongest ? `${strongest.lift}x` : "—" },
      { label: "Baskets Analyzed", value: fmtNum(data.basket_count) },
    ]);

    document.querySelector("#table-basket-rules tbody").innerHTML = rules.map((r) => `
      <tr>
        <td>${r.antecedent}</td>
        <td>${r.consequent}</td>
        <td>${fmtPct(r.support_pct)}</td>
        <td>${fmtPct(r.confidence_pct)}</td>
        <td>${r.lift}x</td>
      </tr>
    `).join("");
  }

  async function runEOQ() {
    const btn = document.getElementById("eoq-run");
    btn.disabled = true;
    try {
      const category = document.getElementById("eoq-category").value;
      const annual_demand = Number(document.getElementById("eoq-demand").value);
      const holding_cost_per_unit_per_year = Number(document.getElementById("eoq-holding").value);

      const result = await postJSON("/api/supply/eoq", { category, annual_demand, holding_cost_per_unit_per_year });

      renderMiniStats("eoq-results", [
        { label: "EOQ", value: fmtNum(result.eoq) + " units" },
        { label: "Reorder Point", value: fmtNum(result.reorder_point) },
        { label: "Safety Stock", value: fmtNum(result.safety_stock) },
        { label: "Orders/Year", value: fmtNum(result.orders_per_year, 1) },
        { label: "Annual Cost @ EOQ", value: fmtINR(result.annual_cost_at_eoq) },
        { label: "Savings vs MOQ Baseline", value: fmtPct(result.savings_vs_moq_baseline_pct) },
      ]);
      document.getElementById("eoq-note").textContent = result.note;
    } catch (err) {
      document.getElementById("eoq-note").textContent = `Calculation failed: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  async function runAllocation() {
    const btn = document.getElementById("alloc-run");
    btn.disabled = true;
    try {
      const category = document.getElementById("alloc-category").value;
      const required_qty = Number(document.getElementById("alloc-qty").value);
      const shareVal = Number(document.getElementById("alloc-share").value);

      const result = await postJSON("/api/supply/allocation", {
        category, required_qty,
        max_share_per_supplier: shareVal > 0 ? shareVal / 100 : null,
      });

      document.querySelector("#table-allocation tbody").innerHTML = result.allocation.map((a) => `
        <tr><td>${a.supplier}</td><td>${a.batches}</td><td>${fmtNum(a.qty, 1)}</td><td>${fmtINR(a.cost)}</td></tr>
      `).join("");

      let note = `Total: ${fmtINR(result.total_cost)} for ${fmtNum(result.total_qty_ordered, 1)} units. ${result.note}`;
      if (result.diversification) {
        note += ` Diversification premium: ${fmtINR(result.diversification.cost_premium_vs_cheapest_single_inr)} (${fmtPct(result.diversification.cost_premium_pct)}) vs single-sourcing.`;
      } else {
        note += ` Savings vs single-cheapest-supplier: ${fmtPct(result.savings_vs_single_supplier_pct)}.`;
      }
      document.getElementById("alloc-note").textContent = note;
    } catch (err) {
      document.getElementById("alloc-note").textContent = `Optimization failed: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  let slide7Loaded = false;
  async function loadSlide7() {
    if (slide7Loaded) return;
    slide7Loaded = true;

    const categories = await getJSON("/api/supply/categories");
    document.getElementById("eoq-category").innerHTML = categories.map((c) => `<option value="${c}">${c}</option>`).join("");
    document.getElementById("alloc-category").innerHTML = categories.map((c) => `<option value="${c}">${c}</option>`).join("");

    wireRangeLabel("alloc-share", "alloc-share-val", (v) => (v == 0 ? "off" : `${v}%`));

    document.getElementById("eoq-run").addEventListener("click", runEOQ);
    document.getElementById("alloc-run").addEventListener("click", runAllocation);

    await loadBasketAnalysis();
  }

  Slides.onActivate((index) => {
    if (index === 5) loadSlide6().catch((err) => console.error("Slide 6 failed to load", err));
    if (index === 6) loadSlide7().catch((err) => console.error("Slide 7 failed to load", err));
  });
})();
