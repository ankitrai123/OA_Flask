(function () {
  function fmtINR(n) {
    return "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  }

  function fmtPct(n, digits = 1) {
    return n === null || n === undefined ? "—" : `${Number(n).toFixed(digits)}%`;
  }

  function fmtNum(n, digits = 0) {
    return Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: digits });
  }

  function fmtPValue(p) {
    if (p === null || p === undefined) return "—";
    return p < 0.0001 ? "p < 0.0001" : `p = ${Number(p).toFixed(4)}`;
  }

  // Every tile needs value+label+context (or a not_supported status) - a
  // bare number is a spec violation, so a missing context warns loudly in
  // dev rather than shipping quietly.
  function renderKPIs(containerId, tiles) {
    const el = document.getElementById(containerId);
    if (!el) return;

    el.innerHTML = tiles.map((t) => {
      if (t.status === "not_supported") {
        return `
          <div class="kpi-tile not-supported">
            <div class="label">${t.label}</div>
            <div class="value">—</div>
            <div class="context">${t.reason || "Not supported by available data."}</div>
          </div>
        `;
      }
      if (!t.context) console.warn(`KPI tile "${t.label}" is missing context - never ship a bare number.`);
      return `
        <div class="kpi-tile">
          <div class="label">${t.label}</div>
          <div class="value">${t.value}</div>
          <div class="context">${t.context || ""}</div>
        </div>
      `;
    }).join("");
  }

  function renderTable(tableId, rows, rowFn) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!tbody) return;
    tbody.innerHTML = rows.map(rowFn).join("");
  }

  function renderMiniStats(containerId, stats) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = stats.map((s) => `
      <div class="mini-stat">
        <div class="label">${s.label}</div>
        <div class="value">${s.value}</div>
        ${s.sub ? `<div class="sub">${s.sub}</div>` : ""}
      </div>
    `).join("");
  }

  function renderLegend(containerId, colorMap) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = Object.entries(colorMap).map(([label, color]) => `
      <div class="legend-item"><span class="legend-swatch" style="background:${color}"></span>${label}</div>
    `).join("");
  }

  window.UI = { fmtINR, fmtPct, fmtNum, fmtPValue, renderKPIs, renderTable, renderMiniStats, renderLegend };
})();
