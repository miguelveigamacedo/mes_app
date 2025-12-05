from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .db import get_connection
from datetime import datetime
from typing import Optional
from .oee_repository import fetch_clipped_events
from .oee_service import (
    build_enriched_events,
    compute_totals,
    compute_by_reason,
    serialize_events,
    compute_stop_stats,        # new
    compute_system_stop_stats, # new
    compute_oee,               # new
)




class MachineCreate(BaseModel):
    code: str
    name: str
    is_active: bool = True


class EventUpdate(BaseModel):
    reason_code_id: int | None = None
    comment: str | None = None

class JustifyEventRequest(BaseModel):
    reason_code_id: int
    comment: str | None = None

class DepartmentCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    is_active: bool = True


class LineCreate(BaseModel):
    department_id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool = True


class MachineCreate(BaseModel):
    code: str
    name: str
    line_id: int | None = None   # new
    is_active: bool = True

class ProductBase(BaseModel):
    code: str
    name: str
    pack_count: Optional[int] = None
    nominal_speed: Optional[int] = None
    target_oee: Optional[float] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    pack_count: Optional[int] = None
    nominal_speed: Optional[int] = None
    target_oee: Optional[float] = None


class OrderRunBase(BaseModel):
    workorder: str
    machine_id: int
    product_id: Optional[int] = None
    planned_qty: Optional[int] = None
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    status: str = "Created"
    qty_good: Optional[int] = None
    qty_scrap: Optional[int] = None
    runtime_sec: Optional[int] = None


class OrderRunCreate(OrderRunBase):
    pass


class OrderRunUpdate(BaseModel):
    workorder: Optional[str] = None
    machine_id: Optional[int] = None
    product_id: Optional[int] = None
    planned_qty: Optional[int] = None
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    status: Optional[str] = None
    qty_good: Optional[int] = None
    qty_scrap: Optional[int] = None
    runtime_sec: Optional[int] = None



app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/test-db")
def test_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT NOW();")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return {"db_time": result[0].isoformat()}

