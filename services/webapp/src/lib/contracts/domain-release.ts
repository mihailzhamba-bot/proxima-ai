/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export type DomainReleaseV1 = {
  [k: string]: unknown;
} & {
  schema_version: 1;
  release_id: string;
  tenant_id: string;
  domain: 'operational' | 'inventory' | 'financial';
  status: 'candidate' | 'published' | 'rejected';
  /**
   * @minItems 1
   */
  attempt_ids: [string, ...string[]];
  /**
   * @minItems 1
   */
  artifact_ids: [string, ...string[]];
  previous_release_id?: string | null;
  published_at?: string | null;
  rejection_reasons?: string[];
  atomic: boolean;
};
