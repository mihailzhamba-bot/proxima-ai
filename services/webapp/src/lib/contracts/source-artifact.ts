/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export interface SourceArtifactV1 {
  schema_version: 1;
  artifact_id: string;
  tenant_id: string;
  source:
    | 'official_wb_manual'
    | 'official_wb_statistics'
    | 'official_wb_analytics'
    | 'official_wb_finance'
    | 'torgstat_supporting';
  dataset: string;
  content_sha256: string;
  content_size: number;
  period: {
    from: string;
    to: string;
    timezone: 'Europe/Moscow';
  };
  data_as_of: string;
  retrieved_at: string;
  parser_version: string;
  source_schema_version: string;
  provenance: {
    acquisition_attempt_id: string;
    retrieval_mode: 'manual_export' | 'official_read_api' | 'supporting_import';
  };
  locator: string;
}
