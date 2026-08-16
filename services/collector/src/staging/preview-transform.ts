import { randomUUID } from 'node:crypto';

import type { Pool } from 'pg';

export const PREVIEW_TRANSFORM_PROFILE = 'wb_detail_history_v1';

export type PreviewTransformFailurePoint =
  | 'after_run_created'
  | 'after_quarantine_written'
  | 'after_preview_written'
  | 'after_success_marker';

export type PreviewTransformErrorCode =
  | 'TASK_NOT_FOUND'
  | 'TENANT_MISMATCH'
  | 'TASK_NOT_DOWNLOADED'
  | 'ARTIFACT_SHA256_MISSING'
  | 'RUN_CONFLICT'
  | 'STAGED_COUNT_MISMATCH'
  | 'PREVIEW_OVERFLOW'
  | 'TRANSFORM_FAILED';

export class PreviewTransformError extends Error {
  constructor(
    readonly code: PreviewTransformErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'PreviewTransformError';
  }
}

export interface PreviewTransformHooks {
  at?: (point: PreviewTransformFailurePoint) => Promise<void> | void;
}

export interface StagingRowInput {
  rowNumber: number;
  nmIdText: string | null;
  rowDateText: string | null;
  payload: Record<string, unknown>;
}

export type QuarantineReason = 'NM_ID_INVALID' | 'ROW_DATE_INVALID' | 'ORDER_COUNT_INVALID';

export interface ValidStagingRow {
  rowNumber: number;
  calendarDay: string;
  nmId: string;
  orderCount: bigint;
}

export interface QuarantinedStagingRow {
  rowNumber: number;
  reason: QuarantineReason;
  payload: Record<string, unknown>;
}

export interface PreviewFact {
  calendarDay: string;
  nmId: string;
  orderCount: bigint;
}

export interface PreviewTransformOptions {
  tenantId: string;
  taskId: string;
  hooks?: PreviewTransformHooks;
}

export interface PreviewTransformResult {
  runId: string;
  tenantId: string;
  taskId: string;
  artifactSha256: string;
  stagedRowCount: number;
  validRowCount: number;
  quarantinedRowCount: number;
  previewRowCount: number;
  state: 'created' | 'existing';
}

const MAX_INT4 = 2147483647n;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const NM_ID_PATTERN = /^[1-9][0-9]{0,17}$/;

function isRealCalendarDay(value: string): boolean {
  const parts = value.split('-').map((part) => Number(part));
  const year = parts[0];
  const month = parts[1];
  const day = parts[2];
  if (year === undefined || month === undefined || day === undefined) return false;
  if (month < 1 || month > 12 || day < 1 || day > 31) return false;
  const composed = new Date(Date.UTC(year, month - 1, day));
  return composed.getUTCFullYear() === year && composed.getUTCMonth() === month - 1 && composed.getUTCDate() === day;
}

function parseOrderCount(payload: Record<string, unknown>): bigint | null {
  const value = payload.ordersCount;
  if (typeof value === 'string') {
    if (!/^[0-9]{1,9}$/.test(value)) return null;
    return BigInt(value);
  }
  if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= 999999999) {
    return BigInt(value);
  }
  return null;
}

export function classifyStagingRow(row: StagingRowInput): ValidStagingRow | QuarantinedStagingRow {
  if (row.nmIdText === null || !NM_ID_PATTERN.test(row.nmIdText)) {
    return { rowNumber: row.rowNumber, reason: 'NM_ID_INVALID', payload: row.payload };
  }
  if (row.rowDateText === null || !DATE_PATTERN.test(row.rowDateText) || !isRealCalendarDay(row.rowDateText)) {
    return { rowNumber: row.rowNumber, reason: 'ROW_DATE_INVALID', payload: row.payload };
  }
  const orderCount = parseOrderCount(row.payload);
  if (orderCount === null) {
    return { rowNumber: row.rowNumber, reason: 'ORDER_COUNT_INVALID', payload: row.payload };
  }
  return { rowNumber: row.rowNumber, calendarDay: row.rowDateText, nmId: row.nmIdText, orderCount };
}

