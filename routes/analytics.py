from flask import Blueprint, jsonify, request

from services import data_quality, eda, forecasting, newsvendor, overview

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
