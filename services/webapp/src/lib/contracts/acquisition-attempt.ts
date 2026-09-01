/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export type AcquisitionAttemptV1 = {
  [k: string]: unknown;
} & {
  schema_version: 1;
  attempt_id: string;
  tenant_id: string;
  source: string;
  dataset: string;
  status: 'running' | 'succeeded' | 'blocked' | 'failed' | 'partial' | 'schema_drift' | 'conflict' | 'stale';
  started_at: string;
  completed_at?: string | null;
  reason_code?: string | null;
  retry_of?: string | null;
  artifact_ids: string[];
  pagination: {
    complete: boolean;
    page_count: number;
  };
};
