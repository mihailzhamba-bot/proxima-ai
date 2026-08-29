import { randomUUID } from 'node:crypto';

import type { PoolClient } from 'pg';

export type PromotionWriteBoundary = 'attempt' | 'quarantine' | 'fact' | 'lineage' | 'quality' | 'success';

export type PromoteOrderCountsInput = {
  tenantId: string;
  taskId: string;
  parserVersion: string;
  afterWrite?: (boundary: PromotionWriteBoundary) => void | Promise<void>;
};

export type PromotionResult = {
  attemptId: string;
  status: 'SUCCEEDED' | 'FAILED';
  accepted: number;
  quarantined: number;
};

export type FileArtifactLineage = {
  sourceFamily: 'file_artifact';
  acquiredVia: 'manual_xlsx_intake';
  evidenceSha256: string;
  evidenceLocator: string;
  parserVersion: string;
};

type StagedRow = {
  row_number: number;
  nm_id: string | null;
  row_date: string | null;
  payload: unknown;
};

type SourceTask = {
  period_from: string;
  period_to: string;
  evidence_sha256: string | null;
  acquired_at: Date | null;
};

type AcceptedRow = { rowNumber: number; nmId: string; calendarDay: string; orderCount: number };
type QuarantinedRow = { rowNumber: number; reason: QuarantineReason; detail: Record<string, unknown> };
type QuarantineReason = 'SCHEMA_DRIFT' | 'STALE' | 'CONFLICTING' | 'PARTIAL' | 'INVALID_DATE' | 'INVALID_PRODUCT' | 'INVALID_COUNT' | 'DUPLICATE_GRAIN';

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

export class PromotionError extends Error {
  constructor(readonly code: 'SOURCE_UNREADABLE' | 'ROLE_REQUIRED', message: string) {
    super(message);
  }
}

export function fileArtifactLineage(input: Omit<FileArtifactLineage, 'sourceFamily' | 'acquiredVia'>): FileArtifactLineage {
  if (!SHA256_PATTERN.test(input.evidenceSha256)) throw new PromotionError('SOURCE_UNREADABLE', 'file artifact evidence sha256 is invalid');
  if (!input.evidenceLocator || !input.parserVersion) throw new PromotionError('SOURCE_UNREADABLE', 'file artifact lineage metadata is incomplete');
  return { sourceFamily: 'file_artifact', acquiredVia: 'manual_xlsx_intake', ...input };
}

function validMoscowCalendarDay(value: string | null): value is string {
  if (!value || !DATE_PATTERN.test(value)) return false;
  const parsed = new Date(`${value}T12:00:00+03:00`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toLocaleDateString('en-CA', { timeZone: 'Europe/Moscow' }) === value;
}

function orderCount(payload: unknown): number | undefined {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return undefined;
  const value = (payload as Record<string, unknown>).ordersCount;
  if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0) return value;
  if (typeof value === 'string' && /^\d+$/.test(value)) {
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) ? parsed : undefined;
  }
  return undefined;
}

function validNmId(value: string | null): value is string {
  return value !== null && /^\d+$/.test(value) && BigInt(value) > 0n;
}

