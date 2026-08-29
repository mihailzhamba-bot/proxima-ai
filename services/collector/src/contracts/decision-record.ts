/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export type DecisionRecordV1 = {
  [k: string]: unknown;
} & {
  schema_version: 1;
  signal_id: string;
  decision: 'accepted' | 'rejected';
  actor: string;
  decided_at: string;
  reason: string | null;
  expected: Measurement;
  actual: null | Measurement;
  delta: null | Measurement;
  outcome?: 'confirmed' | 'refuted' | 'partial' | 'unknown';
};

export interface Measurement {
  /**
   * @minItems 1
   */
  metrics: [Metric, ...Metric[]];
  horizon_days: number;
}
export interface Metric {
  name: string;
  value: number;
  unit: string;
  source_ref: string;
}

