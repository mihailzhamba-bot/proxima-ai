import { Decimal } from 'decimal.js';
import type { PoolClient } from 'pg';

import { mskDay } from '../wb/msk-day.js';

export interface CabinetDailyInput {
  readonly tenantId: string;
  readonly runId: string;
  readonly floor: string;
  readonly runDay: string;
  /** Rows of `loadLatestObservations` when the run shares one SELECT between
   * the cabinet and the nmId writers (AD-19); loaded here when absent. */
  readonly observations?: readonly CabinetObservationRow[];
}

export interface CabinetDailyFact {
  readonly calendarDay: string;
  readonly ordersCount: number;
  readonly cancelledCount: number;
  readonly salesCount: number;
  readonly returnsCount: number;
  readonly revenueRub: string;
  readonly forpayRub: string;
  readonly evidenceSha256: readonly string[];
}

export interface AggregateCabinetDailyResult {
  readonly days: number;
  readonly inputRuns: number;
}

export interface CabinetObservationRow {
  readonly kind: 'order' | 'sale';
  readonly runId: string;
  readonly contentSha256: string;
  readonly payload: Readonly<Record<string, unknown>>;
}

/** One `_latest` row with its natural key and WB lastChangeDate instant - what
 * the dictionary of AD-19 needs on top of the cabinet formulas. */
export interface LatestObservationRow extends CabinetObservationRow {
  /** `srid` of an order, `saleID` of a sale. */
  readonly key: string;
  /** `last_change_at` as an ISO-8601 UTC instant (`...Z`). */
  readonly lastChangeAt: string;
}

type QueryClient = Pick<PoolClient, 'query'>;

const LAST_CHANGE_AT_SQL = `to_char(last_change_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS') || 'Z'`;

/**
 * The single input of the daily aggregators (AD-2): every latest observation
 * of the tenant from both `_latest` views, regardless of run status. Called
 * inside the run transaction after the observations of the run are inserted.
 */
export async function loadLatestObservations(client: QueryClient, tenantId: string): Promise<LatestObservationRow[]> {
  const result = await client.query<LatestObservationRow>(
    `SELECT 'order' AS kind, srid AS key, ${LAST_CHANGE_AT_SQL} AS "lastChangeAt", run_id AS "runId", content_sha256 AS "contentSha256", payload FROM stg_wb_orders_latest WHERE tenant_id = $1
     UNION ALL
     SELECT 'sale' AS kind, sale_id AS key, ${LAST_CHANGE_AT_SQL} AS "lastChangeAt", run_id AS "runId", content_sha256 AS "contentSha256", payload FROM stg_wb_sales_latest WHERE tenant_id = $1`,
    [tenantId],
  );
  return result.rows;
}

/** Content hashes of the run's own WB responses: the evidence of a zero day (AD-2). */
export async function loadRunEvidence(client: QueryClient, tenantId: string, runId: string): Promise<string[]> {
  const result = await client.query<{ contentSha256: string }>(
    'SELECT DISTINCT content_sha256 AS "contentSha256" FROM wb_raw_artifacts WHERE tenant_id = $1 AND run_id = $2 ORDER BY content_sha256',
    [tenantId, runId],
  );
  return result.rows.map((row) => row.contentSha256);
}

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const SHA = /^[0-9a-f]{64}$/;

function nextDay(day: string): string {
  const instant = Date.parse(`${day}T00:00:00Z`);
  if (Number.isNaN(instant)) throw new RangeError(`invalid calendar day ${day}`);
  return new Date(instant + 86_400_000).toISOString().slice(0, 10);
}

function money(value: unknown, field: string): Decimal {
  if (typeof value !== 'string' && typeof value !== 'number') throw new RangeError(`${field} must be numeric`);
  try { return new Decimal(value); }
  catch { throw new RangeError(`${field} must be numeric`); }
}

