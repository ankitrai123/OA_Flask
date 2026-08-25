(function () {
  const css = getComputedStyle(document.documentElement);
  const token = (name) => css.getPropertyValue(name).trim();

  const SERIES = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => token(`--series-${n}`));
  const TEXT_SECONDARY = token("--text-secondary");
  const TEXT_MUTED = token("--text-muted");
  const GRIDLINE = token("--gridline");
  const SURFACE_1 = token("--surface-1");

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
  Chart.defaults.plugins.tooltip.backgroundColor = SURFACE_1;
  Chart.defaults.plugins.tooltip.titleColor = "#ffffff";
  Chart.defaults.plugins.tooltip.bodyColor = TEXT_SECONDARY;
  Chart.defaults.plugins.tooltip.borderColor = GRIDLINE;
  Chart.defaults.plugins.tooltip.borderWidth = 1;
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
  };
})();
