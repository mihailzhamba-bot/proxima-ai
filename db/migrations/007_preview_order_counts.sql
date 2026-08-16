BEGIN;

CREATE TABLE artifact_parse_runs (
    run_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    task_id uuid NOT NULL,
    profile text NOT NULL CHECK (profile = 'wb_detail_history_v1'),
    artifact_sha256 char(64) NOT NULL,
    lifecycle_status text NOT NULL CHECK (lifecycle_status IN ('RUNNING', 'SUCCEEDED')),
    staged_row_count integer NOT NULL CHECK (staged_row_count >= 0),
    valid_row_count integer NOT NULL CHECK (valid_row_count >= 0),
    quarantined_row_count integer NOT NULL CHECK (quarantined_row_count >= 0),
    preview_row_count integer NOT NULL CHECK (preview_row_count >= 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamptz,
    UNIQUE (task_id, profile),
    UNIQUE (run_id, task_id),
    CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (valid_row_count + quarantined_row_count = staged_row_count),
    CHECK ((lifecycle_status = 'SUCCEEDED') = (completed_at IS NOT NULL)),
    FOREIGN KEY (task_id, tenant_id)
        REFERENCES wb_analytics_report_tasks(task_id, tenant_id) ON DELETE RESTRICT
);

CREATE TABLE preview_quarantine_rows (
    task_id uuid NOT NULL,
    run_id uuid NOT NULL,
    row_number integer NOT NULL CHECK (row_number > 0),
    reason text NOT NULL CHECK (
        reason IN ('NM_ID_INVALID', 'ROW_DATE_INVALID', 'ORDER_COUNT_INVALID')
    ),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (task_id, row_number),
    FOREIGN KEY (run_id, task_id)
        REFERENCES artifact_parse_runs(run_id, task_id) ON DELETE RESTRICT
);

CREATE TABLE preview_order_counts (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    task_id uuid NOT NULL,
    run_id uuid NOT NULL,
    calendar_day date NOT NULL,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    order_count integer NOT NULL CHECK (order_count >= 0),
    release_status text NOT NULL DEFAULT 'unreleased' CHECK (release_status = 'unreleased'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, task_id, calendar_day, nm_id),
    FOREIGN KEY (run_id, task_id)
        REFERENCES artifact_parse_runs(run_id, task_id) ON DELETE RESTRICT,
    FOREIGN KEY (task_id, tenant_id)
        REFERENCES wb_analytics_report_tasks(task_id, tenant_id) ON DELETE RESTRICT
);

CREATE INDEX preview_order_counts_day_idx
    ON preview_order_counts (tenant_id, calendar_day DESC, nm_id);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (7, 'preview_order_counts', '788225ce2d5b3d9093bf2a39da24297e298e6752f9cf77b862eaf7499ef61f86');

COMMIT;
