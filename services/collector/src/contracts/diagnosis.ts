/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export interface DiagnosisV1 {
  schema_version: 1;
  signal_id: string;
  primary_cause: string;
  /**
   * @minItems 2
   * @maxItems 3
   */
  alternatives: [string, string] | [string, string, string];
  unknowns: string[];
  /**
   * @minItems 1
   */
  source_refs: [string, ...string[]];
  confidence_note: string;
  reviewer: {
    verdict: 'pass' | 'block';
    model: string;
  };
}

