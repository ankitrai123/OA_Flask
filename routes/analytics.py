from flask import Blueprint, jsonify, request

from services import automation, data_quality, eda, forecasting, newsvendor, overview, procurement, safety_stock

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api")


@analytics_bp.get("/overview")
def api_overview():
    return jsonify(overview.get_executive_overview_bundle())


@analytics_bp.get("/data-quality")
def api_data_quality():
    return jsonify(data_quality.data_quality_scorecard())


@analytics_bp.get("/eda")
def api_eda():
    return jsonify(eda.eda_bundle())


@analytics_bp.get("/demand/forecast")
def api_demand_forecast():
    return jsonify(forecasting.get_demand_forecast_bundle())


@analytics_bp.get("/demand/validation")
def api_demand_validation():
    return jsonify(forecasting.get_demand_validation_bundle())


@analytics_bp.get("/prep/newsvendor")
def api_prep_newsvendor_get():
    return jsonify(newsvendor.get_newsvendor_bundle())


@analytics_bp.post("/prep/newsvendor")
def api_prep_newsvendor_whatif():
    body = request.get_json(silent=True) or {}
    item = body.get("item")
    if not item:
        return jsonify({"error": "item is required"}), 400

    result = newsvendor.simulate_newsvendor_whatif(
        item=item,
        demand_qty=body.get("demand_qty"),
        spoilage_cost=body.get("spoilage_cost"),
        stockout_cost=body.get("stockout_cost"),
        service_level=body.get("service_level"),
    )
    return jsonify(result), (400 if "error" in result else 200)


@analytics_bp.get("/prep/compare")
def api_prep_compare():
    return jsonify(newsvendor.get_prep_compare_bundle())


@analytics_bp.get("/prep/aggregate-comparison")
def api_prep_aggregate_comparison():
    return jsonify(newsvendor.get_prep_policy_aggregate_comparison())


@analytics_bp.get("/inventory/safety-stock")
def api_safety_stock():
    service_level = request.args.get("service_level", safety_stock.DEFAULT_SERVICE_LEVEL)
    b = safety_stock.safety_stock_bundle()
    if service_level != safety_stock.DEFAULT_SERVICE_LEVEL:
        b["items"] = {item: safety_stock.item_safety_stock(item, service_level=service_level) for item in safety_stock.ITEM_TO_CATEGORY}
    return jsonify(b)


@analytics_bp.get("/procurement")
def api_procurement_get():
    return jsonify(procurement.procurement_bundle())


@analytics_bp.post("/procurement")
def api_procurement_post():
    body = request.get_json(silent=True) or {}
    capacity = body.get("capacity")
    if capacity is not None and not isinstance(capacity, dict):
        return jsonify({"error": "capacity must be an object mapping supplier name to a numeric weekly capacity"}), 400
    result = procurement.procurement_bundle(capacity=capacity)
    status = 400 if "error" in result.get("lp_allocation", {}) else 200
    return jsonify(result), status


@analytics_bp.get("/automation")
def api_automation():
    return jsonify(automation.automation_bundle())
