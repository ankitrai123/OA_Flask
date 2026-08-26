(function () {
  function renderInsight(bundle) {
    const items = Object.values(bundle.items);
    const avgStockout = items.reduce((s, r) => s + r.stockout_day_pct, 0) / items.length;
    document.getElementById("automation-insight").innerHTML = `
      <span class="lead-label">Insight</span>
      A rule-based reorder trigger on the corrected (item-specific) reorder points from Inventory would
      have fired ${bundle.total_triggers_across_items} times across all 6 items over the 2-year history,
      holding the average stockout-day rate to ${UI.fmtPct(avgStockout)} - a specified rule, backtested
      against real demand, not a live system (there is no real-time inventory feed in this data).
    `;
  }

  function renderKPIs(bundle) {
    const items = Object.values(bundle.items);
    const avgStockout = items.reduce((s, r) => s + r.stockout_day_pct, 0) / items.length;
    const avgDays = items.reduce((s, r) => s + (r.avg_days_between_triggers || 0), 0) / items.length;
    UI.renderKPIs("automation-kpis", [
      { label: "Total Triggers (2-yr backtest)", value: UI.fmtNum(bundle.total_triggers_across_items), context: "across all 6 items" },
      { label: "Avg Days Between Triggers", value: UI.fmtNum(avgDays, 1), context: "per item, averaged" },
      { label: "Avg Stockout-Day Rate", value: UI.fmtPct(avgStockout), context: "at a 95% service-level ROP" },
      { label: "Items Covered", value: `${items.length} / 6`, context: "rule specified per item" },
    ]);
  }

  function renderChart(bundle) {
    const items = Object.keys(bundle.items);
    DashCharts.bar("chart-automation-triggers", items.map((i) => i.split(" ")[0]), items.map((i) => bundle.items[i].triggers_fired));
  }

  function renderTable(bundle) {
    const rows = Object.values(bundle.items);
    UI.renderTable("table-automation", rows, (r) => `
      <tr title="Supplier: ${r.rule.recommended_supplier}">
        <td>${r.item}</td>
        <td>${r.rule.reorder_point_units}</td>
        <td>${r.rule.order_qty_units}</td>
        <td>${r.rule.lead_time_days}d</td>
        <td>${UI.fmtPct(r.stockout_day_pct)}</td>
      </tr>
    `);
  }

  function renderDecision(bundle) {
    const suppliers = new Set(Object.values(bundle.items).map((r) => r.rule.recommended_supplier));
    document.getElementById("automation-decision").textContent =
      `Specify this rule (IF position ≤ ROP THEN reorder at the stated quantity from ` +
      `${[...suppliers].join(" / ")}) as a scheduled check the purchase desk runs daily, rather than ` +
      "the ad-hoc judgment call it is today.";
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 7 || loaded) return;
    loaded = true;
    Api.getJSON("/api/automation")
      .then((bundle) => {
        renderInsight(bundle);
        renderKPIs(bundle);
        renderChart(bundle);
        renderTable(bundle);
        renderDecision(bundle);
      })
      .catch((err) => console.error("Slide 8 (Automation) failed to load", err));
  });
})();
