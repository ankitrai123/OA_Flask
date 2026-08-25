from flask import Blueprint, jsonify

from services import metrics, optimizer

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/metrics/overview")
def overview():
    return jsonify(metrics.kpi_overview())


@api_bp.get("/metrics/sales")
def sales():
    return jsonify({
        "revenue_trend": metrics.revenue_trend(),
        "revenue_by_category": metrics.revenue_by_category(),
        "item_performance": metrics.item_performance(),
        "hourly_pattern": metrics.hourly_pattern(),
    })


@api_bp.get("/metrics/inventory")
def inventory():
    return jsonify({
        "waste_by_item": metrics.waste_by_item(),
        "forecast_vs_actual": metrics.forecast_vs_actual(),
    })


@api_bp.get("/metrics/supply")
def supply():
    return jsonify({"supplier_comparison": metrics.supplier_comparison()})


@api_bp.get("/optimizer/prep")
def optimizer_prep():
    return jsonify(optimizer.optimize_prep())


@api_bp.get("/optimizer/pricing")
def optimizer_pricing():
    return jsonify(optimizer.optimize_pricing())


@api_bp.get("/optimizer/procurement")
def optimizer_procurement():
    return jsonify(optimizer.optimize_procurement())
