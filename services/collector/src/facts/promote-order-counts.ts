import { randomUUID } from 'node:crypto';

import type { Pool, PoolClient } from 'pg';

export type PromotionFaultPoint = 'after_attempt' | 'after_quarantine' | 'after_fact' | 'after_lineage' | 'after_quality' | 'after_success';
export type QuarantineReason = 'INVALID_DATE' | 'INVALID_PRODUCT' | 'INVALID_COUNT' | 'DUPLICATE_GRAIN' | 'STALE';

export class PromotionError extends Error {
  constructor(readonly code: 'SOURCE_NOT_FOUND' | 'SOURCE_NOT_DOWNLOADED' | 'SOURCE_ROLE_REQUIRED' | 'PROMOTION_FAILED', message: string) {
    super(message);
    this.name = 'PromotionError';
  }
}

export interface PromotionInput {
  tenantId: string;
  taskId: string;
}

export interface PromotionHooks {
  afterWrite?(point: PromotionFaultPoint): void | Promise<void>;
}

export interface PromotionResult {
  attemptId: string;
  status: 'SUCCEEDED' | 'FAILED';
  acceptedRows: number;
  quarantinedRows: number;
}

export interface LineageReference {
  sourceFamily: 'wb_analytics_task' | 'file_artifact';
  sourceRef: string;
  evidenceSha256: string;
  evidenceLocator: string;
  parserVersion: string;
  acquiredVia: 'wb_analytics_task' | 'manual_xlsx_intake';
  acquiredAt: string;
}

export interface PersistLineageInput {
  tenantId: string;
  attemptId: string;
  lineage: LineageReference;
}

interface SourceRow {
  task_id: string;
  report_type: string;
  period_from: string;
  period_to: string;
  content_sha256: string;
  retrieved_at: string;
}

interface StagedRow {
  row_number: number;
  nm_id: string | null;
  row_date: string | null;
  payload: Record<string, unknown>;
}

interface AcceptedRow {
  rowNumber: number;
  nmId: number;
  calendarDay: string;
  orderCount: number;
}

interface RejectedRow {
  rowNumber: number;
  reason: QuarantineReason;
  detail: Record<string, unknown>;
}

const MAX_INTEGER = 2_147_483_647;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

export function makeLineageReference(input: LineageReference): LineageReference {
  if (!SHA256_PATTERN.test(input.evidenceSha256)) throw new PromotionError('PROMOTION_FAILED', 'lineage evidence sha256 is invalid');
  if (input.sourceFamily === 'wb_analytics_task' && input.acquiredVia !== 'wb_analytics_task') {
    throw new PromotionError('PROMOTION_FAILED', 'WB task lineage must use wb_analytics_task acquisition');
  }
  if (input.sourceFamily === 'file_artifact' && input.acquiredVia !== 'manual_xlsx_intake') {
    throw new PromotionError('PROMOTION_FAILED', 'file artifact lineage must use manual_xlsx_intake acquisition');
  }
  return input;
}

function parsePositiveInteger(value: string | null): number | undefined {
  if (!value || !/^\d+$/.test(value)) return undefined;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 && parsed <= MAX_INTEGER ? parsed : undefined;
}

function parseOrderCount(value: unknown): number | undefined {
  if ((typeof value !== 'string' && typeof value !== 'number') || !/^\d+$/.test(String(value))) return undefined;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed <= MAX_INTEGER ? parsed : undefined;
}

