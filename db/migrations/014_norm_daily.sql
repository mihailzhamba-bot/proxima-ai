BEGIN;

CREATE TABLE norm_daily (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    evaluation_day date NOT NULL,
    metric text NOT NULL CHECK (metric IN ('orders', 'revenue')),
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    window_days integer NOT NULL CHECK (window_days = 14),
    sample_days integer NOT NULL CHECK (sample_days >= 0 AND sample_days <= 14),
    value numeric(14,2) NOT NULL,
    status text NOT NULL CHECK (status IN ('ok', 'insufficient')),
    source_sha256 char(64)[] NOT NULL,
    CONSTRAINT norm_daily_status_matches_sample CHECK ((sample_days = 14) = (status = 'ok')),
    PRIMARY KEY (tenant_id, evaluation_day, metric, run_id)
);

CREATE INDEX norm_daily_run_idx ON norm_daily (run_id);
CREATE INDEX norm_daily_day_idx ON norm_daily (tenant_id, evaluation_day);

CREATE VIEW norm_daily_current WITH (security_invoker = true) AS
SELECT DISTINCT ON (n.tenant_id, n.evaluation_day, n.metric) n.*
FROM norm_daily n
JOIN collector_runs r ON r.run_id = n.run_id AND r.tenant_id = n.tenant_id
WHERE r.status = 'SUCCEEDED'
ORDER BY n.tenant_id, n.evaluation_day, n.metric, r.finished_at DESC, n.run_id DESC;

GRANT SELECT ON norm_daily TO proxima_job_norm;
GRANT INSERT ON norm_daily TO proxima_job_norm;
GRANT SELECT ON norm_daily_current TO proxima_job_norm;
GRANT SELECT ON norm_daily TO proxima_webapp_readonly;
GRANT SELECT ON norm_daily_current TO proxima_webapp_readonly;

ALTER TABLE norm_daily ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_norm ON norm_daily FOR ALL TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_webapp ON norm_daily FOR SELECT TO proxima_webapp_readonly USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON norm_daily FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (14, 'norm_daily', '6ed32f1efb76e35e7a4c1071e1797f3c1c41bcfaf3cf6bb7582c5665619f7e55');
COMMIT;
