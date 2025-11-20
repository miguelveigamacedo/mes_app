import mysql.connector
from datetime import datetime

# ---------------------------
# 1. DB CONNECTION
# ---------------------------
def get_conn():
    return mysql.connector.connect(
        host="localhost",
        user="miguelveigamacedo",
        password="123456",
        autocommit=False
    )

# ---------------------------
# 2. MAIN SYNC FUNCTION
# ---------------------------
def run_sync():
    print(f"[{datetime.now()}] Running MES event sync...")

    conn = get_conn()
    cur = conn.cursor()

    # ---------------------------
    # A) INSERT NEW RAW EVENTS
    #    Only last 5 minutes
    # ---------------------------

   
    insert_sql = """
    INSERT INTO mes_core.downtime_event (
    raw_event_id,
    machine_id,
    workorder,
    raw_reason_code,
    start_ts,
    end_ts,
    duration_sec,
    reason_code_id,
    comment,
    source_quality
    )
    SELECT
    mse.Id,
    m.id,
    mse.WorkOrder,
    mse.ReasonCode,
    mse.Ts,
    NULL,
    NULL,
    rc.id AS reason_code_id,
    NULL,
    'Auto'
    FROM mes.MachineStatusEvent mse
    JOIN mes_core.machine m
    ON m.code = mse.MachineId
    LEFT JOIN mes_core.downtime_event d
    ON d.raw_event_id = mse.Id
    LEFT JOIN mes_core.reason_code rc
    ON rc.code = mse.ReasonCode
    WHERE d.raw_event_id IS NULL
    AND mse.Ts >= (NOW() - INTERVAL 5 MINUTE);
    """

    cur.execute(insert_sql)
    print(f"Inserted new events: {cur.rowcount}")

    # ---------------------------
    # B) UPDATE end_ts via LEAD()
    #    Only update recent events
    # ---------------------------

    update_end_sql = """
    UPDATE mes_core.downtime_event d
    JOIN (
        SELECT
            mse.Id AS raw_event_id,
            LEAD(mse.Ts) OVER (
                PARTITION BY mse.MachineId
                ORDER BY mse.Ts
            ) AS next_ts
        FROM mes.MachineStatusEvent mse
        WHERE mse.Ts >= (NOW() - INTERVAL 60 MINUTE)
    ) v
        ON v.raw_event_id = d.raw_event_id
    SET d.end_ts = v.next_ts
    WHERE d.end_ts IS NULL;
    """

    cur.execute(update_end_sql)
    print(f"Updated end_ts for events: {cur.rowcount}")

    # ---------------------------
    # C) UPDATE duration_sec
    # ---------------------------

    update_duration_sql = """
    UPDATE mes_core.downtime_event
    SET duration_sec = TIMESTAMPDIFF(
            SECOND,
            start_ts,
            COALESCE(end_ts, NOW())
        )
    WHERE start_ts >= (NOW() - INTERVAL 60 MINUTE);
    """

    cur.execute(update_duration_sql)
    print(f"Updated duration_sec: {cur.rowcount}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"[{datetime.now()}] Sync complete.\n")


# ---------------------------
# SCRIPT ENTRY
# ---------------------------
if __name__ == "__main__":
    run_sync()
