(function () {
  function renderInsight(rows) {
    const totalGiven = rows.reduce((s, r) => s + r.total_discount_given_inr, 0);
    document.getElementById("pricing-insight").innerHTML = `
      <span class="lead-label">Insight</span>
      ${rows[0].note} Total discount given away across all items: ${UI.fmtINR(totalGiven)}/yr, with no
      offsetting volume lift to show for it.
    `;
  }

  function renderKPIs(rows) {
    const totalGiven = rows.reduce((s, r) => s + r.total_discount_given_inr, 0);
    const avgLeakage = rows.reduce((s, r) => s + r.discount_leakage_pct, 0) / rows.length;
    const tighten = rows.filter((r) => r.recommendation.startsWith("Tighten")).length;
    UI.renderKPIs("pricing-kpis", [
      { label: "Total Discount Given", value: UI.fmtINR(totalGiven), context: "per year, across all items" },
      { label: "Avg Leakage", value: UI.fmtPct(avgLeakage), context: "share of gross revenue given away" },
      { label: "Items to Tighten First", value: `${tighten} / ${rows.length}`, context: "below-median margin cushion" },
      { label: "If Halved", value: UI.fmtINR(rows.reduce((s, r) => s + r.projected_savings_if_halved_inr, 0)), context: "avoided cost, not a volume-loss-adjusted saving" },
    ]);
  }

  function renderChart(rows) {
    DashCharts.bar("chart-pricing-leakage", rows.map((r) => r.item.split(" ")[0]), rows.map((r) => r.discount_leakage_pct));
  }

  function renderTable(rows) {
    UI.renderTable("table-pricing", rows, (r) => `
      <tr>
        <td>${r.item}</td>
        <td>${UI.fmtPct(r.avg_discount_pct)}</td>
        <td>${UI.fmtPct(r.discount_leakage_pct)}</td>
        <td>${UI.fmtPct(r.margin_cushion_pct)}</td>
        <td>${r.recommendation.startsWith("Tighten") ? "Tighten first" : "Lower priority"}</td>
      </tr>
    `);
  }

  function renderDecision(rows) {
    const top = rows[0];
    document.getElementById("pricing-decision").textContent =
      `${top.item} gives away the most in absolute rupees (${UI.fmtINR(top.total_discount_given_inr)}/yr). ` +
      `Since average order quantity doesn't rise with discount depth in this data, tightening discount ` +
      `approval on low-margin-cushion items is a cost avoided, not a volume decision.`;
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 6 || loaded) return;
    loaded = true;
    Api.getJSON("/api/optimizer/pricing")
      .then((rows) => {
        renderInsight(rows);
        renderKPIs(rows);
        renderChart(rows);
        renderTable(rows);
        renderDecision(rows);
      })
      .catch((err) => console.error("Slide 7 (Pricing) failed to load", err));
  });
})();
