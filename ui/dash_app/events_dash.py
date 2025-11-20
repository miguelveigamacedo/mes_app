import dash
from dash import html, dcc, dash_table, Input, Output, State
import requests
import pandas as pd
from datetime import datetime

MES_API = "http://localhost:8000"


def fetch_events():
    try:
        r = requests.get(f"{MES_API}/events", timeout=3)
        r.raise_for_status()
        data = r.json()
    except Exception:
        data = []

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["start_ts_dt"] = pd.to_datetime(df["start_ts"])
    df["start_date"] = df["start_ts_dt"].dt.strftime("%Y-%m-%d")
    df["start_time"] = df["start_ts_dt"].dt.strftime("%H:%M")
    return df


def fetch_reasons():
    try:
        r = requests.get(f"{MES_API}/reason-codes", timeout=3)
        r.raise_for_status()
        return r.json()
    except:
        return []


def init_events_dashboard(flask_app):
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname="/dash/events/",
        suppress_callback_exceptions=True,
    )

    df = fetch_events()

    display_cols = [
        "id",
        "machine_code",
        "workorder",
        "raw_reason_code",
        "start_date",
        "start_time",
        "end_ts",
        "duration_sec",
        "mes_reason_code",
        "category",
        "comment",
        "source_quality",
    ]

    if df.empty:
        machine_options = []
        data_rows = []
    else:
        machine_options = sorted(df["machine_code"].dropna().unique())
        data_rows = df[display_cols].to_dict("records")

    # Reason list for justification
    reasons = fetch_reasons()
    reason_options = [
        {"label": f"{r['code']} - {r.get('description', '')}", "value": r["id"]}
        for r in reasons
    ]

    columns = [
        {"name": "Event ID", "id": "id"},
        {"name": "Machine", "id": "machine_code"},
        {"name": "Work order", "id": "workorder"},
        {"name": "Status (raw)", "id": "raw_reason_code"},
        {"name": "Start date", "id": "start_date"},
        {"name": "Start time", "id": "start_time"},
        {"name": "End timestamp", "id": "end_ts"},
        {"name": "Duration (s)", "id": "duration_sec"},
        {"name": "Reason (MES)", "id": "mes_reason_code"},
        {"name": "Category", "id": "category"},
        {"name": "Comment", "id": "comment"},
        {"name": "Origin", "id": "source_quality"},
    ]

    dash_app.layout = html.Div(
        [
            # Filters
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Machine"),
                            dcc.Dropdown(
                                id="machine-filter",
                                options=[{"label": m, "value": m} for m in machine_options],
                                placeholder="All machines",
                                clearable=True,
                            ),
                        ],
                        style={"width": "25%", "display": "inline-block", "marginRight": "20px"},
                    ),
                    html.Div(
                        [
                            html.Label("From (date and time)"),
                            html.Div(
                                [
                                    dcc.DatePickerSingle(
                                        id="from-date",
                                        display_format="YYYY-MM-DD",
                                    ),
                                    dcc.Input(
                                        id="from-time",
                                        type="text",
                                        placeholder="HH:MM",
                                        style={"width": "80px", "marginLeft": "8px"},
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ],
                        style={"width": "30%", "display": "inline-block", "marginRight": "20px"},
                    ),
                    html.Div(
                        [
                            html.Label("To (date and time)"),
                            html.Div(
                                [
                                    dcc.DatePickerSingle(
                                        id="to-date",
                                        display_format="YYYY-MM-DD",
                                    ),
                                    dcc.Input(
                                        id="to-time",
                                        type="text",
                                        placeholder="HH:MM",
                                        style={"width": "80px", "marginLeft": "8px"},
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ],
                        style={"width": "30%", "display": "inline-block"},
                    ),
                ],
                style={"marginBottom": "15px"},
            ),

            # Events Table
            dash_table.DataTable(
                id="events-table",
                columns=columns,
                data=data_rows,
                page_size=20,
                row_selectable="single",
                selected_rows=[],
                style_table={
                    "overflowX": "auto",
                    "minHeight": "300px",
                    "border": "1px solid #ccc",
                },
                style_cell={"fontSize": 12, "padding": "4px"},
                style_header={"fontWeight": "bold"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": '{raw_reason_code} = "RUNNING"'},
                        "backgroundColor": "#d4edda",
                        "color": "#155724",
                    },
                    {
                        "if": {"filter_query": '{raw_reason_code} = "OFF"'},
                        "backgroundColor": "#e2e3e5",
                        "color": "#383d41",
                    },
                    {
                        "if": {
                            "filter_query": (
                                '{raw_reason_code} != "RUNNING" && '
                                '{raw_reason_code} != "OFF" && '
                                '({mes_reason_code} = "" || {mes_reason_code} is blank)'
                            )
                        },
                        "backgroundColor": "#f5c6cb",
                        "color": "#721c24",
                    },
                ],
            ),

            html.Hr(),

            # Justification Panel
            html.Label("Reason (MES)"),
            dcc.Dropdown(
                id="reason-select",
                options=reason_options,
                placeholder="Select MES Reason",
                clearable=True,
            ),
            html.Br(),
            html.Label("Comment"),
            dcc.Textarea(id="comment-input", style={"width": "100%", "height": "70px"}),
            html.Br(),
            html.Button("Save Justification", id="btn-justify", n_clicks=0),
            html.Div(id="justify-status", style={"marginTop": "10px"}),
        ]
    )

    # Table filter callback (unchanged)
    @dash_app.callback(
        Output("events-table", "data"),
        Input("machine-filter", "value"),
        Input("from-date", "date"),
        Input("from-time", "value"),
        Input("to-date", "date"),
        Input("to-time", "value"),
    )
    def update_table(machine_value, from_date, from_time, to_date, to_time):
        df_local = fetch_events()
        if df_local.empty:
            return []

        if machine_value:
            df_local = df_local[df_local["machine_code"] == machine_value]

        def parse_dt(date_str, time_str, default_time):
            if not date_str:
                return None
            t = time_str.strip() if time_str else default_time
            try:
                return datetime.strptime(f"{date_str} {t}", "%Y-%m-%d %H:%M")
            except:
                return None

        from_dt = parse_dt(from_date, from_time, "00:00")
        to_dt = parse_dt(to_date, to_time, "23:59")

        if from_dt:
            df_local = df_local[df_local["start_ts_dt"] >= from_dt]
        if to_dt:
            df_local = df_local[df_local["start_ts_dt"] <= to_dt]

        if df_local.empty:
            return []

        return df_local[display_cols].to_dict("records")

    # Justification callback
    @dash_app.callback(
        Output("justify-status", "children"),
        Output("events-table", "data", allow_duplicate=True),
        Input("btn-justify", "n_clicks"),
        State("events-table", "selected_rows"),
        State("events-table", "data"),
        State("reason-select", "value"),
        State("comment-input", "value"),
        State("machine-filter", "value"),
        State("from-date", "date"),
        State("from-time", "value"),
        State("to-date", "date"),
        State("to-time", "value"),
        prevent_initial_call=True
    )
    def justify_event(n_clicks, selected_rows, table_data,
                      reason_id, comment,
                      machine_value, from_date, from_time, to_date, to_time):

        if not selected_rows:
            return "Select an event first.", dash.no_update

        if reason_id is None:
            return "Select MES reason.", dash.no_update

        row_index = selected_rows[0]
        event_id = table_data[row_index]["id"]

        try:
            r = requests.post(
                f"{MES_API}/events/{event_id}/justify",
                json={"reason_code_id": reason_id, "comment": comment or ""},
                timeout=3,
            )
            r.raise_for_status()
        except Exception as e:
            return f"Error saving justification: {e}", dash.no_update

        # Reload table with current filters
        df_local = fetch_events()

        if machine_value:
            df_local = df_local[df_local["machine_code"] == machine_value]

        def parse_dt(date_str, time_str, default_time):
            if not date_str:
                return None
            t = time_str.strip() if time_str else default_time
            try:
                return datetime.strptime(f"{date_str} {t}", "%Y-%m-%d %H:%M")
            except:
                return None

        from_dt = parse_dt(from_date, from_time, "00:00")
        to_dt = parse_dt(to_date, to_time, "23:59")

        if from_dt:
            df_local = df_local[df_local["start_ts_dt"] >= from_dt]
        if to_dt:
            df_local = df_local[df_local["start_ts_dt"] <= to_dt]

        if df_local.empty:
            return "Justified. No rows match filters.", []

        return "Justification saved.", df_local[display_cols].to_dict("records")

    return dash_app
