from flask import Blueprint, jsonify, request

from services import agent

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")


@agent_bp.post("/chat")
def chat():
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    history = body.get("history") or []

    if not message:
        return jsonify({"error": "message is required"}), 400
    if not isinstance(history, list):
        return jsonify({"error": "history must be a list"}), 400

    return jsonify(agent.chat(message, history))


@agent_bp.get("/insights")
def insights():
    force = request.args.get("force") == "1"
    return jsonify(agent.get_insights(force=force))
