DELIMITER $$

CREATE EVENT IF NOT EXISTS etl_sync_order_run
ON SCHEDULE EVERY 1 MINUTE
DO
BEGIN
    -- A) Workorders in OrderHistory but missing in mes_core.order_run
    DROP TEMPORARY TABLE IF EXISTS tmp_missing_orders;

    CREATE TEMPORARY TABLE tmp_missing_orders AS
    SELECT DISTINCT
        oh.WorkOrder,
        oh.MachineId,
        oh.StartTs,
        oh.EndTs,
        oh.RunTimeSeconds,
        oh.UnitsProduced,
        oh.WasteProduced
    FROM mes.OrderHistory oh
    LEFT JOIN mes_core.order_run r
        ON r.workorder = oh.WorkOrder
    WHERE r.id IS NULL;  -- only workorders not yet in order_run


    -- B) Insert missing workorders into mes_core.order_run as [VOID] orders
    --    product_id is NULL for these unplanned orders
    INSERT INTO mes_core.order_run (
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
    SELECT
        CONCAT('[VOID] ', t.WorkOrder)      AS workorder,
        t.MachineId                         AS machine_id,
        NULL                                AS product_id,
        t.UnitsProduced + t.WasteProduced   AS planned_qty,
        t.StartTs                           AS start_ts,
        t.EndTs                             AS end_ts,
        'Completed'                         AS status,
        t.UnitsProduced                     AS qty_good,
        t.WasteProduced                     AS qty_scrap,
        t.RunTimeSeconds                    AS runtime_sec
    FROM tmp_missing_orders t;


    -- C) Update OrderHistory WorkOrder for those same missing workorders
    UPDATE mes.OrderHistory oh
    JOIN tmp_missing_orders t
        ON oh.WorkOrder = t.WorkOrder
    SET oh.WorkOrder = CONCAT('[VOID] ', oh.WorkOrder)
    WHERE oh.WorkOrder NOT LIKE '[VOID] %';


    -- D) For workorders that DO exist in order_run (non-[VOID]),
    --    update runtime and quantities from OrderHistory
    UPDATE mes_core.order_run r
    JOIN mes.OrderHistory oh
        ON r.workorder = oh.WorkOrder
    SET
        r.start_ts    = oh.StartTs,
        r.end_ts      = oh.EndTs,
        r.runtime_sec = oh.RunTimeSeconds,
        r.qty_good    = oh.UnitsProduced,
        r.qty_scrap   = oh.WasteProduced
    WHERE r.workorder NOT LIKE '[VOID] %';


    -- E) Sync VOIDED status from mes.Workorder:
    --    if ERP says VOIDED, mark mes_core.order_run as VOIDED too
    UPDATE mes_core.order_run r
    JOIN mes.Workorder w
        ON r.workorder = w.WorkOrder
    SET r.status = 'VOIDED'
    WHERE w.Status = 'VOIDED'
      AND r.workorder NOT LIKE '[VOID] %';

END $$

DELIMITER ;

