(function () {
  const fmtINR = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const fmtPct = (n, digits = 1) => (n === null || n === undefined ? "—" : `${Number(n).toFixed(digits)}%`);
  const fmtNum = (n) => Number(n || 0).toLocaleString("en-IN");

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url} -> ${res.status}`);
    return res.json();
  }

  function renderKPIs(containerId, tiles) {
    const el = document.getElementById(containerId);
    el.innerHTML = tiles.map((t) => `
      <div class="kpi-tile">
        <div class="label">${t.label}</div>
        <div class="value">${t.value}</div>
        ${t.delta ? `<div class="delta ${t.deltaClass || ""}">${t.delta}</div>` : ""}
      </div>
    `).join("");
  }

  function renderLegend(containerId, colorMap) {
    const el = document.getElementById(containerId);
    el.innerHTML = Object.entries(colorMap).map(([label, color]) => `
      <div class="legend-item"><span class="legend-swatch" style="background:${color}"></span>${label}</div>
    `).join("");
  }

  function renderTable(tableId, rows, rowFn) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    tbody.innerHTML = rows.map(rowFn).join("");
  }

  const loaded = new Set();

  async function loadOverview() {
    const [overview, sales] = await Promise.all([
      fetchJSON("/api/metrics/overview"),
      fetchJSON("/api/metrics/sales"),
    ]);

    document.getElementById("date-range-subtitle").textContent =
      `${overview.date_range.start} → ${overview.date_range.end} · ${fmtNum(overview.total_transactions)} transactions`;

    const yoy = overview.yoy_revenue_growth_pct;
    renderKPIs("overview-kpis", [
      { label: "Total Revenue", value: fmtINR(overview.total_revenue) },
      { label: "Total Profit", value: fmtINR(overview.total_profit) },
      { label: "Avg Margin", value: fmtPct(overview.avg_margin_pct) },
      { label: "YoY Revenue Growth", value: yoy !== null ? fmtPct(yoy) : "—", delta: yoy !== null ? (yoy >= 0 ? "▲ vs prior year" : "▼ vs prior year") : "", deltaClass: yoy >= 0 ? "up" : "down" },
      { label: "Total Waste Cost", value: fmtINR(overview.total_waste_cost) },
    ]);

    DashCharts.lineTrend("chart-overview-trend", sales.revenue_trend.labels, [
      { label: "Revenue", data: sales.revenue_trend.revenue },
      { label: "Profit", data: sales.revenue_trend.profit },
    ]);
  }

  async function loadSales() {
    const sales = await fetchJSON("/api/metrics/sales");
    const overview = await fetchJSON("/api/metrics/overview");

    renderKPIs("sales-kpis", [
      { label: "Total Revenue", value: fmtINR(overview.total_revenue) },
      { label: "Transactions", value: fmtNum(overview.total_transactions) },
      { label: "Avg Order Value", value: fmtINR(overview.total_revenue / overview.total_transactions) },
    ]);

    DashCharts.bar(
      "chart-revenue-category",
      sales.revenue_by_category.labels,
      sales.revenue_by_category.values,
      sales.revenue_by_category.labels.map((c) => DashCharts.CATEGORY_COLORS[c] || DashCharts.SERIES[0])
    );
    renderLegend("legend-category", DashCharts.CATEGORY_COLORS);

    const items = sales.item_performance;
    DashCharts.bar(
      "chart-item-performance",
      items.map((r) => r.Item_Name),
      items.map((r) => r.revenue),
      items.map((r) => DashCharts.CATEGORY_COLORS[r.Category] || DashCharts.SERIES[0])
    );

    DashCharts.bar("chart-hourly", sales.hourly_pattern.labels, sales.hourly_pattern.transactions);
  }

  async function loadInventory() {
    const [inv, prep] = await Promise.all([
      fetchJSON("/api/metrics/inventory"),
      fetchJSON("/api/optimizer/prep"),
    ]);
    const overview = await fetchJSON("/api/metrics/overview");

    const avgWaste = inv.waste_by_item.reduce((s, r) => s + r.avg_waste_pct, 0) / inv.waste_by_item.length;
    renderKPIs("inventory-kpis", [
      { label: "Total Waste Units", value: fmtNum(overview.total_waste_units) },
      { label: "Total Waste Cost", value: fmtINR(overview.total_waste_cost) },
      { label: "Avg Waste % of Forecast", value: fmtPct(avgWaste) },
      { label: "Prep Optimizer Total Upside", value: fmtINR(prep.reduce((s, r) => s + r.projected_savings_inr, 0)) },
    ]);

    DashCharts.lineTrend("chart-forecast-actual", inv.forecast_vs_actual.labels, [
      { label: "Forecasted", data: inv.forecast_vs_actual.forecasted },
      { label: "Actual", data: inv.forecast_vs_actual.actual },
    ]);

    DashCharts.bar(
      "chart-waste-item",
      inv.waste_by_item.map((r) => r.Item_Name),
      inv.waste_by_item.map((r) => r.avg_waste_pct)
    );

    renderTable("table-prep-optimizer", prep, (r) => `
      <tr>
        <td>${r.item}</td>
        <td>${r.current_avg_prep_qty}</td>
        <td>${r.recommended_adjustment > 0 ? "+" : ""}${r.recommended_adjustment}</td>
        <td>${r.recommended_avg_prep_qty}</td>
        <td>${fmtINR(r.current_annual_cost)}</td>
        <td>${fmtINR(r.projected_annual_cost)}</td>
        <td>${fmtINR(r.projected_savings_inr)}</td>
        <td>${fmtPct(r.projected_savings_pct)}</td>
      </tr>
    `);
  }

  async function loadSupply() {
    const [supply, procurement] = await Promise.all([
      fetchJSON("/api/metrics/supply"),
      fetchJSON("/api/optimizer/procurement"),
    ]);
    const rows = supply.supplier_comparison;

    const categories = [...new Set(rows.map((r) => r.Ingredient_Category))];
    const suppliers = [...new Set(rows.map((r) => r.Supplier))];
    const byKey = Object.fromEntries(rows.map((r) => [`${r.Ingredient_Category}|${r.Supplier}`, r]));

    DashCharts.upsertChart("chart-supplier-cost", {
      type: "bar",
      data: {
        labels: categories,
        datasets: suppliers.map((s) => ({
          label: s,
          data: categories.map((c) => byKey[`${c}|${s}`]?.avg_delivery_cost ?? null),
          backgroundColor: DashCharts.SUPPLIER_COLORS[s] || DashCharts.SERIES[0],
          borderRadius: 4,
          maxBarThickness: 34,
        })),
      },
      options: DashCharts.baseOptions(),
    });
    renderLegend("legend-supplier", DashCharts.SUPPLIER_COLORS);

    const totalRoutes = rows.reduce((s, r) => s + r.routes, 0);
    renderKPIs("supply-kpis", [
      { label: "Suppliers", value: suppliers.length },
      { label: "Total Routes", value: fmtNum(totalRoutes) },
      { label: "Avg Delivery Cost", value: fmtINR(rows.reduce((s, r) => s + r.avg_delivery_cost, 0) / rows.length) },
      { label: "Avg Lead Time", value: `${(rows.reduce((s, r) => s + r.avg_lead_time, 0) / rows.length).toFixed(1)} days` },
    ]);

    renderTable("table-procurement-optimizer", procurement, (r) => `
      <tr>
        <td>${r.category}</td>
        <td>${r.recommended_supplier}</td>
        <td>${fmtINR(r.recommended_avg_cost)}</td>
        <td>${r.recommended_avg_lead_time} days</td>
        <td>${fmtINR(r.category_avg_cost)}</td>
        <td>${r.category_avg_lead_time} days</td>
        <td>${fmtPct(r.cost_savings_pct)}</td>
        <td>${r.leadtime_improvement_days > 0 ? "-" : "+"}${Math.abs(r.leadtime_improvement_days)} days</td>
      </tr>
    `);
  }

  let pricingData = [];

  function renderPricingChartFor(item) {
    const row = pricingData.find((r) => r.item === item);
    if (!row) return;
    document.getElementById("pricing-chart-item-label").textContent = item;
    document.getElementById("pricing-item-note").textContent = row.note;

    const bucketOrder = ["0%", "0-10%", "10-20%", "20%+"];
    const labels = bucketOrder.filter((b) => row.buckets[b]);
    DashCharts.bar("chart-pricing-buckets", labels, labels.map((b) => row.buckets[b].avg_profit_per_line));
  }

  async function loadPricing() {
    pricingData = await fetchJSON("/api/optimizer/pricing");

    const totalDiscount = pricingData.reduce((s, r) => s + r.total_discount_given_inr, 0);
    const avgLeakage = pricingData.reduce((s, r) => s + r.discount_leakage_pct, 0) / pricingData.length;
    const topLeakage = pricingData[0];

    renderKPIs("pricing-kpis", [
      { label: "Total Discount Given / yr", value: fmtINR(totalDiscount) },
      { label: "Avg Leakage % of Revenue", value: fmtPct(avgLeakage) },
      { label: "Highest-Leakage Item", value: topLeakage.item },
      { label: "Halved-Discounting Upside", value: fmtINR(totalDiscount * 0.5) },
    ]);

    const select = document.getElementById("pricing-item-select");
    select.innerHTML = pricingData.map((r) => `<option value="${r.item}">${r.item}</option>`).join("");
    select.onchange = () => renderPricingChartFor(select.value);
    renderPricingChartFor(pricingData[0].item);

    renderTable("table-pricing-optimizer", pricingData, (r) => `
      <tr>
        <td>${r.item}</td>
        <td>${fmtPct(r.avg_discount_pct)}</td>
        <td>${fmtINR(r.total_discount_given_inr)}</td>
        <td>${fmtPct(r.discount_leakage_pct)}</td>
        <td>${fmtPct(r.margin_cushion_pct)}</td>
        <td>${fmtINR(r.projected_savings_if_halved_inr)}</td>
        <td><span class="tag ${r.recommendation.startsWith("Tighten") ? "priority" : "ok"}">${r.recommendation}</span></td>
      </tr>
    `);
  }

  const LOADERS = [loadOverview, loadSales, loadInventory, loadSupply, loadPricing];

  Slides.onActivate((index) => {
    if (!LOADERS[index] || loaded.has(index)) return;
    loaded.add(index);
    LOADERS[index]().catch((err) => console.error(`Slide ${index} failed to load`, err));
  });

  window.Dashboard = { fmtINR, fmtPct, fmtNum };
})();
