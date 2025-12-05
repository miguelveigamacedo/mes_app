from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
import requests

from dash_app.oee_dash import init_dashboard
from dash_app.events_dash import init_events_dashboard

FASTAPI_BASE = "http://localhost:8000"


def create_app():
    app = Flask(__name__)
    app.secret_key = "change-this-in-prod"

    # Dash apps
    init_dashboard(app)         # /dash/oee/
    init_events_dashboard(app)  # /dash/events/

    # -----------------------------
    # Helper: ISA-95 hierarchy
    # -----------------------------
    def build_isa95_hierarchy():
        depts = requests.get(f"{FASTAPI_BASE}/departments", timeout=3).json()
        lines = requests.get(f"{FASTAPI_BASE}/lines", timeout=3).json()
        machines = requests.get(f"{FASTAPI_BASE}/machines", timeout=3).json()

        dept_map = {d["id"]: {**d, "lines": []} for d in depts}
        line_map = {}

        for l in lines:
            line_obj = {**l, "machines": []}
            line_map[l["id"]] = line_obj
            dept = dept_map.get(l["department_id"])
            if dept:
                dept["lines"].append(line_obj)

        for m in machines:
            line_id = m.get("line_id")
            if line_id and line_id in line_map:
                line_map[line_id]["machines"].append(m)

        hierarchy = list(dept_map.values())
        hierarchy.sort(key=lambda d: d["code"])
        for d in hierarchy:
            d["lines"].sort(key=lambda l: l["code"])
            for l in d["lines"]:
                l["machines"].sort(key=lambda m: m["code"])

        return hierarchy, depts, lines, machines

    # -----------------------------
    # Core pages
    # -----------------------------
    @app.route("/")
    def index():
        return render_template("index.html", title="MES Dashboard")

    @app.route("/machines")
    def machines_page():
        hierarchy, depts, lines, machines = build_isa95_hierarchy()
        return render_template(
            "machines.html",
            hierarchy=hierarchy,
            departments=depts,
            lines=lines,
            machines=machines,
            title="ISA-95 Structure",
        )

    @app.route("/oee")
    def oee_page():
        return render_template("oee.html", title="OEE Dashboard")

    @app.route("/events")
    def events_page():
        return render_template("events.html", title="Events")

    # Optional alias for plant model
    @app.route("/isa95")
    def isa95_overview():
        return machines_page()

    # -----------------------------
    # ISA-95 create endpoints
    # -----------------------------
    @app.route("/isa95/department", methods=["POST"])
    def isa95_create_department():
        payload = {
            "code": request.form.get("code"),
            "name": request.form.get("name"),
            "description": request.form.get("description") or None,
            "is_active": True,
        }
        try:
            requests.post(
                f"{FASTAPI_BASE}/departments", json=payload, timeout=3
            ).raise_for_status()
            flash("Department created", "success")
        except Exception as e:
            flash(f"Error creating department: {e}", "danger")
        return redirect(url_for("machines_page"))

    @app.route("/isa95/line", methods=["POST"])
    def isa95_create_line():
        payload = {
            "department_id": int(request.form.get("department_id")),
            "code": request.form.get("code"),
            "name": request.form.get("name"),
            "description": request.form.get("description") or None,
            "is_active": True,
        }
        try:
            requests.post(
                f"{FASTAPI_BASE}/lines", json=payload, timeout=3
            ).raise_for_status()
            flash("Line created", "success")
        except Exception as e:
            flash(f"Error creating line: {e}", "danger")
        return redirect(url_for("machines_page"))

    @app.route("/isa95/machine", methods=["POST"])
    def isa95_create_machine():
        line_id = request.form.get("line_id")
        payload = {
            "code": request.form.get("code"),
            "name": request.form.get("name"),
            "line_id": int(line_id) if line_id else None,
            "is_active": True,
        }
        try:
            requests.post(
                f"{FASTAPI_BASE}/machines", json=payload, timeout=3
            ).raise_for_status()
            flash("Machine created", "success")
        except Exception as e:
            flash(f"Error creating machine: {e}", "danger")
        return redirect(url_for("machines_page"))

    # -----------------------------
    # Products pages + actions
    # -----------------------------
    @app.route("/products", methods=["GET"])
    def products_page():
        r = requests.get(f"{FASTAPI_BASE}/products", timeout=3)
        products = r.json()
        return render_template(
            "products.html",
            products=products,
            title="Products",
        )

    @app.route("/products/create", methods=["POST"])
    def products_create():
        payload = {
            "code": request.form.get("code"),
            "name": request.form.get("name"),
            "pack_count": request.form.get("pack_count") or None,
            "nominal_speed": request.form.get("nominal_speed") or None,
            "target_oee": request.form.get("target_oee") or None,
        }
        if payload["pack_count"]:
            payload["pack_count"] = int(payload["pack_count"])
        else:
            payload["pack_count"] = None
        if payload["nominal_speed"]:
            payload["nominal_speed"] = int(payload["nominal_speed"])
        else:
            payload["nominal_speed"] = None
        if payload["target_oee"]:
            payload["target_oee"] = float(payload["target_oee"])
        else:
            payload["target_oee"] = None

        try:
            requests.post(
                f"{FASTAPI_BASE}/products", json=payload, timeout=3
            ).raise_for_status()
            flash("Product created", "success")
        except Exception as e:
            flash(f"Error creating product: {e}", "danger")
        return redirect(url_for("products_page"))

    @app.route("/products/update", methods=["POST"])
    def products_update():
        product_id = int(request.form.get("product_id"))
        payload = {
            "code": request.form.get("code") or None,
            "name": request.form.get("name") or None,
            "pack_count": request.form.get("pack_count") or None,
            "nominal_speed": request.form.get("nominal_speed") or None,
            "target_oee": request.form.get("target_oee") or None,
        }

        def to_int(v):
            return int(v) if v not in (None, "") else None

        def to_float(v):
            return float(v) if v not in (None, "") else None

        payload["pack_count"] = to_int(payload["pack_count"])
        payload["nominal_speed"] = to_int(payload["nominal_speed"])
        payload["target_oee"] = to_float(payload["target_oee"])

        try:
            requests.put(
                f"{FASTAPI_BASE}/products/{product_id}",
                json=payload,
                timeout=3,
            ).raise_for_status()
            flash("Product updated", "success")
        except Exception as e:
            flash(f"Error updating product: {e}", "danger")
        return redirect(url_for("products_page"))

    # -----------------------------
    # Orders pages + actions
    # -----------------------------
    @app.route("/orders", methods=["GET"])
    def orders_page():
        r_orders = requests.get(f"{FASTAPI_BASE}/order-runs", timeout=3)
        orders = r_orders.json()

        r_products = requests.get(f"{FASTAPI_BASE}/products", timeout=3)
        products = r_products.json()

        r_machines = requests.get(f"{FASTAPI_BASE}/machines", timeout=3)
        machines = r_machines.json()

        return render_template(
            "orders.html",
            orders=orders,
            products=products,
            machines=machines,
            title="Work Orders",
        )

    @app.route("/orders/create", methods=["POST"])
    def orders_create():
        def to_int(name):
            v = request.form.get(name)
            return int(v) if v not in (None, "") else None

        payload = {
            "workorder": request.form.get("workorder"),
            "machine_id": int(request.form.get("machine_id")),
            "product_id": to_int("product_id"),
            "planned_qty": to_int("planned_qty"),
            "start_ts": request.form.get("start_ts") or None,
            "end_ts": request.form.get("end_ts") or None,
            "status": request.form.get("status") or "Created",
            "qty_good": to_int("qty_good"),
            "qty_scrap": to_int("qty_scrap"),
            "runtime_sec": to_int("runtime_sec"),
        }

        try:
            requests.post(
                f"{FASTAPI_BASE}/order-runs",
                json=payload,
                timeout=3,
            ).raise_for_status()
            flash("Order created", "success")
        except Exception as e:
            flash(f"Error creating order: {e}", "danger")
        return redirect(url_for("orders_page"))

    @app.route("/orders/update", methods=["POST"])
    def orders_update():
        order_id = int(request.form.get("order_id"))

        def to_int(name):
            v = request.form.get(name)
            return int(v) if v not in (None, "") else None

        payload = {
            "workorder": request.form.get("workorder") or None,
            "machine_id": to_int("machine_id"),
            "product_id": to_int("product_id"),
            "planned_qty": to_int("planned_qty"),
            "start_ts": request.form.get("start_ts") or None,
            "end_ts": request.form.get("end_ts") or None,
            "status": request.form.get("status") or None,
            "qty_good": to_int("qty_good"),
            "qty_scrap": to_int("qty_scrap"),
            "runtime_sec": to_int("runtime_sec"),
        }

        try:
            requests.put(
                f"{FASTAPI_BASE}/order-runs/{order_id}",
                json=payload,
                timeout=3,
            ).raise_for_status()
            flash("Order updated", "success")
        except Exception as e:
            flash(f"Error updating order: {e}", "danger")
        return redirect(url_for("orders_page"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)

