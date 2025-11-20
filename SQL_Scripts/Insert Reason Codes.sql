USE mes_core;

INSERT INTO reason_code (code, description, category) VALUES
-- Running states
('RUNNING', 'Machine running in production', 'RUNNING'),
('RUN_EMPTY', 'Machine running without product', 'RUNNING'),

-- Off states
('OFF', 'Machine off / no power', 'OFF'),
('OFF_NO_SHIFT', 'Machine off – outside production shift', 'OFF'),

-- Planned downtime (PDT)
('PDT_SETUP', 'Setup / changeover', 'PDT'),
('PDT_CLEANING', 'Cleaning / sanitation', 'PDT'),
('PDT_MAINT_SCHED', 'Scheduled maintenance', 'PDT'),
('PDT_MEETING', 'Meeting / training', 'PDT'),
('PDT_LUNCH', 'Planned meal / break', 'PDT'),

-- Unplanned downtime (UPDT)
('UPDT_BREAK_MECH', 'Breakdown – mechanical', 'UPDT'),
('UPDT_BREAK_ELEC', 'Breakdown – electrical', 'UPDT'),
('UPDT_JAM', 'Minor stops / jams', 'UPDT'),
('UPDT_NO_MATERIAL', 'No material / components', 'UPDT'),
('UPDT_NO_OPERATOR', 'No operator / staffing issue', 'UPDT'),
('UPDT_QUALITY', 'Quality hold / rework', 'UPDT'),
('UPDT_OTHER', 'Unplanned downtime – other / unspecified', 'UPDT');