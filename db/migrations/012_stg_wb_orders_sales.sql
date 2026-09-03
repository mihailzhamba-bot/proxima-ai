BEGIN;

-- Story 1.4 (AD-2, AD-3, AD-11, AD-13): row-level observations of WB Statistics
-- orders and sales. One row = one observation of a natural key at its WB
-- lastChangeDate. Observations are append-only; a replay of the same
-- (key, lastChangeDate) with the same canonical payload is a no-op, a different
-- payload is WB_SCHEMA_DRIFT raised by the job. The _latest views are the only
-- input of the daily aggregator (Story 1.6) and deliberately ignore run status:
-- an observation is evidence regardless of how its run ended.
CREATE TABLE stg_wb_orders_obs (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    srid text NOT NULL CHECK (srid <> ''),
    last_change_at timestamptz NOT NULL,
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    canonical_sha256 char(64) NOT NULL CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    observed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, srid, last_change_at)
);

CREATE TABLE stg_wb_sales_obs (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    sale_id text NOT NULL CHECK (sale_id <> ''),
    last_change_at timestamptz NOT NULL,
    run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE,
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    canonical_sha256 char(64) NOT NULL CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    observed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, sale_id, last_change_at)
);

CREATE INDEX stg_wb_orders_obs_run_idx ON stg_wb_orders_obs (run_id);
CREATE INDEX stg_wb_orders_obs_change_idx ON stg_wb_orders_obs (tenant_id, last_change_at);
CREATE INDEX stg_wb_sales_obs_run_idx ON stg_wb_sales_obs (run_id);
CREATE INDEX stg_wb_sales_obs_change_idx ON stg_wb_sales_obs (tenant_id, last_change_at);

CREATE VIEW stg_wb_orders_latest WITH (security_invoker = true) AS
SELECT DISTINCT ON (tenant_id, srid) *
FROM stg_wb_orders_obs
ORDER BY tenant_id, srid, last_change_at DESC;

CREATE VIEW stg_wb_sales_latest WITH (security_invoker = true) AS
SELECT DISTINCT ON (tenant_id, sale_id) *
FROM stg_wb_sales_obs
ORDER BY tenant_id, sale_id, last_change_at DESC;

GRANT SELECT, INSERT ON stg_wb_orders_obs TO proxima_job_collector;
GRANT SELECT, INSERT ON stg_wb_sales_obs TO proxima_job_collector;
GRANT SELECT ON stg_wb_orders_latest TO proxima_job_collector;
GRANT SELECT ON stg_wb_sales_latest TO proxima_job_collector;

ALTER TABLE stg_wb_orders_obs ENABLE ROW LEVEL SECURITY;
ALTER TABLE stg_wb_sales_obs ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_collector ON stg_wb_orders_obs FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON stg_wb_orders_obs FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_collector ON stg_wb_sales_obs FOR ALL TO proxima_job_collector USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_janitor ON stg_wb_sales_obs FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (12, 'stg_wb_orders_sales', '2c15509485970a146b854115c09f5f0be168e88bd30abb57d3b3024565528d7f');
COMMIT;
