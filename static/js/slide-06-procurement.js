(function () {
  let topsisData = null;

  function renderInsight(lp) {
    if ("error" in lp) {
      document.getElementById("procurement-insight").innerHTML = `<span class="lead-label">Insight</span>${lp.error}`;
      return;
    }
    const binding = lp.binding_suppliers.length ? lp.binding_suppliers.join(" and ") : "no supplier";
    const isPlural = lp.binding_suppliers.length > 1;
    document.getElementById("procurement-insight").innerHTML = `
      <span class="lead-label">Insight</span>
      Under the capacity figures above (an assumption - not in the source data), the binding
      constraint on least-cost allocation is <strong>${binding}</strong>'s ${isPlural ? "capacities" : "capacity"},
      not any supplier's lead time. Raise ${isPlural ? "those capacities" : "that capacity"} and cost
      falls; lead time doesn't change the picture at all.
    `;
  }

  function renderKPIs(lp) {
    if ("error" in lp) {
      UI.renderKPIs("procurement-kpis", [{ status: "not_supported", label: "LP Allocation", reason: lp.error }]);
      return;
    }
    const binding = lp.binding_suppliers[0];
    const shadow = binding ? lp.shadow_prices[binding].shadow_price_inr_per_unit : 0;
    UI.renderKPIs("procurement-kpis", [
      { label: "Weekly Cost (LP Optimum)", value: UI.fmtINR(lp.total_weekly_cost_inr), context: `${lp.total_weekly_qty} units/week across 4 categories` },
      { label: "Binding Supplier(s)", value: lp.binding_suppliers.length ? lp.binding_suppliers.join(", ") : "none", context: "assumed capacity, not lead time, is the constraint" },
      { label: "Shadow Price", value: binding ? `${UI.fmtINR(shadow)}/unit` : "—", context: binding ? `at ${binding}'s capacity ceiling` : "no supplier is capacity-bound" },
      { label: "Suppliers With Slack", value: `${3 - lp.binding_suppliers.length} / 3`, context: "capacity not fully used" },
    ]);
  }

  function renderAllocationChart(lp) {
    if ("error" in lp) return;
    const suppliers = Object.keys(lp.capacity_used);
    const categories = [...new Set(lp.allocation.map((a) => a.category))];
    const series = categories.map((cat) => ({
      label: cat,
      data: suppliers.map((s) => {
        const row = lp.allocation.find((a) => a.supplier === s && a.category === cat);
        return row ? row.qty : 0;
      }),
    }));
    DashCharts.stackedBar("chart-allocation", suppliers, series);
  }

  function renderDecision(lp) {
    if ("error" in lp) {
      document.getElementById("procurement-decision").textContent = "Raise a supplier's capacity above to see a feasible allocation.";
      return;
    }
    document.getElementById("procurement-decision").textContent = lp.note;
  }

  function renderTopsisTable(category) {
    const cat = topsisData.by_category[category];
    const scenarios = Object.keys(cat.scenario_rankings);
    UI.renderTable("table-topsis", scenarios, (scenario) => {
      const ranked = cat.scenario_rankings[scenario];
      return `<tr><td>${scenario.replace(/_/g, " ")}</td>${ranked.slice(0, 2).map((r) => `<td>${r.supplier} (${r.closeness})</td>`).join("")}</tr>`;
    });
    document.getElementById("topsis-note").innerHTML = `
      <span class="label">Ranking stability</span>
      ${cat.rankings_flip_with_weighting
        ? "The top-ranked supplier changes depending on how cost is weighted against lead time - no supplier is 'the best' independent of that weighting."
        : "The top-ranked supplier is stable across the tested weighting scenarios for this category."}
    `;
  }

  function renderProcurementDrawer(lp) {
    const rows = "error" in lp ? [] : lp.allocation;
    document.getElementById("procurement-drawer").innerHTML = `
      <p><strong>LP formulation:</strong> minimize Σ(unit_cost[s,c] × qty[s,c]) subject to
      Σ_s qty[s,c] ≥ required_qty[c] for each category c, and Σ_c qty[s,c] ≤ capacity[s] for each
      supplier s. Solved via scipy.optimize.linprog (method="highs"); the shadow price is the dual
      value of a binding capacity constraint.</p>
      <p><strong>Required weekly qty by category</strong> (derived from real POS demand via each item's
      assumed ingredient category): ${"error" in lp ? "" : Object.entries(lp.required_weekly_qty).map(([c, q]) => `${c}: ${q}`).join(" · ")}</p>
      <p><strong>TOPSIS criteria:</strong> unit cost, lead time, MOQ - all "lower is better" - normalized,
      weighted per scenario, ranked by closeness to the ideal solution.</p>
    `;
  }

  async function runLP() {
    const btn = document.getElementById("procurement-run");
    btn.disabled = true;
    try {
      const capacity = {};
      const cityVal = document.getElementById("cap-city").value;
      const localVal = document.getElementById("cap-local").value;
      const metroVal = document.getElementById("cap-metro").value;
      if (cityVal) capacity["City Central Market"] = Number(cityVal);
      if (localVal) capacity["Local Farm Co."] = Number(localVal);
      if (metroVal) capacity["Metro Wholesale"] = Number(metroVal);

      const body = await Api.postJSON("/api/procurement", { capacity });
      const lp = body.lp_allocation;
      renderInsight(lp);
      renderKPIs(lp);
      renderAllocationChart(lp);
      renderDecision(lp);
      renderProcurementDrawer(lp);
    } catch (err) {
      console.error("Procurement recalculation failed", err);
    } finally {
      btn.disabled = false;
    }
  }

  let loaded = false;
  async function loadProcurement() {
    if (loaded) return;
    loaded = true;

    const bundle = await Api.getJSON("/api/procurement");
    const lp = bundle.lp_allocation;
    document.getElementById("cap-city").value = lp.capacity_used["City Central Market"];
    document.getElementById("cap-local").value = lp.capacity_used["Local Farm Co."];
    document.getElementById("cap-metro").value = lp.capacity_used["Metro Wholesale"];

    renderInsight(lp);
    renderKPIs(lp);
    renderAllocationChart(lp);
    renderDecision(lp);
    renderProcurementDrawer(lp);

    topsisData = bundle.topsis_sensitivity;
    const categories = Object.keys(topsisData.by_category);
    const select = document.getElementById("topsis-category-select");
    select.innerHTML = categories.map((c) => `<option value="${c}">${c}</option>`).join("");
    select.onchange = () => renderTopsisTable(select.value);
    renderTopsisTable(categories[0]);

    document.getElementById("procurement-run").addEventListener("click", runLP);
    Drawer.wire();
  }

  Slides.onActivate((index) => {
    if (index === 5) loadProcurement().catch((err) => console.error("Slide 6 (Procurement) failed to load", err));
  });
})();
