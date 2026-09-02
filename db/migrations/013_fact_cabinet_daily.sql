BEGIN;

CREATE TABLE fact_cabinet_daily (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    calendar_day date NOT NULL,
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    orders_count integer NOT NULL CHECK (orders_count >= 0),
    cancelled_count integer NOT NULL CHECK (cancelled_count >= 0),
    sales_count integer NOT NULL CHECK (sales_count >= 0),
    returns_count integer NOT NULL CHECK (returns_count >= 0),
    revenue_rub numeric(14,2) NOT NULL,
    forpay_rub numeric(14,2) NOT NULL,
    evidence_sha256 char(64)[] NOT NULL,
    PRIMARY KEY (tenant_id, calendar_day, run_id)
);

CREATE INDEX fact_cabinet_daily_run_idx ON fact_cabinet_daily (run_id);
CREATE INDEX fact_cabinet_daily_day_idx ON fact_cabinet_daily (tenant_id, calendar_day);

CREATE VIEW fact_cabinet_daily_current WITH (security_invoker = true) AS
SELECT DISTINCT ON (f.tenant_id, f.calendar_day) f.*
FROM fact_cabinet_daily f
JOIN collector_runs r ON r.run_id = f.run_id AND r.tenant_id = f.tenant_id
WHERE r.status = 'SUCCEEDED'
ORDER BY f.tenant_id, f.calendar_day, r.finished_at DESC, f.run_id DESC;

CREATE VIEW data_status_current WITH (security_invoker = true) AS
SELECT t.tenant_id,
       facts.last_full_day,
       runs.collected_at,
       COALESCE(
           runs.collected_at < now() - interval '24 hours'
           OR facts.last_full_day < (now() AT TIME ZONE 'Europe/Moscow')::date - 1,
           true
       ) AS stale
FROM tenants t
LEFT JOIN LATERAL (
    SELECT max(f.calendar_day) AS last_full_day
    FROM fact_cabinet_daily_current f
    WHERE f.tenant_id = t.tenant_id
) facts ON true
LEFT JOIN LATERAL (
    SELECT max(r.finished_at) AS collected_at
    FROM collector_runs r
    WHERE r.tenant_id = t.tenant_id
      AND r.status = 'SUCCEEDED'
      AND r.kind IN ('collect', 'backfill')
) runs ON true
WHERE t.tenant_id = current_setting('proxima.tenant_id', true);

GRANT SELECT, INSERT, UPDATE ON fact_cabinet_daily TO proxima_job_collector;
GRANT SELECT ON fact_cabinet_daily_current TO proxima_job_collector;
GRANT SELECT ON data_status_current TO proxima_job_collector;
GRANT SELECT ON fact_cabinet_daily TO proxima_job_norm;
GRANT SELECT ON fact_cabinet_daily_current TO proxima_job_norm;
GRANT SELECT ON data_status_current TO proxima_job_norm;
GRANT SELECT ON tenants TO proxima_job_norm;
GRANT SELECT ON fact_cabinet_daily TO proxima_webapp_readonly;
GRANT SELECT ON fact_cabinet_daily_current TO proxima_webapp_readonly;
GRANT SELECT ON data_status_current TO proxima_webapp_readonly;
GRANT SELECT ON tenants TO proxima_webapp_readonly;

ALTER TABLE fact_cabinet_daily ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_collector ON fact_cabinet_daily FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_norm ON fact_cabinet_daily FOR SELECT TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_webapp ON fact_cabinet_daily FOR SELECT TO proxima_webapp_readonly USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON fact_cabinet_daily FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (13, 'fact_cabinet_daily', '8eeca5c1b99ebb13e29faa9992ae13fe99c9306621ec529865713c6b511250a4');
COMMIT;
