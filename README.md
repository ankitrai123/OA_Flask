# Peyala Pulse

An Operations Analytics Decision Console built over a fictional café's (Peyala
Café) POS, inventory, and supplier data — a Flask + vanilla JS dashboard
modeled directly on a real academic capstone deck ("Peyala Café: How much to
prepare, and from whom to buy", Group 7) so it can survive the same scrutiny
that deck was written for. The governing rule is data integrity: **every KPI,
chart, and recommendation traces to the source CSVs, an explicit statistical
model, or an explicit disclosed input — never a fabricated number.** Where the
data can't support a claim, the UI says so directly instead of quietly
estimating it.

The console follows the capstone's own four-question structure — **Q1**
demand sensing, **Q2** prep quantity, **Q3** replenishment & sourcing
(safety stock, procurement), **Q4** automation — across an 11-slide flow.
Every slide is built around one pattern: **Insight → KPI → Chart → Decision**
at a glance, with the underlying formulas, coefficients, p-values, AIC,
critical ratios, LP constraints, shadow prices, and TOPSIS weights pushed into
an expandable **Technical Details** panel (visible by default only in Analyst
mode) rather than removed. Executive mode stays simple; nothing technical is
deleted, only tucked behind one click.

## The data-integrity taxonomy

Every figure on every slide is implicitly or explicitly tagged as one of:

- **Observed** — read directly from a source CSV, no transformation beyond parsing.
- **Derived** — computed from observed data via an explicit, disclosed formula or statistical test.
- **Assumption** — supplied by the user/analyst; not present in or computable from the source data.
- **Unsupported** — cannot be computed from available data with acceptable confidence; shown as a labeled gap, never a guess.

Slide 02 (Data Quality & Audit) surfaces four real defects in the source data
that this taxonomy exists because of — including one (the inventory log's
`Actual_Demand_Qty` vs. actual POS-derived demand) that turns out to be
empirically uncorrelated (r ≈ -0.02), not just "a bit noisy." Forecasting,
the newsvendor model, safety stock, and automation are all built on
POS-derived demand as a result — the inventory log's demand figures are used
only for what they're internally self-consistent for (its own prep/spoilage
relationship), never as a demand-level signal. See `services/data_quality.py`
and Slide 02's Technical Details drawers for the full audit.