/** Pure formula implementation used by the DB writer and unit tests. */
export function summarizeCabinetDaily(
  rows: readonly CabinetObservationRow[],
  floor: string,
  runDay: string,
  emptyEvidence: readonly string[],
): CabinetDailyFact[] {
  if (!DAY.test(floor) || !DAY.test(runDay) || floor > runDay) throw new RangeError('invalid cabinet-daily interval');
  const facts = new Map<string, { orders: number; cancelled: number; sales: number; returns: number; revenue: Decimal; forpay: Decimal; evidence: Set<string> }>();
  for (let day = floor; day < runDay; day = nextDay(day)) {
    facts.set(day, { orders: 0, cancelled: 0, sales: 0, returns: 0, revenue: new Decimal(0), forpay: new Decimal(0), evidence: new Set() });
  }
  for (const row of rows) {
    const rawDate = row.payload.date;
    if (typeof rawDate !== 'string') throw new RangeError('observation payload.date must be a string');
    const day = mskDay(rawDate);
    const fact = facts.get(day);
    if (!fact) continue;
    if (!SHA.test(row.contentSha256)) throw new RangeError('observation contentSha256 must be lowercase sha256');
    fact.evidence.add(row.contentSha256);
    if (row.kind === 'order') {
      if (row.payload.isCancel === true) fact.cancelled += 1;
      else fact.orders += 1;
    } else {
      const saleId = row.payload.saleID;
      if (typeof saleId !== 'string') throw new RangeError('sale payload.saleID must be a string');
      if (saleId.startsWith('S')) {
        fact.sales += 1;
        fact.revenue = fact.revenue.plus(money(row.payload.finishedPrice, 'finishedPrice'));
        fact.forpay = fact.forpay.plus(money(row.payload.forPay, 'forPay'));
      } else if (saleId.startsWith('R')) fact.returns += 1;
    }
  }
  return [...facts].map(([calendarDay, fact]) => ({
    calendarDay,
    ordersCount: fact.orders,
    cancelledCount: fact.cancelled,
    salesCount: fact.sales,
    returnsCount: fact.returns,
    revenueRub: fact.revenue.toFixed(2),
    forpayRub: fact.forpay.toFixed(2),
    evidenceSha256: [...(fact.evidence.size > 0 ? fact.evidence : new Set(emptyEvidence))].sort(),
  }));
}

export async function aggregateCabinetDaily(client: QueryClient, input: CabinetDailyInput): Promise<AggregateCabinetDailyResult> {
  const observations = input.observations ?? await loadLatestObservations(client, input.tenantId);
  const evidence = await loadRunEvidence(client, input.tenantId, input.runId);
  const facts = summarizeCabinetDaily(observations, input.floor, input.runDay, evidence);
  if (facts.length > 0) {
    await client.query(
      `INSERT INTO fact_cabinet_daily (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256)
       SELECT $1, x.calendar_day::date, $2, x.orders_count, x.cancelled_count, x.sales_count, x.returns_count, x.revenue_rub::numeric, x.forpay_rub::numeric, x.evidence_sha256::char(64)[]
       FROM jsonb_to_recordset($3::jsonb) AS x(calendar_day text, orders_count integer, cancelled_count integer, sales_count integer, returns_count integer, revenue_rub text, forpay_rub text, evidence_sha256 text[])`,
      [input.tenantId, input.runId, JSON.stringify(facts.map((fact) => ({ calendar_day: fact.calendarDay, orders_count: fact.ordersCount, cancelled_count: fact.cancelledCount, sales_count: fact.salesCount, returns_count: fact.returnsCount, revenue_rub: fact.revenueRub, forpay_rub: fact.forpayRub, evidence_sha256: fact.evidenceSha256 })))],
    );
  }
  const inputRuns = [...new Set(observations.filter((row) => mskDay(String(row.payload.date)) >= input.floor && mskDay(String(row.payload.date)) < input.runDay && row.runId !== input.runId).map((row) => row.runId))];
  if (inputRuns.length > 0) {
    await client.query(
      'INSERT INTO collector_run_inputs (tenant_id, run_id, input_run_id) SELECT $1, $2, unnest($3::uuid[]) ON CONFLICT (tenant_id, run_id, input_run_id) DO NOTHING',
      [input.tenantId, input.runId, inputRuns],
    );
  }
  return { days: facts.length, inputRuns: inputRuns.length };
}