export function aggregatePreviewFacts(valid: ValidStagingRow[]): PreviewFact[] {
  const totals = new Map<string, bigint>();
  for (const row of valid) {
    const key = `${row.calendarDay}\u0000${row.nmId}`;
    const current = totals.get(key);
    if (current === undefined) {
      totals.set(key, row.orderCount);
      continue;
    }
    totals.set(key, current + row.orderCount);
  }
  const facts: PreviewFact[] = [];
  for (const [key, orderCount] of totals) {
    if (orderCount > MAX_INT4) {
      throw new PreviewTransformError('PREVIEW_OVERFLOW', `aggregated order_count exceeds integer range: ${key}`);
    }
    const separator = key.indexOf('\u0000');
    const calendarDay = key.slice(0, separator);
    const nmId = key.slice(separator + 1);
    facts.push({ calendarDay, nmId, orderCount });
  }
  facts.sort((left, right) =>
    left.calendarDay === right.calendarDay
      ? (BigInt(left.nmId) < BigInt(right.nmId) ? -1 : BigInt(left.nmId) > BigInt(right.nmId) ? 1 : 0)
      : left.calendarDay < right.calendarDay ? -1 : 1,
  );
  return facts;
}

interface TaskRecord {
  tenant_id: string;
  lifecycle_status: string;
  downloaded_sha256: string | null;
  staged_row_count: number | null;
}

interface RunRecord {
  run_id: string;
  artifact_sha256: string;
  staged_row_count: number;
  valid_row_count: number;
  quarantined_row_count: number;
  preview_row_count: number;
  lifecycle_status: string;
}

