SELECT
    de.id                      AS event_id,
    de.raw_event_id,
    m.code                     AS machine_code,
    de.workorder,
    rc.code                    AS reason_code,
    rc.category                AS reason_category,
    CASE
        WHEN rc.category = 'RUNNING' THEN 'RUNNING'
        WHEN rc.category = 'PDT'     THEN 'PDT'
        WHEN rc.category = 'UPDT'    THEN 'UPDT'
        WHEN rc.category = 'OFF' AND rc.code = 'OFF_NO_SHIFT' THEN 'OFF_NO_SHIFT'
        WHEN rc.category = 'OFF'     THEN 'OFF'
        ELSE 'OTHER'
    END AS state_bucket,
    -- Clip each event to the requested analysis window
    GREATEST(de.start_ts, @start_ts) AS clipped_start_ts,
    LEAST(de.end_ts,   @end_ts)      AS clipped_end_ts,
    -- Adjusted duration in seconds inside the window
    TIMESTAMPDIFF(
        SECOND,
        GREATEST(de.start_ts, @start_ts),
        LEAST(de.end_ts,   @end_ts)
    ) AS adj_duration_sec
FROM downtime_event de
JOIN reason_code rc
  ON rc.id = de.reason_code_id
JOIN machine m
  ON m.id = de.machine_id
WHERE m.code      = @machine_code
  -- Only events that overlap the window
  AND de.end_ts   > @start_ts
  AND de.start_ts < @end_ts
  -- Defensive: ensure we do not get zero/negative durations after clipping
  AND LEAST(de.end_ts, @end_ts) > GREATEST(de.start_ts, @start_ts)
ORDER BY clipped_start_ts;
