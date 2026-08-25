from flask import Flask, render_template

from config import Config
from routes.agent_routes import agent_bp
from routes.api import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(api_bp)
    app.register_blueprint(agent_bp)

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
