"""AI agent backed by NVIDIA's Nemotron model (OpenAI-compatible endpoint).

The agent never invents numbers: every fact it states comes back through a
tool call into our own metrics/optimizer functions. Chat is stateless on the
server (the client resends history); insights are cached briefly so we don't
hammer the API on every dashboard refresh.
"""

import json
import time

from openai import APIError, AuthenticationError, OpenAI

from config import Config
from services import metrics, optimizer

SYSTEM_PROMPT = """You are the on-dashboard AI analyst for an Indian restaurant.
You have tools to fetch the restaurant's real sales, inventory/waste, supplier,
and optimizer numbers. ALWAYS call a tool before stating any figure — never
guess or estimate a number yourself. Currency is INR (₹). Be concise, concrete,
and action-oriented: prefer short bullet points with actual numbers over vague
advice. If the user asks to see/plot/visualize/chart something, call
generate_chart in addition to your text reply."""

DATASETS = {
    "overview": metrics.kpi_overview,
    "revenue_trend": metrics.revenue_trend,
    "revenue_by_category": metrics.revenue_by_category,
    "item_performance": metrics.item_performance,
    "hourly_pattern": metrics.hourly_pattern,
    "waste_by_item": metrics.waste_by_item,
    "forecast_vs_actual": metrics.forecast_vs_actual,
    "supplier_comparison": metrics.supplier_comparison,
    "optimizer_prep": optimizer.optimize_prep,
    "optimizer_pricing": optimizer.optimize_pricing,
    "optimizer_procurement": optimizer.optimize_procurement,
}

_DATASET_ENUM = list(DATASETS.keys())

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_business_metrics",
            "description": "Fetch real computed business metrics/KPIs to ground your answer. Pick the dataset that matches the question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "enum": _DATASET_ENUM},
                },
                "required": ["dataset"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "Produce chart-ready data for the dashboard to render when the user asks to see, plot, visualize, or graph something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "enum": _DATASET_ENUM},
                    "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "doughnut"]},
                    "title": {"type": "string"},
                },
                "required": ["dataset", "chart_type", "title"],
            },
        },
    },
]

# For list-of-record datasets: which field is the label and which numeric
# field is the default plotted value when turning it into a chart.
_LIST_CHART_FIELDS = {
    "item_performance": ("Item_Name", "revenue"),
    "waste_by_item": ("Item_Name", "avg_waste_pct"),
    "optimizer_prep": ("item", "projected_savings_inr"),
    "optimizer_pricing": ("item", "total_discount_given_inr"),
    "optimizer_procurement": ("category", "cost_savings_pct"),
    "supplier_comparison": ("Supplier", "avg_delivery_cost"),
}


def _client():
    if not Config.NVIDIA_API_KEY:
        return None
    return OpenAI(base_url=Config.NVIDIA_BASE_URL, api_key=Config.NVIDIA_API_KEY)


def _run_dataset(dataset):
    fn = DATASETS.get(dataset)
    if fn is None:
        return {"error": f"unknown dataset '{dataset}'"}
    return fn()


def _to_chart_payload(dataset, chart_type, title):
    raw = _run_dataset(dataset)
    if isinstance(raw, dict) and "error" in raw:
        return raw

    if isinstance(raw, list):
        label_field, value_field = _LIST_CHART_FIELDS.get(dataset, (None, None))
        if not label_field:
            return {"error": f"dataset '{dataset}' cannot be charted directly"}
        labels = [str(row.get(label_field)) for row in raw]
        data = [row.get(value_field) for row in raw]
        return {
            "type": chart_type,
            "title": title,
            "labels": labels,
            "datasets": [{"label": value_field, "data": data}],
        }

    if "labels" in raw:
        series_keys = [k for k in raw.keys() if k != "labels"]
        return {
            "type": chart_type,
            "title": title,
            "labels": raw["labels"],
            "datasets": [{"label": k, "data": raw[k]} for k in series_keys],
        }

    # overview / scalar dict — flatten numeric fields into a single bar
    numeric = {k: v for k, v in raw.items() if isinstance(v, (int, float))}
    return {
        "type": chart_type,
        "title": title,
        "labels": list(numeric.keys()),
        "datasets": [{"label": title, "data": list(numeric.values())}],
    }


