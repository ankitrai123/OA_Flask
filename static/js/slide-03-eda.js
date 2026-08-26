(function () {
  function renderKPIs(b) {
    const topItem = b.revenue_mix.items[0];
    const sigCount = b.seasonality.per_item_summer_uplift.filter((x) => x.significant).length;
    const dailyCV = b.demand_distribution.daily_overall.cv;

    UI.renderKPIs("eda-kpis", [
      { label: "Top Item Revenue Share", value: UI.fmtPct(topItem ? topItem.revenue_share_pct : null), context: topItem ? topItem.item : "" },
      { label: "Daily Demand CV", value: dailyCV != null ? dailyCV.toFixed(2) : "—", context: "coefficient of variation, all items pooled" },
      { label: "Summer Uplift (Apr-Jun)", value: UI.fmtPct(b.seasonality.summer_vs_rest.uplift_pct), context: "vs. rest of year, aggregate demand" },
      { label: "Items w/ Significant Seasonality", value: `${sigCount} / 6`, context: "p < 0.05, Welch's t-test" },
    ]);
  }

  function renderRevenueMix(items) {
    DashCharts.bar(
      "chart-revenue-mix",
      items.map((i) => i.item),
      items.map((i) => i.revenue_inr),
      items.map((i) => DashCharts.CATEGORY_COLORS[i.category] || DashCharts.SERIES[0])
    );
    UI.renderLegend("legend-category", DashCharts.CATEGORY_COLORS);
  }

  function renderSeasonality(seasonality) {
    DashCharts.bar("chart-seasonality", seasonality.monthly_index.labels, seasonality.monthly_index.index);

    UI.renderTable("table-seasonality", seasonality.per_item_summer_uplift, (r) => `
      <tr>
        <td>${r.item}</td>
        <td>${r.summer_mean}</td>
        <td>${r.rest_mean}</td>
        <td>${r.uplift_pct > 0 ? "+" : ""}${r.uplift_pct}%</td>
        <td>${UI.fmtPValue(r.p_value)}</td>
        <td>${r.significant ? "Yes" : "No"}</td>
      </tr>
    `);

    document.getElementById("seasonality-interpretation").textContent = seasonality.interpretation;
  }

  function renderSpoilageBias(data) {
    DashCharts.groupedBar(
      "chart-spoilage-bias",
      data.per_item.map((r) => r.item),
      [
        { label: "Forecasted Prep", data: data.per_item.map((r) => r.avg_forecasted_prep_qty) },
        { label: "Actual Demand", data: data.per_item.map((r) => r.avg_actual_demand_qty) },
        { label: "Spoiled", data: data.per_item.map((r) => r.avg_spoiled_qty) },
      ]
    );
    document.getElementById("spoilage-scope-note").textContent = data.scope_note;
  }

  function renderHourlyStatus(status) {
    document.getElementById("hourly-status-card").innerHTML = `<strong>Time-of-day analysis: ${status.status}.</strong> ${status.reason}`;
  }

  function renderMenuAffinity(affinity) {
    const el = document.getElementById("menu-affinity-card");
    if (!affinity.top_rules.length) {
      el.innerHTML = `<div class="note">No strong menu-item affinities found at the current thresholds.</div>`;
      return;
    }
    el.innerHTML = `
      <h2 style="font-size:12.5px; margin-bottom:6px;">Menu Affinity (apriori, top ${affinity.top_rules.length})</h2>
      ${affinity.top_rules.map((r) => `<div class="note" style="margin-top:4px;">${r.recommendation}</div>`).join("")}
    `;
  }

  async function loadEDA() {
    const b = await Api.getJSON("/api/eda");
    renderKPIs(b);
    renderRevenueMix(b.revenue_mix.items);
    renderSeasonality(b.seasonality);
    renderSpoilageBias(b.spoilage_and_prep_bias);
    renderHourlyStatus(b.hourly_pattern_status);
    renderMenuAffinity(b.menu_affinity);
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 2 || loaded) return;
    loaded = true;
    loadEDA().catch((err) => console.error("Slide 3 (EDA) failed to load", err));
  });
})();
