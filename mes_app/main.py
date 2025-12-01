from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .db import get_connection
from datetime import datetime
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


@app.get("/machines")
def list_machines():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, code, name, is_active FROM machine ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.post("/machines")
def create_machine(machine: MachineCreate):
    conn = get_connection()
    cursor = conn.cursor()
    sql = "INSERT INTO machine (code, name, is_active) VALUES (%s, %s, %s)"
    values = (machine.code, machine.name, int(machine.is_active))
    cursor.execute(sql, values)
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"id": new_id, **machine.dict()}


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
