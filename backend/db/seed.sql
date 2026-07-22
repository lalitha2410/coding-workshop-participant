-- ============================================================
-- Meridian — realistic demo seed data (domain tables only)
-- ============================================================
-- Idempotent / re-runnable: resets the four domain tables to a known state and
-- reseeds. users & roles are NOT touched here (see bin/seed-data.sh for demo
-- users). Deadlines/dates are relative to CURRENT_DATE so "at-risk" stays real.
--
-- TRUNCATE ... RESTART IDENTITY makes serial ids deterministic (projects 1..12,
-- resources 1..9), so the deliverable/allocation foreign keys below are stable.

BEGIN;

TRUNCATE allocations, deliverables, resources, projects RESTART IDENTITY CASCADE;

-- ---- Projects (ids 1..12) ---------------------------------------------------
INSERT INTO projects (name, description, status, department, start_date, end_date, deadline, budget_planned, budget_consumed) VALUES
  ('Apollo Platform Rebuild',    'Re-architect the core platform onto a modular services stack.', 'active',    'Engineering', CURRENT_DATE - 120, CURRENT_DATE + 90,  CURRENT_DATE + 40, 800000.00, 540000.00), -- 1
  ('Nimbus Data Warehouse',      'Consolidate analytics into a governed warehouse.',              'active',    'Data',        CURRENT_DATE - 90,  CURRENT_DATE + 30,  CURRENT_DATE + 12, 650000.00, 612000.00), -- 2  near deadline + hot budget
  ('Q3 Brand Refresh',           'Refresh brand identity and campaign system for Q3.',            'on_hold',   'Marketing',   CURRENT_DATE - 60,  CURRENT_DATE + 20,  CURRENT_DATE - 5,  220000.00,  96000.00), -- 3  past deadline
  ('Helios Mobile App',          'Native mobile companion app for field teams.',                  'active',    'Engineering', CURRENT_DATE - 40,  CURRENT_DATE + 120, CURRENT_DATE + 75, 500000.00, 210000.00), -- 4
  ('Orion Analytics Suite',      'Self-serve analytics and dashboards for product teams.',        'planning',  'Data',        CURRENT_DATE + 10,  CURRENT_DATE + 160, CURRENT_DATE + 130, 300000.00,      0.00), -- 5
  ('Atlas CRM Migration',        'Migrate legacy CRM to the new operations platform.',            'active',    'Operations',  CURRENT_DATE - 75,  CURRENT_DATE + 25,  CURRENT_DATE + 6,  420000.00, 401000.00), -- 6  near deadline + hot budget
  ('Vega Design System',         'Unified component library and design tokens.',                  'active',    'Design',      CURRENT_DATE - 50,  CURRENT_DATE + 70,  CURRENT_DATE + 30, 180000.00, 118000.00), -- 7
  ('Titan Security Audit',       'Third-party security review and remediation.',                  'completed', 'Engineering', CURRENT_DATE - 110, CURRENT_DATE - 20,  CURRENT_DATE - 20, 150000.00, 148000.00), -- 8
  ('Lyra Marketing Automation',  'Lifecycle campaigns and lead scoring automation.',              'active',    'Marketing',   CURRENT_DATE - 35,  CURRENT_DATE + 45,  CURRENT_DATE + 18, 260000.00, 176000.00), -- 9
  ('Draco Finance Portal',       'Self-service finance and expense portal.',                      'planning',  'Finance',     CURRENT_DATE + 5,   CURRENT_DATE + 150, CURRENT_DATE + 110, 340000.00,      0.00), -- 10
  ('Phoenix Support Revamp',     'Overhaul the customer support tooling and workflows.',          'on_hold',   'Operations',  CURRENT_DATE - 25,  CURRENT_DATE + 80,  CURRENT_DATE + 55, 130000.00,  61000.00), -- 11
  ('Zephyr Internal Tools',      'Internal admin tooling and automation.',                        'active',    'Engineering', CURRENT_DATE - 30,  CURRENT_DATE + 30,  CURRENT_DATE + 9,  210000.00, 205000.00); -- 12 near deadline + hot budget

-- ---- Resources (ids 1..9) ---------------------------------------------------
INSERT INTO resources (name, email, title) VALUES
  ('Marcus Reed',   'marcus.reed@acme.test',   'Staff Engineer'),      -- 1  -> over-allocated
  ('Priya Nair',    'priya.nair@acme.test',    'Principal Designer'),  -- 2
  ('Ana Duarte',    'ana.duarte@acme.test',    'Delivery Lead'),       -- 3  -> over-allocated
  ('Tom Alvarez',   'tom.alvarez@acme.test',   'Data Engineer'),       -- 4  -> over-allocated
  ('Sofia Rossi',   'sofia.rossi@acme.test',   'Product Manager'),     -- 5
  ('Liam O''Brien', 'liam.obrien@acme.test',   'Backend Engineer'),    -- 6
  ('Chen Wei',      'chen.wei@acme.test',      'Marketing Manager'),   -- 7
  ('Nadia Hassan',  'nadia.hassan@acme.test',  'Data Scientist'),      -- 8
  ('Diego Santos',  'diego.santos@acme.test',  'DevOps Engineer');     -- 9

