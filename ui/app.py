from flask import Flask, render_template
import requests

from dash_app.oee_dash import init_dashboard
from dash_app.events_dash import init_events_dashboard

FASTAPI_BASE = "http://localhost:8000"


def create_app():
    app = Flask(__name__)

    # Initialize Dash apps
    init_dashboard(app)         # /dash/oee/
    init_events_dashboard(app)  # /dash/events/

    # =====================================================
    # Flask routes (with sidebar + layout)
    # =====================================================

    @app.route("/")
    def index():
        return render_template("index.html", title="MES Dashboard")

    @app.route("/machines")
    def machines():
        r = requests.get(f"{FASTAPI_BASE}/machines")
        data = r.json()
        return render_template("machines.html", machines=data, title="Machines")

    @app.route("/oee")
    def oee_page():
        return render_template("oee.html", title="OEE Dashboard")

    @app.route("/events")
    def events_page():
        return render_template("events.html", title="Events")

    return app


# ============================================================
# Standalone execution
# ============================================================
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
