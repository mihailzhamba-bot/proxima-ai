/**
 * WB sales funnel v3 history as product-day observations (Story 3.1, AD-5).
 *
 * `analytics.sales_funnel_v3_history` answers with one entry per product and
 * one history record per calendar day. Each record becomes an observation
 * keyed by (nm_id, calendar_day, source = 'v3', canonical_sha256): the same
 * payload observed again is a replay (DO NOTHING), a changed payload for the
 * same product-day is a new observation and `stg_wb_funnel_latest` picks the
 * newest one. The dictionary columns follow COLUMN_MAP scn001.
 *
 * Window: the job asks for WB's confirmed `[today-6, today]`, where today is
 * `run_day` in Moscow (API-FACTS, 30.08; AD-7). The incomplete run day is
 * observed but never versioned. Records after the window end are dropped;
 * records before its start are still WB evidence and are kept.
 */
import type { PoolClient } from 'pg';

import { canonicalJson, sha256 } from '../intake/manifest.js';
import { WbClientError } from './client.js';
import { wbEndpoint } from './registry.js';

export const FUNNEL_ENDPOINT = 'analytics.sales_funnel_v3_history' as const;
export const FUNNEL_SOURCE = 'v3' as const;
export type FunnelSource = 'v3' | 'csv';
/** WB accepts at most 20 nmIds per call (registry `maxPerPage`, API-FACTS). */
export const FUNNEL_BATCH_SIZE = wbEndpoint(FUNNEL_ENDPOINT).maxPerPage ?? 20;
/** Window start offset: `run_day-6` is the confirmed WB boundary (API-FACTS). */
export const FUNNEL_WINDOW_START_OFFSET = 6;
/** Active nmId = ordered on one of the last 30 full Moscow days before run_day. */
export const ACTIVE_NM_ID_DAYS = 30;
export const FUNNEL_CURRENCY = 'RUB';

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const SHA256_HEX = /^[0-9a-f]{64}$/;

export interface FunnelWindow {
  readonly runDay: string;
  /** First requested day, `run_day-6`. */
  readonly start: string;
  /** Last requested day, `run_day`; nothing after it is ever observed. */
  readonly end: string;
}

export interface FunnelObservation {
  readonly nmId: number;
  readonly calendarDay: string;
  readonly canonicalSha256: string;
  readonly openCard: number;
  readonly cart: number;
  readonly orders: number;
  readonly ordersSumRub: string;
  readonly buyouts: number;
  readonly buyoutsSumRub: string;
  readonly payload: Readonly<Record<string, unknown>>;
}

export interface FunnelBatch {
  /** sha256 of the raw response body the rows were parsed from. */
  readonly evidenceSha256: string;
  /** History records in the response before the window filter. */
  readonly received: number;
  readonly rows: readonly FunnelObservation[];
}

export interface InsertFunnelObservationsResult {
  readonly received: number;
  readonly inserted: number;
  readonly skipped: number;
}

export function shiftDay(day: string, offset: number): string {
  if (!DAY.test(day)) throw new RangeError(`shiftDay: expected YYYY-MM-DD, got ${JSON.stringify(day)}`);
  const parsed = Date.parse(`${day}T00:00:00Z`);
  if (Number.isNaN(parsed) || new Date(parsed).toISOString().slice(0, 10) !== day) {
    throw new RangeError(`shiftDay: ${day} is not a calendar date`);
  }
  return new Date(parsed + offset * 86_400_000).toISOString().slice(0, 10);
}

export function funnelWindow(runDay: string): FunnelWindow {
  return { runDay, start: shiftDay(runDay, -FUNNEL_WINDOW_START_OFFSET), end: runDay };
}

export function windowDays(window: FunnelWindow): string[] {
  const days: string[] = [];
  for (let day = window.start; day <= window.end; day = shiftDay(day, 1)) days.push(day);
  return days;
}

