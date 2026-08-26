(function () {
  const TIER_LABELS = { observed: "Observed", derived: "Derived", assumption: "Assumption", unsupported: "Unsupported" };

  function renderTaxonomyLegend(taxonomy) {
    document.getElementById("taxonomy-legend").innerHTML = Object.entries(taxonomy).map(([tier, desc]) => `
      <div class="taxonomy-legend-item" title="${desc}">
        <span class="tag-${tier}">${TIER_LABELS[tier]}</span>
      </div>
    `).join("");
  }

  function renderSourceCards(sources) {
    document.getElementById("data-source-cards").innerHTML = sources.map((s) => `
      <div class="source-card">
        <div class="name">${s.name}</div>
        <div class="meta">${UI.fmtNum(s.rows)} rows${s.date_range ? ` · ${s.date_range.start} to ${s.date_range.end}` : ""}</div>
        <div class="desc">${s.description}</div>
      </div>
    `).join("");
  }

  function defectDetail(defect) {
    if (defect.defect === "A") {
      return `
        <code>${defect.correct_formula}</code> matches ${UI.fmtPct(defect.match_pct)} of
        ${UI.fmtNum(defect.total_rows)} rows. The naive lump-sum formula
        (<code>${defect.naive_formula}</code>) mismatches ${UI.fmtPct(defect.naive_formula_mismatch_pct)} of rows.
      `;
    }
    if (defect.defect === "B") {
      return `
        Mean ${defect.mean}/hr, std ${defect.std}, CV ${UI.fmtPct(defect.cv_pct)}. Outside plausible trading hours:
        ${defect.windows_tested.map((w) => `${w.label} &rarr; ${UI.fmtPct(w.pct_outside)}`).join(" &middot; ")}.
      `;
    }
    if (defect.defect === "C") {
      return `
        POS daily mean ${defect.pos_daily_mean_qty}/item &middot; Inventory-log daily mean ${defect.inventory_daily_mean_qty}/item &middot;
        Correlation ${defect.correlation} (n=${UI.fmtNum(defect.n_matched_rows)} matched rows).
      `;
    }
    if (defect.defect === "D") {
      return `
        ${UI.fmtNum(defect.total_rows)} rows, ${defect.unique_route_ids} unique Route_IDs,
        ${defect.duplicate_route_ids_found} reused across ${defect.affected_rows} affected rows.
      `;
    }
    return "";
  }

  function defectScopeNote(defect) {
    return defect.still_valid_for || defect.existing_treatment || "";
  }

  function renderDefectCard(defect) {
    const scopeNote = defectScopeNote(defect);
    return `
      <div class="defect-card">
        <div class="head">
          <div class="defect-title">Defect ${defect.defect} &mdash; ${defect.title}</div>
          <span class="tag-${defect.tier}">${TIER_LABELS[defect.tier]}</span>
        </div>
        <div class="verdict">${defect.verdict}</div>
        <div class="drawer analyst-only" data-drawer>
          <button type="button" class="drawer-trigger">Methodology <span class="chevron">&#9662;</span></button>
          <div class="drawer-panel"><div class="drawer-panel-inner">${defectDetail(defect)}</div></div>
        </div>
        ${scopeNote ? `<div class="note" style="margin-top:8px;">${scopeNote}</div>` : ""}
      </div>
    `;
  }

  async function loadDataQuality() {
    const b = await Api.getJSON("/api/data-quality");
    renderTaxonomyLegend(b.taxonomy);
    renderSourceCards(b.data_sources.sources);
    document.getElementById("defect-cards").innerHTML = b.defects.map(renderDefectCard).join("");
    Drawer.wire();
  }

  let loaded = false;
  Slides.onActivate((index) => {
    if (index !== 1 || loaded) return;
    loaded = true;
    loadDataQuality().catch((err) => console.error("Slide 2 (Data Quality) failed to load", err));
  });
})();
