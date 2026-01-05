-- Show current Historian Entries
SELECT * FROM mes.MachineStatusEvent
ORDER BY Ts DESC;

-- Show current Historian Entries
SELECT * FROM mes_core.downtime_event
ORDER BY start_ts DESC;

-- Show current reason codes
SELECT * FROM mes_core.product;

-- Show current reason codes
SELECT * FROM mes_core.reason_code;

