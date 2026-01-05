import dash
from dash import html, dcc, Input, Output, State
import requests
from datetime import timedelta, date
import plotly.graph_objects as go
import logging

MES_API = "http://localhost:8000"
log = logging.getLogger(__name__)


def fetch_machines():
    try:
        r = requests.get(f"{MES_API}/machines", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def fetch_oee(machine_code: str, start_ts: str, end_ts: str):
    params = {"machine_code": machine_code, "start_ts": start_ts, "end_ts": end_ts}
    r = requests.get(f"{MES_API}/oee", params=params, timeout=5)
    r.raise_for_status()
    return r.json()


def fmt_min(m): return "-" if m is None else f"{m:.1f}"
def fmt_min_with_unit(m): return "-" if m is None else f"{m:.1f} min"
def fmt_pct(v): return "-" if v is None else f"{v * 100:.1f}%"
def fmt_units(v): return "-" if v is None else f"{v:,.0f}"


def render_loss_tree(oee_data):
    totals = {t["metric"]: t["minutes"] for t in oee_data.get("totals", [])}
    oee = oee_data.get("oee", {})
    by_reason = oee_data.get("by_reason", [])
    system_stats = oee_data.get("system_stop_stats", [])
    stop_stats = oee_data.get("stop_stats", [])

    planned = oee.get("planned_time_min", 0.0)
    runtime = oee.get("runtime_min", 0.0)
    pdt = oee.get("pdt_min", 0.0)
    updt = oee.get("updt_min", 0.0)
    calendar = totals.get("TOTAL_INTERVAL", planned)
    excluded = max(calendar - planned, 0.0)
    days = calendar / 60.0 / 24.0 if calendar else 0.0

    bucket_stats = {s["bucket"]: s for s in system_stats}
    pdt_sys = bucket_stats.get("PDT", {"stop_count": 0, "total_downtime_min": pdt, "avg_stop_min": None})
    updt_sys = bucket_stats.get("UPDT", {"stop_count": 0, "total_downtime_min": updt, "avg_stop_min": None, "mtbf_min": None})
    avg_updt_per_day = (updt_sys["stop_count"] / days) if days and updt_sys["stop_count"] else 0.0

    def share_of_planned(mins):
        if not planned:
            return "-"
        return f"{mins / planned * 100:.1f}%"

    pdt_reasons = [r for r in by_reason if r["reason_category"] == "PDT"]

    cell = {"padding": "2px 6px", "borderBottom": "1px solid #eee", "fontSize": "12px"}
    header_row = {"backgroundColor": "#f0f0f0", "fontWeight": "600", "borderBottom": "1px solid #ccc"}

    header_table = html.Table([
        html.Tbody([
            html.Tr([
                html.Td("Calendar Time (min)", style=cell),
                html.Td(fmt_min(calendar), style=cell),
                html.Td("Days", style=cell),
                html.Td(f"{days:.2f}" if days else "-", style=cell),
            ]),
            html.Tr([
                html.Td("Excluded Time (min)", style=cell),
                html.Td(fmt_min(excluded), style=cell),
                html.Td("Avg UPDT stops/day", style=cell),
                html.Td(f"{avg_updt_per_day:.1f}" if days else "-", style=cell),
            ]),
            html.Tr([
                html.Td("Scheduled Time (min)", style=cell),
                html.Td(fmt_min(planned), style=cell),
                html.Td("UPDT stops total", style=cell),
                html.Td(str(updt_sys["stop_count"]), style=cell),
            ]),
        ])
    ], style={"borderCollapse": "collapse", "width": "60%"})

    oee_summary_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Metric", style=cell),
            html.Th("Value", style=cell),
        ], style=header_row)),
        html.Tbody([
            html.Tr([html.Td("OEE", style=cell), html.Td(fmt_pct(oee.get("oee")), style=cell)]),
            html.Tr([html.Td("Availability", style=cell), html.Td(fmt_pct(oee.get("availability")), style=cell)]),
            html.Tr([html.Td("Scheduled time", style=cell), html.Td(fmt_min_with_unit(planned), style=cell)]),
            html.Tr([html.Td("Runtime", style=cell), html.Td(fmt_min_with_unit(runtime), style=cell)]),
            html.Tr([html.Td("PDT", style=cell), html.Td(f"{fmt_min_with_unit(pdt)} ({share_of_planned(pdt)})", style=cell)]),
            html.Tr([html.Td("UPDT", style=cell), html.Td(f"{fmt_min_with_unit(updt)} ({share_of_planned(updt)})", style=cell)]),
        ])
    ], style={"borderCollapse": "collapse", "width": "280px"})

    pdt_summary_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Stops", style=cell),
            html.Th("DT Min", style=cell),
            html.Th("% of scheduled", style=cell),
            html.Th("Avg stop (min)", style=cell),
        ], style=header_row)),
        html.Tbody([
            html.Tr([
                html.Td(str(pdt_sys.get("stop_count", 0)), style=cell),
                html.Td(fmt_min(pdt), style=cell),
                html.Td(share_of_planned(pdt), style=cell),
                html.Td(fmt_min(pdt_sys.get("avg_stop_min")), style=cell),
            ])
        ])
    ], style={"borderCollapse": "collapse", "width": "50%"})

    updt_summary_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Stops", style=cell),
            html.Th("DT Min", style=cell),
            html.Th("% of scheduled", style=cell),
            html.Th("MTBF (min)", style=cell),
            html.Th("Avg stop (min)", style=cell),
        ], style=header_row)),
        html.Tbody([
            html.Tr([
                html.Td(str(updt_sys.get("stop_count", 0)), style=cell),
                html.Td(fmt_min(updt), style=cell),
                html.Td(share_of_planned(updt), style=cell),
                html.Td(fmt_min(updt_sys.get("mtbf_min")), style=cell),
                html.Td(fmt_min(updt_sys.get("avg_stop_min")), style=cell),
            ])
        ])
    ], style={"borderCollapse": "collapse", "width": "60%"})

    pdt_detail_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Reason", style=cell),
            html.Th("DT Min", style=cell),
            html.Th("% of scheduled", style=cell),
        ], style=header_row)),
        html.Tbody([
            html.Tr([
                html.Td(r["reason_code"], style=cell),
                html.Td(fmt_min(r["minutes"]), style=cell),
                html.Td(share_of_planned(r["minutes"]), style=cell),
            ]) for r in pdt_reasons
        ])
    ], style={"borderCollapse": "collapse", "width": "100%", "marginTop": "4px"})

    updt_detail_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Reason", style=cell),
            html.Th("Stops", style=cell),
            html.Th("DT Min", style=cell),
            html.Th("% of scheduled", style=cell),
            html.Th("MTTR (min)", style=cell),
            html.Th("MTBF (min)", style=cell),
        ], style=header_row)),
        html.Tbody([
            html.Tr([
                html.Td(s["reason_code"], style=cell),
                html.Td(str(s["stop_count"]), style=cell),
                html.Td(fmt_min(s["total_downtime_min"]), style=cell),
                html.Td(share_of_planned(s["total_downtime_min"]), style=cell),
                html.Td(fmt_min(s["mttr_min"]), style=cell),
                html.Td(fmt_min(s["mtbf_min"]), style=cell),
            ]) for s in stop_stats
        ])
    ], style={"borderCollapse": "collapse", "width": "100%", "marginTop": "4px"})

    raw_speed_loss_min = oee.get("speed_loss_min")
    raw_quality_loss_min = oee.get("quality_loss_min")

    # If speed/quality loss cannot be computed, treat them as zero.
    speed_loss_min = raw_speed_loss_min if raw_speed_loss_min is not None else 0.0
    quality_loss_min = raw_quality_loss_min if raw_quality_loss_min is not None else 0.0

    # Loss percentages based on scheduled time (minutes equivalent / planned time)
    speed_loss_pct_of_planned = (
        (speed_loss_min / planned) if planned else None
    )
    quality_loss_pct_of_planned = (
        (quality_loss_min / planned) if planned else None
    )

    speed_loss_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Metric", style=cell),
            html.Th("Value", style=cell),
        ], style=header_row)),
        html.Tbody([
            html.Tr([
                html.Td("Minutes lost", style=cell),
                html.Td(fmt_min(speed_loss_min), style=cell),
            ]),
            html.Tr([
                html.Td("OEE loss (performance)", style=cell),
                html.Td(fmt_pct(speed_loss_pct_of_planned), style=cell),
            ]),
        ])
    ], style={"borderCollapse": "collapse", "width": "220px"})

    quality_loss_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Metric", style=cell),
            html.Th("Value", style=cell),
        ], style=header_row)),
        html.Tbody([
            html.Tr([
                html.Td("Minutes lost", style=cell),
                html.Td(fmt_min(quality_loss_min), style=cell),
            ]),
            html.Tr([
                html.Td("OEE loss (quality)", style=cell),
                html.Td(fmt_pct(quality_loss_pct_of_planned), style=cell),
            ]),
        ])
    ], style={"borderCollapse": "collapse", "width": "220px"})

    # -----------------------------
    # Mini OEE dashboard (top strip)
    # -----------------------------
    oee_value = oee.get("oee")
    # Use 0% for OEE in the bar when it cannot be computed
    oee_pct_for_bar = oee_value if (oee_value is not None and oee_value > 0.0) else 0.0

    # Build a 100%-stacked breakdown whose "OEE" slice
    # matches the numeric OEE value (or 0% if not available),
    # and the loss slices are proportional to their minutes.
    planned_min = planned or 0.0
    labels = []
    values = []
    colors = []

    if planned_min > 0:
        pdt_min = max(pdt or 0.0, 0.0)
        updt_min = max(updt or 0.0, 0.0)
        speed_loss_min_val = max(speed_loss_min or 0.0, 0.0)
        quality_loss_min_val = max(quality_loss_min or 0.0, 0.0)

        # Loss shares from minutes
        pdt_pct = pdt_min / planned_min
        updt_pct = updt_min / planned_min
        speed_pct = speed_loss_min_val / planned_min
        quality_pct = quality_loss_min_val / planned_min

        loss_sum = pdt_pct + updt_pct + speed_pct + quality_pct
        remaining_for_losses = max(1.0 - oee_pct_for_bar, 0.0)

        # Debug logging for mini-bar composition
        log.info(
            "OEE mini-bar: planned_min=%s, oee_value=%s, "
            "pdt_min=%s, updt_min=%s, speed_loss_min=%s, quality_loss_min=%s, "
            "pdt_pct=%s, updt_pct=%s, speed_pct=%s, quality_pct=%s, "
            "loss_sum=%s, remaining_for_losses=%s",
            planned_min,
            oee_value,
            pdt_min,
            updt_min,
            speed_loss_min_val,
            quality_loss_min_val,
            pdt_pct,
            updt_pct,
            speed_pct,
            quality_pct,
            loss_sum,
            remaining_for_losses,
        )

        if loss_sum > 0 and remaining_for_losses > 0:
            scale = remaining_for_losses / loss_sum
            # Non-OEE components first so OEE appears last/right
            components = [
                ("PDT", pdt_pct * scale, "#ffb74d"),
                ("UPDT", updt_pct * scale, "#e57373"),
                ("Speed loss", speed_pct * scale, "#64b5f6"),
                ("Quality loss", quality_pct * scale, "#ba68c8"),
                ("OEE", oee_pct_for_bar, "#2e7d32"),
            ]
        else:
            # No visible losses -> pure OEE bar
            components = [("OEE", oee_pct_for_bar, "#2e7d32")]

        total = sum(v for _, v, _ in components)
        log.info("OEE mini-bar components (raw): %s (total=%s)", components, total)
        if total > 0:
            for label, val, col in components:
                labels.append(label)
                values.append(val / total)
                colors.append(col)

    if values:
        # One trace per component so they truly stack
        traces = []
        for label, val, col in zip(labels, values, colors):
            opacity = 1.0 if label == "OEE" else 0.5
            traces.append(
                go.Bar(
                    x=[val],
                    y=["OEE breakdown"],
                    orientation="h",
                    marker=dict(color=col, opacity=opacity),
                    text=[f"{val * 100:.1f}%"],
                    textposition="inside",
                    textfont=dict(size=12),
                    hovertemplate=f"{label}: {{x:.1%}}<extra></extra>",
                    customdata=[[label]],
                    name=label,
                )
            )
        fig = go.Figure(data=traces)
        fig.update_layout(
            barmode="stack",
            showlegend=False,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[0, 1]),
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            height=80,
        )
    else:
        fig = go.Figure()
        fig.update_layout(
            showlegend=False,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            height=80,
        )

    oee_value_text = "-" if oee_value is None else f"{oee_value * 100:.2f}%"

    mini_dashboard = html.Div([
        html.Div([
            html.Div("OEE", style={"fontSize": "12px", "color": "#666"}),
            html.Div(
                oee_value_text,
                style={"fontSize": "28px", "fontWeight": "700", "color": "#2e7d32"},
            ),
        ], style={"marginRight": "24px", "minWidth": "120px"}),
        html.Div([
            dcc.Graph(
                id="oee-mini-bar",
                figure=fig,
                config={"displayModeBar": False},
                style={"height": "80px", "width": "360px"},
            )
        ]),
    ], style={
        "display": "flex",
        "alignItems": "center",
        "columnGap": "12px",
        "margin": "8px 0 16px 0",
    })

    return html.Div([
        mini_dashboard,

        html.Div([
            html.Div("Period summary", style={"fontWeight": "600", "marginBottom": "4px"}),
            header_table,
        ], style={
            "backgroundColor": "#fafafa",
            "border": "1px solid #ddd",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "marginBottom": "16px"
        }),

        html.Div([
            html.Div("OEE summary", style={"fontWeight": "600", "marginBottom": "4px"}),
            oee_summary_table,
        ], style={
            "backgroundColor": "#fdfdfd",
            "border": "1px solid #ddd",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "marginBottom": "16px"
        }),

        html.Div([
            html.Div("PDT – Planned Downtime", style={"fontWeight": "600", "marginBottom": "4px"}),
            pdt_summary_table,
            pdt_detail_table,
        ], style={
            "backgroundColor": "#f7fbff",
            "border": "1px solid #c7dfff",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "marginBottom": "16px"
        }),

        html.Div([
            html.Div("UPDT – Unplanned Downtime", style={"fontWeight": "600", "marginBottom": "4px"}),
            updt_summary_table,
            updt_detail_table,
        ], style={
            "backgroundColor": "#fff7f7",
            "border": "1px solid #ffcccc",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "marginBottom": "16px"
        }),

        html.Div([
            html.Div("Rate loss (speed)", style={"fontWeight": "600", "marginBottom": "4px"}),
            speed_loss_table,
        ], style={
            "backgroundColor": "#fdfbf4",
            "border": "1px solid #eddca9",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "marginBottom": "16px"
        }),

        html.Div([
            html.Div("Quality loss", style={"fontWeight": "600", "marginBottom": "4px"}),
            quality_loss_table,
        ], style={
            "backgroundColor": "#fdfbf4",
            "border": "1px solid #eddca9",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "marginBottom": "16px"
        }),
    ])


