(function () {
  const KPI_ORDER = ["annual_revenue", "gross_margin", "orders", "order_lines", "spoilage_cost", "shortage_days", "num_items", "num_suppliers"];

  function formatKpiValue(key, k) {
    if (key === "annual_revenue" || key === "spoilage_cost") return UI.fmtINR(k.value);
    if (key === "gross_margin" || key === "shortage_days") return UI.fmtPct(k.value);
    return UI.fmtNum(k.value);
  }

  function renderKPIs(kpis) {
    const tiles = KPI_ORDER.map((key) => {
      const k = kpis[key];
      if (k.status === "not_supported") return { status: "not_supported", label: k.label, reason: k.reason };
      return { label: k.label, value: formatKpiValue(key, k), context: k.context };
    });
    UI.renderKPIs("overview-kpis", tiles);
  }

  function renderPipeline(stages) {
    document.getElementById("decision-pipeline").innerHTML = stages.map((s, i) => `
      <div style="display:flex; align-items:center; gap:10px; padding:9px 0; ${i < stages.length - 1 ? "border-bottom:1px solid var(--gridline);" : ""}">
        <span class="model-status-badge status-${s.status === "built" ? "validated" : "planned"}">${s.stage}</span>
        <span style="font-size:12px; color:var(--text-muted);">${s.note}</span>
      </div>
    `).join("");
  }

  const FINDING_LABELS = {
    demand_forecast_improvement: "Demand Forecast",
    prep_policy_implication: "Prep Policy",
    inventory_reorder_implication: "Inventory &amp; Reorder",
    procurement_implication: "Procurement",
  };

  function renderDecisionSummary(findings) {
    document.getElementById("decision-summary").innerHTML = findings.map((f) => {
      const label = FINDING_LABELS[f.topic] || f.topic;
      if (f.status === "not_supported") {
        return `<div class="not-supported-note" style="margin-bottom:8px;"><strong>${label}:</strong> ${f.reason}</div>`;
      }
      return `<div class="recommendation-callout" style="margin-top:0; margin-bottom:8px;"><strong>${label}:</strong> ${f.text}</div>`;
    }).join("");
  }

  async function loadOverview() {
    const b = await Api.getJSON("/api/overview");
    renderKPIs(b.kpis);
    renderPipeline(b.decision_pipeline.stages);
    renderDecisionSummary(b.decision_summary.findings);
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 0 || loaded) return;
    loaded = true;
    loadOverview().catch((err) => console.error("Slide 1 (Overview) failed to load", err));
  });
})();
