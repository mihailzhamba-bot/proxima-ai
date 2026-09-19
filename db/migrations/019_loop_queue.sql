BEGIN;

-- LOOP pilot, approved by Mike 2026-09-13. Auth and domain grants are separate.
CREATE ROLE proxima_auth_writer NOLOGIN;
CREATE ROLE proxima_loop_writer NOLOGIN;
CREATE SCHEMA webapp_auth;
CREATE TABLE webapp_auth."user" (
    id text PRIMARY KEY, name text NOT NULL, email text NOT NULL UNIQUE,
    email_verified boolean NOT NULL DEFAULT false, image text,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE webapp_auth."session" (
    id text PRIMARY KEY, token text NOT NULL UNIQUE, expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    ip_address text, user_agent text,
    user_id text NOT NULL REFERENCES webapp_auth."user"(id) ON DELETE CASCADE
);
CREATE TABLE webapp_auth."account" (
    id text PRIMARY KEY, account_id text NOT NULL, provider_id text NOT NULL,
    user_id text NOT NULL REFERENCES webapp_auth."user"(id) ON DELETE CASCADE,
    access_token text, refresh_token text, id_token text,
    access_token_expires_at timestamptz, refresh_token_expires_at timestamptz,
    scope text, password text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider_id, account_id)
);
CREATE TABLE webapp_auth."verification" (
    id text PRIMARY KEY, identifier text NOT NULL, value text NOT NULL,
    expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX auth_session_user_idx ON webapp_auth."session"(user_id);
GRANT USAGE ON SCHEMA webapp_auth TO proxima_auth_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON webapp_auth."user" TO proxima_auth_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON webapp_auth."session" TO proxima_auth_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON webapp_auth."account" TO proxima_auth_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON webapp_auth."verification" TO proxima_auth_writer;

-- No synthetic collector kind. Each command has its own durable workflow run.
CREATE TABLE workflow_runs (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    run_id uuid NOT NULL, actor_id text NOT NULL, command text NOT NULL,
    idempotency_key text NOT NULL, request_hash text NOT NULL CHECK (length(request_hash) = 64),
    state text NOT NULL CHECK (state IN ('running', 'succeeded', 'cancelled', 'interrupted')),
    result jsonb,
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt > 0),
    created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
    PRIMARY KEY (tenant_id, run_id), UNIQUE (tenant_id, actor_id, idempotency_key)
);
CREATE TABLE cabinet_memberships (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    user_id text NOT NULL REFERENCES webapp_auth."user"(id) ON DELETE RESTRICT,
    role text NOT NULL CHECK (role IN ('owner', 'employee')),
    active boolean NOT NULL DEFAULT true, run_id uuid NOT NULL,
    PRIMARY KEY (tenant_id, user_id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES workflow_runs(tenant_id, run_id) ON DELETE RESTRICT
);
CREATE TABLE decision_records (
    tenant_id text NOT NULL, decision_id uuid NOT NULL, run_id uuid NOT NULL,
    signal_id text NOT NULL, actor_id text NOT NULL,
    source_brief_run_id uuid REFERENCES collector_runs(run_id) ON DELETE SET NULL,
    signal_snapshot jsonb NOT NULL, diagnosis_snapshot jsonb NOT NULL, payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, decision_id), UNIQUE (tenant_id, run_id), UNIQUE (tenant_id, signal_id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES workflow_runs(tenant_id, run_id) ON DELETE RESTRICT
);
CREATE TABLE loop_tasks (
    tenant_id text NOT NULL, task_id uuid NOT NULL, decision_id uuid NOT NULL, run_id uuid NOT NULL,
    assignee_id text NOT NULL, action text NOT NULL CHECK (length(trim(action)) > 0),
    due_at timestamptz NOT NULL, expected_outcome text NOT NULL CHECK (length(trim(expected_outcome)) > 0),
    horizon_days integer NOT NULL CHECK (horizon_days BETWEEN 1 AND 365),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, task_id), UNIQUE (tenant_id, decision_id),
    FOREIGN KEY (tenant_id, decision_id) REFERENCES decision_records(tenant_id, decision_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, assignee_id) REFERENCES cabinet_memberships(tenant_id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, run_id) REFERENCES workflow_runs(tenant_id, run_id) ON DELETE RESTRICT
);
CREATE TABLE task_events (
    tenant_id text NOT NULL, event_id uuid NOT NULL, task_id uuid NOT NULL, run_id uuid NOT NULL,
    actor_id text NOT NULL, kind text NOT NULL CHECK (kind IN ('blocked', 'completed', 'cancelled')),
    evidence text NOT NULL CHECK (length(trim(evidence)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (tenant_id, event_id),
    UNIQUE (tenant_id, task_id, kind), UNIQUE (tenant_id, run_id),
    FOREIGN KEY (tenant_id, task_id) REFERENCES loop_tasks(tenant_id, task_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, run_id) REFERENCES workflow_runs(tenant_id, run_id) ON DELETE RESTRICT
);
CREATE TABLE task_observations (
    tenant_id text NOT NULL, observation_id uuid NOT NULL, task_id uuid NOT NULL, run_id uuid NOT NULL,
    actor_id text NOT NULL, status text NOT NULL CHECK (status IN ('pending', 'unknown', 'observed')),
    reason text NOT NULL, snapshot jsonb, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, observation_id), UNIQUE (tenant_id, run_id),
    FOREIGN KEY (tenant_id, task_id) REFERENCES loop_tasks(tenant_id, task_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, run_id) REFERENCES workflow_runs(tenant_id, run_id) ON DELETE RESTRICT
);
CREATE INDEX loop_tasks_assignee_idx ON loop_tasks(tenant_id, assignee_id, created_at);
CREATE INDEX task_observations_task_idx ON task_observations(tenant_id, task_id, created_at);

ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_loop ON workflow_runs FOR ALL TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
GRANT SELECT ON workflow_runs TO proxima_loop_writer;
GRANT INSERT ON workflow_runs TO proxima_loop_writer;

ALTER TABLE cabinet_memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_loop ON cabinet_memberships FOR ALL TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
GRANT SELECT ON cabinet_memberships TO proxima_loop_writer;

ALTER TABLE decision_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_loop ON decision_records FOR ALL TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
GRANT SELECT ON decision_records TO proxima_loop_writer;
GRANT INSERT ON decision_records TO proxima_loop_writer;

ALTER TABLE loop_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_loop ON loop_tasks FOR ALL TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
GRANT SELECT ON loop_tasks TO proxima_loop_writer;
GRANT INSERT ON loop_tasks TO proxima_loop_writer;

ALTER TABLE task_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_loop ON task_events FOR ALL TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
GRANT SELECT ON task_events TO proxima_loop_writer;
GRANT INSERT ON task_events TO proxima_loop_writer;

ALTER TABLE task_observations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_loop ON task_observations FOR ALL TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
GRANT SELECT ON task_observations TO proxima_loop_writer;
GRANT INSERT ON task_observations TO proxima_loop_writer;
GRANT UPDATE ON workflow_runs TO proxima_loop_writer;
-- Decisions, tasks and events have no UPDATE/DELETE grant; membership is operator-managed.
GRANT SELECT ON brief_daily TO proxima_loop_writer;
GRANT SELECT ON brief_current TO proxima_loop_writer;
CREATE POLICY tenant_isolation_loop_read ON brief_daily FOR SELECT TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true));
GRANT SELECT ON collector_runs TO proxima_loop_writer;
CREATE POLICY tenant_isolation_loop_read ON collector_runs FOR SELECT TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true));
-- data_status_current is a security-invoker view with explicit tenant filtering.
GRANT SELECT ON data_status_current TO proxima_loop_writer;

GRANT SELECT ON tenants TO proxima_loop_writer;
GRANT SELECT ON fact_cabinet_daily TO proxima_loop_writer;
GRANT SELECT ON fact_cabinet_daily_current TO proxima_loop_writer;
CREATE POLICY tenant_isolation_loop_read ON fact_cabinet_daily FOR SELECT TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true));

GRANT SELECT ON fact_nm_daily TO proxima_loop_writer;
GRANT SELECT ON fact_nm_daily_current TO proxima_loop_writer;
CREATE POLICY tenant_isolation_loop_read ON fact_nm_daily FOR SELECT TO proxima_loop_writer USING (tenant_id = current_setting('proxima.tenant_id', true));

GRANT USAGE ON SCHEMA webapp_auth TO proxima_loop_writer;
GRANT SELECT (id, name) ON webapp_auth."user" TO proxima_loop_writer;

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (19, 'loop_queue', 'ef006b6e4a853d3095a6bbd78f76a96c716b4ac8b079f56a45c68f9c7c571482');
COMMIT;
