# app/oee_repository.py
from datetime import datetime
from .db import get_connection

def fetch_clipped_events(machine_code: str, start_ts: datetime, end_ts: datetime):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
    SELECT
    de.id AS event_id,
    de.raw_event_id,
    m.code AS machine_code,
    de.workorder,
    de.comment,
    rc.code AS reason_code,
    rc.category AS reason_category,
    CASE
        WHEN rc.category = 'RUNNING' THEN 'RUNNING'
        WHEN rc.category = 'PDT'     THEN 'PDT'
        WHEN rc.category = 'UPDT'    THEN 'UPDT'
        WHEN rc.category = 'OFF' AND rc.code = 'OFF_NO_SHIFT' THEN 'OFF_NO_SHIFT'
        WHEN rc.category = 'OFF'     THEN 'OFF'
        ELSE 'OTHER'
    END AS state_bucket,
    GREATEST(de.start_ts, %s) AS clipped_start_ts,
    LEAST(de.end_ts,   %s)    AS clipped_end_ts,
    TIMESTAMPDIFF(
        SECOND,
        GREATEST(de.start_ts, %s),
        LEAST(de.end_ts,   %s)
    ) AS adj_duration_sec,
    -- new fields for loss calculations
    de.duration_sec        AS base_duration_sec,
    de.units_total,
    de.waste_total,
    de.target_speed_ups
    FROM downtime_event de
    JOIN reason_code rc
      ON rc.id = de.reason_code_id
    JOIN machine m
      ON m.id = de.machine_id
    WHERE m.code    = %s
      AND de.end_ts > %s
      AND de.start_ts < %s
      AND LEAST(de.end_ts, %s) > GREATEST(de.start_ts, %s)
    ORDER BY clipped_start_ts
    """
    params = (start_ts, end_ts, start_ts, end_ts, machine_code, start_ts, end_ts, end_ts, start_ts)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
