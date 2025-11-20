DELIMITER $$

CREATE EVENT IF NOT EXISTS etl_update_downtime_event
ON SCHEDULE EVERY 1 MINUTE
DO
BEGIN

    -- 1) Insert new events from last 6 hours (no duplicates)
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
        CASE
            WHEN mse.ReasonCode = 'RUNNING' THEN 1
            WHEN mse.ReasonCode = 'OFF'     THEN 3
            ELSE NULL
        END,
        NULL,
        'Auto'
    FROM mes.MachineStatusEvent mse
    JOIN mes_core.machine m
        ON m.code = mse.MachineId
    LEFT JOIN mes_core.downtime_event de
        ON de.raw_event_id = mse.Id
    WHERE de.raw_event_id IS NULL
      AND mse.Ts >= NOW() - INTERVAL 6 HOUR
      AND mse.Ts <= NOW();


    -- 2) Set end_ts using the next event timestamp per machine
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
        WHERE mse.Ts >= NOW() - INTERVAL 6 HOUR
    )
    UPDATE mes_core.downtime_event de
    JOIN ordered o
        ON o.Id = de.raw_event_id
    SET de.end_ts = o.next_ts
    WHERE de.end_ts IS NULL
      AND o.next_ts IS NOT NULL;


    -- 3) Recalculate duration_sec (safe-update friendly using PK)
    UPDATE mes_core.downtime_event
    SET duration_sec = TIMESTAMPDIFF(
            SECOND,
            start_ts,
            COALESCE(end_ts, NOW())
        )
    WHERE id IN (
        SELECT id FROM (
            SELECT id
            FROM mes_core.downtime_event
            WHERE start_ts >= NOW() - INTERVAL 6 HOUR
        ) AS x
    );

END $$

DELIMITER ;