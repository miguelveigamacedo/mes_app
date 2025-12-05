DELIMITER $$

CREATE EVENT IF NOT EXISTS etl_update_downtime_event
ON SCHEDULE EVERY 1 MINUTE
DO
BEGIN

    /* 1) Insert new events from MachineStatusEvent (no duplicates) */
    INSERT INTO mes_core.downtime_event (
        raw_event_id,
        machine_id,
        workorder,
        raw_reason_code,
        start_ts,
        end_ts,
        duration_sec,
        shift_id,
        reason_code_id,
        comment,
        source_quality
    )
    SELECT
        mse.Id                         AS raw_event_id,
        m.id                           AS machine_id,
        mse.WorkOrder                  AS workorder,
        mse.ReasonCode                 AS raw_reason_code,
        mse.Ts                         AS start_ts,
        NULL                           AS end_ts,
        NULL                           AS duration_sec,
        mse.ShiftId                    AS shift_id,
        rc.id                          AS reason_code_id,
        NULL                           AS comment,
        'AUTO'                         AS source_quality
    FROM mes.MachineStatusEvent mse
    JOIN mes_core.machine m
        ON m.code = mse.MachineId
    LEFT JOIN mes_core.reason_code rc
        ON rc.code = CONCAT('[AUTO] ', mse.ReasonCode)
    LEFT JOIN mes_core.downtime_event de
        ON de.raw_event_id = mse.Id
    WHERE de.raw_event_id IS NULL
      AND mse.Ts >= NOW() - INTERVAL 24 HOUR;


    /* 2) Set end_ts using the next event timestamp per machine */
    WITH ordered AS (
        SELECT
            mse.Id,
            mse.MachineId,
            mse.Ts,
            LEAD(mse.Ts) OVER (
                PARTITION BY mse.MachineId
                ORDER BY mse.Ts
            ) AS next_ts
        FROM mes.MachineStatusEvent mse
        WHERE mse.Ts >= NOW() - INTERVAL 24 HOUR
    )
    UPDATE mes_core.downtime_event de
    JOIN ordered o
        ON o.Id = de.raw_event_id
    SET de.end_ts = o.next_ts
    WHERE de.end_ts IS NULL
      AND o.next_ts IS NOT NULL;


    /* 3) Recalculate duration_sec for recent events */
    UPDATE mes_core.downtime_event
    SET duration_sec = TIMESTAMPDIFF(
            SECOND,
            start_ts,
            COALESCE(end_ts, NOW())
        )
    WHERE start_ts >= NOW() - INTERVAL 24 HOUR;

END $$

DELIMITER ;
