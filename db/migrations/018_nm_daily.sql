BEGIN;

-- Story 4.0 (AD-19, AD-2, AD-3, AD-11, AD-13): the nmId and subject grain for
-- anomalies. The same collect/backfill run that versions fact_cabinet_daily
-- writes, in the same transaction, one dictionary version per nmId seen in
-- stg_wb_orders_latest UNION stg_wb_sales_latest and one daily row per
-- versioned day x nmId with the cabinet formulas (glossary.md) grouped by
-- payload.nmId. A missing row means "day not versioned", a zero row means
-- "no observations" (AD-2). The subject is an attribute of the SKU as seen by
-- the run, not of the day: JOIN ... USING (tenant_id, nm_id, run_id) gives the
-- subject a specific run saw, dim_nm_subject_current the latest one.
CREATE TABLE dim_nm_subject (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    subject_name text NOT NULL,
    category_name text NOT NULL,
    brand text NOT NULL,
    supplier_article text NOT NULL,
    last_change_at timestamptz NOT NULL,
    evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (tenant_id, nm_id, run_id)
);

CREATE TABLE fact_nm_daily (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    calendar_day date NOT NULL,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    orders_count integer NOT NULL CHECK (orders_count >= 0),
    cancelled_count integer NOT NULL CHECK (cancelled_count >= 0),
    sales_count integer NOT NULL CHECK (sales_count >= 0),
    returns_count integer NOT NULL CHECK (returns_count >= 0),
    revenue_rub numeric(14,2) NOT NULL,
    forpay_rub numeric(14,2) NOT NULL,
    evidence_sha256 char(64)[] NOT NULL,
    PRIMARY KEY (tenant_id, calendar_day, nm_id, run_id)
);

CREATE INDEX dim_nm_subject_run_idx ON dim_nm_subject (run_id);
CREATE INDEX fact_nm_daily_run_idx ON fact_nm_daily (run_id);
CREATE INDEX fact_nm_daily_day_idx ON fact_nm_daily (tenant_id, calendar_day);
CREATE INDEX fact_nm_daily_nm_idx ON fact_nm_daily (tenant_id, nm_id, calendar_day);

-- AD-3 rule: the latest SUCCEEDED run per key.
CREATE VIEW dim_nm_subject_current WITH (security_invoker = true) AS
SELECT DISTINCT ON (d.tenant_id, d.nm_id) d.*
FROM dim_nm_subject d
JOIN collector_runs r ON r.run_id = d.run_id AND r.tenant_id = d.tenant_id
WHERE r.status = 'SUCCEEDED'
ORDER BY d.tenant_id, d.nm_id, r.finished_at DESC, d.run_id DESC;

CREATE VIEW fact_nm_daily_current WITH (security_invoker = true) AS
SELECT DISTINCT ON (f.tenant_id, f.calendar_day, f.nm_id) f.*
FROM fact_nm_daily f
JOIN collector_runs r ON r.run_id = f.run_id AND r.tenant_id = f.tenant_id
WHERE r.status = 'SUCCEEDED'
ORDER BY f.tenant_id, f.calendar_day, f.nm_id, r.finished_at DESC, f.run_id DESC;

-- AD-11 template: the collector writes both tables, norm reads them for the
-- detector adapter (Story 4.1), the janitor deletes through its LOGIN role.
-- proxima_webapp_readonly gets no grant: the webapp reads brief_current and
-- data_status_current only (AD-9); anomalies travel in brief_daily.payload.
GRANT SELECT, INSERT ON dim_nm_subject TO proxima_job_collector;
GRANT SELECT ON dim_nm_subject_current TO proxima_job_collector;
GRANT SELECT, INSERT ON fact_nm_daily TO proxima_job_collector;
GRANT SELECT ON fact_nm_daily_current TO proxima_job_collector;
GRANT SELECT ON dim_nm_subject TO proxima_job_norm;
GRANT SELECT ON dim_nm_subject_current TO proxima_job_norm;
GRANT SELECT ON fact_nm_daily TO proxima_job_norm;
GRANT SELECT ON fact_nm_daily_current TO proxima_job_norm;

ALTER TABLE dim_nm_subject ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_nm_daily ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_collector ON dim_nm_subject FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_norm ON dim_nm_subject FOR SELECT TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON dim_nm_subject FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_collector ON fact_nm_daily FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_norm ON fact_nm_daily FOR SELECT TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON fact_nm_daily FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (18, 'nm_daily', '90572e353fb92f8c1c77ba6486dff4024febe55b48e795758125d17a8bd07a92');
COMMIT;