function isCalendarDay(value: string | null): value is string {
  if (!value || !DATE_PATTERN.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function validateStagedRows(rows: StagedRow[], source: Pick<SourceRow, 'period_from' | 'period_to'>): { accepted: AcceptedRow[]; rejected: RejectedRow[] } {
  const accepted: AcceptedRow[] = [];
  const rejected: RejectedRow[] = [];
  const grains = new Set<string>();
  for (const row of rows) {
    if (!isCalendarDay(row.row_date)) {
      rejected.push({ rowNumber: row.row_number, reason: 'INVALID_DATE', detail: { row_date: row.row_date } });
      continue;
    }
    const nmId = parsePositiveInteger(row.nm_id);
    if (nmId === undefined) {
      rejected.push({ rowNumber: row.row_number, reason: 'INVALID_PRODUCT', detail: { nm_id: row.nm_id } });
      continue;
    }
    const orderCount = parseOrderCount(row.payload.ordersCount);
    if (orderCount === undefined) {
      rejected.push({ rowNumber: row.row_number, reason: 'INVALID_COUNT', detail: { ordersCount: row.payload.ordersCount } });
      continue;
    }
    if (row.row_date < source.period_from || row.row_date > source.period_to) {
      rejected.push({ rowNumber: row.row_number, reason: 'STALE', detail: { row_date: row.row_date, period_from: source.period_from, period_to: source.period_to } });
      continue;
    }
    const grain = `${nmId}:${row.row_date}`;
    if (grains.has(grain)) {
      rejected.push({ rowNumber: row.row_number, reason: 'DUPLICATE_GRAIN', detail: { nm_id: nmId, calendar_day: row.row_date } });
      continue;
    }
    grains.add(grain);
    accepted.push({ rowNumber: row.row_number, nmId, calendarDay: row.row_date, orderCount });
  }
  return { accepted, rejected };
}

async function afterWrite(hooks: PromotionHooks | undefined, point: PromotionFaultPoint): Promise<void> {
  await hooks?.afterWrite?.(point);
}

async function enterSourcePublisher(client: PoolClient, tenantId: string): Promise<void> {
  const membership = await client.query<{ is_member: boolean }>(
    `SELECT pg_has_role(session_user, 'proxima_source_publisher', 'MEMBER')
            AND NOT (SELECT rolsuper FROM pg_roles WHERE rolname = session_user) AS is_member`,
  );
  if (membership.rows[0]?.is_member !== true) {
    throw new PromotionError('SOURCE_ROLE_REQUIRED', 'promotion requires a login role granted proxima_source_publisher');
  }
  await client.query('SET LOCAL ROLE proxima_source_publisher');
  await client.query(`SELECT set_config('proxima.tenant_id', $1, true)`, [tenantId]);
}

async function loadSource(client: PoolClient, input: PromotionInput): Promise<SourceRow> {
  const result = await client.query<SourceRow>(
    `SELECT t.task_id::text, t.report_type, t.period_from::text, t.period_to::text,
            raw.content_sha256, raw.retrieved_at::text
       FROM wb_analytics_report_tasks t
       JOIN LATERAL (
         SELECT content_sha256, retrieved_at
           FROM raw_wb_analytics_responses
          WHERE task_id = t.task_id AND stage = 'download' AND http_status BETWEEN 200 AND 299
          ORDER BY retrieved_at DESC, raw_response_id DESC
          LIMIT 1
       ) raw ON true
      WHERE t.task_id = $1 AND t.tenant_id = $2`,
    [input.taskId, input.tenantId],
  );
  if (result.rowCount === 0) throw new PromotionError('SOURCE_NOT_FOUND', 'staged WB task with successful download is not visible for tenant');
  return result.rows[0]!;
}

async function insertQuality(client: PoolClient, attemptId: string, tenantId: string, name: string, status: 'PASS' | 'FAIL', detail: Record<string, unknown>): Promise<void> {
  await client.query(
    `INSERT INTO quality_check_results (attempt_id, tenant_id, check_name, status, detail)
     VALUES ($1, $2, $3, $4, $5::jsonb)`,
    [attemptId, tenantId, name, status, JSON.stringify(detail)],
  );
}

async function insertLineage(client: PoolClient, tenantId: string, attemptId: string, lineage: LineageReference): Promise<void> {
  await client.query(
    `INSERT INTO fact_lineage_records
       (attempt_id, tenant_id, evidence_sha256, evidence_locator, parser_version, acquired_via, acquired_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7)`,
    [attemptId, tenantId, lineage.evidenceSha256, lineage.evidenceLocator, lineage.parserVersion, lineage.acquiredVia, lineage.acquiredAt],
  );
}

async function assertFileArtifactLineage(client: PoolClient, input: PersistLineageInput, lineage: LineageReference): Promise<void> {
  const source = await client.query<{ source_ref: string; content_sha256: string; object_locator: string; source_schema_version: string; retrieved_at: string }>(
    `SELECT f.source_ref, artifact.content_sha256, artifact.object_locator, intake.source_schema_version, intake.retrieved_at::text
       FROM fact_attempt_runs f
       JOIN intake_attempts intake ON intake.attempt_id = f.source_ref AND intake.tenant_id = f.tenant_id
       JOIN source_artifacts artifact ON artifact.artifact_id = intake.artifact_id
      WHERE f.attempt_id = $1 AND f.tenant_id = $2 AND f.source_family = 'file_artifact'`,
    [input.attemptId, input.tenantId],
  );
  const row = source.rows[0];
  if (!row || lineage.sourceRef !== row.source_ref || lineage.evidenceSha256 !== row.content_sha256 || lineage.evidenceLocator !== row.object_locator || lineage.parserVersion !== row.source_schema_version || new Date(lineage.acquiredAt).getTime() !== new Date(row.retrieved_at).getTime()) {
    throw new PromotionError('SOURCE_NOT_FOUND', 'file artifact lineage does not resolve to the immutable intake chain');
  }
}

export async function persistLineageReference(pool: Pool, input: PersistLineageInput): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    try {
      await enterSourcePublisher(client, input.tenantId);
      const lineage = makeLineageReference(input.lineage);
      if (lineage.sourceFamily !== 'file_artifact') throw new PromotionError('PROMOTION_FAILED', 'standalone lineage persistence is reserved for file artifacts');
      await assertFileArtifactLineage(client, input, lineage);
      await insertLineage(client, input.tenantId, input.attemptId, lineage);
      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    }
  } catch (error) {
    if (error instanceof PromotionError) throw error;
    throw new PromotionError('PROMOTION_FAILED', 'lineage persistence failed');
  } finally {
    client.release();
  }
}

