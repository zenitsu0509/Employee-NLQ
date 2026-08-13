-- =============================================================================
--  Employee NLQ — Complete Test Data Setup for Supabase
--  Run this entire script in Supabase → SQL Editor → New Query
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1: DROP existing tables (clean slate)
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS skills      CASCADE;
DROP TABLE IF EXISTS salaries    CASCADE;
DROP TABLE IF EXISTS employees   CASCADE;
DROP TABLE IF EXISTS departments CASCADE;


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 2: CREATE TABLES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE departments (
    department_id   SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    manager_id      INT,                          -- FK added after employees are created
    location        VARCHAR(100)
);

CREATE TABLE employees (
    id              SERIAL PRIMARY KEY,
    first_name      VARCHAR(50)  NOT NULL,
    last_name       VARCHAR(50)  NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    title           VARCHAR(100),
    salary          NUMERIC(12, 2),
    hire_date       DATE,
    department      VARCHAR(100) REFERENCES departments(name) ON UPDATE CASCADE
);

CREATE TABLE salaries (
    id              SERIAL PRIMARY KEY,
    employee_id     INT  NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    month           VARCHAR(7)   NOT NULL,        -- format: YYYY-MM
    base_salary     NUMERIC(12, 2),
    bonus           NUMERIC(12, 2),
    UNIQUE(employee_id, month)
);

CREATE TABLE skills (
    id              SERIAL PRIMARY KEY,
    employee_id     INT  NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    skill           VARCHAR(100) NOT NULL,
    proficiency     VARCHAR(50)  CHECK (proficiency IN ('Beginner', 'Intermediate', 'Advanced'))
);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3: INSERT DEPARTMENTS
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO departments (department_id, name, location) VALUES
    (101, 'Engineering', 'San Francisco'),
    (102, 'HR',          'New York'),
    (103, 'Sales',       'Chicago'),
    (104, 'Finance',     'Boston'),
    (105, 'Marketing',   'Austin'),
    (106, 'Operations',  'Seattle');

-- Reset sequence after manual ID inserts
SELECT setval('departments_department_id_seq', 200);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 4: INSERT EMPLOYEES  (30 realistic employees)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO employees (id, first_name, last_name, email, title, salary, hire_date, department) VALUES
-- Engineering (8 employees)
( 1, 'Alice',   'Johnson',  'alice.johnson@company.com',   'HR Manager',              85000,  '2023-01-15', 'HR'),
( 2, 'Bob',     'Smith',    'bob.smith@company.com',       'Software Engineer',       110000, '2022-07-01', 'Engineering'),
( 3, 'Carol',   'Lee',      'carol.lee@company.com',       'Sales Associate',         75000,  '2024-03-10', 'Sales'),
( 4, 'David',   'Kim',      'david.kim@company.com',       'Financial Analyst',       90000,  '2021-11-20', 'Finance'),
( 5, 'Eva',     'Patel',    'eva.patel@company.com',       'Senior Engineer',         130000, '2020-05-05', 'Engineering'),
( 6, 'Frank',   'Wong',     'frank.wong@company.com',      'DevOps Engineer',         120000, '2023-06-18', 'Engineering'),
( 7, 'Grace',   'Ng',       'grace.ng@company.com',        'Recruiter',               78000,  '2022-02-01', 'HR'),
( 8, 'Henry',   'Brown',    'henry.brown@company.com',     'Sales Manager',           95000,  '2021-08-25', 'Sales'),
( 9, 'Isha',    'Gupta',    'isha.gupta@company.com',      'Data Analyst',            98000,  '2023-03-22', 'Finance'),
(10, 'Jon',     'Park',     'jon.park@company.com',        'Product Manager',         115000, '2022-11-11', 'Engineering'),
-- More employees
(11, 'Karen',   'Martinez', 'karen.martinez@company.com',  'Marketing Manager',       92000,  '2021-04-12', 'Marketing'),
(12, 'Leo',     'Chen',     'leo.chen@company.com',        'Full Stack Engineer',     105000, '2023-09-01', 'Engineering'),
(13, 'Mia',     'Russo',    'mia.russo@company.com',       'Operations Analyst',      82000,  '2022-05-17', 'Operations'),
(14, 'Nate',    'Wilson',   'nate.wilson@company.com',     'Lead Engineer',           140000, '2019-03-03', 'Engineering'),
(15, 'Olivia',  'Taylor',   'olivia.taylor@company.com',   'Sales Executive',         88000,  '2024-01-08', 'Sales'),
(16, 'Peter',   'Davis',    'peter.davis@company.com',     'HR Coordinator',          72000,  '2023-07-20', 'HR'),
(17, 'Quinn',   'Garcia',   'quinn.garcia@company.com',    'Marketing Analyst',       80000,  '2022-10-05', 'Marketing'),
(18, 'Rachel',  'Moore',    'rachel.moore@company.com',    'Finance Manager',         108000, '2020-08-14', 'Finance'),
(19, 'Sam',     'Anderson', 'sam.anderson@company.com',    'Backend Engineer',        112000, '2023-02-28', 'Engineering'),
(20, 'Tina',    'Thomas',   'tina.thomas@company.com',     'Operations Manager',      97000,  '2021-06-30', 'Operations'),
(21, 'Uma',     'Jackson',  'uma.jackson@company.com',     'Sales Associate',         70000,  '2024-05-01', 'Sales'),
(22, 'Victor',  'White',    'victor.white@company.com',    'Senior Data Analyst',     118000, '2020-11-09', 'Finance'),
(23, 'Wendy',   'Harris',   'wendy.harris@company.com',    'Recruiter',               76000,  '2022-08-22', 'HR'),
(24, 'Xander',  'Martin',   'xander.martin@company.com',   'Cloud Architect',         155000, '2019-01-15', 'Engineering'),
(25, 'Yara',    'Thompson', 'yara.thompson@company.com',   'Marketing Coordinator',   74000,  '2023-11-03', 'Marketing'),
(26, 'Zoe',     'Robinson', 'zoe.robinson@company.com',    'Operations Coordinator',  71000,  '2024-02-14', 'Operations'),
(27, 'Aaron',   'Lewis',    'aaron.lewis@company.com',     'Financial Controller',    125000, '2020-03-25', 'Finance'),
(28, 'Bella',   'Walker',   'bella.walker@company.com',    'QA Engineer',             95000,  '2022-12-01', 'Engineering'),
(29, 'Carlos',  'Hall',     'carlos.hall@company.com',     'Sales Director',          145000, '2018-07-10', 'Sales'),
(30, 'Diana',   'Young',    'diana.young@company.com',     'HR Director',             132000, '2017-09-01', 'HR');

