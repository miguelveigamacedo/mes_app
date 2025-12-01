import dash
from dash import html, dcc, Input, Output, State
import requests
from datetime import timedelta, date

MES_API = "http://localhost:8000"


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

    return html.Div([
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
    ])


def init_dashboard(flask_app):

    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname="/dash/oee/",
        suppress_callback_exceptions=True
    )

    machines = fetch_machines()
    machine_options = [{"label": m["name"], "value": m["code"]} for m in machines]
    default_machine = machine_options[0]["value"] if machine_options else None

    today = date.today()
    default_start_date = today - timedelta(days=6)
    default_end_date = today

    dash_app.layout = html.Div([
        html.H2("OEE / Loss Tree Dashboard"),

        html.Div([
            html.Div([
                html.Label("Machine"),
                dcc.Dropdown(
                    id="oee-machine",
                    options=machine_options,
                    value=default_machine,
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

        html.Div(id="oee-error", style={"color": "red", "marginBottom": "8px"}),
        html.Div(id="oee-loss-tree-container")
    ])

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