Two figures on this console are explicit **Assumptions**, clearly labeled as
such rather than presented as derived from data: the mapping of each of the 6
menu items to the ingredient category that dominates its own replenishment
(Slide 05, `services/safety_stock.py`'s `ITEM_TO_CATEGORY`), and each
supplier's weekly delivery **capacity** (Slide 06's Procurement LP —
`restaurant_supply_network.csv` has no capacity column at all). Both are
user-adjustable; nothing about them is invented and passed off as measured.

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
Analyst** mode at the bottom of the sidebar — Analyst mode reveals the
Technical Details drawers and deeper statistical detail; Executive mode shows
the same headline figures without that depth. The AI chat is available on
every slide via the floating button (bottom-right), and gets a dedicated
full-page home on Slide 11.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite (`tests/`) is the primary correctness gate: it regression-guards
every empirical data-quality finding against the live CSVs (including that
Annual Revenue is correctly annualized, not a raw 2-year total — see below),
checks the ARIMAX models' significance patterns and rolling-origin validation
math, verifies the LP allocation's feasibility and shadow-price sign, checks
that TOPSIS rankings actually flip across weighting scenarios rather than
just asserting it, and structurally asserts the newsvendor module's
inventory-log-scale and POS-scale comparisons can never be mixed into one
fabricated number (see [The Defect-C rule](#the-defect-c-rule) below).

## Project layout

- `app.py` — Flask app factory, blueprint registration, JSON 500 handler
- `config.py` — env/config loading
- `services/data_loader.py` — loads the 3 CSVs into pandas once, cached in memory
- `services/data_quality.py` — the four-defect data audit backing Slide 02
- `services/eda.py` — revenue mix, demand distribution, seasonality (monthly + weekday ANOVA), spoilage/prep bias, menu affinity — feeds Slides 01, 03, and 05
- `services/forecasting.py` — ARIMAX(0,1,1) on log-transformed weekly demand + summer regressor, with 5-fold rolling-origin and naive-80/20-split validation, backing Slide 03; a parallel daily (raw) model still powers Slide 04's per-day dynamic prep quantity
- `services/newsvendor.py` — prep-quantity optimization: an aggregate Current/Static/Dynamic policy comparison (Slide 04's headline) plus the original per-item Defect-C-safe comparison (Technical Details)
- `services/safety_stock.py` — decomposed-by-supplier safety stock & reorder point (Slide 05)
- `services/procurement.py` — LP allocation (`scipy.optimize.linprog`) with shadow price, and TOPSIS supplier ranking across 3 weighting scenarios (Slide 06)
- `services/automation.py` — rule-based reorder trigger, specified and backtested against real demand (Slide 08)
- `services/overview.py` — executive KPIs, decision pipeline, decision summary — backs Slide 01
- `services/item_economics.py` — shared margin/critical-ratio helper (used by the optimizer, forecaster, simulator, newsvendor, and safety-stock modules so the definition can't drift between them)
- `services/metrics.py` — legacy KPI/chart-data aggregations (still used internally by the AI agent)
- `services/optimizer.py` — prep bias-correction, pricing/discount-leakage (Slide 07), and a legacy procurement scorer (superseded on-slide by `procurement.py`'s LP+TOPSIS, kept as a cross-check)
- `services/simulator.py` — Monte Carlo what-if engine for both scenario types, consolidated on Slide 09
- `services/basket_analysis.py` — apriori menu/basket analysis, surfaced on Slide 10's Recommendations
- `services/supply_optimization.py` — EOQ + reorder-point calculator and a combinatorial supplier-allocation optimizer (feeds Slide 09's supplier what-if; kept as a complementary method to the LP)
- `services/agent.py` — NVIDIA Nemotron client, tool-calling chat, cached insights
- `routes/analytics.py` — the main blueprint (`/api/overview`, `/api/data-quality`, `/api/eda`, `/api/demand/*`, `/api/prep/*`, `/api/inventory/safety-stock`, `/api/procurement`, `/api/automation`)
- `routes/api.py`, `routes/agent_routes.py`, `routes/advanced.py` — supporting blueprints (optimizers, simulators, supply/EOQ endpoints)
- `templates/dashboard.html`, `static/` — the sidebar-navigated 11-slide frontend (vanilla JS + Chart.js); `static/js/api.js`/`ui.js` are shared fetch/render helpers, `mode-toggle.js`/`drawer.js` back the Executive/Analyst toggle and Technical Details drawers, `slide-01-overview.js` … `slide-11-ai-analyst.js` are the per-slide modules
- `tests/` — pytest suite (backend correctness + data-quality regression guards)
- `data/` — the source CSVs

## The 11 slides

| # | Slide | What it answers |
|---|---|---|
| 1 | Executive Overview | Headline KPIs, decision pipeline, decision summary, AI insights |
| 2 | Data Quality & Audit | Four data defects and how each is handled |
| 3 | Demand Sensing — ARIMAX | **Q1**: what will next week's demand be? |
| 4 | Prep & Newsvendor | **Q2**: how much should the kitchen prepare? |
| 5 | Inventory | **Q3a**: how much buffer, and when to reorder? |
| 6 | Procurement | **Q3b**: when and from whom to replenish? |
| 7 | Pricing | What discounting actually costs, item by item |
| 8 | Automation | **Q4**: who watches stock every day? |
| 9 | What-if Simulator | Monte Carlo scenarios for demand/prep and supplier/lead time |
| 10 | Recommendations | Five actions, each with an owner, horizon, and live-sourced evidence, plus limitations |
| 11 | AI Analyst | Full-page chat, every figure fetched live |

**Slide 01 — Executive Overview.** Eight KPIs including **Annual Revenue**
(correctly annualized — `services/overview.py` divides the 2-year POS total by
the number of distinct calendar years spanned, not a raw 2-year sum) and
**Prep Shortfall Days** (the inventory log's own `Actual_Demand_Qty >
Forecasted_Prep_Qty` rate — a real, disclosed figure now that Slides 05/08
give it a downstream use, never conflated with a true stockout metric). All
six decision-pipeline stages (Demand → Forecast → Prep → Inventory → Reorder
→ Supplier Allocation) are now built.

**Slide 02 — Data Quality & Audit.** Four defects, each with a Technical
Details drawer and a live-computed number: the POS discount formula (exact
match on every row), the synthetic/near-uniform transaction timestamp
(making time-of-day analysis inadmissible), the inventory-log-vs-POS demand
mismatch (Defect C, the console's central design constraint — see below),
and duplicate supplier `Route_ID`s (widened this build to compare all 5
relevant columns, reconciling to 14 duplicate rows across 13 conflicting IDs).

**Slide 03 — Demand Sensing.** ARIMAX(0,1,1) fit on **log-transformed
weekly** demand with a summer (Apr–Jun) regressor — only in log space does
the fitted coefficient exponentiate into a clean multiplicative uplift (e.g.
`exp(0.66) ≈ 1.9×`), matching the capstone's own "ARIMAX(0,1,1) on log
demand" specification. Opens with the seasonality finding that motivates it
(monthly uplift, real and beverage-specific; a weekday cycle tested via
one-way ANOVA and found too marginal to model). Validated by 5-fold
rolling-origin backtesting *and* a naive single 80/20 split shown side by
side — deliberately, because a single holdout window can land outside the
summer months and understate the model's real value, which is exactly what
this console's own test window does.

**Slide 04 — Prep & Newsvendor.** Leads with an aggregate policy comparison —
Current judgment vs. a Static (one blanket order-up-to quantity for every
item) vs. Dynamic (each item's own critical-ratio-tailored quantity) policy,
scored in annual cost — showing a single fixed quantity costs roughly 75%
more than tailoring per item, because critical ratios differ by item
(≈0.58–0.71) and the café's own judgment is already close to its per-item
optimum. The original per-item, Defect-C-safe comparison (see below) and the
interactive what-if form move to this slide's Technical Details as the
detailed drill-down.

**Slide 05 — Inventory (Safety Stock & ROP).** Opens with the spoilage/
shortfall figures that motivate it, then decomposes safety stock **by which
supplier actually serves each item's assumed ingredient category** — using
that supplier's own lead-time mean/std, not a lead time pooled across all
suppliers regardless of identity. Pooling inflates and flattens safety stock
because supplier identity explains the large majority of lead-time variance
(a one-way ANOVA quantifies this live); decomposing gives a realistic,
item-specific range.

**Slide 06 — Procurement (LP + TOPSIS).** A linear program
(`scipy.optimize.linprog`) allocates weekly category-level purchases across
suppliers at least cost subject to each supplier's capacity (an adjustable
Assumption input — the source data has no capacity column at all) and each
category's real required quantity (derived from POS demand via the item→
category mapping). A binding supplier's shadow price is shown live. Alongside
it, TOPSIS ranks suppliers per category under three weighting scenarios
(cost-heavy, lead-time-heavy, balanced) — the ranking changes with the
weighting in every category tested here, so no supplier is presented as "the
best" independent of that choice.

**Slide 07 — Pricing.** The original discount-leakage optimizer
(`services/optimizer.py`, built earlier, never exposed until now): average
order quantity doesn't rise with discount depth in this data, so deeper
discounts show up as margin given away rather than a proven volume driver.

**Slide 08 — Automation (Reorder Trigger).** A specified rule (*if projected
inventory position ≤ the item's reorder point, order the stated quantity from
the recommended supplier*) backtested mechanically against each item's real
historical demand — not a live system, since there's no real-time inventory
feed in this data, but a demonstrated one.

**Slide 09 — What-if Simulator.** Both of `services/simulator.py`'s Monte
Carlo scenario types get a home here: demand/prep (bootstrap-resampled from
real historical demand) and supplier/lead-time (a periodic-review
reorder-point simulation). The supplier scenario existed since an earlier
build phase but never had a frontend until now.

**Slide 10 — Recommendations & Limitations.** Five action rows (owner,
horizon, evidence) with every evidence figure pulled live from its backing
module rather than hardcoded, plus the apriori menu-affinity rules and an
explicit limitations list (six items not the full menu, no time-of-day
inference, the inventory log unusable as a demand signal, TOPSIS's
weight-sensitivity, the capacity assumption, and the summer effect resting on
two observed annual cycles).

**Slide 11 — AI Analyst.** The chat gets a dedicated full-page slide,
sharing one conversation history with the floating panel available
everywhere else.

### The Defect-C rule

Because the inventory log's demand figures and POS-derived demand are
empirically uncorrelated, Slide 04's per-item comparison (in Technical
Details) never bridges them with a single "savings" number. Instead:
- **Inventory-log scale** — "current judgment" vs. a static newsvendor
  quantity, both computed on the inventory log's own internally self-consistent
  scale.
- **POS scale** — the ARIMAX-driven dynamic newsvendor quantity, compared
  only against a POS-scale naive baseline — never against the inventory-log
  panel above.

This split is enforced by an automated test
(`tests/test_newsvendor.py::test_defect_c_structural_separation`), not just
documentation, and every "cost avoided" figure is phrased as a projection
against a stated counterfactual policy, never as a claimed booked saving.

## AI agent

`services/agent.py` uses NVIDIA's OpenAI-compatible endpoint
(`https://integrate.api.nvidia.com/v1`) with tool-calling: the model never
states a number without first calling back into our own metrics/service
functions, so it can't hallucinate figures. It can also return a chart spec
when asked to plot something, which the frontend renders inline in the chat
with Chart.js. Its tool registry covers every module on the console —
overview, data quality, EDA, demand forecasting, newsvendor (per-item and
aggregate), safety stock, procurement, and automation — and is instructed
never to present a supplier as "the best" or a forecast as perfect, matching
the same honesty rules the UI itself follows.