def init_dashboard(flask_app):

    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname="/dash/oee/",
        suppress_callback_exceptions=True
    )

    today = date.today()
    default_start_date = today - timedelta(days=6)
    default_end_date = today

    dash_app.layout = html.Div([
        html.H2("OEE / Loss Tree Dashboard"),

        html.Div([
            html.Div([
                html.Label("Department"),
                dcc.Dropdown(
                    id="oee-department",
                    options=[],
                    value=None,
                    placeholder="Select department",
                    clearable=True,
                    style={"width": "220px"}
                ),
            ], style={"marginRight": "16px"}),

            html.Div([
                html.Label("Line"),
                dcc.Dropdown(
                    id="oee-line",
                    options=[],
                    value=None,
                    placeholder="Select line",
                    clearable=True,
                    style={"width": "220px"}
                ),
            ], style={"marginRight": "16px"}),

            html.Div([
                html.Label("Machine"),
                dcc.Dropdown(
                    id="oee-machine",
                    options=[],
                    value=None,
                    placeholder="Select machine",
                    clearable=False,
                    style={"width": "220px"}
                )
            ], style={"marginRight": "16px"}),

            html.Div([
                html.Label("Date range"),
                dcc.DatePickerRange(
                    id="oee-date-range",
                    start_date=default_start_date,
                    end_date=default_end_date,
                    display_format="YYYY-MM-DD",
                    minimum_nights=0,
                )
            ], style={"marginRight": "16px"}),

            html.Div([
                html.Label("Start time"),
                dcc.Input(
                    id="oee-start-time",
                    type="time",
                    value="06:00",
                    style={"width": "120px"}
                )
            ], style={"marginRight": "16px"}),

            html.Div([
                html.Label("End time"),
                dcc.Input(
                    id="oee-end-time",
                    type="time",
                    value="18:00",
                    style={"width": "120px"}
                )
            ]),
            html.Button(
                "Refresh",
                id="oee-refresh",
                n_clicks=0,
                style={"marginLeft": "16px", "marginTop": "18px"}
            )
        ], style={
            "display": "flex",
            "flexWrap": "wrap",
            "alignItems": "flex-end",
            "columnGap": "8px"
        }),

        html.Div(style={
            "backgroundColor": "#f5f5f5",
            "border": "1px solid #ddd",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "margin": "12px 0 16px 0"
        }, children=[
            html.Div("Controls", style={"fontWeight": "600", "marginBottom": "4px"}),
            html.Div("Select machine and time window, then press Refresh.",
                     style={"fontSize": "12px"})
        ]),

        dcc.Store(id="oee-machines-store"),
        dcc.Interval(id="oee-machine-loader", interval=500, n_intervals=0, max_intervals=1),

        html.Div(id="oee-machine-error", style={"color": "red", "marginBottom": "4px"}),
        html.Div(id="oee-error", style={"color": "red", "marginBottom": "8px"}),
        html.Div(id="oee-loss-tree-container")
    ])

    @dash_app.callback(
        Output("oee-machines-store", "data"),
        Output("oee-department", "options"),
        Output("oee-department", "value"),
        Output("oee-machine-error", "children"),
        Input("oee-machine-loader", "n_intervals"),
        prevent_initial_call=False,
    )
    def load_machines(n_intervals):
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
        Output("oee-line", "options"),
        Output("oee-line", "value"),
        Input("oee-department", "value"),
        State("oee-machines-store", "data"),
        State("oee-line", "value"),
    )
    def update_lines(selected_department, machines, current_line):
        if not machines:
            return [], None

        filtered = machines
        if selected_department:
            filtered = [
                m for m in machines
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
        Output("oee-machine", "options"),
        Output("oee-machine", "value"),
        Input("oee-department", "value"),
        Input("oee-line", "value"),
        State("oee-machines-store", "data"),
        State("oee-machine", "value"),
    )
    def update_machines(selected_department, selected_line, machines, current_machine):
        if not machines:
            return [], None

        filtered = machines
        if selected_department:
            filtered = [
                m for m in filtered
                if m.get("department_code") == selected_department
            ]
        if selected_line:
            filtered = [
                m for m in filtered
                if m.get("line_code") == selected_line
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
        if current_machine and any(opt["value"] == current_machine for opt in machine_options):
            selected_machine = current_machine
        elif machine_options:
            selected_machine = machine_options[0]["value"]

        return machine_options, selected_machine

    @dash_app.callback(
        Output("oee-loss-tree-container", "children"),
        Output("oee-error", "children"),
        Input("oee-refresh", "n_clicks"),
        State("oee-machine", "value"),
        State("oee-date-range", "start_date"),
        State("oee-date-range", "end_date"),
        State("oee-start-time", "value"),
        State("oee-end-time", "value"),
        prevent_initial_call=False
    )
    def update_loss_tree(n_clicks, machine_code, start_date, end_date, start_time, end_time):
        if not machine_code:
            return html.Div("No machine selected."), ""
        if not start_date or not end_date or not start_time or not end_time:
            return html.Div("Please select date range and times."), ""

        def to_iso(d, t):
            t_str = t if len(t) == 8 else (t + ":00" if len(t) == 5 else t)
            return f"{d}T{t_str}"

        start_iso = to_iso(start_date, start_time)
        end_iso = to_iso(end_date, end_time)

        try:
            oee_data = fetch_oee(machine_code, start_iso, end_iso)
        except Exception as e:
            return html.Div(), f"Error calling /oee: {e}"

        return render_loss_tree(oee_data), ""

    return dash_app
