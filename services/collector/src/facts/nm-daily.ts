/**
 * nmId and subject grain for anomalies (Story 4.0, AD-19).
 *
 * The same `collect`/`backfill` run that versions `fact_cabinet_daily` writes,
 * inside transaction (3) right after `aggregateCabinetDaily` and from the same
 * `_latest` rows (one SELECT, `loadLatestObservations`), two more things:
 *
 *  - `dim_nm_subject`: one dictionary version per nmId seen in
 *    `stg_wb_orders_latest UNION stg_wb_sales_latest`, taken from the
 *    observation with the greatest `last_change_at` (ties: order before sale,
 *    then the greater `srid`/`saleID`). Category of an anomaly = WB `subject`.
 *  - `fact_nm_daily`: for every versioned day of `[floor, run_day-1]` x every
 *    nmId of that dictionary exactly one row with the cabinet formulas
 *    (glossary.md) grouped by `payload.nmId`, zeros included: no row means the
 *    day is not versioned, a zero row means no observations (AD-2); a zero row
 *    carries the run's artifacts as evidence, like a zero cabinet day.
 *
 * Fail-closed like `date`: a missing or non-positive `nmId` is a RangeError
 * and the run ends FAILED; a dictionary key missing from the winning payload
 * is WB_SCHEMA_DRIFT; an empty string is a literal value (a visible group).
 * `collector_run_inputs` is not written a second time - the cabinet aggregator
 * already recorded the runs whose observations fed the versions.
 *
 * Quality check `per_nm_sums_vs_cabinet`: one SQL over this run's rows after
 * both inserts, the six column sums of `fact_nm_daily` per day against
 * `fact_cabinet_daily` of the same run (a day without nm rows counts as zero).
 * The result is one JSON log line of the run (AD-17) and never blocks: the
 * threshold is UNKNOWN until OQ-7, so any non-zero difference is MISMATCH.
 * "Cabinet orders" stay `fact_cabinet_daily` only (AD-2): the equality is a
 * check, not a second source.
 */
import { Decimal } from 'decimal.js';
import type { PoolClient } from 'pg';

import { WbClientError } from '../wb/client.js';
import { mskDay } from '../wb/msk-day.js';
import type { WbEndpointId } from '../wb/registry.js';
import { loadLatestObservations, loadRunEvidence, type LatestObservationRow } from './cabinet-daily.js';

export interface NmDailyInput {
  readonly tenantId: string;
  readonly runId: string;
  readonly floor: string;
  readonly runDay: string;
  /** Rows of `loadLatestObservations` shared with the cabinet aggregator; loaded here when absent. */
  readonly observations?: readonly LatestObservationRow[];
}

export interface NmSubjectVersion {
  readonly nmId: number;
  readonly subjectName: string;
  readonly categoryName: string;
  readonly brand: string;
  readonly supplierArticle: string;
  /** `last_change_at` of the winning observation as an instant string. */
  readonly lastChangeAt: string;
  readonly evidenceSha256: string;
}

export interface NmDailyFact {
  readonly calendarDay: string;
  readonly nmId: number;
  readonly ordersCount: number;
  readonly cancelledCount: number;
  readonly salesCount: number;
  readonly returnsCount: number;
  readonly revenueRub: string;
  readonly forpayRub: string;
  readonly evidenceSha256: readonly string[];
}

export type QualityCheckStatus = 'PASS' | 'MISMATCH';

export interface PerNmSumsMismatch {
  readonly calendar_day: string;
  readonly column: string;
  readonly cabinet: string;
  readonly per_nm_sum: string;
}

/** Log fields of the `quality_check` step (AD-17/AD-19), spread into the run's JSON line as they are. */
export interface PerNmSumsVsCabinetResult {
  readonly check: 'per_nm_sums_vs_cabinet';
  readonly status: QualityCheckStatus;
  readonly days_checked: number;
  readonly mismatches: readonly PerNmSumsMismatch[];
}

export interface WriteNmDailyResult {
  readonly subjects: number;
  readonly rows: number;
  readonly days: number;
  readonly check: PerNmSumsVsCabinetResult;
}