/** Request body of `analytics.sales_funnel_v3_history` (API-FACTS: ItemHistoryRequest). */
export function funnelRequestBody(window: FunnelWindow, nmIds: readonly number[]): { selectedPeriod: { start: string; end: string }; nmIds: number[]; aggregationLevel: 'day' } {
  if (nmIds.length < 1 || nmIds.length > FUNNEL_BATCH_SIZE) throw new RangeError(`funnel request must carry 1..${FUNNEL_BATCH_SIZE} nmIds`);
  return { selectedPeriod: { start: window.start, end: window.end }, nmIds: [...nmIds], aggregationLevel: 'day' };
}

/** Sorted, de-duplicated batches of at most `size` positive integers. */
export function batchNmIds(ids: readonly number[], size = FUNNEL_BATCH_SIZE): number[][] {
  if (!Number.isSafeInteger(size) || size < 1 || size > FUNNEL_BATCH_SIZE) {
    throw new RangeError(`funnel batch size must be 1..${FUNNEL_BATCH_SIZE}`);
  }
  const unique = [...new Set(ids)].sort((a, b) => a - b);
  for (const id of unique) {
    if (!Number.isSafeInteger(id) || id <= 0) throw new RangeError(`nmId must be a positive safe integer, got ${String(id)}`);
  }
  const batches: number[][] = [];
  for (let offset = 0; offset < unique.length; offset += size) batches.push(unique.slice(offset, offset + size));
  return batches;
}

function drift(message: string): WbClientError {
  return new WbClientError('WB_SCHEMA_DRIFT', `${FUNNEL_ENDPOINT}: ${message}`, FUNNEL_ENDPOINT);
}

function count(record: Record<string, unknown>, field: string, context: string): number {
  const value = record[field];
  if (!Number.isSafeInteger(value) || (value as number) < 0) throw drift(`${context} has no non-negative integer ${field}`);
  return value as number;
}

function money(record: Record<string, unknown>, field: string, context: string): string {
  const value = record[field];
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) throw drift(`${context} has no non-negative number ${field}`);
  return value.toFixed(2);
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Parses one response body. Fails closed with WB_SCHEMA_DRIFT on any shape
 * surprise; never invents a field. Records dated after `window.end` are
 * dropped; the incomplete run day and everything earlier WB returned are
 * kept as evidence.
 */
export function parseFunnelV3(body: Buffer, evidenceSha256: string, window: FunnelWindow): FunnelBatch {
  if (!SHA256_HEX.test(evidenceSha256)) throw new RangeError('parseFunnelV3: evidenceSha256 must be 64 lowercase hex chars');
  let parsed: unknown;
  try {
    parsed = JSON.parse(body.toString('utf8'));
  } catch {
    throw drift('response is not valid JSON');
  }
  if (!Array.isArray(parsed)) throw drift('response must be a JSON array');
  const rows: FunnelObservation[] = [];
  let received = 0;
  parsed.forEach((entry, productIndex) => {
    if (!object(entry)) throw drift(`entry ${productIndex} is not an object`);
    const product = entry.product;
    if (!object(product)) throw drift(`entry ${productIndex} has no product object`);
    const nmId = product.nmId;
    if (!Number.isSafeInteger(nmId) || (nmId as number) <= 0) throw drift(`entry ${productIndex} has no positive nmId`);
    if (entry.currency !== FUNNEL_CURRENCY) throw drift(`nmId ${nmId as number} currency is not ${FUNNEL_CURRENCY}`);
    if (!Array.isArray(entry.history)) throw drift(`nmId ${nmId as number} has no history array`);
    entry.history.forEach((record, dayIndex) => {
      received += 1;
      const context = `nmId ${nmId as number} history ${dayIndex}`;
      if (!object(record)) throw drift(`${context} is not an object`);
      const day = record.date;
      if (typeof day !== 'string' || !DAY.test(day)) throw drift(`${context} has no YYYY-MM-DD date`);
      try {
        shiftDay(day, 0);
      } catch {
        throw drift(`${context} date is not a calendar date`);
      }
      if (day > window.end) return;
      rows.push({
        nmId: nmId as number,
        calendarDay: day,
        canonicalSha256: sha256(canonicalJson(record)),
        openCard: count(record, 'openCount', context),
        cart: count(record, 'cartCount', context),
        orders: count(record, 'orderCount', context),
        ordersSumRub: money(record, 'orderSum', context),
        buyouts: count(record, 'buyoutCount', context),
        buyoutsSumRub: money(record, 'buyoutSum', context),
        payload: record,
      });
    });
  });
  return { evidenceSha256, received, rows };
}

