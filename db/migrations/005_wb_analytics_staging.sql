BEGIN;

CREATE TABLE stg_wb_nm_report_rows (
    task_id uuid NOT NULL REFERENCES wb_analytics_report_tasks(task_id) ON DELETE RESTRICT,
    row_number integer NOT NULL CHECK (row_number > 0),
    nm_id bigint,
    row_date date,
    payload jsonb NOT NULL,
    staged_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, row_number),
    CHECK (jsonb_typeof(payload) = 'object')
);

CREATE INDEX stg_wb_nm_report_rows_nm_idx
    ON stg_wb_nm_report_rows (nm_id, row_date);

ALTER TABLE wb_analytics_report_tasks
    ADD COLUMN parsed_row_count integer CHECK (parsed_row_count IS NULL OR parsed_row_count >= 0),
    ADD COLUMN staged_row_count integer CHECK (staged_row_count IS NULL OR staged_row_count >= 0);

ALTER TABLE wb_analytics_report_tasks
    ADD CONSTRAINT wb_analytics_report_tasks_staged_matches_parsed
    CHECK (staged_row_count IS NULL OR parsed_row_count IS NULL OR staged_row_count = parsed_row_count);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (5, 'wb_analytics_staging', '1c6053e010524990264a3748ef4de854a930e3e4048457671c4752a43ddc8e54');

COMMIT;