type QueryClient = Pick<PoolClient, 'query'>;
type ObservationRow = Pick<LatestObservationRow, 'kind' | 'key' | 'payload'>;

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const SHA = /^[0-9a-f]{64}$/;
const INSERT_BATCH = 5_000;
const CHECKED_COLUMNS = ['orders_count', 'cancelled_count', 'sales_count', 'returns_count', 'revenue_rub', 'forpay_rub'] as const;
const SUBJECT_FIELDS = [
  ['subjectName', 'subject'],
  ['categoryName', 'category'],
  ['brand', 'brand'],
  ['supplierArticle', 'supplierArticle'],
] as const;

interface NmCell {
  orders: number;
  cancelled: number;
  sales: number;
  returns: number;
  revenue: Decimal;
  forpay: Decimal;
  evidence: Set<string>;
}

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

function endpointOf(row: ObservationRow): WbEndpointId {
  return row.kind === 'order' ? 'statistics.orders' : 'statistics.sales';
}

/** `payload.nmId` of an observation: a positive safe integer, or the run fails (AD-19, like `date`). */
export function nmIdOf(row: ObservationRow): number {
  const value = row.payload.nmId;
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new RangeError(`${row.kind} ${row.key}: payload.nmId must be a positive integer`);
  }
  return value;
}

function subjectField(row: ObservationRow, field: (typeof SUBJECT_FIELDS)[number][1]): string {
  const value = row.payload[field];
  if (typeof value !== 'string') {
    const endpoint = endpointOf(row);
    throw new WbClientError('WB_SCHEMA_DRIFT', `${endpoint}: ${row.kind} ${row.key} has no string ${field} in its payload`, endpoint);
  }
  return value;
}

function instantOf(row: LatestObservationRow): number {
  const instant = Date.parse(row.lastChangeAt);
  if (Number.isNaN(instant)) throw new RangeError(`${row.kind} ${row.key}: lastChangeAt must be an instant`);
  return instant;
}

/** AD-19 winner between two observations of one nmId: greatest last_change_at, then order before sale, then the greater key. */
function outranks(candidate: LatestObservationRow, incumbent: LatestObservationRow): boolean {
  const candidateAt = instantOf(candidate);
  const incumbentAt = instantOf(incumbent);
  if (candidateAt !== incumbentAt) return candidateAt > incumbentAt;
  if (candidate.kind !== incumbent.kind) return candidate.kind === 'order';
  return candidate.key > incumbent.key;
}

/** Pure dictionary builder: one version per nmId from the winning observation, sorted by nmId. */
export function summarizeNmSubjects(rows: readonly LatestObservationRow[]): NmSubjectVersion[] {
  const winners = new Map<number, LatestObservationRow>();
  for (const row of rows) {
    const nmId = nmIdOf(row);
    if (!SHA.test(row.contentSha256)) throw new RangeError('observation contentSha256 must be lowercase sha256');
    const incumbent = winners.get(nmId);
    if (incumbent === undefined || outranks(row, incumbent)) winners.set(nmId, row);
  }
  return [...winners.entries()]
    .sort(([a], [b]) => a - b)
    .map(([nmId, row]) => ({
      nmId,
      subjectName: subjectField(row, 'subject'),
      categoryName: subjectField(row, 'category'),
      brand: subjectField(row, 'brand'),
      supplierArticle: subjectField(row, 'supplierArticle'),
      lastChangeAt: row.lastChangeAt,
      evidenceSha256: row.contentSha256,
    }));
}

/**
 * Pure formula implementation, the second function over the rows the cabinet
 * aggregator consumes: every day of `[floor, runDay)` x every nmId of the rows
 * (the dictionary of this run), grouped by `payload.nmId`, sorted by day and nmId.
 */
