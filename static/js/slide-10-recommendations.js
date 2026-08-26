(function () {
  function buildActions(agg, ss, procurement, eda, dq) {
    const lp = procurement.lp_allocation;
    const binding = !("error" in lp) && lp.binding_suppliers.length ? lp.binding_suppliers[0] : null;
    const shadow = binding ? lp.shadow_prices[binding].shadow_price_inr_per_unit : null;
    const range = ss.decomposed_safety_stock_range_units;
    const topRule = eda.menu_affinity.top_rules[0];
    const defectB = dq.defects.find((d) => d.defect === "B");
    const defectD = dq.defects.find((d) => d.defect === "D");

    return [
      {
        action: "Keep judgment-based daily prep; do not standardize to a fixed quantity",
        owner: "Kitchen lead",
        horizon: "Immediate",
        evidence: agg.status === "supported" ? `Prep &amp; Newsvendor: a single fixed quantity costs ${UI.fmtPct(agg.static_worse_than_dynamic_pct)} more than tailoring per item` : "Not supported",
      },
      {
        action: "Adopt item-specific safety stock and reorder points",
        owner: "Purchase desk",
        horizon: "2 weeks",
        evidence: `Inventory: ${range.min}–${range.max} units, decomposed by supplier (95% service level)`,
      },
      {
        action: binding ? `Negotiate additional weekly capacity with ${binding}` : "Monitor supplier capacity constraints",
        owner: "Owner",
        horizon: "1 month",
        evidence: binding ? `Procurement: shadow price ${UI.fmtINR(shadow)}/unit on ${binding}'s assumed capacity` : "No supplier capacity is currently binding under the assumed defaults",
      },
      {
        action: topRule ? `Bundle ${topRule.consequent} with ${topRule.antecedent}; stop discounting items with no volume response` : "Bundle high-affinity items; stop discounting items with no volume response",
        owner: "Owner",
        horizon: "1 month",
        evidence: topRule ? `Menu affinity: lift ${topRule.lift}× &middot; Pricing: no volume response to discount depth` : "Pricing: no volume response to discount depth",
      },
      {
        action: "Repair the POS timestamp and the delivery-cost/Route_ID fields at source",
        owner: "App vendor",
        horizon: "1 quarter",
        evidence: `Data Quality: Defects B (${UI.fmtPct(defectB.cv_pct)} CV, near-uniform hours) and D (${defectD.duplicate_route_ids_found} duplicate rows)`,
      },
    ];
  }

  function renderTable(actions) {
    UI.renderTable("table-recommendations", actions, (a) => `
      <tr><td>${a.action}</td><td>${a.owner}</td><td>${a.horizon}</td><td>${a.evidence}</td></tr>
    `);
  }

  function renderMenuAffinity(eda) {
    const rules = eda.menu_affinity.top_rules;
    document.getElementById("recs-menu-affinity").innerHTML = rules.length
      ? rules.map((r) => `<div class="recommendation-callout" style="margin-top:8px;">${r.recommendation}</div>`).join("")
      : `<div class="not-supported-note">${eda.menu_affinity.note || "No rules available."}</div>`;
  }

  function renderLimitations() {
    const items = [
      "Six items analyzed, not the full menu.",
      "No time-of-day inference is possible - the POS timestamp is synthetic (Defect B).",
      "The inventory log's demand figures are unusable as a demand-level signal - only POS is (Defect C).",
      "TOPSIS supplier rankings are weight-sensitive; no supplier is 'the best' independent of weighting.",
      "Supplier capacity for the Procurement LP is an analyst assumption - it is not in the source data.",
      "The ARIMAX summer uplift rests on two observed annual cycles (2023 and 2024).",
    ];
    document.getElementById("recs-limitations").innerHTML = `<ul style="margin:0; padding-left:18px; font-size:13px; line-height:1.7; color:var(--text-secondary);">${items.map((i) => `<li>${i}</li>`).join("")}</ul>`;
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 9 || loaded) return;
    loaded = true;
    Promise.all([
      Api.getJSON("/api/prep/aggregate-comparison"),
      Api.getJSON("/api/inventory/safety-stock"),
      Api.getJSON("/api/procurement"),
      Api.getJSON("/api/eda"),
      Api.getJSON("/api/data-quality"),
    ])
      .then(([agg, ss, procurement, eda, dq]) => {
        renderTable(buildActions(agg, ss, procurement, eda, dq));
        renderMenuAffinity(eda);
        renderLimitations();
      })
      .catch((err) => console.error("Slide 10 (Recommendations) failed to load", err));
  });
})();
