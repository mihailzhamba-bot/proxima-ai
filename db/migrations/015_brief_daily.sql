BEGIN;

CREATE TABLE brief_daily (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    brief_day date NOT NULL,
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('ok', 'insufficient', 'blocked')),
    payload jsonb NOT NULL,
    PRIMARY KEY (tenant_id, brief_day, run_id)
);

CREATE INDEX brief_daily_run_idx ON brief_daily (run_id);
CREATE INDEX brief_daily_day_idx ON brief_daily (tenant_id, brief_day);

CREATE VIEW brief_current WITH (security_invoker = true) AS
SELECT DISTINCT ON (b.tenant_id) b.*
FROM brief_daily b
JOIN collector_runs r ON r.run_id = b.run_id AND r.tenant_id = b.tenant_id
WHERE r.status = 'SUCCEEDED'
ORDER BY b.tenant_id, b.brief_day DESC, r.finished_at DESC, b.run_id DESC;

GRANT SELECT ON brief_daily TO proxima_job_norm;
GRANT INSERT ON brief_daily TO proxima_job_norm;
GRANT UPDATE ON brief_daily TO proxima_job_norm;
GRANT SELECT ON brief_current TO proxima_job_norm;
GRANT SELECT ON brief_daily TO proxima_webapp_readonly;
GRANT SELECT ON brief_current TO proxima_webapp_readonly;

ALTER TABLE brief_daily ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_norm ON brief_daily FOR ALL TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_webapp ON brief_daily FOR SELECT TO proxima_webapp_readonly USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON brief_daily FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (15, 'brief_daily', '28d9367c05d899ec492fbfe80eb23a16408b5c7673cb0955bc94d9904d67056e');
COMMIT;