export function summarizeNmDaily(
  rows: readonly LatestObservationRow[],
  floor: string,
  runDay: string,
  emptyEvidence: readonly string[],
): NmDailyFact[] {
  if (!DAY.test(floor) || !DAY.test(runDay) || floor > runDay) throw new RangeError('invalid nm-daily interval');
  const nmIds = new Set<number>();
  const cells = new Map<string, NmCell>();
  for (const row of rows) {
    const nmId = nmIdOf(row);
    nmIds.add(nmId);
    const rawDate = row.payload.date;
    if (typeof rawDate !== 'string') throw new RangeError('observation payload.date must be a string');
    const day = mskDay(rawDate);
    if (day < floor || day >= runDay) continue;
    if (!SHA.test(row.contentSha256)) throw new RangeError('observation contentSha256 must be lowercase sha256');
    const key = `${day}|${nmId}`;
    let cell = cells.get(key);
    if (cell === undefined) {
      cell = { orders: 0, cancelled: 0, sales: 0, returns: 0, revenue: new Decimal(0), forpay: new Decimal(0), evidence: new Set() };
      cells.set(key, cell);
    }
    cell.evidence.add(row.contentSha256);
    if (row.kind === 'order') {
      if (row.payload.isCancel === true) cell.cancelled += 1;
      else cell.orders += 1;
    } else {
      const saleId = row.payload.saleID;
      if (typeof saleId !== 'string') throw new RangeError('sale payload.saleID must be a string');
      if (saleId.startsWith('S')) {
        cell.sales += 1;
        cell.revenue = cell.revenue.plus(money(row.payload.finishedPrice, 'finishedPrice'));
        cell.forpay = cell.forpay.plus(money(row.payload.forPay, 'forPay'));
      } else if (saleId.startsWith('R')) cell.returns += 1;
    }
  }
  const sortedNmIds = [...nmIds].sort((a, b) => a - b);
  const zero: NmCell = { orders: 0, cancelled: 0, sales: 0, returns: 0, revenue: new Decimal(0), forpay: new Decimal(0), evidence: new Set() };
  const facts: NmDailyFact[] = [];
  for (let day = floor; day < runDay; day = nextDay(day)) {
    for (const nmId of sortedNmIds) {
      const cell = cells.get(`${day}|${nmId}`) ?? zero;
      facts.push({
        calendarDay: day,
        nmId,
        ordersCount: cell.orders,
        cancelledCount: cell.cancelled,
        salesCount: cell.sales,
        returnsCount: cell.returns,
        revenueRub: cell.revenue.toFixed(2),
        forpayRub: cell.forpay.toFixed(2),
        evidenceSha256: [...(cell.evidence.size > 0 ? cell.evidence : new Set(emptyEvidence))].sort(),
      });
    }
  }
  return facts;
}

/**
 * The one SQL of the check: six column sums of the nmId rows per day against
 * the cabinet row of the same day. With `runId` it reads this run's rows of the
 * base tables (the run's own quality check); without it the `_current` views of
 * the tenant (the harness assertion of Story 4.0). Days come from the cabinet
 * side; a day without nm rows compares against zeros.
 */
export async function checkPerNmSumsVsCabinet(client: QueryClient, scope: { readonly tenantId: string; readonly runId?: string }): Promise<PerNmSumsVsCabinetResult> {
  const byRun = scope.runId !== undefined;
  const nmTable = byRun ? 'fact_nm_daily' : 'fact_nm_daily_current';
  const cabinetTable = byRun ? 'fact_cabinet_daily' : 'fact_cabinet_daily_current';
  const scopeOf = (alias: string): string => (byRun ? `${alias}tenant_id = $1 AND ${alias}run_id = $2` : `${alias}tenant_id = $1`);
  const params = byRun ? [scope.tenantId, scope.runId] : [scope.tenantId];
  const result = await client.query<{ calendar_day: string; column_name: string; cabinet: string; per_nm_sum: string; mismatch: boolean }>(
    `WITH per_nm AS (
       SELECT calendar_day,
              sum(orders_count) AS orders_count, sum(cancelled_count) AS cancelled_count,
              sum(sales_count) AS sales_count, sum(returns_count) AS returns_count,
              sum(revenue_rub) AS revenue_rub, sum(forpay_rub) AS forpay_rub
       FROM ${nmTable}
       WHERE ${scopeOf('')}
       GROUP BY calendar_day
     )
     SELECT c.calendar_day::text AS calendar_day, v.column_name, v.cabinet::text AS cabinet, v.per_nm_sum::text AS per_nm_sum, (v.cabinet <> v.per_nm_sum) AS mismatch
     FROM ${cabinetTable} c
     LEFT JOIN per_nm n ON n.calendar_day = c.calendar_day
     CROSS JOIN LATERAL (VALUES
       ('orders_count', c.orders_count::numeric, COALESCE(n.orders_count, 0)::numeric),
       ('cancelled_count', c.cancelled_count::numeric, COALESCE(n.cancelled_count, 0)::numeric),
       ('sales_count', c.sales_count::numeric, COALESCE(n.sales_count, 0)::numeric),
       ('returns_count', c.returns_count::numeric, COALESCE(n.returns_count, 0)::numeric),
       ('revenue_rub', c.revenue_rub, COALESCE(n.revenue_rub, 0.00)),
       ('forpay_rub', c.forpay_rub, COALESCE(n.forpay_rub, 0.00))
     ) AS v(column_name, cabinet, per_nm_sum)
     WHERE ${scopeOf('c.')}
     ORDER BY c.calendar_day, v.column_name`,
    params,
  );
  const days = new Set<string>();
  const mismatches: PerNmSumsMismatch[] = [];
  for (const row of result.rows) {
    days.add(row.calendar_day);
    if (!(CHECKED_COLUMNS as readonly string[]).includes(row.column_name)) throw new RangeError(`per_nm_sums_vs_cabinet: unexpected column ${row.column_name}`);
    if (row.mismatch) mismatches.push({ calendar_day: row.calendar_day, column: row.column_name, cabinet: row.cabinet, per_nm_sum: row.per_nm_sum });
  }
  return { check: 'per_nm_sums_vs_cabinet', status: mismatches.length === 0 ? 'PASS' : 'MISMATCH', days_checked: days.size, mismatches };
}

