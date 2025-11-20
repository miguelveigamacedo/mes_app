import dash
from dash import html, dcc
import plotly.express as px
import requests

MES_API = "http://localhost:8000"   # FastAPI backend

def init_dashboard(flask_app):

    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname="/dash/oee/",
        suppress_callback_exceptions=True
    )

    try:
        r = requests.get(f"{MES_API}/machines", timeout=3)
        machines = r.json()
    except Exception:
        machines = []

    codes = [m["code"] for m in machines]
    fig = px.bar(x=codes, y=[1] * len(codes), title="Machine Availability (placeholder)")

    dash_app.layout = html.Div([
        html.H2("OEE Dashboard"),
        html.P("Placeholder OEE values – live integration coming soon."),
        dcc.Graph(figure=fig)
    ])

    return dash_app
