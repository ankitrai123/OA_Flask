(function () {
  const fab = document.getElementById("chat-fab");
  const panel = document.getElementById("chat-panel");
  const closeBtn = document.getElementById("chat-close");

  // Shared across both chat surfaces (the floating panel and the full-page
  // AI Analyst slide) so a conversation started in one continues in the
  // other, rather than each keeping its own disconnected history.
  let history = [];
  let chartCounter = 0;

  fab.addEventListener("click", () => {
    panel.classList.add("open");
    fab.style.display = "none";
  });
  closeBtn.addEventListener("click", () => {
    panel.classList.remove("open");
    fab.style.display = "";
  });

  function appendMessage(messagesEl, role, text) {
    const div = document.createElement("div");
    div.className = `chat-msg ${role}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function renderChartInto(container, payload) {
    if (!payload || !payload.labels || !payload.datasets) return;
    const canvasId = `chat-chart-${++chartCounter}`;
    const canvas = document.createElement("canvas");
    canvas.id = canvasId;
    canvas.height = 180;
    container.appendChild(canvas);

    const isShareType = payload.type === "pie" || payload.type === "doughnut";
    const multi = payload.datasets.length > 1;

    new Chart(canvas, {
      type: payload.type,
      data: {
        labels: payload.labels,
        datasets: payload.datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.data,
          backgroundColor: isShareType
            ? payload.labels.map((_, j) => DashCharts.SERIES[j % DashCharts.SERIES.length])
            : DashCharts.SERIES[i % DashCharts.SERIES.length],
          borderColor: DashCharts.SERIES[i % DashCharts.SERIES.length],
          borderWidth: payload.type === "line" ? 2 : 0,
          pointRadius: payload.type === "line" ? 0 : undefined,
          tension: payload.type === "line" ? 0.25 : undefined,
          borderRadius: payload.type === "bar" ? 4 : undefined,
        })),
      },
      options: Object.assign(DashCharts.baseOptions(), {
        plugins: { legend: { display: multi || isShareType, position: "bottom", labels: { boxWidth: 10, boxHeight: 10, color: "#c3c2b7" } } },
      }),
    });
  }

  function wireChat(messagesEl, input, sendBtn) {
    async function send() {
      const message = input.value.trim();
      if (!message) return;
      input.value = "";
      sendBtn.disabled = true;

      appendMessage(messagesEl, "user", message);
      const thinking = appendMessage(messagesEl, "assistant", "Thinking…");

      try {
        const res = await fetch("/api/agent/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, history }),
        });
        const data = await res.json();

        thinking.textContent = data.reply || "(no response)";
        if (data.chart) renderChartInto(thinking, data.chart);

        history.push({ role: "user", content: message });
        history.push({ role: "assistant", content: data.reply || "" });
        if (history.length > 20) history = history.slice(-20);
      } catch (err) {
        thinking.textContent = "Something went wrong reaching the AI assistant.";
        console.error(err);
      } finally {
        sendBtn.disabled = false;
      }
    }

    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") send();
    });
  }

  wireChat(document.getElementById("chat-messages"), document.getElementById("chat-input"), document.getElementById("chat-send"));
  wireChat(document.getElementById("page-chat-messages"), document.getElementById("page-chat-input"), document.getElementById("page-chat-send"));

  async function loadInsights(force = false) {
    const narrativeEl = document.getElementById("insight-narrative");
    const recsEl = document.getElementById("insight-recs");
    const updatedEl = document.getElementById("insight-updated");
    if (force) narrativeEl.innerHTML = 'Regenerating<span class="loading-dots"></span>';

    try {
      const res = await fetch(`/api/agent/insights${force ? "?force=1" : ""}`);
      const data = await res.json();
      narrativeEl.textContent = data.narrative;
      recsEl.innerHTML = (data.recommendations || [])
        .map((r) => `<li>${r.replace(/^\d+\.\s*/, "")}</li>`)
        .join("");
      if (updatedEl) {
        updatedEl.textContent = data.generated_at
          ? `Last updated ${new Date(data.generated_at * 1000).toLocaleString()}`
          : "";
      }
    } catch (err) {
      narrativeEl.textContent = "Couldn't load AI insights right now.";
      console.error(err);
    }
  }

  document.getElementById("regen-insights").addEventListener("click", () => loadInsights(true));

  Slides.onActivate((index) => {
    if (index === 0) loadInsights(false);
  });
})();
