from flask import Flask, jsonify, render_template

from config import Config
from routes.advanced import advanced_bp
from routes.agent_routes import agent_bp
from routes.analytics import analytics_bp
from routes.api import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(api_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(advanced_bp)
    app.register_blueprint(analytics_bp)

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({"error": "Something went wrong processing this request."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
