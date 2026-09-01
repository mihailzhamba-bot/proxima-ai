/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export interface BriefV1 {
  schema_version: 1;
  /**
   * The day the brief is about (= brief_day, = norm evaluation_day, AD-9).
   */
  evaluation_day: string;
  data_status: {
    last_full_day: string;
    /**
     * finished_at of the last SUCCEEDED collect/backfill run (AD-7).
     */
    collected_at: string;
    stale: boolean;
  };
  actual: {
    /**
     * Yesterday's cabinet orders (count).
     */
    orders: number;
    /**
     * Money as a string with exactly two decimal places (AD-10).
     */
    revenue: string;
  };
  norm: {
    /**
     * Median of orders as a string with two decimals - mirrors norm_daily.value numeric(14,2) (AD-8/AD-10); fractional part is legitimate for an even sample.
     */
    orders: string;
    /**
     * Money as a string with exactly two decimal places (AD-10).
     */
    revenue: string;
    /**
     * D21: median of the last 14 full days before evaluation_day.
     */
    window_days: 14;
    sample_days: number;
  };
  deviation_pct: {
    /**
     * (yesterday - norm) / norm * 100 for orders.
     */
    orders: number;
    /**
     * (yesterday - norm) / norm * 100 for revenue.
     */
    revenue: number;
  };
  /**
   * Anomalies ranked by money (AD-10 signal v1); empty until M-04 (AD-9).
   */
  signals: SignalV1[];
  /**
   * Evidence pointers (AD-1) behind the brief: fact versions, norm rows, artifacts; never empty.
   *
   * @minItems 1
   */
  source_refs: [string, ...string[]];
}
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

