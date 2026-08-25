from flask import Blueprint, jsonify, request

from services import basket_analysis, forecasting, simulator, supply_optimization

advanced_bp = Blueprint("advanced", __name__, url_prefix="/api")


@advanced_bp.get("/forecast")
def forecast():
    return jsonify(forecasting.get_forecast())


@advanced_bp.post("/simulator/prep")
def simulator_prep():
    body = request.get_json(silent=True) or {}
    item = body.get("item")
    if not item:
        return jsonify({"error": "item is required"}), 400

    result = simulator.simulate_prep_scenario(
        item=item,
        demand_growth_pct=float(body.get("demand_growth_pct", 0)),
        demand_vol_multiplier=float(body.get("demand_vol_multiplier", 1.0)),
        prep_quantity=body.get("prep_quantity"),
        n_trials=min(int(body.get("n_trials", 2000)), 5000),
        n_days=min(int(body.get("n_days", 90)), 365),
    )
    status = 400 if "error" in result else 200
    return jsonify(result), status


@advanced_bp.post("/simulator/supplier")
def simulator_supplier():
    body = request.get_json(silent=True) or {}
    category = body.get("category")
    try:
        annual_demand = float(body["annual_demand"])
        holding_cost = float(body["holding_cost_per_unit_per_year"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "category, annual_demand, and holding_cost_per_unit_per_year are required"}), 400

    result = simulator.simulate_supplier_scenario(
        category=category,
        annual_demand=annual_demand,
        holding_cost_per_unit_per_year=holding_cost,
        lead_time_override=body.get("lead_time_override"),
        demand_growth_pct=float(body.get("demand_growth_pct", 0)),
        order_qty_override=body.get("order_qty_override"),
        service_level=body.get("service_level", "95%"),
        demand_cv=float(body.get("demand_cv", supply_optimization.DEFAULT_DEMAND_CV)),
        n_trials=min(int(body.get("n_trials", 1000)), 3000),
        n_days=min(int(body.get("n_days", 180)), 365),
    )
    status = 400 if "error" in result else 200
    return jsonify(result), status


@advanced_bp.get("/basket-analysis")
def basket_rules():
    return jsonify(basket_analysis.get_association_rules())


@advanced_bp.get("/supply/categories")
def supply_categories():
    return jsonify(supply_optimization.list_categories())


@advanced_bp.get("/supply/stats/<path:category>")
def supply_stats(category):
    result = supply_optimization.category_supply_stats(category)
    if result is None:
        return jsonify({"error": f"unknown category '{category}'"}), 404
    return jsonify(result)


@advanced_bp.post("/supply/eoq")
def supply_eoq():
    body = request.get_json(silent=True) or {}
    try:
        annual_demand = float(body["annual_demand"])
        holding_cost = float(body["holding_cost_per_unit_per_year"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "category, annual_demand, and holding_cost_per_unit_per_year are required"}), 400

    result = supply_optimization.eoq_calculator(
        category=body.get("category"),
        annual_demand=annual_demand,
        holding_cost_per_unit_per_year=holding_cost,
        service_level=body.get("service_level", "95%"),
        demand_cv=float(body.get("demand_cv", supply_optimization.DEFAULT_DEMAND_CV)),
    )
    status = 400 if "error" in result else 200
    return jsonify(result), status


@advanced_bp.post("/supply/allocation")
def supply_allocation():
    body = request.get_json(silent=True) or {}
    try:
        required_qty = float(body["required_qty"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "category and required_qty are required"}), 400

    max_share = body.get("max_share_per_supplier")
    result = supply_optimization.supplier_allocation(
        category=body.get("category"),
        required_qty=required_qty,
        max_lead_time_days=body.get("max_lead_time_days"),
        max_share_per_supplier=float(max_share) if max_share not in (None, "") else None,
    )
    status = 400 if "error" in result else 200
    return jsonify(result), status
