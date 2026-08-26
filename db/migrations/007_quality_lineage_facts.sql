BEGIN;

CREATE TABLE fact_attempt_runs (
    attempt_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    source_family text NOT NULL CHECK (source_family IN ('wb_analytics_task', 'file_artifact')),
    source_ref text NOT NULL CHECK (char_length(source_ref) BETWEEN 1 AND 256),
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    failure_code text CHECK (
        failure_code IS NULL OR failure_code IN ('ALL_ROWS_QUARANTINED', 'SOURCE_UNREADABLE', 'CRASHED')
    ),
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, source_family, source_ref),
    UNIQUE (tenant_id, attempt_id),
    CHECK (status <> 'SUCCEEDED' OR finished_at IS NOT NULL),
    CHECK (status <> 'FAILED' OR failure_code IS NOT NULL)
);

CREATE TABLE stg_quarantine_rows (
    quarantine_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    attempt_id uuid NOT NULL REFERENCES fact_attempt_runs(attempt_id) ON DELETE RESTRICT,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    source_task_id uuid,
    source_row_number integer,
    reason text NOT NULL CHECK (
        reason IN (
            'SCHEMA_DRIFT',
            'STALE',
            'CONFLICTING',
            'PARTIAL',
            'INVALID_DATE',
            'INVALID_PRODUCT',
            'INVALID_COUNT',
            'DUPLICATE_GRAIN'
        )
    ),
    detail jsonb NOT NULL CHECK (jsonb_typeof(detail) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (attempt_id, source_task_id, source_row_number),
    CHECK (source_task_id IS NULL OR source_row_number IS NOT NULL),
    FOREIGN KEY (source_task_id, source_row_number)
        REFERENCES stg_wb_nm_report_rows (task_id, row_number) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, attempt_id)
        REFERENCES fact_attempt_runs (tenant_id, attempt_id) ON DELETE RESTRICT
);

CREATE TABLE fact_order_counts (
    fact_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    attempt_id uuid NOT NULL REFERENCES fact_attempt_runs(attempt_id) ON DELETE RESTRICT,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    calendar_day date NOT NULL,
    order_count integer NOT NULL CHECK (order_count >= 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (attempt_id, tenant_id, nm_id, calendar_day),
    FOREIGN KEY (tenant_id, attempt_id)
        REFERENCES fact_attempt_runs (tenant_id, attempt_id) ON DELETE RESTRICT
);

CREATE INDEX fact_order_counts_grain_idx
    ON fact_order_counts (tenant_id, nm_id, calendar_day DESC);

CREATE TABLE fact_lineage_records (
    lineage_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    attempt_id uuid NOT NULL REFERENCES fact_attempt_runs(attempt_id) ON DELETE RESTRICT,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    evidence_locator text NOT NULL CHECK (char_length(evidence_locator) BETWEEN 1 AND 256),
    parser_version text NOT NULL CHECK (char_length(parser_version) BETWEEN 1 AND 64),
    acquired_via text NOT NULL CHECK (acquired_via IN ('wb_analytics_task', 'manual_xlsx_intake')),
    acquired_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (attempt_id),
    FOREIGN KEY (tenant_id, attempt_id)
        REFERENCES fact_attempt_runs (tenant_id, attempt_id) ON DELETE RESTRICT
);

CREATE TABLE quality_check_results (
    check_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    attempt_id uuid NOT NULL REFERENCES fact_attempt_runs(attempt_id) ON DELETE RESTRICT,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    check_name text NOT NULL CHECK (char_length(check_name) BETWEEN 1 AND 64),
    status text NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    detail jsonb NOT NULL CHECK (jsonb_typeof(detail) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (attempt_id, check_name),
    FOREIGN KEY (tenant_id, attempt_id)
        REFERENCES fact_attempt_runs (tenant_id, attempt_id) ON DELETE RESTRICT
);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (7, 'quality_lineage_facts', 'df2f563aa5c438fa3b6bc0d4fa6e5fbda018e3b7322159c977029b9abca46d07');

COMMIT;