/** Writes the dictionary, then the daily rows, then runs the check - inside the caller's run transaction. */
export async function writeNmDaily(client: QueryClient, input: NmDailyInput): Promise<WriteNmDailyResult> {
  const observations = input.observations ?? await loadLatestObservations(client, input.tenantId);
  const evidence = await loadRunEvidence(client, input.tenantId, input.runId);
  const subjects = summarizeNmSubjects(observations);
  const facts = summarizeNmDaily(observations, input.floor, input.runDay, evidence);
  for (let offset = 0; offset < subjects.length; offset += INSERT_BATCH) {
    await client.query(
      `INSERT INTO dim_nm_subject (tenant_id, nm_id, run_id, subject_name, category_name, brand, supplier_article, last_change_at, evidence_sha256)
       SELECT $1, x.nm_id, $2, x.subject_name, x.category_name, x.brand, x.supplier_article, x.last_change_at::timestamptz, x.evidence_sha256::char(64)
       FROM jsonb_to_recordset($3::jsonb) AS x(nm_id bigint, subject_name text, category_name text, brand text, supplier_article text, last_change_at text, evidence_sha256 text)`,
      [input.tenantId, input.runId, JSON.stringify(subjects.slice(offset, offset + INSERT_BATCH).map((subject) => ({
        nm_id: subject.nmId, subject_name: subject.subjectName, category_name: subject.categoryName, brand: subject.brand,
        supplier_article: subject.supplierArticle, last_change_at: subject.lastChangeAt, evidence_sha256: subject.evidenceSha256,
      })))],
    );
  }
  for (let offset = 0; offset < facts.length; offset += INSERT_BATCH) {
    await client.query(
      `INSERT INTO fact_nm_daily (tenant_id, calendar_day, nm_id, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256)
       SELECT $1, x.calendar_day::date, x.nm_id, $2, x.orders_count, x.cancelled_count, x.sales_count, x.returns_count, x.revenue_rub::numeric, x.forpay_rub::numeric, x.evidence_sha256::char(64)[]
       FROM jsonb_to_recordset($3::jsonb) AS x(calendar_day text, nm_id bigint, orders_count integer, cancelled_count integer, sales_count integer, returns_count integer, revenue_rub text, forpay_rub text, evidence_sha256 text[])`,
      [input.tenantId, input.runId, JSON.stringify(facts.slice(offset, offset + INSERT_BATCH).map((fact) => ({
        calendar_day: fact.calendarDay, nm_id: fact.nmId, orders_count: fact.ordersCount, cancelled_count: fact.cancelledCount,
        sales_count: fact.salesCount, returns_count: fact.returnsCount, revenue_rub: fact.revenueRub, forpay_rub: fact.forpayRub, evidence_sha256: fact.evidenceSha256,
      })))],
    );
  }
  const check = await checkPerNmSumsVsCabinet(client, { tenantId: input.tenantId, runId: input.runId });
  return { subjects: subjects.length, rows: facts.length, days: subjects.length === 0 ? 0 : facts.length / subjects.length, check };
}
