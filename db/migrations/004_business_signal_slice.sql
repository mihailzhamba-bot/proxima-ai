BEGIN;

CREATE TABLE dim_product (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    internal_article text NOT NULL CHECK (char_length(internal_article) BETWEEN 1 AND 128),
    cogs_rub numeric(14, 2) NOT NULL CHECK (cogs_rub >= 0),
    lead_time_days integer NOT NULL CHECK (lead_time_days > 0),
    safety_buffer_days integer NOT NULL CHECK (safety_buffer_days >= 0),
    effective_from date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, nm_id, effective_from),
    UNIQUE (tenant_id, internal_article, effective_from)
);

CREATE INDEX dim_product_current_idx
    ON dim_product (tenant_id, nm_id, effective_from DESC);

CREATE TABLE dim_warehouse_map (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    sales_warehouse_name text NOT NULL CHECK (char_length(sales_warehouse_name) BETWEEN 1 AND 256),
    stock_warehouse_name text NOT NULL CHECK (char_length(stock_warehouse_name) BETWEEN 1 AND 256),
    canonical_warehouse text NOT NULL CHECK (char_length(canonical_warehouse) BETWEEN 1 AND 256),
    effective_from date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, sales_warehouse_name, effective_from),
    UNIQUE (tenant_id, stock_warehouse_name, effective_from)
);

CREATE INDEX dim_warehouse_map_current_idx
    ON dim_warehouse_map (tenant_id, effective_from DESC);

CREATE TABLE business_signal_runs (
    run_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (
        status IN ('RUNNING', 'NO_SIGNAL', 'BLOCKED', 'READY', 'SENT', 'SEND_FAILED')
    ),
    window_from date NOT NULL,
    window_to date NOT NULL,
    timezone text NOT NULL CHECK (timezone = 'Europe/Moscow'),
    block_reason text,
    selected_nm_id bigint,
    selected_internal_article text,
    selected_warehouse text,
    stock_quantity integer,
    velocity_units_per_day numeric(18, 6),
    days_cover integer,
    threshold_days integer,
    margin_per_unit_rub numeric(14, 2),
    stock_as_of timestamptz,
    telegram_attempted_at timestamptz,
    telegram_message_id bigint,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamptz,
    CHECK (window_from <= window_to),
    CHECK (block_reason IS NULL OR char_length(block_reason) BETWEEN 1 AND 128),
    CHECK (stock_quantity IS NULL OR stock_quantity >= 0),
    CHECK (velocity_units_per_day IS NULL OR velocity_units_per_day > 0),
    CHECK (days_cover IS NULL OR days_cover >= 0),
    CHECK (threshold_days IS NULL OR threshold_days > 0),
    CHECK (
        (status IN ('READY', 'SENT', 'SEND_FAILED')
            AND selected_nm_id IS NOT NULL
            AND selected_internal_article IS NOT NULL
            AND selected_warehouse IS NOT NULL
            AND stock_quantity IS NOT NULL
            AND velocity_units_per_day IS NOT NULL
            AND days_cover IS NOT NULL
            AND threshold_days IS NOT NULL
            AND margin_per_unit_rub IS NOT NULL
            AND stock_as_of IS NOT NULL)
        OR status NOT IN ('READY', 'SENT', 'SEND_FAILED')
    ),
    CHECK (
        (status = 'SENT' AND telegram_attempted_at IS NOT NULL AND telegram_message_id IS NOT NULL)
        OR status <> 'SENT'
    )
);

CREATE INDEX business_signal_runs_tenant_created_idx
    ON business_signal_runs (tenant_id, created_at DESC);

CREATE TABLE business_signal_raw_artifacts (
    raw_artifact_id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES business_signal_runs(run_id) ON DELETE RESTRICT,
    source text NOT NULL CHECK (
        source IN ('official_wb_statistics', 'official_wb_analytics', 'official_wb_finance')
    ),
    stage text NOT NULL CHECK (char_length(stage) BETWEEN 1 AND 64),
    page_sequence integer NOT NULL CHECK (page_sequence >= 0),
    endpoint_path text NOT NULL CHECK (endpoint_path LIKE '/%'),
    http_status smallint NOT NULL CHECK (http_status BETWEEN 100 AND 599),
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    content_size bigint NOT NULL CHECK (content_size >= 0),
    object_locator text NOT NULL CHECK (object_locator ~ '^artifact://business-signal/sha256/[0-9a-f]{64}$'),
    manifest_sha256 char(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    retrieved_at timestamptz NOT NULL,
    persisted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, source, stage, page_sequence),
    UNIQUE (run_id, object_locator, source, stage, page_sequence)
);

CREATE INDEX business_signal_raw_artifacts_run_idx
    ON business_signal_raw_artifacts (run_id, source, stage, page_sequence);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (4, 'business_signal_slice', '94174bc9c0537d6ed168bce547f205b602fcd00854176554a799b8d8d62b99be');

COMMIT;