-- ---- Deliverables (varied status + completion) ------------------------------
INSERT INTO deliverables (project_id, name, description, status, completion_pct, due_date) VALUES
  (1, 'Service decomposition plan',  'Define bounded contexts and service boundaries.', 'completed',   100, CURRENT_DATE - 30),
  (1, 'Auth service extraction',     'Split auth into its own service.',                'in_progress',  65, CURRENT_DATE + 10),
  (1, 'Platform API gateway',        'Introduce a shared API gateway.',                 'in_progress',  40, CURRENT_DATE + 25),
  (1, 'Data migration tooling',      'Backfill + dual-write tooling.',                  'blocked',      20, CURRENT_DATE + 15),
  (2, 'Warehouse schema design',     'Star-schema modeling for analytics.',             'completed',   100, CURRENT_DATE - 12),
  (2, 'ETL pipeline build',          'Batch + streaming ingestion.',                    'in_progress',  75, CURRENT_DATE + 5),
  (2, 'Governance & access model',   'Row/column governance.',                          'blocked',      30, CURRENT_DATE + 8),
  (3, 'Brand guidelines v2',         'Updated identity guidelines.',                    'in_progress',  50, CURRENT_DATE - 2),
  (3, 'Campaign templates',          'Reusable campaign templates.',                    'not_started',   0, CURRENT_DATE + 12),
  (4, 'Mobile design spec',          'Screens and flows.',                              'completed',   100, CURRENT_DATE - 10),
  (4, 'Offline sync engine',         'Local-first sync.',                               'in_progress',  55, CURRENT_DATE + 30),
  (4, 'Push notifications',          'Notification service integration.',               'not_started',   0, CURRENT_DATE + 45),
  (5, 'Requirements discovery',      'Stakeholder interviews.',                         'in_progress',  35, CURRENT_DATE + 20),
  (5, 'Metrics catalog',             'Define core metrics.',                            'not_started',   0, CURRENT_DATE + 40),
  (6, 'CRM data mapping',            'Field + object mapping.',                         'completed',   100, CURRENT_DATE - 8),
  (6, 'Migration dry run',           'Full rehearsal migration.',                       'in_progress',  70, CURRENT_DATE + 4),
  (6, 'Cutover runbook',             'Go-live runbook.',                                'blocked',      15, CURRENT_DATE + 5),
  (7, 'Core components',             'Buttons, inputs, tables.',                        'in_progress',  80, CURRENT_DATE + 10),
  (7, 'Design tokens',               'Color/spacing/type tokens.',                      'completed',   100, CURRENT_DATE - 5),
  (8, 'Pen test',                    'External penetration test.',                      'completed',   100, CURRENT_DATE - 25),
  (8, 'Remediation',                 'Fix findings.',                                   'completed',   100, CURRENT_DATE - 21),
  (9, 'Lead scoring model',          'Scoring rules + model.',                          'in_progress',  60, CURRENT_DATE + 14),
  (9, 'Lifecycle journeys',          'Onboarding + retention flows.',                   'not_started',   0, CURRENT_DATE + 22),
  (10,'Portal wireframes',           'Key screens.',                                    'not_started',   0, CURRENT_DATE + 30),
  (11,'Support tooling audit',       'Current-state audit.',                            'in_progress',  45, CURRENT_DATE + 20),
  (12,'Admin console v1',            'Internal admin console.',                         'in_progress',  85, CURRENT_DATE + 3),
  (12,'Bulk operations',             'Batch admin actions.',                            'not_started',   0, CURRENT_DATE + 9);

-- ---- Allocations (3 resources deliberately over 100%) -----------------------
INSERT INTO allocations (resource_id, project_id, allocation_pct, start_date, end_date) VALUES
  (1, 1,  70, CURRENT_DATE - 100, CURRENT_DATE + 90),  -- Marcus  70
  (1, 4,  40, CURRENT_DATE - 40,  CURRENT_DATE + 120), -- Marcus +40
  (1, 12, 30, CURRENT_DATE - 30,  CURRENT_DATE + 30),  -- Marcus +30  = 140 OVER
  (4, 2,  80, CURRENT_DATE - 90,  CURRENT_DATE + 30),  -- Tom     80
  (4, 5,  50, CURRENT_DATE + 10,  CURRENT_DATE + 160), -- Tom    +50  = 130 OVER
  (3, 6,  60, CURRENT_DATE - 75,  CURRENT_DATE + 25),  -- Ana     60
  (3, 11, 30, CURRENT_DATE - 25,  CURRENT_DATE + 80),  -- Ana    +30
  (3, 9,  25, CURRENT_DATE - 35,  CURRENT_DATE + 45),  -- Ana    +25  = 115 OVER
  (2, 7,  60, CURRENT_DATE - 50,  CURRENT_DATE + 70),  -- Priya   60
  (2, 1,  30, CURRENT_DATE - 100, CURRENT_DATE + 90),  -- Priya  +30  = 90
  (5, 4,  50, CURRENT_DATE - 40,  CURRENT_DATE + 120), -- Sofia   50
  (5, 9,  40, CURRENT_DATE - 35,  CURRENT_DATE + 45),  -- Sofia  +40  = 90
  (6, 1,  55, CURRENT_DATE - 100, CURRENT_DATE + 90),  -- Liam    55
  (6, 12, 45, CURRENT_DATE - 30,  CURRENT_DATE + 30),  -- Liam   +45  = 100
  (7, 3,  50, CURRENT_DATE - 60,  CURRENT_DATE + 20),  -- Chen    50
  (7, 9,  30, CURRENT_DATE - 35,  CURRENT_DATE + 45),  -- Chen   +30  = 80
  (8, 2,  60, CURRENT_DATE - 90,  CURRENT_DATE + 30),  -- Nadia   60
  (8, 5,  40, CURRENT_DATE + 10,  CURRENT_DATE + 160), -- Nadia  +40  = 100
  (9, 6,  45, CURRENT_DATE - 75,  CURRENT_DATE + 25),  -- Diego   45
  (9, 8,  20, CURRENT_DATE - 110, CURRENT_DATE - 20);  -- Diego  +20  = 65

COMMIT;
