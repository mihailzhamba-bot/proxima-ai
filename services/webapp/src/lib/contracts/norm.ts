/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export type NormV1 = {
  [k: string]: unknown;
} & {
  schema_version: 1;
  tenant_id: string;
  /**
   * The assessed day = last full day (AD-8); the window never includes it.
   */
  evaluation_day: string;
  metric: 'orders' | 'revenue';
  /**
   * Median of the 14 calendar days before evaluation_day (D21, AD-8). A different window is a new schema version.
   */
  window_days: 14;
  /**
   * Days of the window that have a version in fact_cabinet_daily_current; a gap must stay visible.
   */
  sample_days: number;
  /**
   * Money/amount as a string with exactly two decimal places (AD-10); mirrors the DB numeric(14,2) column. Median of the sampled days; for orders it may carry a fractional part (median of an even sample).
   */
  value: string;
  status: 'ok' | 'insufficient';
  /**
   * Evidence pointers (AD-1): content_sha256 of the fact versions the median was taken over; never empty.
   *
   * @minItems 1
   */
  source_refs: [string, ...string[]];
};

