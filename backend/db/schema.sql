-- ============================================================
-- Project Management Platform - Database Schema
-- ============================================================

CREATE TABLE IF NOT EXISTS roles (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'planning'
                    CHECK (status IN ('planning','active','on_hold','completed','cancelled')),
    department      VARCHAR(100),
    start_date      DATE,
    end_date        DATE,
    deadline        DATE,
    budget_planned  NUMERIC(12,2) DEFAULT 0,
    budget_consumed NUMERIC(12,2) DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resources (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(150) NOT NULL,
    email      VARCHAR(255) UNIQUE NOT NULL,
    title      VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deliverables (
    id             SERIAL PRIMARY KEY,
    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name           VARCHAR(200) NOT NULL,
    description    TEXT,
    status         VARCHAR(20) NOT NULL DEFAULT 'not_started'
                   CHECK (status IN ('not_started','in_progress','blocked','completed')),
    completion_pct INTEGER DEFAULT 0 CHECK (completion_pct BETWEEN 0 AND 100),
    due_date       DATE,
    created_at     TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deliverable_dependencies (
    deliverable_id INTEGER NOT NULL REFERENCES deliverables(id) ON DELETE CASCADE,
    depends_on_id  INTEGER NOT NULL REFERENCES deliverables(id) ON DELETE CASCADE,
    PRIMARY KEY (deliverable_id, depends_on_id),
    CHECK (deliverable_id <> depends_on_id)
);

CREATE TABLE IF NOT EXISTS allocations (
    id             SERIAL PRIMARY KEY,
    resource_id    INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    allocation_pct INTEGER DEFAULT 0 CHECK (allocation_pct BETWEEN 0 AND 100),
    start_date     DATE,
    end_date       DATE,
    UNIQUE (resource_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_projects_status      ON projects(status);
CREATE INDEX IF NOT EXISTS idx_deliverables_status  ON deliverables(status);
CREATE INDEX IF NOT EXISTS idx_deliverables_project ON deliverables(project_id);
CREATE INDEX IF NOT EXISTS idx_allocations_resource ON allocations(resource_id);
CREATE INDEX IF NOT EXISTS idx_allocations_project  ON allocations(project_id);

INSERT INTO roles (name) VALUES ('Admin'),('Manager'),('Contributor'),('Viewer')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- Activity log / audit trail
-- ============================================================
-- user_id keeps a FK to users but survives deletion (SET NULL); username and
-- entity_name are denormalized so history stays readable after the referenced
-- rows are gone. `changes` holds field-level [{field, old, new}] for updates.

CREATE TABLE IF NOT EXISTS activity_log (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username    VARCHAR(100),
    action      VARCHAR(20)  NOT NULL CHECK (action IN ('created','updated','deleted')),
    entity_type VARCHAR(30)  NOT NULL
                CHECK (entity_type IN ('project','deliverable','resource','allocation','dependency','user')),
    entity_id   INTEGER,
    entity_name VARCHAR(255),
    changes     JSONB,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_entity  ON activity_log(entity_type);
CREATE INDEX IF NOT EXISTS idx_activity_user    ON activity_log(user_id);