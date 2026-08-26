(function () {
  let currentItem = null;

  function renderInputs(inputs) {
    UI.renderMiniStats("nv-inputs-kpis", [
      { label: "Unit Cost (Co)", value: UI.fmtINR(inputs.unit_cost_inr) },
      { label: "Contribution Margin (Cu)", value: UI.fmtINR(inputs.contribution_margin_inr) },
      { label: "Critical Ratio", value: inputs.critical_ratio, sub: "Cu / (Cu + Co)" },
      { label: "Avg Realized Price", value: UI.fmtINR(inputs.avg_realized_price_inr) },
    ]);
  }

  function renderPolicyComparison(compare) {
    const inv = compare.inventory_log_policies;
    const dyn = compare.dynamic_newsvendor_pos_scale;
    let html = "";

    if (inv.status === "not_supported") {
      html += `<div class="not-supported-note">${inv.reason}</div>`;
    } else {
      html += `
        <div style="font-size:12.5px; font-weight:600; margin-bottom:6px;">Inventory-log scale (kitchen's own prep record)</div>
        <div class="result-row">
          <div class="mini-stat"><div class="label">Current Judgment</div><div class="value">${inv.current_judgment.avg_qty}</div><div class="sub">${UI.fmtINR(inv.current_judgment.annual_cost_inr)}/yr</div></div>
          <div class="mini-stat"><div class="label">Static Newsvendor</div><div class="value">${inv.static_newsvendor.avg_qty}</div><div class="sub">${UI.fmtINR(inv.static_newsvendor.annual_cost_inr)}/yr</div></div>
        </div>
        <div class="note">Cost avoided vs. current judgment: ${UI.fmtINR(inv.static_newsvendor.cost_avoided_vs_current_judgment_inr)}/yr (${UI.fmtPct(inv.static_newsvendor.cost_avoided_vs_current_judgment_pct)})</div>
        <div class="note analyst-only">${inv.scope_note}</div>
      `;
    }

    if (dyn.status === "not_supported") {
      html += `<div class="not-supported-note" style="margin-top:14px;">${dyn.reason}</div>`;
    } else {
      html += `
        <div style="font-size:12.5px; font-weight:600; margin:14px 0 6px;">POS scale (ARIMAX-driven)</div>
        <div class="result-row">
          <div class="mini-stat"><div class="label">Naive Baseline</div><div class="value">${dyn.naive_baseline_qty}</div><div class="sub">${UI.fmtINR(dyn.annual_cost_at_naive_baseline_inr)}/yr</div></div>
          <div class="mini-stat"><div class="label">Dynamic Newsvendor</div><div class="value">${dyn.recommended_qty}</div><div class="sub">${UI.fmtINR(dyn.annual_cost_at_recommended_inr)}/yr</div></div>
        </div>
        <div class="note">Cost avoided vs. naive baseline: ${UI.fmtINR(dyn.cost_avoided_vs_naive_baseline_inr)}/yr (${UI.fmtPct(dyn.cost_avoided_vs_naive_baseline_pct)})</div>
        <div class="note analyst-only">${dyn.scope_note}</div>
      `;
    }

    html += `<div class="why-method-callout analyst-only" style="margin-top:14px;"><span class="label">Framing</span>${compare.framing_note}</div>`;
    document.getElementById("nv-policy-comparison").innerHTML = html;
    Drawer.wire();
  }

  async function loadItem(item) {
    currentItem = item;
    const [nvBundle, compareBundle] = await Promise.all([
      Api.getJSON("/api/prep/newsvendor"),
      Api.getJSON("/api/prep/compare"),
    ]);
    renderInputs(nvBundle.items[item]);
    renderPolicyComparison(compareBundle.items[item]);

    document.getElementById("nv-whatif-results").innerHTML = "";
    document.getElementById("nv-whatif-note").textContent = "";
    ["nv-demand-qty", "nv-spoilage-cost", "nv-stockout-cost", "nv-service-level"].forEach((id) => {
      document.getElementById(id).value = "";
    });
  }

  async function runWhatIf() {
    const btn = document.getElementById("nv-run");
    btn.disabled = true;
    try {
      const demandQty = document.getElementById("nv-demand-qty").value;
      const spoilageCost = document.getElementById("nv-spoilage-cost").value;
      const stockoutCost = document.getElementById("nv-stockout-cost").value;
      const serviceLevel = document.getElementById("nv-service-level").value;

      const result = await Api.postJSON("/api/prep/newsvendor", {
        item: currentItem,
        demand_qty: demandQty ? Number(demandQty) : null,
        spoilage_cost: spoilageCost ? Number(spoilageCost) : null,
        stockout_cost: stockoutCost ? Number(stockoutCost) : null,
        service_level: serviceLevel ? Number(serviceLevel) : null,
      });

      UI.renderMiniStats("nv-whatif-results", [
        { label: "Critical Ratio", value: result.critical_ratio },
        { label: "Recommended Qty", value: result.recommended_qty },
        { label: "Expected Total Cost", value: UI.fmtINR(result.expected_total_cost_inr) },
        { label: "Fill Rate (median)", value: UI.fmtPct(result.simulation.fill_rate_pct.p50) },
      ]);
      document.getElementById("nv-whatif-note").textContent = `Demand source: ${result.demand_source}.`;
    } catch (err) {
      document.getElementById("nv-whatif-note").textContent = `Calculation failed: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  let loaded = false;
  async function loadSlide5() {
    if (loaded) return;
    loaded = true;

    const nvBundle = await Api.getJSON("/api/prep/newsvendor");
    const items = Object.keys(nvBundle.items);

    const select = document.getElementById("nv-item-select");
    select.innerHTML = items.map((i) => `<option value="${i}">${i}</option>`).join("");
    select.onchange = () => loadItem(select.value).catch((err) => console.error("Item reload failed", err));

    document.getElementById("nv-run").addEventListener("click", runWhatIf);

    await loadItem(items[0]);
  }

  Slides.onActivate((index) => {
    if (index === 4) loadSlide5().catch((err) => console.error("Slide 5 (Newsvendor) failed to load", err));
  });
})();