/**
 * Validates identities in a successfully received batch and returns active
 * nmIds for which WB supplied no record inside the requested window. Missing
 * products are a known deleted/hidden-card condition and are log-and-skip;
 * duplicates and unrequested products remain schema drift.
 */
export function assertBatchCoverage(rows: readonly FunnelObservation[], nmIds: readonly number[], window: FunnelWindow): number[] {
  const requested = new Set(nmIds);
  const seen = new Set<string>();
  const present = new Set<number>();
  for (const row of rows) {
    if (!requested.has(row.nmId)) throw drift(`response contains unrequested nmId ${row.nmId}`);
    const key = `${row.nmId}:${row.calendarDay}`;
    if (seen.has(key)) throw drift(`response repeats nmId ${row.nmId} on ${row.calendarDay}`);
    seen.add(key);
    if (row.calendarDay >= window.start && row.calendarDay <= window.end) present.add(row.nmId);
  }
  return nmIds.filter((nmId) => !present.has(nmId));
}

type QueryClient = Pick<PoolClient, 'query'>;

/**
 * Writes one batch of observations inside the caller's transaction. The
 * primary key carries the canonical hash, so ON CONFLICT DO NOTHING can only
 * ever skip an identical replay (AD-5); a changed payload is a new row.
 */
export async function insertFunnelObservations(
  client: QueryClient,
  tenantId: string,
  runId: string,
  batch: FunnelBatch,
  source: FunnelSource = FUNNEL_SOURCE,
): Promise<InsertFunnelObservationsResult> {
  if (batch.rows.length === 0) return { received: batch.received, inserted: 0, skipped: 0 };
  const values = JSON.stringify(batch.rows.map((row) => ({
    nm_id: row.nmId,
    calendar_day: row.calendarDay,
    canonical_sha256: row.canonicalSha256,
    open_card: row.openCard,
    cart: row.cart,
    orders: row.orders,
    orders_sum_rub: row.ordersSumRub,
    buyouts: row.buyouts,
    buyouts_sum_rub: row.buyoutsSumRub,
    payload: row.payload,
  })));
  const result = await client.query(
    `INSERT INTO stg_wb_funnel_obs (tenant_id, nm_id, calendar_day, source, canonical_sha256, run_id, evidence_sha256,
       open_card, cart, orders, orders_sum_rub, buyouts, buyouts_sum_rub, payload, observed_at)
     SELECT $1::text, v.nm_id, v.calendar_day, $4::text, v.canonical_sha256, $2::uuid, $3::text,
       v.open_card, v.cart, v.orders, v.orders_sum_rub::numeric, v.buyouts, v.buyouts_sum_rub::numeric, v.payload, clock_timestamp()
     FROM jsonb_to_recordset($5::jsonb) AS v(nm_id bigint, calendar_day date, canonical_sha256 text, open_card integer, cart integer,
       orders integer, orders_sum_rub text, buyouts integer, buyouts_sum_rub text, payload jsonb)
     ON CONFLICT (tenant_id, nm_id, calendar_day, source, canonical_sha256) DO NOTHING`,
    [tenantId, runId, batch.evidenceSha256, source, values],
  );
  const inserted = result.rowCount ?? 0;
  return { received: batch.received, inserted, skipped: batch.rows.length - inserted };
}
