import dash
from dash import html, dcc, Input, Output, State
from datetime import timedelta, date

from .oee_dash import fetch_machines


def init_historical_dashboard(flask_app):
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname="/dash/historical/",
        suppress_callback_exceptions=True,
    )

    today = date.today()
    default_start_date = today - timedelta(days=30)
    default_end_date = today

    dash_app.layout = html.Div(
        [
            html.H2("Historical Performance"),
            html.P(
                "Explore historical performance per shift. "
                "Selectors mirror the OEE dashboard and will be used for charts later."
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Department"),
                            dcc.Dropdown(
                                id="hist-department",
                                options=[],
                                value=None,
                                placeholder="Select department",
                                clearable=True,
                                style={"width": "220px"},
                            ),
                        ],
                        style={"marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            html.Label("Line"),
                            dcc.Dropdown(
                                id="hist-line",
                                options=[],
                                value=None,
                                placeholder="Select line",
                                clearable=True,
                                style={"width": "220px"},
                            ),
                        ],
                        style={"marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            html.Label("Machine"),
                            dcc.Dropdown(
                                id="hist-machine",
                                options=[],
                                value=None,
                                placeholder="Select machine",
                                clearable=False,
                                style={"width": "220px"},
                            ),
                        ],
                        style={"marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            html.Label("Date range"),
                            dcc.DatePickerRange(
                                id="hist-date-range",
                                start_date=default_start_date,
                                end_date=default_end_date,
                                display_format="YYYY-MM-DD",
                            ),
                        ],
                        style={"marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            html.Label("Start time"),
                            dcc.Input(
                                id="hist-start-time",
                                type="time",
                                value="06:00",
                                style={"width": "120px"},
                            ),
                        ],
                        style={"marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            html.Label("End time"),
                            dcc.Input(
                                id="hist-end-time",
                                type="time",
                                value="18:00",
                                style={"width": "120px"},
                            ),
                        ]
                    ),
                    html.Button(
                        "Refresh",
                        id="hist-refresh",
                        n_clicks=0,
                        style={"marginLeft": "16px", "marginTop": "18px"},
                    ),
                ],
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "alignItems": "flex-end",
                    "columnGap": "8px",
                },
            ),
            html.Div(
                style={
                    "backgroundColor": "#f5f5f5",
                    "border": "1px solid #ddd",
                    "borderRadius": "6px",
                    "padding": "8px 12px",
                    "margin": "12px 0 16px 0",
                },
                children=[
                    html.Div(
                        "Controls",
                        style={"fontWeight": "600", "marginBottom": "4px"},
                    ),
                    html.Div(
                        "Select scope and time window, then press Refresh.",
                        style={"fontSize": "12px"},
                    ),
                ],
            ),
            dcc.Store(id="hist-machines-store"),
            dcc.Interval(
                id="hist-machine-loader",
                interval=500,
                n_intervals=0,
                max_intervals=1,
            ),
            html.Div(
                id="hist-machine-error",
                style={"color": "red", "marginBottom": "4px"},
            ),
            html.Div(
                id="hist-error",
                style={"color": "red", "marginBottom": "8px"},
            ),
            html.Div(
                id="hist-content",
                children=html.Div(
                    "Charts will appear here once implemented.",
                    style={"fontStyle": "italic", "color": "#555"},
                ),
            ),
        ]
    )

    @dash_app.callback(
        Output("hist-machines-store", "data"),
        Output("hist-department", "options"),
        Output("hist-department", "value"),
        Output("hist-machine-error", "children"),
        Input("hist-machine-loader", "n_intervals"),
        prevent_initial_call=False,
    )
    def load_machines(_n):
        machines = fetch_machines()
        if not machines:
            return [], [], None, "No machines available. Check the API connection."

        dept_map = {}
        for m in machines:
            dept_code = m.get("department_code")
            dept_name = m.get("department_name")
            if not dept_code:
                continue
            if dept_code not in dept_map:
                label = f"{dept_code} – {dept_name}" if dept_name else dept_code
                dept_map[dept_code] = {"label": label, "value": dept_code}

        dept_options = sorted(dept_map.values(), key=lambda d: d["value"])
        default_dept = dept_options[0]["value"] if dept_options else None
        return machines, dept_options, default_dept, ""

    @dash_app.callback(
        Output("hist-line", "options"),
        Output("hist-line", "value"),
        Input("hist-department", "value"),
        State("hist-machines-store", "data"),
        State("hist-line", "value"),
    )
    def update_lines(selected_department, machines, current_line):
        if not machines:
            return [], None

        filtered = machines
        if selected_department:
            filtered = [
                m
                for m in machines
                if m.get("department_code") == selected_department
            ]

        line_map = {}
        for m in filtered:
            line_code = m.get("line_code")
            line_name = m.get("line_name")
            if not line_code:
                continue
            if line_code not in line_map:
                label = f"{line_code} – {line_name}" if line_name else line_code
                line_map[line_code] = {"label": label, "value": line_code}

        line_options = sorted(line_map.values(), key=lambda l: l["value"])

        selected_line = None
        if current_line and any(opt["value"] == current_line for opt in line_options):
            selected_line = current_line
        elif line_options:
            selected_line = line_options[0]["value"]

        return line_options, selected_line

    @dash_app.callback(
        Output("hist-machine", "options"),
        Output("hist-machine", "value"),
        Input("hist-department", "value"),
        Input("hist-line", "value"),
        State("hist-machines-store", "data"),
        State("hist-machine", "value"),
    )
    def update_machines(selected_department, selected_line, machines, current_machine):
        if not machines:
            return [], None

        filtered = machines
        if selected_department:
            filtered = [
                m
                for m in filtered
                if m.get("department_code") == selected_department
            ]
        if selected_line:
            filtered = [
                m for m in filtered if m.get("line_code") == selected_line
            ]

        machine_map = {}
        for m in filtered:
            code = m.get("code")
            name = m.get("name")
            if not code:
                continue
            if code not in machine_map:
                label = f"{code} – {name}" if name else code
                machine_map[code] = {"label": label, "value": code}

        machine_options = sorted(machine_map.values(), key=lambda x: x["value"])

        selected_machine = None
        if current_machine and any(
            opt["value"] == current_machine for opt in machine_options
        ):
            selected_machine = current_machine
        elif machine_options:
            selected_machine = machine_options[0]["value"]

        return machine_options, selected_machine

    @dash_app.callback(
        Output("hist-content", "children"),
        Output("hist-error", "children"),
        Input("hist-refresh", "n_clicks"),
        State("hist-machine", "value"),
        State("hist-date-range", "start_date"),
        State("hist-date-range", "end_date"),
        State("hist-start-time", "value"),
        State("hist-end-time", "value"),
        prevent_initial_call=False,
    )
    def update_placeholder(
        _n,
        machine_code,
        start_date,
        end_date,
        start_time,
        end_time,
    ):
        if not machine_code:
            return html.Div("No machine selected."), ""
        if not start_date or not end_date or not start_time or not end_time:
            return html.Div("Please select date range and times."), ""

        summary = html.Ul(
            [
                html.Li(f"Machine: {machine_code}"),
                html.Li(f"Date range: {start_date} to {end_date}"),
                html.Li(f"Time: {start_time} – {end_time}"),
            ]
        )
        return html.Div(
            [
                html.Div(
                    "Historical performance charts will be implemented here.",
                    style={
                        "fontWeight": "600",
                        "marginBottom": "8px",
                    },
                ),
                summary,
            ]
        ), ""

    return dash_app

