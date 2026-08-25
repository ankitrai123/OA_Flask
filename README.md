# Restaurant Command Center

A Flask dashboard over the restaurant's POS, inventory, and supplier data —
seven full-screen landscape slides (Overview, Sales Analytics, Inventory &
Waste, Supply Chain, Pricing, Forecasting & Simulation, Menu & Supply
Optimization), an AI analyst powered by NVIDIA's Nemotron model, three
built-in optimizers, an ML demand forecaster, a Monte Carlo what-if
simulator, apriori menu-basket analysis, and an EOQ/supplier-allocation
optimizer.

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
- `services/item_economics.py` — shared margin/newsvendor-critical-ratio helper (used by the optimizer, forecaster, and simulator so the definition can't drift between them)
- `services/metrics.py` — KPI and chart-data aggregations
- `services/optimizer.py` — the three descriptive-data optimizers (see below)
- `services/forecasting.py` — ML demand forecasting (see below)
- `services/simulator.py` — Monte Carlo what-if engine (see below)
- `services/basket_analysis.py` — apriori menu/basket analysis (see below)
- `services/supply_optimization.py` — EOQ + supplier allocation (see below)
- `services/agent.py` — NVIDIA Nemotron client, tool-calling chat, cached insights
- `routes/api.py`, `routes/agent_routes.py`, `routes/advanced.py` — Flask blueprints
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

## ML demand forecasting (`services/forecasting.py`)

A single global gradient-boosted quantile regression model (item is a
feature — 366 obs/item is thin, pooling all 6 items gives the trees more
signal) trained on 2024 inventory logs, with day-of-week/month/lag/rolling
features. Evaluated on a genuine time-based 45-day holdout: **22% lower MAE
than a naive "same as last week" baseline** — a real, honest backtest
number, not a curve-fit one. Trained at 7 quantiles (0.1-0.9); each item's
newsvendor critical ratio is satisfied by interpolating between the two
nearest quantiles, turning the forecast directly into a prescriptive
"recommended prep qty" for each of the next 14 days.

## Monte Carlo what-if simulator (`services/simulator.py`)

Two bootstrap/Normal-sampling scenario types, run on demand from the
Forecasting slide:
- **Demand & Prep** — resamples real historical daily demand (scaled by a
  growth/volatility input), runs it through the same newsvendor cost math as
  the prep optimizer, and reports the resulting cost/waste/stockout
  distribution (p10/p50/p90).
- **Supplier & Lead Time** — a periodic-review (reorder-point,
  order-quantity) simulation seeded with the EOQ policy below. Safety stock
  is recomputed fresh at whatever lead time you test (not reused from the
  baseline), so a lead-time-shock scenario correctly shows the reorder point
  the policy *should* move to, and the added holding cost of doing so.

## Apriori menu/basket analysis (`services/basket_analysis.py`)

Real association rules (support/confidence/lift) over the 12,000 POS
transactions via `mlxtend`. With only 6 items the itemset space is tiny, but
the result is genuinely informative: Bbq Wings + Chicken Lollipop have the
strongest affinity (lift ~3.15x) despite far lower raw transaction counts
than the Pizza combos — lift correctly discounts Pizza's pairings for how
popular Pizza already is on its own, which raw co-occurrence counts can't do.

## EOQ + supplier allocation (`services/supply_optimization.py`)

The supply-network data has delivery cost, lead time, and MOQ per route —
but no per-unit ingredient cost or consumption quantity, both of which a
textbook EOQ needs. Rather than fabricate those, the calculator takes the
one or two figures only the restaurant actually knows (annual demand,
holding cost per unit) as inputs, and derives everything else (ordering
cost, lead time, demand variability default) from the real data.
Supplier allocation is an exact combinatorial search over MOQ-sized batches
per supplier minimizing total delivery cost for a quantity you specify —
without a capacity constraint, single-sourcing the cheapest supplier is
always mathematically optimal (correctly so — there's no data-supported
reason to split otherwise), so an optional "max share per supplier" input
lets you see the real-world case that isn't in the data: the cost premium
of deliberately diversifying suppliers for risk.

## AI agent

`services/agent.py` uses NVIDIA's OpenAI-compatible endpoint
(`https://integrate.api.nvidia.com/v1`) with tool-calling: the model never
states a number without first calling back into our own metrics/optimizer
functions, so it can't hallucinate figures. It can also return a chart spec
when asked to plot something, which the frontend renders inline in the chat
with Chart.js. `/api/agent/insights` generates a short cached executive
narrative + 3 recommendations for the Overview slide (15-minute cache, or hit
"Regenerate"). It can also read the ML forecast backtest/accuracy and the
apriori basket rules. It deliberately does **not** have tool access to the
simulator, EOQ calculator, or supplier allocation optimizer — those need
real business inputs (annual demand, holding cost) that only the restaurant
owner knows, and letting the model invent plausible-sounding numbers for
them would break the "never state an ungrounded number" rule everything
else here follows. Those three stay interactive forms on the Forecasting
and Menu & Supply Optimization slides.
