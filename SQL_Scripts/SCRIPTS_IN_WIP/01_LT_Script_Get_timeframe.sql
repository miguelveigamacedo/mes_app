-- Define input variables for the script

SET @machine_code = 'CASEPK013';        -- or use 'CASEPK013'
SET @start_ts     = '2025-11-24 06:00:00';
SET @end_ts       = '2025-12-01 00:00:00';

-- Build the needed view

SELECT
    state_bucket,
    SUM(adj_duration_sec) AS duration_sec
FROM (
    SELECT
        de.id,
        de.start_ts,
        de.end_ts,
        de.duration_sec,
        rc.code      AS reason_code,
        rc.category  AS reason_category,
        
        -- Define state bucket 
        
        CASE
            WHEN rc.category = 'RUNNING' THEN 'RUNNING'
            WHEN rc.category = 'PDT'     THEN 'PDT'
            WHEN rc.category = 'UPDT'    THEN 'UPDT'
            WHEN rc.category = 'OFF' AND rc.code = 'OFF_NO_SHIFT' THEN 'OFF_NO_SHIFT'
            WHEN rc.category = 'OFF'     THEN 'OFF'
            ELSE 'OTHER'
        END AS state_bucket,
        
        -- Essentially it's "cutting" the event if provided timestamps overlap with the end or start of an event
        
        TIMESTAMPDIFF(
            SECOND,
            GREATEST(de.start_ts, @start_ts),
            LEAST(de.end_ts,   @end_ts)
        ) AS adj_duration_sec
	
    -- Joins with other tables (machine and reason_code
    
    FROM downtime_event de
    
    JOIN reason_code rc
        ON rc.id = de.reason_code_id
    JOIN machine m
        ON m.id = de.machine_id
    WHERE m.code     = @machine_code
      AND de.end_ts  > @start_ts   -- event overlaps window
      AND de.start_ts < @end_ts
) AS x
WHERE adj_duration_sec > 0
GROUP BY state_bucket;