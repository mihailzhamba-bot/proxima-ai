export const OFFICIAL_WB_MANUAL_SOURCE = 'official_wb_manual' as const;
export const MANUAL_EXPORT_RETRIEVAL_MODE = 'manual_export' as const;
export const UNPARSED_PARSER_VERSION = '0.0.0' as const;

export interface ManualWbXlsxMetadata {
  tenantId: string;
  dataset: string;
  periodFrom: string;
  periodTo: string;
  dataAsOf: string;
  retrievedAt: string;
  sourceSchemaVersion: string;
}

export interface SourceArtifactManifest {
  schema_version: 1;
  artifact_id: string;
  tenant_id: string;
  source: typeof OFFICIAL_WB_MANUAL_SOURCE;
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
  parser_version: typeof UNPARSED_PARSER_VERSION;
  source_schema_version: string;
  provenance: {
    acquisition_attempt_id: string;
    retrieval_mode: typeof MANUAL_EXPORT_RETRIEVAL_MODE;
  };
  locator: string;
}

export type IntakeState = 'created' | 'existing';

export interface ManualWbXlsxIntakeResult {
  artifactId: string;
  contentSha256: string;
  locator: string;
  state: IntakeState;
}

export type IntakeFailureCode =
  | 'ARTIFACT_CHECKSUM_MISMATCH'
  | 'INPUT_NOT_XLSX'
  | 'MANIFEST_CONFLICT'
  | 'METADATA_INVALID'
  | 'STORAGE_INSIDE_REPOSITORY'
  | 'UNSAFE_INPUT'
  | 'UNSAFE_STORAGE';

export class IntakeError extends Error {
  constructor(
    readonly code: IntakeFailureCode,
    message: string,
  ) {
    super(message);
    this.name = 'IntakeError';
  }
}

export type IntakeFailurePoint =
  | 'after_temp_durable'
  | 'after_raw_published'
  | 'before_manifest_published'
  | 'after_manifest_published';

export interface IntakeHooks {
  at?(point: IntakeFailurePoint): Promise<void> | void;
}