function classify(rows: StagedRow[], periodFrom: string, periodTo: string): { accepted: AcceptedRow[]; quarantined: QuarantinedRow[] } {
  const accepted: AcceptedRow[] = [];
  const quarantined: QuarantinedRow[] = [];
  const seenGrains = new Set<string>();
  for (const row of rows) {
    if (!validMoscowCalendarDay(row.row_date)) {
      quarantined.push({ rowNumber: row.row_number, reason: 'INVALID_DATE', detail: { row_date: row.row_date } });
      continue;
    }
    if (row.row_date < periodFrom || row.row_date > periodTo) {
      quarantined.push({ rowNumber: row.row_number, reason: 'STALE', detail: { row_date: row.row_date, period_from: periodFrom, period_to: periodTo } });
      continue;
    }
    if (!validNmId(row.nm_id)) {
      quarantined.push({ rowNumber: row.row_number, reason: 'INVALID_PRODUCT', detail: { nm_id: row.nm_id } });
      continue;
    }
    const count = orderCount(row.payload);
    if (count === undefined) {
      quarantined.push({ rowNumber: row.row_number, reason: 'INVALID_COUNT', detail: { ordersCount: (row.payload as Record<string, unknown> | null)?.ordersCount } });
      continue;
    }
    const grain = `${row.nm_id}/${row.row_date}`;
    if (seenGrains.has(grain)) {
      quarantined.push({ rowNumber: row.row_number, reason: 'DUPLICATE_GRAIN', detail: { nm_id: row.nm_id, calendar_day: row.row_date } });
      continue;
    }
    seenGrains.add(grain);
    accepted.push({ rowNumber: row.row_number, nmId: row.nm_id, calendarDay: row.row_date, orderCount: count });
  }
  return { accepted, quarantined };
}

async function existingResult(client: PoolClient, tenantId: string, taskId: string): Promise<PromotionResult | undefined> {
  const attempt = await client.query<{ attempt_id: string; status: 'SUCCEEDED' | 'FAILED' }>(
    `SELECT attempt_id, status FROM fact_attempt_runs
     WHERE tenant_id = $1 AND source_family = 'wb_analytics_task' AND source_ref = $2`,
    [tenantId, taskId],
  );
  const row = attempt.rows[0];
  if (!row) return undefined;
  const [facts, quarantines] = await Promise.all([
    client.query<{ count: number }>('SELECT count(*)::int AS count FROM fact_order_counts WHERE attempt_id = $1', [row.attempt_id]),
    client.query<{ count: number }>('SELECT count(*)::int AS count FROM stg_quarantine_rows WHERE attempt_id = $1', [row.attempt_id]),
  ]);
  return { attemptId: row.attempt_id, status: row.status, accepted: facts.rows[0]?.count ?? 0, quarantined: quarantines.rows[0]?.count ?? 0 };
}

async function writeHook(input: PromoteOrderCountsInput, boundary: PromotionWriteBoundary): Promise<void> {
  await input.afterWrite?.(boundary);
}