-- Reset sequence after manual ID inserts
SELECT setval('employees_id_seq', 100);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 5: SET DEPARTMENT MANAGERS (now employees exist)
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE departments SET manager_id = 30  WHERE name = 'HR';
UPDATE departments SET manager_id = 14  WHERE name = 'Engineering';
UPDATE departments SET manager_id = 29  WHERE name = 'Sales';
UPDATE departments SET manager_id = 18  WHERE name = 'Finance';
UPDATE departments SET manager_id = 11  WHERE name = 'Marketing';
UPDATE departments SET manager_id = 20  WHERE name = 'Operations';


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 6: INSERT SALARY HISTORY (2 snapshots per employee: Jan & Jul 2024)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO salaries (employee_id, month, base_salary, bonus) VALUES
-- January 2024
( 1, '2024-01',  85000, 2000), ( 2, '2024-01', 110000, 5000), ( 3, '2024-01',  75000, 1500),
( 4, '2024-01',  90000, 2500), ( 5, '2024-01', 130000, 6000), ( 6, '2024-01', 120000, 4000),
( 7, '2024-01',  78000, 1000), ( 8, '2024-01',  95000, 3000), ( 9, '2024-01',  98000, 2500),
(10, '2024-01', 115000, 3500), (11, '2024-01',  92000, 2200), (12, '2024-01', 105000, 3200),
(13, '2024-01',  82000, 1800), (14, '2024-01', 140000, 7000), (15, '2024-01',  88000, 2000),
(16, '2024-01',  72000,  900), (17, '2024-01',  80000, 1600), (18, '2024-01', 108000, 4500),
(19, '2024-01', 112000, 4000), (20, '2024-01',  97000, 2800), (21, '2024-01',  70000,  800),
(22, '2024-01', 118000, 5000), (23, '2024-01',  76000, 1100), (24, '2024-01', 155000, 8000),
(25, '2024-01',  74000, 1200), (26, '2024-01',  71000,  750), (27, '2024-01', 125000, 5500),
(28, '2024-01',  95000, 2700), (29, '2024-01', 145000, 9000), (30, '2024-01', 132000, 6500),
-- July 2024 (with raises)
( 1, '2024-07',  88000, 2500), ( 2, '2024-07', 114000, 5500), ( 3, '2024-07',  77000, 1700),
( 4, '2024-07',  93000, 3000), ( 5, '2024-07', 135000, 6500), ( 6, '2024-07', 123000, 4200),
( 7, '2024-07',  80000, 1200), ( 8, '2024-07',  98000, 3200), ( 9, '2024-07', 100000, 2800),
(10, '2024-07', 118000, 3800), (11, '2024-07',  95000, 2500), (12, '2024-07', 108000, 3500),
(13, '2024-07',  84000, 2000), (14, '2024-07', 145000, 7500), (15, '2024-07',  90000, 2200),
(16, '2024-07',  74000, 1000), (17, '2024-07',  82000, 1800), (18, '2024-07', 112000, 5000),
(19, '2024-07', 116000, 4500), (20, '2024-07', 100000, 3000), (21, '2024-07',  72000,  900),
(22, '2024-07', 122000, 5500), (23, '2024-07',  78000, 1300), (24, '2024-07', 160000, 8500),
(25, '2024-07',  76000, 1400), (26, '2024-07',  73000,  850), (27, '2024-07', 130000, 6000),
(28, '2024-07',  98000, 3000), (29, '2024-07', 150000, 9500), (30, '2024-07', 136000, 7000);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 7: INSERT SKILLS
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO skills (employee_id, skill, proficiency) VALUES
-- Alice (HR)
( 1, 'Recruiting',           'Advanced'),    ( 1, 'Onboarding',         'Intermediate'),
-- Bob (Engineering)
( 2, 'Python',               'Advanced'),    ( 2, 'Docker',             'Advanced'),    ( 2, 'AWS',                'Intermediate'),
-- Carol (Sales)
( 3, 'CRM',                  'Intermediate'),( 3, 'Negotiation',        'Advanced'),
-- David (Finance)
( 4, 'Excel',                'Advanced'),    ( 4, 'Financial Modeling', 'Advanced'),
-- Eva (Engineering)
( 5, 'Go',                   'Intermediate'),( 5, 'Distributed Systems','Advanced'),
-- Frank (Engineering)
( 6, 'CI/CD',                'Advanced'),    ( 6, 'Kubernetes',         'Intermediate'),
-- Grace (HR)
( 7, 'Interviewing',         'Advanced'),    ( 7, 'Onboarding',         'Intermediate'),
-- Henry (Sales)
( 8, 'Sales Strategy',       'Advanced'),    ( 8, 'Presentation',       'Advanced'),
-- Isha (Finance)
( 9, 'SQL',                  'Advanced'),    ( 9, 'Data Visualization', 'Intermediate'),
-- Jon (Engineering)
(10, 'Product Management',   'Advanced'),    (10, 'Agile',              'Advanced'),
-- Karen (Marketing)
(11, 'SEO',                  'Advanced'),    (11, 'Content Marketing',  'Intermediate'), (11, 'Google Ads',        'Advanced'),
-- Leo (Engineering)
(12, 'React',                'Advanced'),    (12, 'Node.js',            'Advanced'),    (12, 'PostgreSQL',        'Intermediate'),
-- Mia (Operations)
(13, 'Process Improvement',  'Advanced'),    (13, 'Lean Six Sigma',     'Intermediate'),
-- Nate (Engineering)
(14, 'Java',                 'Advanced'),    (14, 'Microservices',      'Advanced'),    (14, 'System Design',     'Advanced'),
-- Olivia (Sales)
(15, 'B2B Sales',            'Intermediate'),(15, 'Salesforce',         'Advanced'),
-- Peter (HR)
(16, 'HRIS',                 'Intermediate'),(16, 'Benefits Admin',     'Beginner'),
-- Quinn (Marketing)
(17, 'Social Media',         'Advanced'),    (17, 'Analytics',          'Intermediate'),
-- Rachel (Finance)
(18, 'Budgeting',            'Advanced'),    (18, 'SAP',                'Advanced'),    (18, 'Financial Planning', 'Advanced'),
-- Sam (Engineering)
(19, 'Python',               'Advanced'),    (19, 'FastAPI',            'Advanced'),    (19, 'PostgreSQL',        'Advanced'),
-- Tina (Operations)
(20, 'Project Management',   'Advanced'),    (20, 'Vendor Management',  'Intermediate'),
-- Uma (Sales)
(21, 'Cold Calling',         'Intermediate'),(21, 'CRM',                'Beginner'),
-- Victor (Finance)
(22, 'Power BI',             'Advanced'),    (22, 'SQL',                'Advanced'),    (22, 'Python',            'Intermediate'),
-- Wendy (HR)
(23, 'Talent Acquisition',   'Advanced'),    (23, 'LinkedIn Recruiter', 'Advanced'),
-- Xander (Engineering)
(24, 'AWS',                  'Advanced'),    (24, 'GCP',                'Advanced'),    (24, 'Terraform',         'Advanced'),
-- Yara (Marketing)
(25, 'Email Marketing',      'Intermediate'),(25, 'Canva',              'Advanced'),
-- Zoe (Operations)
(26, 'Data Entry',           'Intermediate'),(26, 'Excel',              'Beginner'),
-- Aaron (Finance)
(27, 'GAAP',                 'Advanced'),    (27, 'Financial Reporting','Advanced'),
-- Bella (Engineering)
(28, 'Selenium',             'Advanced'),    (28, 'JIRA',               'Intermediate'),(28, 'Cypress',           'Intermediate'),
-- Carlos (Sales)
(29, 'Enterprise Sales',     'Advanced'),    (29, 'CRM',                'Advanced'),    (29, 'Team Leadership',   'Advanced'),
-- Diana (HR)
(30, 'HR Strategy',          'Advanced'),    (30, 'Labor Law',          'Advanced'),    (30, 'Recruiting',        'Advanced');


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 8: ADD FK constraint on departments.manager_id (after both tables exist)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE departments
    ADD CONSTRAINT fk_dept_manager
    FOREIGN KEY (manager_id) REFERENCES employees(id) ON DELETE SET NULL;


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9: VERIFY — quick row counts
-- ─────────────────────────────────────────────────────────────────────────────

SELECT 'departments' AS "table", COUNT(*) AS rows FROM departments
UNION ALL
SELECT 'employees',              COUNT(*)         FROM employees
UNION ALL
SELECT 'salaries',               COUNT(*)         FROM salaries
UNION ALL
SELECT 'skills',                 COUNT(*)         FROM skills;