def _execute_tool(name, arguments):
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return {"error": "invalid tool arguments"}

    if name == "get_business_metrics":
        return _run_dataset(args.get("dataset"))
    if name == "generate_chart":
        return _to_chart_payload(args.get("dataset"), args.get("chart_type", "bar"), args.get("title", ""))
    return {"error": f"unknown tool '{name}'"}


def chat(user_message, history=None):
    client = _client()
    if client is None:
        return {
            "reply": "The AI assistant isn't configured yet — add NVIDIA_API_KEY to your .env file and restart the server.",
            "chart": None,
        }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or []):
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    chart_payload = None
    try:
        for _ in range(3):
            resp = client.chat.completions.create(
                model=Config.NVIDIA_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=800,
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })
                for tc in msg.tool_calls:
                    result = _execute_tool(tc.function.name, tc.function.arguments)
                    if tc.function.name == "generate_chart" and "error" not in result:
                        chart_payload = result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str)[:6000],
                    })
                continue

            return {"reply": msg.content, "chart": chart_payload}

        return {
            "reply": "I gathered the data but need a more specific question to summarize it well — could you narrow it down?",
            "chart": chart_payload,
        }
    except AuthenticationError:
        return {"reply": "NVIDIA rejected the API key — double-check NVIDIA_API_KEY in your .env file.", "chart": None}
    except APIError as e:
        return {"reply": f"The AI service returned an error: {e}", "chart": None}


_insights_cache = {"data": None, "generated_at": 0}
_INSIGHTS_TTL_SECONDS = 900


def get_insights(force=False):
    now = time.time()
    if not force and _insights_cache["data"] and (now - _insights_cache["generated_at"]) < _INSIGHTS_TTL_SECONDS:
        return _insights_cache["data"]

    client = _client()
    if client is None:
        data = {
            "narrative": "AI assistant not configured — add NVIDIA_API_KEY to your .env file to enable auto-generated insights.",
            "recommendations": [],
            "generated_at": None,
        }
        _insights_cache.update(data=data, generated_at=now)
        return data

    overview = metrics.kpi_overview()
    waste = metrics.waste_by_item()[:3]
    prep_savings = optimizer.optimize_prep()[:3]
    pricing_savings = optimizer.optimize_pricing()[:3]
    procurement_savings = optimizer.optimize_procurement()[:3]

    payload = {
        "overview": overview,
        "top_waste_items": waste,
        "top_prep_optimizer_opportunities": prep_savings,
        "top_pricing_optimizer_opportunities": pricing_savings,
        "top_procurement_optimizer_opportunities": procurement_savings,
    }

    prompt = (
        "Here is the restaurant's current data snapshot as JSON:\n"
        f"{json.dumps(payload, default=str)}\n\n"
        "Write: (1) a 2-3 sentence executive narrative on current business health, "
        "then (2) exactly 3 concrete, numbered recommendations, each one sentence, "
        "each citing a real figure from the data above. Plain text, no markdown headers."
    )

    try:
        resp = client.chat.completions.create(
            model=Config.NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=500,
        )
        text = resp.choices[0].message.content or ""
        narrative, _, rest = text.partition("1.")
        recommendations = []
        if rest:
            chunks = ("1." + rest).split("\n")
            recommendations = [c.strip() for c in chunks if c.strip()]
        data = {
            "narrative": narrative.strip() or text.strip(),
            "recommendations": recommendations,
            "generated_at": now,
        }
    except (AuthenticationError, APIError) as e:
        data = {"narrative": f"AI insights unavailable right now ({e}).", "recommendations": [], "generated_at": None}

    _insights_cache.update(data=data, generated_at=now)
    return data
