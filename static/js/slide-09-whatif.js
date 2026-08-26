(function () {
  async function runPrepScenario() {
    const btn = document.getElementById("wf-prep-run");
    btn.disabled = true;
    try {
      const item = document.getElementById("wf-prep-item").value;
      const result = await Api.postJSON("/api/simulator/prep", {
        item,
        demand_growth_pct: Number(document.getElementById("wf-prep-growth").value || 0),
        demand_vol_multiplier: Number(document.getElementById("wf-prep-vol").value || 1),
      });
      if (result.error) {
        document.getElementById("wf-prep-note").textContent = result.error;
        return;
      }
      UI.renderMiniStats("wf-prep-results", [
        { label: "Total Cost (p50)", value: UI.fmtINR(result.total_cost_inr.p50), sub: `p10 ${UI.fmtINR(result.total_cost_inr.p10)} · p90 ${UI.fmtINR(result.total_cost_inr.p90)}` },
        { label: "Fill Rate (p50)", value: UI.fmtPct(result.fill_rate_pct.p50) },
        { label: "Waste Units (p50)", value: UI.fmtNum(result.waste_units.p50) },
        { label: "Stockout Day Rate (p50)", value: UI.fmtPct(result.stockout_day_rate_pct.p50) },
      ]);
      DashCharts.bar("chart-wf-prep", result.cost_histogram_edges.slice(0, -1).map((v) => UI.fmtNum(v)), result.cost_histogram);
      document.getElementById("wf-prep-note").textContent = result.note;
    } catch (err) {
      document.getElementById("wf-prep-note").textContent = `Simulation failed: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  async function runSupplierScenario() {
    const btn = document.getElementById("wf-sup-run");
    btn.disabled = true;
    try {
      const leadTime = document.getElementById("wf-sup-leadtime").value;
      const result = await Api.postJSON("/api/simulator/supplier", {
        category: document.getElementById("wf-sup-category").value,
        annual_demand: Number(document.getElementById("wf-sup-demand").value || 1000),
        holding_cost_per_unit_per_year: Number(document.getElementById("wf-sup-holding").value || 10),
        lead_time_override: leadTime ? Number(leadTime) : null,
      });
      if (result.error) {
        document.getElementById("wf-sup-note").textContent = result.error;
        return;
      }
      UI.renderMiniStats("wf-sup-results", [
        { label: "Reorder Point", value: UI.fmtNum(result.inputs.reorder_point), sub: `order qty ${UI.fmtNum(result.inputs.order_qty)}` },
        { label: "Stockout Days (p50)", value: UI.fmtPct(result.stockout_days_pct_of_horizon.p50), sub: "% of simulated horizon" },
        { label: "Total Cost (p50)", value: UI.fmtINR(result.total_cost_inr.p50), sub: `holding ${UI.fmtINR(result.holding_cost_inr.p50)} + ordering ${UI.fmtINR(result.ordering_cost_inr.p50)}` },
        { label: "Orders Placed (p50)", value: UI.fmtNum(result.orders_placed.p50), sub: `over ${result.inputs.n_days} days` },
      ]);
      document.getElementById("wf-sup-note").textContent = result.note;
    } catch (err) {
      document.getElementById("wf-sup-note").textContent = `Simulation failed: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  let loaded = false;
  async function loadWhatIf() {
    if (loaded) return;
    loaded = true;

    const [nvBundle, categories] = await Promise.all([
      Api.getJSON("/api/prep/newsvendor"),
      Api.getJSON("/api/supply/categories"),
    ]);

    const itemSelect = document.getElementById("wf-prep-item");
    const items = Object.keys(nvBundle.items);
    itemSelect.innerHTML = items.map((i) => `<option value="${i}">${i}</option>`).join("");

    const catSelect = document.getElementById("wf-sup-category");
    catSelect.innerHTML = categories.map((c) => `<option value="${c}">${c}</option>`).join("");

    document.getElementById("wf-prep-run").addEventListener("click", runPrepScenario);
    document.getElementById("wf-sup-run").addEventListener("click", runSupplierScenario);

    await runPrepScenario();
    await runSupplierScenario();
  }

  Slides.onActivate((index) => {
    if (index === 8) loadWhatIf().catch((err) => console.error("Slide 9 (What-if Simulator) failed to load", err));
  });
})();
