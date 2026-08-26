# Peyala Pulse

An Operations Analytics Decision Console built over a fictional café's (Peyala
Café) POS, inventory, and supplier data — a Flask + vanilla JS dashboard
designed to survive close scrutiny (an MBA-capstone / viva context), not just
look good. The governing rule is data integrity: **every KPI, chart, and
recommendation traces to the source CSVs, an explicit statistical model, or an
explicit user input — never a fabricated number.** Where the data can't
support a claim, the UI says so directly ("Not supported by available data")
instead of quietly estimating it.

This is a substantial rebuild of an earlier 7-slide version of this project,
being delivered in three milestones. **This is Milestone 1**: the Executive
Overview, plus the Data Quality, EDA, Demand Sensing, and Prep/Newsvendor
slides, along with the visual and interaction framework (sidebar navigation,
Executive/Analyst mode toggle, methodology drawers) that Milestones 2-3 will
extend. See [What's not in this milestone](#whats-not-in-this-milestone-yet)
below.

## The data-integrity taxonomy

Every figure on every slide is implicitly or explicitly tagged as one of:

- **Observed** — read directly from a source CSV, no transformation beyond parsing.
- **Derived** — computed from observed data via an explicit, disclosed formula or statistical test.
- **Assumption** — supplied by the user/analyst; not present in or computable from the source data.
- **Unsupported** — cannot be computed from available data with acceptable confidence; shown as a labeled gap, never a guess.

Slide 02 (Data Quality & Audit) surfaces four real defects in the source data
that this taxonomy exists because of — including one (the inventory log's
`Actual_Demand_Qty` vs. actual POS-derived demand) that turned out to be
empirically uncorrelated (r ≈ -0.02), not just "a bit noisy." Forecasting and
the newsvendor model are both built on POS-derived demand as a result — the
inventory log's demand figures are used only for what they're internally
self-consistent for (its own prep/spoilage relationship), never as a
demand-level signal. See `services/data_quality.py` and Slide 02's
methodology drawers for the full audit.

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

Open http://localhost:5000. Navigate slides via the left sidebar, the arrow
buttons, the keyboard (←/→), or swipe on touch devices. Toggle **Executive /
Analyst** mode at the bottom of the sidebar — Analyst mode reveals model
internals (AIC, p-values, fold-level validation detail, methodology drawers,
scope notes); Executive mode shows the same figures without that depth. The
AI chat is available on every slide via the floating button (bottom-right).

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite (`tests/`) is the primary correctness gate: it regression-guards
every empirical data-quality finding against the live CSVs, checks the ARIMAX
models' significance patterns and rolling-origin validation math, and
structurally asserts the newsvendor module's inventory-log-scale and
POS-scale comparisons can never be mixed into one fabricated number (see
[The Defect-C rule](#the-defect-c-rule) below).

## Project layout

- `app.py` — Flask app factory, blueprint registration, JSON 500 handler
- `config.py` — env/config loading
- `services/data_loader.py` — loads the 3 CSVs into pandas once, cached in memory
- `services/data_quality.py` — the four-defect data audit backing Slide 02
- `services/eda.py` — revenue mix, demand distribution, seasonality (Welch's t-test), menu affinity — backs Slide 03
- `services/forecasting.py` — ARIMAX(0,1,1)+summer-regressor demand model, rolling-origin validation — backs Slide 04 (see below)
- `services/newsvendor.py` — prep-quantity optimization and policy comparison — backs Slide 05 (see below)
- `services/overview.py` — executive KPIs, decision pipeline, decision summary — backs Slide 01
- `services/item_economics.py` — shared margin/critical-ratio helper (used by the optimizer, forecaster, simulator, and newsvendor module so the definition can't drift between them)
- `services/metrics.py` — legacy KPI/chart-data aggregations (still used internally; no longer has a dedicated slide this milestone)
- `services/optimizer.py` — the three original descriptive-data optimizers (prep, pricing, procurement — see below); backend intact, frontend deferred to Milestones 2-3 except where noted
- `services/simulator.py` — Monte Carlo what-if engine (demand/prep scenario now sources POS-derived demand; supplier/lead-time scenario unchanged)
- `services/basket_analysis.py` — apriori menu/basket analysis (unchanged; now surfaced via Slide 03's Menu Affinity card)
- `services/supply_optimization.py` — EOQ + supplier allocation (unchanged; backend intact, frontend deferred)
- `services/agent.py` — NVIDIA Nemotron client, tool-calling chat, cached insights
- `routes/analytics.py` — the new blueprint backing Slides 01-05 (`/api/overview`, `/api/data-quality`, `/api/eda`, `/api/demand/*`, `/api/prep/*`)
- `routes/api.py`, `routes/agent_routes.py`, `routes/advanced.py` — existing blueprints (trimmed where a route's only consumer was replaced this milestone)
- `templates/dashboard.html`, `static/` — the sidebar-navigated slide-deck frontend (vanilla JS + Chart.js); `static/js/api.js`/`ui.js` are the shared fetch/render helpers, `mode-toggle.js`/`drawer.js` back the Executive/Analyst toggle and methodology drawers, `slide-01-overview.js` … `slide-05-newsvendor.js` are the per-slide modules
- `tests/` — pytest suite (backend correctness + data-quality regression guards)
- `data/` — the source CSVs

## What's built in Milestone 1

**Slide 01 — Executive Overview.** Eight headline KPIs (Annual Revenue, Gross
Margin, Orders, Order Lines, Spoilage Cost, Shortage Days, Number of Items,
Number of Suppliers) — Shortage Days is deliberately shown as unsupported
pending Milestone 2's inventory/reorder-point model, rather than conflated
with the inventory log's internal prep-shortfall figure (a different
concept). A decision-pipeline status strip shows which stages are built vs.
planned, and a decision summary lists real findings alongside honestly
deferred ones.

**Slide 02 — Data Quality & Audit.** The four-defect audit described above,
each with a methodology drawer and a real, live-computed number: the POS
discount-calculation formula (verified exact across all rows), the synthetic
/ near-uniform transaction-timestamp distribution (making time-of-day
analysis inadmissible — see Slide 03), the inventory-log-vs-POS demand
mismatch, and the duplicate supplier Route_IDs (and how the existing
supplier-aggregation logic already sidesteps it).

**Slide 03 — Exploratory Data Analysis.** Revenue mix, demand distribution,
monthly seasonality (real and significant in aggregate, but concentrated
almost entirely in two beverage items — shown per-item, not flattened into a
single misleading claim), the inventory log's internal prep/spoilage
relationship (explicitly scoped as not a demand signal), the inadmissible
time-of-day status card, and a Menu Affinity card surfacing the strongest
apriori association rules.

**Slide 04 — Demand Sensing.** An ARIMAX(0,1,1) model with a summer (Apr-Jun)
exogenous regressor, fit per item on POS-derived daily demand, replacing the
old gradient-boosted forecaster entirely — which, independent of anything in
this spec, turned out to have been trained on the wrong series (the
inventory log, not POS demand; the same Defect-C issue above). Validated by
5-fold rolling-origin (walk-forward) backtesting against a naive
trailing-mean baseline, refit fresh per fold with no leakage. The summer
regressor is correctly significant only for the two beverage items and
correctly insignificant for food items — the model isn't tuned to look good,
it's tuned to be honest about what the data supports.

**Slide 05 — Prep Quantity / Newsvendor.** An interactive newsvendor model
(critical ratio = contribution margin / (margin + unit cost)) with a
what-if form for demand, cost, and service-level overrides. The policy
comparison is structurally split into two panels that are never compared to
each other in one number — see below.

### The Defect-C rule

Because the inventory log's demand figures and POS-derived demand are
empirically uncorrelated, Slide 05 never bridges them with a single
"savings" number. Instead:
- **Inventory-log scale** — "current judgment" vs. a static newsvendor
  quantity, both computed on the inventory log's own internally self-consistent
  scale (this is what the original prep optimizer already validly did).
- **POS scale** — the ARIMAX-driven dynamic newsvendor quantity, compared
  only against a POS-scale naive baseline — never against the inventory-log
  panel above.

This split is enforced by an automated test
(`tests/test_newsvendor.py`), not just documentation, and every "cost
avoided" figure is phrased as a projection against a stated counterfactual
policy, never as a claimed booked saving.

## What's not in this milestone yet

Milestones 2 and 3 will add: Inventory & Replenishment (safety stock,
reorder point), Procurement (LP allocation + TOPSIS supplier ranking, with
supplier capacity as a user-adjustable input rather than a fabricated
figure), a repositioned Pricing/discount-leakage slide, an
Automation/Reorder-Trigger slide, a consolidated What-If Simulator,
Consolidated Results, Recommendations, Limitations, and an upgraded AI
Analyst copilot.

Until then, three pieces of backend from the earlier version of this project
stay fully intact and tested but have **no visible slide**:
`services/optimizer.py`'s pricing/discount-leakage and procurement scoring,
and `services/supply_optimization.py`'s EOQ + supplier allocation. (The third
original module, apriori basket analysis, does have a visible home already —
folded into Slide 03 as the Menu Affinity card.) Nothing has been deleted;
all of it is exercised by the test suite and ready for Milestones 2-3 to
build new frontend against.

## AI agent

`services/agent.py` uses NVIDIA's OpenAI-compatible endpoint
(`https://integrate.api.nvidia.com/v1`) with tool-calling: the model never
states a number without first calling back into our own metrics/service
functions, so it can't hallucinate figures. It can also return a chart spec
when asked to plot something, which the frontend renders inline in the chat
with Chart.js. `/api/agent/insights` generates a short cached executive
narrative for the Overview slide (15-minute cache, or hit "Regenerate"). Its
tool registry currently covers data quality, EDA, demand forecasting +
validation, and the newsvendor/prep-comparison bundles — a broader "AI
Analyst copilot" upgrade covering Milestones 2-3's modules is planned for
Milestone 3.
