(function () {
  function renderInsight(shortfallPct, spoilageCost) {
    document.getElementById("inventory-insight").innerHTML = `
      <span class="lead-label">Insight</span>
      Spoilage costs ${UI.fmtINR(spoilageCost)} a year, and the kitchen's own judgment-based prep plan
      still runs short on ${UI.fmtPct(shortfallPct)} of item-days - a judgment plan, not a costed one.
      Safety stock and a reorder point below put a number on the buffer that plan actually needs.
    `;
  }

  function renderKPIs(ssBundle, spoilageCost, shortfallPct) {
    const range = ssBundle.decomposed_safety_stock_range_units;
    const variance = ssBundle.between_supplier_variance;
    UI.renderKPIs("inventory-kpis", [
      { label: "Spoilage Cost", value: UI.fmtINR(spoilageCost), context: "2024 inventory log, all items" },
      { label: "Prep Shortfall Days", value: UI.fmtPct(shortfallPct), context: "actual demand exceeded planned prep" },
      { label: "Decomposed Safety Stock Range", value: `${range.min}–${range.max} units`, context: "95% service level, by supplier serving each item" },
      { label: "Lead-Time Variance: Supplier Share", value: UI.fmtPct(variance.between_supplier_variance_share_pct), context: "why pooling lead time across suppliers is wrong" },
    ]);
  }

  function renderChart(ssBundle) {
    const items = Object.keys(ssBundle.items);
    const suppliers = ["City Central Market", "Local Farm Co.", "Metro Wholesale"];
    const series = suppliers.map((s) => ({
      label: s,
      data: items.map((item) => {
        const row = ssBundle.items[item].decomposed_by_supplier.find((r) => r.supplier === s);
        return row ? row.safety_stock_units : null;
      }),
    }));
    series.push({
      label: "Pooled (wrong)",
      data: items.map((item) => ssBundle.items[item].pooled_wrong_comparator.safety_stock_units),
    });
    DashCharts.groupedBar("chart-safety-stock", items.map((i) => i.split(" ")[0]), series);
  }

  function renderTable(ssBundle) {
    // Recommended supplier only, one row per item - the full per-supplier
    // breakdown (all 18 item x supplier combinations) lives in Technical
    // Details instead, so the at-a-glance table stays scannable.
    const rows = Object.entries(ssBundle.items).map(([item, v]) => {
      const rec = v.decomposed_by_supplier.find((r) => r.supplier === v.recommended_supplier);
      return { item, category: v.assumed_ingredient_category, ...rec };
    });
    UI.renderTable("table-safety-stock", rows, (r) => `
      <tr>
        <td>${r.item}</td>
        <td>${r.category}</td>
        <td>${r.supplier}</td>
        <td>${r.safety_stock_units}</td>
        <td>${r.reorder_point_units}</td>
      </tr>
    `);
  }

  function fullBreakdownHtml(ssBundle) {
    const rows = [];
    Object.entries(ssBundle.items).forEach(([item, v]) => {
      v.decomposed_by_supplier.forEach((r) => {
        rows.push(`<tr><td>${item}${v.recommended_supplier === r.supplier ? " ★" : ""}</td><td>${r.supplier}</td><td>${r.safety_stock_units}</td><td>${r.reorder_point_units}</td></tr>`);
      });
    });
    return `
      <div class="table-wrap" style="max-height:260px;">
        <table><thead><tr><th>Item</th><th>Supplier</th><th>Safety Stock</th><th>ROP</th></tr></thead>
        <tbody>${rows.join("")}</tbody></table>
      </div>
    `;
  }

  function renderDecision() {
    document.getElementById("inventory-decision").textContent =
      "Recommended supplier per item (★ in the table) minimizes safety stock given that supplier's " +
      "own lead-time consistency. Adopt item-specific safety stock and reorder points rather than one pooled figure.";
  }

  function renderDrawer(ssBundle) {
    const v = ssBundle.between_supplier_variance;
    document.getElementById("safety-stock-drawer").innerHTML = `
      <div class="formula">SS = z × √(LT_mean × σ_demand² + demand_mean² × σ_LT²); ROP = demand_mean × LT_mean + SS</div>
      <p>${ssBundle.assumption_note}</p>
      <p><strong>Between-supplier lead-time variance:</strong> F=${v.f_stat}, ${UI.fmtPValue(v.p_value)},
      ${UI.fmtPct(v.between_supplier_variance_share_pct)} of variance explained by supplier identity.
      ${v.interpretation}</p>
      <p><strong>Full per-supplier breakdown</strong> (★ = recommended):</p>
      ${fullBreakdownHtml(ssBundle)}
    `;
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 4 || loaded) return;
    loaded = true;
    Promise.all([Api.getJSON("/api/inventory/safety-stock"), Api.getJSON("/api/overview")])
      .then(([ss, overview]) => {
        const shortfallPct = overview.kpis.shortage_days.value;
        const spoilageCost = overview.kpis.spoilage_cost.value;
        renderInsight(shortfallPct, spoilageCost);
        renderKPIs(ss, spoilageCost, shortfallPct);
        renderChart(ss);
        renderTable(ss);
        renderDecision();
        renderDrawer(ss);
        Drawer.wire();
      })
      .catch((err) => console.error("Slide 5 (Inventory) failed to load", err));
  });
})();