export async function transformStagingToPreview(
  pool: Pool,
  options: PreviewTransformOptions,
): Promise<PreviewTransformResult> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    try {
      const taskResult = await client.query<TaskRecord>(
        `SELECT tenant_id, lifecycle_status, downloaded_sha256, staged_row_count
         FROM wb_analytics_report_tasks WHERE task_id = $1 FOR UPDATE`,
        [options.taskId],
      );
      const task = taskResult.rows[0];
      if (task === undefined) {
        throw new PreviewTransformError('TASK_NOT_FOUND', `task ${options.taskId} does not exist`);
      }
      if (task.tenant_id !== options.tenantId) {
        throw new PreviewTransformError('TENANT_MISMATCH', `task ${options.taskId} belongs to tenant ${task.tenant_id}`);
      }
      if (task.lifecycle_status !== 'DOWNLOADED') {
        throw new PreviewTransformError(
          'TASK_NOT_DOWNLOADED',
          `task ${options.taskId} lifecycle status is ${task.lifecycle_status}, not DOWNLOADED`,
        );
      }
      if (task.downloaded_sha256 === null) {
        throw new PreviewTransformError('ARTIFACT_SHA256_MISSING', `task ${options.taskId} has no downloaded artifact checksum`);
      }

      const existingResult = await client.query<RunRecord>(
        `SELECT run_id, artifact_sha256, staged_row_count, valid_row_count, quarantined_row_count, preview_row_count, lifecycle_status
         FROM artifact_parse_runs WHERE task_id = $1 AND profile = $2`,
        [options.taskId, PREVIEW_TRANSFORM_PROFILE],
      );
      const existing = existingResult.rows[0];
      if (existing !== undefined) {
        if (existing.lifecycle_status !== 'SUCCEEDED') {
          throw new PreviewTransformError('RUN_CONFLICT', `parse run ${existing.run_id} is ${existing.lifecycle_status}`);
        }
        await client.query('COMMIT');
        return {
          runId: existing.run_id,
          tenantId: options.tenantId,
          taskId: options.taskId,
          artifactSha256: existing.artifact_sha256,
          stagedRowCount: existing.staged_row_count,
          validRowCount: existing.valid_row_count,
          quarantinedRowCount: existing.quarantined_row_count,
          previewRowCount: existing.preview_row_count,
          state: 'existing',
        };
      }

      const stagedResult = await client.query<{ row_number: number; nm_id_text: string | null; row_date_text: string | null; payload: Record<string, unknown> }>(
        `SELECT row_number, nm_id::text AS nm_id_text, row_date::text AS row_date_text, payload
         FROM stg_wb_nm_report_rows WHERE task_id = $1 ORDER BY row_number`,
        [options.taskId],
      );
      const stagedRows = stagedResult.rows;
      if (task.staged_row_count !== null && stagedRows.length !== task.staged_row_count) {
        throw new PreviewTransformError(
          'STAGED_COUNT_MISMATCH',
          `task ${options.taskId} records ${task.staged_row_count} staged rows but ${stagedRows.length} are present`,
        );
      }

      const valid: ValidStagingRow[] = [];
      const quarantined: QuarantinedStagingRow[] = [];
      for (const row of stagedRows) {
        const classified = classifyStagingRow({
          rowNumber: row.row_number,
          nmIdText: row.nm_id_text,
          rowDateText: row.row_date_text,
          payload: row.payload,
        });
        if ('reason' in classified) quarantined.push(classified);
        else valid.push(classified);
      }
      const facts = aggregatePreviewFacts(valid);

      const runId = randomUUID();
      await client.query(
        `INSERT INTO artifact_parse_runs
         (run_id, tenant_id, task_id, profile, artifact_sha256, lifecycle_status,
          staged_row_count, valid_row_count, quarantined_row_count, preview_row_count)
         VALUES ($1, $2, $3, $4, $5, 'RUNNING', 0, 0, 0, 0)`,
        [runId, options.tenantId, options.taskId, PREVIEW_TRANSFORM_PROFILE, task.downloaded_sha256],
      );
      await options.hooks?.at?.('after_run_created');

      for (let offset = 0; offset < quarantined.length; offset += 200) {
        const chunk = quarantined.slice(offset, offset + 200);
        const values: unknown[] = [];
        const placeholders = chunk.map((row, index) => {
          values.push(options.taskId, runId, row.rowNumber, row.reason, JSON.stringify(row.payload));
          const base = index * 5;
          return `($${base + 1}, $${base + 2}, $${base + 3}, $${base + 4}, $${base + 5})`;
        });
        await client.query(
          `INSERT INTO preview_quarantine_rows (task_id, run_id, row_number, reason, payload) VALUES ${placeholders.join(', ')}`,
          values,
        );
      }
      await options.hooks?.at?.('after_quarantine_written');

      for (let offset = 0; offset < facts.length; offset += 200) {
        const chunk = facts.slice(offset, offset + 200);
        const values: unknown[] = [];
        const placeholders = chunk.map((fact, index) => {
          values.push(options.tenantId, options.taskId, runId, fact.calendarDay, fact.nmId, fact.orderCount.toString());
          const base = index * 6;
          return `($${base + 1}, $${base + 2}, $${base + 3}, $${base + 4}, $${base + 5}, $${base + 6})`;
        });
        await client.query(
          `INSERT INTO preview_order_counts (tenant_id, task_id, run_id, calendar_day, nm_id, order_count) VALUES ${placeholders.join(', ')}`,
          values,
        );
      }
      await options.hooks?.at?.('after_preview_written');

      const marked = await client.query(
        `UPDATE artifact_parse_runs
         SET lifecycle_status = 'SUCCEEDED', staged_row_count = $2, valid_row_count = $3,
             quarantined_row_count = $4, preview_row_count = $5, completed_at = CURRENT_TIMESTAMP
         WHERE run_id = $1 AND lifecycle_status = 'RUNNING'`,
        [runId, stagedRows.length, valid.length, quarantined.length, facts.length],
      );
      if (marked.rowCount !== 1) {
        throw new PreviewTransformError('RUN_CONFLICT', `parse run ${runId} could not be marked succeeded`);
      }
      await options.hooks?.at?.('after_success_marker');

      await client.query('COMMIT');
      return {
        runId,
        tenantId: options.tenantId,
        taskId: options.taskId,
        artifactSha256: task.downloaded_sha256,
        stagedRowCount: stagedRows.length,
        validRowCount: valid.length,
        quarantinedRowCount: quarantined.length,
        previewRowCount: facts.length,
        state: 'created',
      };
    } catch (error) {
      await client.query('ROLLBACK');
      throw error instanceof PreviewTransformError
        ? error
        : new PreviewTransformError('TRANSFORM_FAILED', error instanceof Error ? error.message : String(error));
    }
  } finally {
    client.release();
  }
}