@app.get("/reason-codes")
def list_reason_codes():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, code, description, category
        FROM reason_code
        ORDER BY code
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/events")
def list_events():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            d.id,
            d.raw_event_id,
            m.code AS machine_code,
            d.workorder,
            d.raw_reason_code,
            d.start_ts,
            d.end_ts,
            d.duration_sec,
            rc.code AS mes_reason_code,
            rc.category,
            d.comment,
            d.source_quality
        FROM downtime_event d
        LEFT JOIN machine m
            ON d.machine_id = m.id
        LEFT JOIN reason_code rc
            ON d.reason_code_id = rc.id
        ORDER BY d.start_ts DESC
        LIMIT 200
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.post("/events/{event_id}/justify")
def justify_event(event_id: int, body: JustifyEventRequest):
    # 1) Check that the event exists
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id FROM downtime_event WHERE id = %s",
        (event_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    # 2) Update event with justification
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE downtime_event
            SET reason_code_id = %s,
                comment = %s,
                source_quality = 'Manual'
            WHERE id = %s
            """,
            (body.reason_code_id, body.comment or "", event_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        # Log to console and return clear error to client
        print("ERROR updating downtime_event:", e)
        raise HTTPException(status_code=500, detail=f"DB update failed: {e}")

    # 3) Read back minimal info to return
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, reason_code_id, comment, source_quality
        FROM downtime_event
        WHERE id = %s
        """,
        (event_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        # This should not happen if UPDATE succeeded, but be explicit
        raise HTTPException(status_code=500, detail="Event updated but could not be reloaded")

    return row

@app.get("/oee")
def get_oee(machine_code: str, start_ts: datetime, end_ts: datetime):
    if end_ts <= start_ts:
        raise HTTPException(status_code=400, detail="end_ts must be after start_ts")

    if start_ts.tzinfo is not None:
        start_ts = start_ts.replace(tzinfo=None)
    if end_ts.tzinfo is not None:
        end_ts = end_ts.replace(tzinfo=None)

    rows = fetch_clipped_events(machine_code, start_ts, end_ts)
    enriched_events = build_enriched_events(rows, start_ts, end_ts)

    totals = compute_totals(enriched_events, start_ts, end_ts)
    by_reason = compute_by_reason(enriched_events)
    stop_stats = compute_stop_stats(enriched_events, start_ts, end_ts)
    system_stop_stats = compute_system_stop_stats(enriched_events, start_ts, end_ts)
    oee = compute_oee(enriched_events)
    events_out = serialize_events(enriched_events)

    return {
        "context": {
            "machine_code": machine_code,
            "start_ts": start_ts.isoformat(),
            "end_ts": end_ts.isoformat(),
        },
        "totals": totals,
        "by_reason": by_reason,
        "stop_stats": stop_stats,              # per UPDT reason (count, MTTR, MTBF)
        "system_stop_stats": system_stop_stats,# PDT vs UPDT (counts, avg stop, MTBF)
        "oee": oee,                            # availability-based OEE
        "events": events_out,
    }


@app.get("/oee-debug-fetch")
def oee_debug_service(machine_code: str, start_ts: datetime, end_ts: datetime):
    if end_ts <= start_ts:
        raise HTTPException(status_code=400, detail="end_ts must be after start_ts")
    
    if start_ts.tzinfo is not None:
        start_ts = start_ts.replace(tzinfo=None)
    if end_ts.tzinfo is not None:
        end_ts = end_ts.replace(tzinfo=None)

    rows = fetch_clipped_events(machine_code, start_ts, end_ts)
    enriched_events = build_enriched_events(rows, start_ts, end_ts)
    return {
        "db_rows": len(rows),
        "enriched_events": len(enriched_events),
        "first_start": enriched_events[0]["start_ts"] if enriched_events else None,
        "last_end": enriched_events[-1]["end_ts"] if enriched_events else None,
    }

@app.get("/departments")
def list_departments():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, code, name, description, is_active
        FROM department
        ORDER BY code
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.post("/departments")
def create_department(dept: DepartmentCreate):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO department (code, name, description, is_active)
        VALUES (%s, %s, %s, %s)
    """
    values = (dept.code, dept.name, dept.description, int(dept.is_active))
    cursor.execute(sql, values)
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"id": new_id, **dept.dict()}

@app.get("/lines")
def list_lines(department_id: int | None = None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if department_id is None:
        cursor.execute(
            """
            SELECT
                l.id,
                l.code,
                l.name,
                l.description,
                l.is_active,
                l.department_id,
                d.code AS department_code,
                d.name AS department_name
            FROM line l
            JOIN department d ON d.id = l.department_id
            ORDER BY d.code, l.code
            """
        )
        rows = cursor.fetchall()
    else:
        cursor.execute(
            """
            SELECT
                l.id,
                l.code,
                l.name,
                l.description,
                l.is_active,
                l.department_id,
                d.code AS department_code,
                d.name AS department_name
            FROM line l
            JOIN department d ON d.id = l.department_id
            WHERE l.department_id = %s
            ORDER BY l.code
            """,
            (department_id,),
        )
        rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows


@app.post("/lines")
def create_line(line: LineCreate):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO line (department_id, code, name, description, is_active)
        VALUES (%s, %s, %s, %s, %s)
    """
    values = (
        line.department_id,
        line.code,
        line.name,
        line.description,
        int(line.is_active),
    )
    cursor.execute(sql, values)
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"id": new_id, **line.dict()}

@app.get("/machines")
def list_machines():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            m.id,
            m.code,
            m.name,
            m.is_active,
            m.line_id,
            l.code AS line_code,
            l.name AS line_name,
            d.id   AS department_id,
            d.code AS department_code,
            d.name AS department_name
        FROM machine m
        LEFT JOIN line l
            ON m.line_id = l.id
        LEFT JOIN department d
            ON l.department_id = d.id
        ORDER BY d.code, l.code, m.code
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

@app.post("/machines")
def create_machine(machine: MachineCreate):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO machine (code, name, line_id, is_active)
        VALUES (%s, %s, %s, %s)
    """
    values = (
        machine.code,
        machine.name,
        machine.line_id,
        int(machine.is_active),
    )
    cursor.execute(sql, values)
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"id": new_id, **machine.dict()}

@app.get("/products")
def list_products():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            id,
            code,
            name,
            pack_count,
            nominal_speed,
            target_oee
        FROM product
        ORDER BY code
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/products/{product_id}")
def get_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            id,
            code,
            name,
            pack_count,
            nominal_speed,
            target_oee
        FROM product
        WHERE id = %s
        """,
        (product_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return row


@app.post("/products")
def create_product(product: ProductCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO product (
            code,
            name,
            pack_count,
            nominal_speed,
            target_oee
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            product.code,
            product.name,
            product.pack_count,
            product.nominal_speed,
            product.target_oee,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"id": new_id, **product.dict()}


@app.put("/products/{product_id}")
def update_product(product_id: int, product: ProductUpdate):
    fields = []
    values = []

    if product.code is not None:
        fields.append("code = %s")
        values.append(product.code)
    if product.name is not None:
        fields.append("name = %s")
        values.append(product.name)
    if product.pack_count is not None:
        fields.append("pack_count = %s")
        values.append(product.pack_count)
    if product.nominal_speed is not None:
        fields.append("nominal_speed = %s")
        values.append(product.nominal_speed)
    if product.target_oee is not None:
        fields.append("target_oee = %s")
        values.append(product.target_oee)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(product_id)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE product SET {', '.join(fields)} WHERE id = %s",
        tuple(values),
    )
    conn.commit()
    cursor.close()
    conn.close()

    return get_product(product_id)

@app.get("/order-runs")
def list_order_runs(
    machine_id: int | None = None,
    status: str | None = None
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    base_sql = """
        SELECT
            o.id,
            o.workorder,
            o.machine_id,
            m.code AS machine_code,
            o.product_id,
            p.code AS product_code,
            o.planned_qty,
            o.start_ts,
            o.end_ts,
            o.status,
            o.qty_good,
            o.qty_scrap,
            o.runtime_sec
        FROM order_run o
        LEFT JOIN machine m ON o.machine_id = m.id
        LEFT JOIN product p ON o.product_id = p.id
    """
    where = []
    params: list = []

    if machine_id is not None:
        where.append("o.machine_id = %s")
        params.append(machine_id)
    if status is not None:
        where.append("o.status = %s")
        params.append(status)

    if where:
        base_sql += " WHERE " + " AND ".join(where)

    base_sql += " ORDER BY o.start_ts DESC, o.id DESC"

    cursor.execute(base_sql, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/order-runs/{order_id}")
def get_order_run(order_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            o.id,
            o.workorder,
            o.machine_id,
            m.code AS machine_code,
            o.product_id,
            p.code AS product_code,
            o.planned_qty,
            o.start_ts,
            o.end_ts,
            o.status,
            o.qty_good,
            o.qty_scrap,
            o.runtime_sec
        FROM order_run o
        LEFT JOIN machine m ON o.machine_id = m.id
        LEFT JOIN product p ON o.product_id = p.id
        WHERE o.id = %s
        """,
        (order_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Order run not found")
    return row


@app.post("/order-runs")
def create_order_run(order: OrderRunCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO order_run (
            workorder,
            machine_id,
            product_id,
            planned_qty,
            start_ts,
            end_ts,
            status,
            qty_good,
            qty_scrap,
            runtime_sec
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            order.workorder,
            order.machine_id,
            order.product_id,
            order.planned_qty,
            order.start_ts,
            order.end_ts,
            order.status,
            order.qty_good,
            order.qty_scrap,
            order.runtime_sec,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return get_order_run(new_id)


@app.put("/order-runs/{order_id}")
def update_order_run(order_id: int, order: OrderRunUpdate):
    fields = []
    values = []

    if order.workorder is not None:
        fields.append("workorder = %s")
        values.append(order.workorder)
    if order.machine_id is not None:
        fields.append("machine_id = %s")
        values.append(order.machine_id)
    if order.product_id is not None:
        fields.append("product_id = %s")
        values.append(order.product_id)
    if order.planned_qty is not None:
        fields.append("planned_qty = %s")
        values.append(order.planned_qty)
    if order.start_ts is not None:
        fields.append("start_ts = %s")
        values.append(order.start_ts)
    if order.end_ts is not None:
        fields.append("end_ts = %s")
        values.append(order.end_ts)
    if order.status is not None:
        fields.append("status = %s")
        values.append(order.status)
    if order.qty_good is not None:
        fields.append("qty_good = %s")
        values.append(order.qty_good)
    if order.qty_scrap is not None:
        fields.append("qty_scrap = %s")
        values.append(order.qty_scrap)
    if order.runtime_sec is not None:
        fields.append("runtime_sec = %s")
        values.append(order.runtime_sec)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(order_id)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE order_run SET {', '.join(fields)} WHERE id = %s",
        tuple(values),
    )
    conn.commit()
    cursor.close()
    conn.close()

    return get_order_run(order_id)