export async function promoteOrderCounts(pool: Pool, input: PromotionInput, hooks?: PromotionHooks): Promise<PromotionResult> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    try {
      await enterSourcePublisher(client, input.tenantId);
      const source = await loadSource(client, input);
      const attemptId = randomUUID();
      await client.query(
        `INSERT INTO fact_attempt_runs (attempt_id, tenant_id, source_family, source_ref, status)
         VALUES ($1, $2, 'wb_analytics_task', $3, 'RUNNING')`,
        [attemptId, input.tenantId, source.task_id],
      );
      await afterWrite(hooks, 'after_attempt');

      const staged = await client.query<StagedRow>(
        `SELECT row_number, nm_id::text, row_date::text, payload
           FROM stg_wb_nm_report_rows
          WHERE task_id = $1
          ORDER BY row_number`,
        [source.task_id],
      );
      const { accepted, rejected } = validateStagedRows(staged.rows, source);
      for (const row of rejected) {
        await client.query(
          `INSERT INTO stg_quarantine_rows (attempt_id, tenant_id, source_task_id, source_row_number, reason, detail)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb)`,
          [attemptId, input.tenantId, source.task_id, row.rowNumber, row.reason, JSON.stringify(row.detail)],
        );
      }
      if (rejected.length > 0) await afterWrite(hooks, 'after_quarantine');

      for (const row of accepted) {
        await client.query(
          `INSERT INTO fact_order_counts (attempt_id, tenant_id, nm_id, calendar_day, order_count)
           VALUES ($1, $2, $3, $4, $5)`,
          [attemptId, input.tenantId, row.nmId, row.calendarDay, row.orderCount],
        );
      }
      if (accepted.length > 0) await afterWrite(hooks, 'after_fact');

      if (accepted.length > 0) {
        const lineage = makeLineageReference({
          sourceFamily: 'wb_analytics_task',
          sourceRef: source.task_id,
          evidenceSha256: source.content_sha256,
          evidenceLocator: `wb-analytics://task/${source.task_id}/sha256/${source.content_sha256}`,
          parserVersion: `${source.report_type}:staged-v1`,
          acquiredVia: 'wb_analytics_task',
          acquiredAt: source.retrieved_at,
        });
        await insertLineage(client, input.tenantId, attemptId, lineage);
        await afterWrite(hooks, 'after_lineage');
      }

      await insertQuality(client, attemptId, input.tenantId, 'row_counts', 'PASS', { accepted: accepted.length, quarantined: rejected.length });
      await insertQuality(client, attemptId, input.tenantId, 'grain_uniqueness', rejected.some((row) => row.reason === 'DUPLICATE_GRAIN') ? 'FAIL' : 'PASS', { duplicate_grains: rejected.filter((row) => row.reason === 'DUPLICATE_GRAIN').length });
      await insertQuality(client, attemptId, input.tenantId, 'date_window', rejected.some((row) => row.reason === 'INVALID_DATE' || row.reason === 'STALE') ? 'FAIL' : 'PASS', { invalid_or_stale_dates: rejected.filter((row) => row.reason === 'INVALID_DATE' || row.reason === 'STALE').length, timezone: 'Europe/Moscow' });
      await afterWrite(hooks, 'after_quality');

      const status = accepted.length === 0 ? 'FAILED' : 'SUCCEEDED';
      await client.query(
        `UPDATE fact_attempt_runs
            SET status = $3, failure_code = $4, finished_at = CURRENT_TIMESTAMP
          WHERE attempt_id = $1 AND tenant_id = $2 AND status = 'RUNNING'`,
        [attemptId, input.tenantId, status, status === 'FAILED' ? 'ALL_ROWS_QUARANTINED' : null],
      );
      await afterWrite(hooks, 'after_success');
      await client.query('COMMIT');
      return { attemptId, status, acceptedRows: accepted.length, quarantinedRows: rejected.length };
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    }
  } catch (error) {
    if (error instanceof PromotionError) throw error;
    throw new PromotionError('PROMOTION_FAILED', 'promotion transaction failed');
  } finally {
    client.release();
  }
}
