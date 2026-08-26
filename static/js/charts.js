(function () {
  const css = getComputedStyle(document.documentElement);
  const token = (name) => css.getPropertyValue(name).trim();

  const SERIES = [1, 2, 3, 4, 5, 6].map((n) => token(`--series-${n}`));
  const TEXT_MUTED = token("--text-muted");
  const GRIDLINE = token("--gridline");

  // Fixed categorical order — same entity always gets the same color across every chart.
  const CATEGORY_COLORS = {
    "Pizza": SERIES[0],
    "Mocktails": SERIES[1],
    "Cold Beverages": SERIES[2],
    "Starter": SERIES[3],
    "Snacks": SERIES[4],
  };

  const SUPPLIER_COLORS = {
    "City Central Market": SERIES[0],
    "Metro Wholesale": SERIES[1],
    "Local Farm Co.": SERIES[2],
  };

  Chart.defaults.color = TEXT_MUTED;
  Chart.defaults.borderColor = GRIDLINE;
  Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.tooltip.backgroundColor = "#1a1a18";
  Chart.defaults.plugins.tooltip.titleColor = "#ffffff";
  Chart.defaults.plugins.tooltip.bodyColor = "#e5e3dd";
  Chart.defaults.plugins.tooltip.borderColor = GRIDLINE;
  Chart.defaults.plugins.tooltip.borderWidth = 0;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;

  function baseOptions(overrides) {
    return Object.assign(
      {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: TEXT_MUTED } },
          y: { grid: { color: GRIDLINE }, ticks: { color: TEXT_MUTED }, beginAtZero: true },
        },
      },
      overrides || {}
    );
  }

  const registry = new Map();

  function upsertChart(canvasId, config) {
    const existing = registry.get(canvasId);
    if (existing) {
      existing.data = config.data;
      existing.options = config.options;
      existing.config.type = config.type;
      existing.update();
      return existing;
    }
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const chart = new Chart(ctx, config);
    registry.set(canvasId, chart);
    return chart;
  }

  function pad(arr, before, after) {
    return [...new Array(before).fill(null), ...arr, ...new Array(after).fill(null)];
  }

  window.DashCharts = {
    SERIES,
    CATEGORY_COLORS,
    SUPPLIER_COLORS,
    baseOptions,
    upsertChart,

    lineTrend(canvasId, labels, series) {
      return upsertChart(canvasId, {
        type: "line",
        data: {
          labels,
          datasets: series.map((s, i) => ({
            label: s.label,
            data: s.data,
            borderColor: SERIES[i],
            backgroundColor: SERIES[i],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.25,
          })),
        },
        options: baseOptions({
          plugins: { legend: { display: series.length > 1, position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10 } } },
        }),
      });
    },

    bar(canvasId, labels, data, colors) {
      return upsertChart(canvasId, {
        type: "bar",
        data: {
          labels,
          datasets: [{ data, backgroundColor: colors || SERIES[0], borderRadius: 4, maxBarThickness: 40 }],
        },
        options: baseOptions(),
      });
    },

    // Stacked bar - e.g. LP allocation qty per supplier, stacked by category.
    stackedBar(canvasId, labels, series) {
      return upsertChart(canvasId, {
        type: "bar",
        data: {
          labels,
          datasets: series.map((s, i) => ({ label: s.label, data: s.data, backgroundColor: SERIES[i], borderRadius: 3, maxBarThickness: 60 })),
        },
        options: baseOptions({
          scales: {
            x: { stacked: true, grid: { display: false }, ticks: { color: TEXT_MUTED } },
            y: { stacked: true, grid: { color: GRIDLINE }, ticks: { color: TEXT_MUTED }, beginAtZero: true },
          },
          plugins: {
            legend: { display: true, position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10 } },
          },
        }),
      });
    },

    // Grouped bar for model/policy comparisons (e.g. baseline vs ARIMAX RMSE per fold).
    groupedBar(canvasId, labels, series) {
      return upsertChart(canvasId, {
        type: "bar",
        data: {
          labels,
          datasets: series.map((s, i) => ({ label: s.label, data: s.data, backgroundColor: SERIES[i], borderRadius: 4, maxBarThickness: 34 })),
        },
        options: baseOptions({
          plugins: { legend: { display: true, position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10 } } },
        }),
      });
    },

    // History (actual) + in-sample fitted + future point/CI band, on one
    // continuous timeline. Not zero-based — the point is showing the band
    // clearly, not anchoring a magnitude comparison.
    forecastBand(canvasId, { historyLabels, historyValues, fittedValues, futureLabels, futureMedian, futureLower, futureUpper }) {
      const labels = [...historyLabels, ...futureLabels];
      const nHist = historyLabels.length;
      const nFuture = futureLabels.length;
      const seriesColor = SERIES[0];

      return upsertChart(canvasId, {
        type: "line",
        data: {
          labels,
          datasets: [
            { label: "Actual", data: pad(historyValues, 0, nFuture), borderColor: seriesColor, backgroundColor: seriesColor, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.15 },
            { label: "Fitted", data: pad(fittedValues, 0, nFuture), borderColor: SERIES[1], backgroundColor: SERIES[1], borderWidth: 1.5, borderDash: [3, 3], pointRadius: 0, fill: false, tension: 0.15 },
            { label: "Lower", data: pad(futureLower, nHist, 0), borderColor: "transparent", backgroundColor: "transparent", pointRadius: 0, fill: false },
            { label: "Upper", data: pad(futureUpper, nHist, 0), borderColor: "transparent", backgroundColor: seriesColor + "26", pointRadius: 0, fill: "-1" },
            { label: "Forecast", data: pad(futureMedian, nHist, 0), borderColor: seriesColor, backgroundColor: seriesColor, borderWidth: 2, borderDash: [5, 3], pointRadius: 0, fill: false, tension: 0.15 },
          ],
        },
        options: baseOptions({
          scales: {
            x: { grid: { display: false }, ticks: { color: TEXT_MUTED, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
            y: { grid: { color: GRIDLINE }, ticks: { color: TEXT_MUTED }, beginAtZero: false },
          },
          plugins: {
            legend: {
              display: true, position: "top", align: "end",
              labels: { boxWidth: 10, boxHeight: 10, filter: (item) => !["Lower", "Upper"].includes(item.text) },
            },
          },
        }),
      });
    },
  };
})();
