DELIMITER $$

CREATE EVENT IF NOT EXISTS etl_update_order_run_shift
ON SCHEDULE EVERY 5 MINUTE
DO
BEGIN
    DROP TEMPORARY TABLE IF EXISTS tmp_order_run_shift;

    CREATE TEMPORARY TABLE tmp_order_run_shift AS
    SELECT
        de.workorder,
        de.machine_id,
        de.shift_id,
        MAX(mse.UnitsTotal) - MIN(mse.UnitsTotal) AS qty_good,
        MAX(mse.WasteTotal) - MIN(mse.WasteTotal) AS qty_scrap,
        SUM(
            CASE WHEN de.raw_reason_code = 'RUNNING'
                 THEN de.duration_sec ELSE 0 END
        ) AS runtime_sec
    FROM mes_core.downtime_event de
    JOIN mes.MachineStatusEvent mse
        ON mse.Id = de.raw_event_id
    WHERE de.start_ts >= NOW() - INTERVAL 2 DAY
      AND de.workorder IS NOT NULL
      AND de.workorder <> ''
    GROUP BY
        de.workorder,
        de.machine_id,
        de.shift_id;

    INSERT INTO mes_core.order_run_shift (
        workorder,
        machine_id,
        shift_id,
        qty_good,
        qty_scrap,
        runtime_sec
    )
    SELECT
        t.workorder,
        t.machine_id,
        t.shift_id,
        t.qty_good,
        t.qty_scrap,
        t.runtime_sec
    FROM tmp_order_run_shift t
    ON DUPLICATE KEY UPDATE
        qty_good    = VALUES(qty_good),
        qty_scrap   = VALUES(qty_scrap),
        runtime_sec = VALUES(runtime_sec);

END $$

DELIMITER ;
