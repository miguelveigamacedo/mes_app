SELECT * FROM mes.MachineStatusEvent
ORDER BY Ts DESC
LIMIT 10;

SELECT * FROM mes.shift
LIMIT 10;

SELECT * FROM mes.ProcessSnapshot
LIMIT 10;

SELECT * FROM mes_core.machine
LIMIT 10;

SELECT * FROM mes_core.product
LIMIT 10;

SELECT * FROM mes_core.reason_code
LIMIT 10;

SELECT * FROM mes_core.downtime_event
order by start_ts DESc
LIMIT 10;

