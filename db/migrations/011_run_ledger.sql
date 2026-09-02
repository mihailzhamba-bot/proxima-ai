BEGIN;

CREATE ROLE proxima_job_collector NOLOGIN;
CREATE ROLE proxima_job_norm NOLOGIN;
CREATE ROLE proxima_webapp_readonly NOLOGIN;
CREATE ROLE proxima_run_janitor NOLOGIN;

CREATE TABLE collector_runs (
    run_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN ('collect', 'backfill', 'funnel_v3', 'funnel_csv_download', 'funnel_csv_promote', 'norm', 'brief')),
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    git_sha text,
    image_id text,
    notes text,
    CHECK ((status = 'RUNNING' AND finished_at IS NULL) OR (status IN ('SUCCEEDED', 'FAILED') AND finished_at IS NOT NULL))
);

CREATE TABLE collector_run_inputs (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    input_run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE RESTRICT,
    PRIMARY KEY (tenant_id, run_id, input_run_id),
    CHECK (run_id <> input_run_id)
);

CREATE TABLE wb_raw_artifacts (
    artifact_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    endpoint_id text NOT NULL,
    endpoint_path text NOT NULL,
    http_status smallint NOT NULL CHECK (http_status BETWEEN 100 AND 599),
    response_headers jsonb NOT NULL CHECK (jsonb_typeof(response_headers) = 'object'),
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    content_size bigint NOT NULL CHECK (content_size >= 0),
    object_locator text NOT NULL CHECK (object_locator ~ '^artifact://business-signal/sha256/[0-9a-f]{64}$'),
    manifest_sha256 char(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    retrieved_at timestamptz NOT NULL,
    attempt smallint NOT NULL CHECK (attempt >= 1),
    UNIQUE (run_id, endpoint_id, attempt, content_sha256)
);

ALTER TABLE fact_attempt_runs ADD COLUMN collector_run_id uuid NULL REFERENCES collector_runs(run_id) ON DELETE RESTRICT;
ALTER TABLE wb_analytics_report_tasks ADD COLUMN collector_run_id uuid NULL REFERENCES collector_runs(run_id) ON DELETE RESTRICT;

CREATE INDEX wb_raw_artifacts_run_idx ON wb_raw_artifacts (run_id, retrieved_at);

GRANT SELECT, INSERT, UPDATE ON collector_runs TO proxima_job_collector;
GRANT SELECT, INSERT ON collector_run_inputs TO proxima_job_collector;
GRANT SELECT, INSERT ON wb_raw_artifacts TO proxima_job_collector;
GRANT SELECT ON tenants TO proxima_job_collector;
GRANT SELECT, INSERT, UPDATE ON collector_runs TO proxima_job_norm;
GRANT SELECT, INSERT, UPDATE ON collector_run_inputs TO proxima_job_norm;
GRANT SELECT ON collector_runs TO proxima_webapp_readonly;

ALTER TABLE collector_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE collector_run_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE wb_raw_artifacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_collector ON collector_runs FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_norm ON collector_runs FOR ALL TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_webapp ON collector_runs FOR SELECT TO proxima_webapp_readonly USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON collector_runs FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_collector ON collector_run_inputs FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_norm ON collector_run_inputs FOR ALL TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON collector_run_inputs FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_collector ON wb_raw_artifacts FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON wb_raw_artifacts FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (11, 'run_ledger', 'cf01a1a7eb9e31d8b28758ef21ca6b92fc27d443d725c7f5a5f3ad5868497135');
COMMIT;
