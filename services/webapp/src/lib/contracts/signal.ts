/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export interface SignalV1 {
  schema_version: 1;
  signal_id: string;
  scenario_code: 'SCN-001' | 'SCN-005' | 'SCN-008';
  snapshot_id: string;
  tenant_id: string;
  created_at: string;
  trust_marking: 'unreleased' | 'released';
  rub_assessment: null | {
    /**
     * Money as a string with exactly two decimal places (AD-10).
     */
    value_rub: string;
    method: 'revenue' | 'profit';
  };
  /**
   * @minItems 1
   */
  source_refs: [string, ...string[]];
  detection_data: {
    [k: string]: {
      [k: string]: unknown;
    };
  };
}
