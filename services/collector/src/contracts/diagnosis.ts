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
   * Positional: exactly 1 + len(alternatives) + len(unknowns) entries - first for the primary cause, then one per alternative, then one per unknown. Enforced by tools/verify_contracts.py and services/collector/tests/product-contracts.test.ts (not expressible in JSON Schema alone).
   *
   * @minItems 1
   */
  source_refs: [string, ...string[]];
  confidence_note: string;
  reviewer: {
    verdict: 'pass' | 'block';
    model: string;
  };
}

