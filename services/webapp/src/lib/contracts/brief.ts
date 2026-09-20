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
  /**
   * Null when the evaluated day has no fact version at all (status blocked). Absence is written as null, never as a missing key, for the same reason as norm and deviation_pct.
   */
  actual: {
    /**
     * Yesterday's cabinet orders (count).
     */
    orders: number;
    /**
     * Money as a string with exactly two decimal places (AD-10).
     */
    revenue: string;
  } | null;
  /**
   * Null when the day has no usable norm: no version for evaluation_day (status blocked) or an incomplete window (status insufficient). Absence is written as null, never as a missing key - a reader must be able to tell 'not computed' from 'not looked at'. The trustworthiness of a non-null value is carried by brief_daily.status, not by the payload.
   */
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
  } | null;
  /**
   * Null when the day has no usable norm: no version for evaluation_day (status blocked) or an incomplete window (status insufficient). Absence is written as null, never as a missing key - a reader must be able to tell 'not computed' from 'not looked at'. The trustworthiness of a non-null value is carried by brief_daily.status, not by the payload.
   */
  deviation_pct: {
    /**
     * (yesterday - norm) / norm * 100 for orders. Calculation conventions (D27): rounded to 0.1 of a percentage point exactly once, at the last step after the division; intermediates keep full precision.
     */
    orders: number;
    /**
     * (yesterday - norm) / norm * 100 for revenue. Calculation conventions (D27): rounded to 0.1 of a percentage point exactly once, at the last step after the division; intermediates keep full precision.
     */
    revenue: number;
  } | null;
  /**
   * Alert threshold configuration as applied to this brief (decision 6a, D25; PRD FR-34; Story 4.2/4.4): alert_threshold_pct, threshold_source, threshold_date from the control-plane configuration (detector/threshold.toml). Written in every status - it is configuration, not a computed value - and mirrored into each signal's detection_data as threshold_pct, threshold_source, threshold_date. Absence of a threshold is written as nulls, never as a missing key.
   */
  threshold:
    | {
        value: null;
        source: null;
        date: null;
      }
    | {
        /**
         * alert_threshold_pct: one-sided drop threshold in percent of deviation_pct (PRD FR-34, decision 6a: -30 preliminary). A candidate stays in signals[] when at least one of its dropping metrics has deviation_pct at or below this value; growth never alerts. Negative by construction.
         */
        value: number;
        /**
         * threshold_source: where the value comes from, as written in DECISIONS.md (decision 6a: the retro run of 184 fixture days 01.03-31.08). A threshold without a source is not applied.
         */
        source: string;
        /**
         * threshold_date: the day the value was decided (the DECISIONS.md entry).
         */
        date: string;
      };
  /**
   * Anomalies ranked by money at risk: rub_assessment.value_rub descending (CAP-7, Story 4.2); ties broken by the deepest deviation_pct first, then SKU before subject, then nm_id / subject_name. Only candidates below the norm (D32: orders or revenue) and, when threshold.value is set, at or beyond it; growth is reported as a number in deviation_pct / detection_data and never becomes a signal (PRD FR-34). Empty unless brief_daily.status = ok (PRD FR-7). Items are signal v1 (AD-10).
   */
  signals: SignalV1[];
  /**
   * Evidence pointers (AD-1) behind the brief: fact versions, norm rows, artifacts; never empty.
   *
   * @minItems 1
   */
  source_refs: [string, ...string[]];
  /**
   * Why the day carries no norm. Present only when the brief is blocked.
   */
  reason?: string;
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

