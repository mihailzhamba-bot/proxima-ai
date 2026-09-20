BEGIN;

CREATE TABLE wb_analytics_report_tasks (
    task_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    report_type text NOT NULL CHECK (report_type = 'DETAIL_HISTORY_REPORT'),
    period_from date NOT NULL,
    period_to date NOT NULL,
    timezone text NOT NULL CHECK (timezone = 'Europe/Moscow'),
    aggregation_level text NOT NULL CHECK (aggregation_level = 'day'),
    request_body jsonb NOT NULL,
    lifecycle_status text NOT NULL CHECK (
        lifecycle_status IN (
            'RESERVED',
            'CREATE_IN_FLIGHT',
            'WAITING',
            'PROCESSING',
            'RETRY',
            'SUCCESS',
            'REGENERATE_IN_FLIGHT',
            'DOWNLOADED',
            'FAILED',
            'BLOCKED'
        )
    ),
    api_status text,
    consecutive_not_found smallint NOT NULL DEFAULT 0 CHECK (consecutive_not_found >= 0),
    create_replay_count smallint NOT NULL DEFAULT 0 CHECK (create_replay_count BETWEEN 0 AND 2),
    regenerate_count smallint NOT NULL DEFAULT 0 CHECK (regenerate_count BETWEEN 0 AND 2),
    downloaded_sha256 char(64),
    downloaded_size bigint CHECK (downloaded_size IS NULL OR downloaded_size > 0),
    last_error_code text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    downloaded_at timestamptz,
    CHECK (period_from <= period_to),
    CHECK (jsonb_typeof(request_body) = 'object'),
    CHECK (request_body ? 'id'),
    CHECK (request_body ? 'reportType'),
    CHECK (request_body->>'id' = task_id::text),
    CHECK (request_body->>'reportType' = report_type),
    CHECK (downloaded_sha256 IS NULL OR downloaded_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (
        (lifecycle_status = 'DOWNLOADED' AND downloaded_sha256 IS NOT NULL AND downloaded_size IS NOT NULL AND downloaded_at IS NOT NULL)
        OR lifecycle_status <> 'DOWNLOADED'
    ),
    UNIQUE (tenant_id, report_type, period_from, period_to),
    UNIQUE (task_id, tenant_id)
);

CREATE TABLE wb_analytics_quota_events (
    event_id bigserial PRIMARY KEY,
    task_id uuid NOT NULL,
    tenant_id text NOT NULL,
    quota_date date NOT NULL,
    action text NOT NULL CHECK (action IN ('create', 'create_replay', 'regenerate')),
    action_sequence smallint NOT NULL CHECK (action_sequence > 0),
    reserved_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at timestamptz,
    UNIQUE (task_id, action, action_sequence),
    FOREIGN KEY (task_id, tenant_id)
        REFERENCES wb_analytics_report_tasks(task_id, tenant_id) ON DELETE RESTRICT
);

CREATE INDEX wb_analytics_quota_events_daily_idx
    ON wb_analytics_quota_events (tenant_id, quota_date);

CREATE TABLE raw_wb_analytics_responses (
    raw_response_id bigserial PRIMARY KEY,
    response_id uuid NOT NULL UNIQUE,
    task_id uuid NOT NULL REFERENCES wb_analytics_report_tasks(task_id) ON DELETE RESTRICT,
    stage text NOT NULL CHECK (stage IN ('create', 'status', 'regenerate', 'download')),
    http_status smallint NOT NULL CHECK (http_status BETWEEN 100 AND 599),
    response_headers jsonb NOT NULL,
    payload jsonb NOT NULL,
    content_sha256 char(64) NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    retrieved_at timestamptz NOT NULL,
    persisted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(response_headers) = 'object'),
    CHECK (jsonb_typeof(payload) = 'object'),
    CHECK (payload ? 'encoding'),
    CHECK (payload->>'encoding' = 'base64'),
    CHECK (payload ? 'body_base64')
);

CREATE INDEX raw_wb_analytics_responses_task_stage_idx
    ON raw_wb_analytics_responses (task_id, stage, retrieved_at);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (3, 'wb_analytics_raw', '0448bb64551f0426d61247706fa1a7a900c2328073e52ad852d0184bfb8da464');

COMMIT;
