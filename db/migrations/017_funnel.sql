BEGIN;

-- Story 3.1 (AD-5, AD-3, AD-11, AD-13): daily sales funnel per product, one
-- table for both sources (`v3` daily job, `csv` promotion in Story 3.3).
-- One observation = one product-day payload as WB serialised it; the canonical
-- hash is part of the key, so an identical replay is a no-op (DO NOTHING only
-- on the same canonical_sha256) and a changed payload for the same
-- product-day-source is a new observation. The dictionary columns follow
-- COLUMN_MAP scn001 (AD-5); `payload` keeps the full WB entry as evidence.
-- Like the 012 views, `_latest` ignores run status: an observation is
-- evidence regardless of how its run ended - the funnel job commits every
-- received batch on its own, so a failed batch never cancels received ones
-- (Story 3.1 AC), while facts and SUCCEEDED stay one transaction (AD-3).
CREATE TABLE stg_wb_funnel_obs (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    calendar_day date NOT NULL,
    source text NOT NULL CHECK (source IN ('v3', 'csv')),
    canonical_sha256 char(64) NOT NULL CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$'),
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    open_card integer NOT NULL CHECK (open_card >= 0),
    cart integer NOT NULL CHECK (cart >= 0),
    orders integer NOT NULL CHECK (orders >= 0),
    orders_sum_rub numeric(14,2) NOT NULL,
    buyouts integer NOT NULL CHECK (buyouts >= 0),
    buyouts_sum_rub numeric(14,2) NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    observed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, nm_id, calendar_day, source, canonical_sha256)
);

-- Versions per run (AD-2 shape): a run versions every product-day it observed,
-- copying the dictionary values of the latest observation together with the
-- observation key (canonical_sha256) and its evidence.
CREATE TABLE fact_funnel_daily (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    calendar_day date NOT NULL,
    source text NOT NULL CHECK (source IN ('v3', 'csv')),
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    canonical_sha256 char(64) NOT NULL CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$'),
    evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    open_card integer NOT NULL CHECK (open_card >= 0),
    cart integer NOT NULL CHECK (cart >= 0),
    orders integer NOT NULL CHECK (orders >= 0),
    orders_sum_rub numeric(14,2) NOT NULL,
    buyouts integer NOT NULL CHECK (buyouts >= 0),
    buyouts_sum_rub numeric(14,2) NOT NULL,
    PRIMARY KEY (tenant_id, nm_id, calendar_day, source, run_id)
);

CREATE INDEX stg_wb_funnel_obs_run_idx ON stg_wb_funnel_obs (run_id);
CREATE INDEX stg_wb_funnel_obs_day_idx ON stg_wb_funnel_obs (tenant_id, calendar_day);
CREATE INDEX fact_funnel_daily_run_idx ON fact_funnel_daily (run_id);
CREATE INDEX fact_funnel_daily_day_idx ON fact_funnel_daily (tenant_id, calendar_day);

-- AD-5: DISTINCT ON the key without the hash, newest observation first.
CREATE VIEW stg_wb_funnel_latest WITH (security_invoker = true) AS
SELECT DISTINCT ON (tenant_id, nm_id, calendar_day, source) *
FROM stg_wb_funnel_obs
ORDER BY tenant_id, nm_id, calendar_day, source, observed_at DESC, canonical_sha256 DESC;

-- AD-3 rule (latest SUCCEEDED run per key) with the AD-5 preference of csv over v3.
CREATE VIEW fact_funnel_daily_current WITH (security_invoker = true) AS
SELECT DISTINCT ON (f.tenant_id, f.nm_id, f.calendar_day) f.*
FROM fact_funnel_daily f
JOIN collector_runs r ON r.run_id = f.run_id AND r.tenant_id = f.tenant_id
WHERE r.status = 'SUCCEEDED'
ORDER BY f.tenant_id, f.nm_id, f.calendar_day, CASE f.source WHEN 'csv' THEN 0 ELSE 1 END, r.finished_at DESC, f.run_id DESC;

GRANT SELECT, INSERT ON stg_wb_funnel_obs TO proxima_job_collector;
GRANT SELECT ON stg_wb_funnel_latest TO proxima_job_collector;
GRANT SELECT, INSERT ON fact_funnel_daily TO proxima_job_collector;
GRANT SELECT ON fact_funnel_daily_current TO proxima_job_collector;
GRANT SELECT ON fact_funnel_daily TO proxima_job_norm;
GRANT SELECT ON fact_funnel_daily_current TO proxima_job_norm;

ALTER TABLE stg_wb_funnel_obs ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_funnel_daily ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_collector ON stg_wb_funnel_obs FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON stg_wb_funnel_obs FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_collector ON fact_funnel_daily FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_norm ON fact_funnel_daily FOR SELECT TO proxima_job_norm USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON fact_funnel_daily FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (17, 'funnel', '01546dfb93c12d485234342df94ae1ba2fc4480a49ddc52ab03a0ac40fb8bc1d');
COMMIT;
