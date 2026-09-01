/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export type NormV1 = {
  [k: string]: unknown;
} & {
  schema_version: 1;
  evaluation_day: string;
  metric: 'orders' | 'revenue';
  window_days: number;
  sample_days: number;
  value: number | string;
  status: 'ok' | 'insufficient';
  /**
   * @minItems 1
   */
  source_refs: [string, ...string[]];
};
