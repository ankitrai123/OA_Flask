# Restaurant Command Center

A Flask dashboard over the restaurant's POS, inventory, and supplier data — five
full-screen landscape slides (Overview, Sales Analytics, Inventory & Waste,
Supply Chain, Pricing), an AI analyst powered by NVIDIA's Nemotron model, and
three built-in optimizers.

## Setup

macOS / Linux:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Windows (`cmd.exe`):

```cmd
python -m pip install -r requirements.txt
copy .env.example .env
```

Windows (PowerShell):

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If `python` itself isn't recognized on Windows, install it from
https://python.org/downloads and make sure "Add python.exe to PATH" is
checked in the installer, then reopen your terminal.

Edit `.env` and set:
- `NVIDIA_API_KEY` — your key from https://build.nvidia.com
- `NVIDIA_MODEL` — the exact model slug your key has access to (the default is
  a placeholder; check your NVIDIA catalog and adjust if it doesn't match)

Without a key, the dashboard still runs fully — the AI insight card and chat
just report that the assistant isn't configured yet.

## Run

```bash
python app.py
```

Open http://localhost:5000. Navigate slides with the arrow buttons, the dots,
the keyboard (←/→), or swipe on touch devices. The AI chat is available on
every slide via the floating button (bottom-right).

## Project layout

- `app.py` — Flask app factory
- `config.py` — env/config loading
- `services/data_loader.py` — loads the 3 CSVs into pandas once, cached in memory
- `services/metrics.py` — KPI and chart-data aggregations
- `services/optimizer.py` — the three optimizers (see below)
- `services/agent.py` — NVIDIA Nemotron client, tool-calling chat, cached insights
- `routes/api.py`, `routes/agent_routes.py` — Flask blueprints
- `templates/dashboard.html`, `static/` — the slide-deck frontend (vanilla JS + Chart.js)
- `data/` — the source CSVs

## The three optimizers

1. **Prep / waste** (`optimize_prep`) — newsvendor bias correction. Each item's
   day-to-day prep forecast already tracks actual demand closely (~0.85+
   correlation), so instead of replacing it, this finds the constant shift
   (in units) that minimizes historical spoilage + stockout cost, derived from
   the newsvendor critical ratio (margin vs. spoilage cost).
2. **Pricing** (`optimize_pricing`) — discount-leakage analysis. The POS data
   shows no volume lift from deeper discounts (average order size is flat
   across discount levels), so rather than claim a causal "optimal discount,"
   this quantifies how much margin each item gives up to discounting per year
   and how much margin cushion it has to absorb that, so you can prioritize
   which items' discount policy to tighten first.
3. **Procurement** (`optimize_procurement`) — weighted least-cost supplier
   scoring per ingredient category (delivery cost + lead-time, normalized and
   weighted 60/40). Shows both the cost saving and the lead-time trade-off
   side by side rather than hiding it.

## AI agent

`services/agent.py` uses NVIDIA's OpenAI-compatible endpoint
(`https://integrate.api.nvidia.com/v1`) with tool-calling: the model never
states a number without first calling back into our own metrics/optimizer
functions, so it can't hallucinate figures. It can also return a chart spec
when asked to plot something, which the frontend renders inline in the chat
with Chart.js. `/api/agent/insights` generates a short cached executive
narrative + 3 recommendations for the Overview slide (15-minute cache, or hit
"Regenerate").