export async function promoteOrderCounts(client: PoolClient, input: PromoteOrderCountsInput): Promise<PromotionResult> {
  const attemptId = randomUUID();
  await client.query('BEGIN');
  try {
    await client.query("SELECT set_config('proxima.tenant_id', $1, true)", [input.tenantId]);
    const existing = await existingResult(client, input.tenantId, input.taskId);
    if (existing) {
      await client.query('COMMIT');
      return existing;
    }
    const source = await client.query<SourceTask>(
      `SELECT t.period_from::text, t.period_to::text, raw.content_sha256 AS evidence_sha256, raw.retrieved_at AS acquired_at
       FROM wb_analytics_report_tasks t
       LEFT JOIN LATERAL (
         SELECT content_sha256, retrieved_at FROM raw_wb_analytics_responses
         WHERE task_id = t.task_id AND stage = 'download' ORDER BY retrieved_at DESC, raw_response_id DESC LIMIT 1
       ) raw ON TRUE
       WHERE t.task_id = $1 AND t.tenant_id = $2 AND t.lifecycle_status = 'DOWNLOADED'`,
      [input.taskId, input.tenantId],
    );
    const task = source.rows[0];
    if (!task) throw new PromotionError('SOURCE_UNREADABLE', 'staged task is unavailable for tenant');
    if (!task.evidence_sha256 || !task.acquired_at || !SHA256_PATTERN.test(task.evidence_sha256)) {
      await client.query(
        `INSERT INTO fact_attempt_runs (attempt_id, tenant_id, source_family, source_ref, status, failure_code, finished_at)
         VALUES ($1, $2, 'wb_analytics_task', $3, 'FAILED', 'SOURCE_UNREADABLE', CURRENT_TIMESTAMP)`,
        [attemptId, input.tenantId, input.taskId],
      );
      await writeHook(input, 'attempt');
      await client.query('COMMIT');
      return { attemptId, status: 'FAILED', accepted: 0, quarantined: 0 };
    }
    const staged = await client.query<StagedRow>(
      'SELECT row_number, nm_id::text, row_date::text, payload FROM stg_wb_nm_report_rows WHERE task_id = $1 ORDER BY row_number',
      [input.taskId],
    );
    const classified = classify(staged.rows, task.period_from, task.period_to);
    const status = classified.accepted.length === 0 ? 'FAILED' : 'RUNNING';
    await client.query(
      `INSERT INTO fact_attempt_runs (attempt_id, tenant_id, source_family, source_ref, status, failure_code, finished_at)
       VALUES ($1, $2, 'wb_analytics_task', $3, $4, $5, CASE WHEN $4 = 'FAILED' THEN CURRENT_TIMESTAMP ELSE NULL END)`,
      [attemptId, input.tenantId, input.taskId, status, status === 'FAILED' ? 'ALL_ROWS_QUARANTINED' : null],
    );
    await writeHook(input, 'attempt');
    let quarantineWritten = false;
    for (const row of classified.quarantined) {
      await client.query(
        `INSERT INTO stg_quarantine_rows (attempt_id, tenant_id, source_task_id, source_row_number, reason, detail)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [attemptId, input.tenantId, input.taskId, row.rowNumber, row.reason, JSON.stringify(row.detail)],
      );
      if (!quarantineWritten) {
        quarantineWritten = true;
        await writeHook(input, 'quarantine');
      }
    }
    if (status === 'FAILED') {
      await client.query('COMMIT');
      return { attemptId, status, accepted: 0, quarantined: classified.quarantined.length };
    }
    let factWritten = false;
    for (const row of classified.accepted) {
      await client.query(
        `INSERT INTO fact_order_counts (attempt_id, tenant_id, nm_id, calendar_day, order_count)
         VALUES ($1, $2, $3, $4, $5)`,
        [attemptId, input.tenantId, row.nmId, row.calendarDay, row.orderCount],
      );
      if (!factWritten) {
        factWritten = true;
        await writeHook(input, 'fact');
      }
    }
    await client.query(
      `INSERT INTO fact_lineage_records (attempt_id, tenant_id, evidence_sha256, evidence_locator, parser_version, acquired_via, acquired_at)
       VALUES ($1, $2, $3, $4, $5, 'wb_analytics_task', $6)`,
      [attemptId, input.tenantId, task.evidence_sha256, `wb_analytics_report_tasks/${input.taskId}`, input.parserVersion, task.acquired_at],
    );
    await writeHook(input, 'lineage');
    const checks: Array<[string, Record<string, unknown>]> = [
      ['accepted_quarantined_counts', { accepted: classified.accepted.length, quarantined: classified.quarantined.length }],
      ['grain_uniqueness', { accepted_grains: classified.accepted.length }],
      ['date_window_sanity', { period_from: task.period_from, period_to: task.period_to, rejected_outside_window: classified.quarantined.filter((row) => row.reason === 'STALE').length }],
    ];
    for (const [index, [name, detail]] of checks.entries()) {
      await client.query(
        `INSERT INTO quality_check_results (attempt_id, tenant_id, check_name, status, detail)
         VALUES ($1, $2, $3, 'PASS', $4)`,
        [attemptId, input.tenantId, name, JSON.stringify(detail)],
      );
      if (index === 0) await writeHook(input, 'quality');
    }
    await client.query(
      `UPDATE fact_attempt_runs
       SET status = 'SUCCEEDED', finished_at = CURRENT_TIMESTAMP
       WHERE attempt_id = $1 AND tenant_id = $2 AND status = 'RUNNING'`,
      [attemptId, input.tenantId],
    );
    await writeHook(input, 'success');
    await client.query('COMMIT');
    return { attemptId, status: 'SUCCEEDED', accepted: classified.accepted.length, quarantined: classified.quarantined.length };
  } catch (error) {
    await client.query('ROLLBACK').catch(() => {});
    throw error;
  }
}
