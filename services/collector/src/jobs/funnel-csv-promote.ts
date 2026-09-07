#!/usr/bin/env node
/** Promote durable async CSV rows into the common funnel observations/facts. */
import { Decimal } from 'decimal.js';
import { Pool, type PoolClient } from 'pg';

import { versionFunnelDaily, type FunnelProductDay, type VersionFunnelDailyResult } from '../facts/funnel-daily.js';
import { canonicalJson, sha256 } from '../intake/manifest.js';
import {
  insertFunnelObservations,
  shiftDay,
  type FunnelBatch,
  type FunnelObservation,
  type InsertFunnelObservationsResult,
} from '../wb/funnel-v3.js';
import { logRunStep } from '../wb/log.js';
import { RunLedger } from '../wb/run-ledger.js';
import { readPrivateSecret } from '../business-signal/secrets.js';

const RUN_KIND = 'funnel_csv_promote';
const FUNNEL_SOURCE = 'csv' as const;
const TENANT_ID = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const SHA256_HEX = /^[0-9a-f]{64}$/;

/**
 * [ASSUMPTION until Story 3.0] Real metric column names must be confirmed from
 * a captured WB CSV. The correction is deliberately confined to this table.
 * `nmID` and `dt` are confirmed by tools/wb_async_report.py:complete_download.
 */
export const CSV_COLUMN_MAP = {
  nmId: 'nmID',
  calendarDay: 'dt',
  openCard: 'open_card',
  cart: 'cart',
  orders: 'orders',
  ordersSumRub: 'orders_sum_rub',
  buyouts: 'buyouts',
  buyoutsSumRub: 'buyouts_sum_rub',
} as const;

export interface FunnelCsvPromoteArgs { tenantId: string }
export interface FunnelCsvPromoteDeps {
  env?: NodeJS.ProcessEnv;
  onRunOpened?: (runId: string) => void;
}
export interface FunnelCsvPromoteResult {
  runId: string;
  tenantId: string;
  tasks: number;
  rows: number;
  observations: InsertFunnelObservationsResult;
  facts: VersionFunnelDailyResult;
}

interface StagedCsvRow {
  task_id: string;
  row_number: number;
  downloaded_sha256: string;
  payload: unknown;
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function text(record: Record<string, unknown>, column: string, context: string): string {
  const value = record[column];
  if (typeof value !== 'string' || value.trim() === '') throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} has no ${column}`);
  return value.trim();
}

function count(record: Record<string, unknown>, column: string, context: string): number {
  const raw = text(record, column, context);
  if (!/^\d+$/.test(raw)) throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} ${column} is not a non-negative integer`);
  const value = Number(raw);
  if (!Number.isSafeInteger(value)) throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} ${column} is outside the safe integer range`);
  return value;
}

function money(record: Record<string, unknown>, column: string, context: string): string {
  const raw = text(record, column, context).replace(',', '.');
  if (!/^\d+(?:\.\d{1,2})?$/.test(raw)) throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} ${column} is not non-negative money`);
  return new Decimal(raw).toFixed(2);
}

export function parseFunnelCsvRow(payload: unknown, context = 'CSV row'): FunnelObservation {
  if (!object(payload)) throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} payload is not an object`);
  const nmIdRaw = text(payload, CSV_COLUMN_MAP.nmId, context);
  if (!/^\d+$/.test(nmIdRaw)) throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} nmID is not a positive integer`);
  const nmId = Number(nmIdRaw);
  if (!Number.isSafeInteger(nmId) || nmId <= 0) throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} nmID is not a positive safe integer`);
  const calendarDay = text(payload, CSV_COLUMN_MAP.calendarDay, context);
  try { shiftDay(calendarDay, 0); }
  catch { throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: ${context} dt is not a calendar date`); }
  const openCard = count(payload, CSV_COLUMN_MAP.openCard, context);
  const cart = count(payload, CSV_COLUMN_MAP.cart, context);
  const orders = count(payload, CSV_COLUMN_MAP.orders, context);
  const ordersSumRub = money(payload, CSV_COLUMN_MAP.ordersSumRub, context);
  const buyouts = count(payload, CSV_COLUMN_MAP.buyouts, context);
  const buyoutsSumRub = money(payload, CSV_COLUMN_MAP.buyoutsSumRub, context);
  return {
    nmId,
    calendarDay,
    canonicalSha256: sha256(canonicalJson(payload)),
    openCard,
    cart,
    orders,
    ordersSumRub,
    buyouts,
    buyoutsSumRub,
    payload,
  };
}

export function parseFunnelCsvArgs(argv: readonly string[]): FunnelCsvPromoteArgs {
  if (argv.length !== 2 || argv[0] !== '--tenant' || !argv[1]) throw new Error('usage: funnel-csv-promote --tenant <tenant>');
  if (!TENANT_ID.test(argv[1])) throw new Error('--tenant must match ^[a-z0-9][a-z0-9_-]{2,63}$');
  return { tenantId: argv[1] };
}

async function loadRows(client: PoolClient, tenantId: string): Promise<StagedCsvRow[]> {
  const result = await client.query<StagedCsvRow>(
    `SELECT r.task_id::text, r.row_number, t.downloaded_sha256, r.payload
     FROM wb_analytics_report_tasks t
     JOIN stg_wb_nm_report_rows r ON r.task_id = t.task_id
     WHERE t.tenant_id = $1 AND t.downloaded_sha256 IS NOT NULL
     ORDER BY t.downloaded_at NULLS FIRST, t.updated_at, t.task_id, r.row_number`,
    [tenantId],
  );
  return result.rows;
}

export async function promoteFunnelCsv(args: FunnelCsvPromoteArgs, deps: FunnelCsvPromoteDeps = {}): Promise<FunnelCsvPromoteResult> {
  const env = deps.env ?? process.env;
  const uriFile = env.COLLECTOR_DATABASE_URI_FILE;
  if (!uriFile) throw new Error('COLLECTOR_DATABASE_URI_FILE is not set');
  const connectionString = await readPrivateSecret(uriFile, 'collector database URI file');
  const pool = new Pool({ connectionString, max: 2, application_name: 'proxima-funnel-csv-promote' });
  const ledger = new RunLedger(pool);
  let runId: string | undefined;
  try {
    runId = await ledger.open({ tenantId: args.tenantId, kind: RUN_KIND, gitSha: env.PROXIMA_GIT_SHA, imageId: env.PROXIMA_IMAGE_ID });
    deps.onRunOpened?.(runId);
    let outcome: Omit<FunnelCsvPromoteResult, 'runId' | 'tenantId'> | undefined;
    await ledger.succeed(args.tenantId, runId, async (client) => {
      const staged = await loadRows(client, args.tenantId);
      const tasks = new Set(staged.map((row) => row.task_id));
      const grouped = new Map<string, { evidenceSha256: string; rows: FunnelObservation[] }>();
      for (const row of staged) {
        if (!SHA256_HEX.test(row.downloaded_sha256)) throw new Error(`FUNNEL_CSV_SCHEMA_DRIFT: task ${row.task_id} has invalid downloaded_sha256`);
        const group = grouped.get(row.task_id) ?? { evidenceSha256: row.downloaded_sha256, rows: [] };
        group.rows.push(parseFunnelCsvRow(row.payload, `task ${row.task_id} row ${row.row_number}`));
        grouped.set(row.task_id, group);
      }
      let observations: InsertFunnelObservationsResult = { received: 0, inserted: 0, skipped: 0 };
      const productDays: FunnelProductDay[] = [];
      for (const group of grouped.values()) {
        const batch: FunnelBatch = { evidenceSha256: group.evidenceSha256, received: group.rows.length, rows: group.rows };
        const written = await insertFunnelObservations(client, args.tenantId, runId!, batch, FUNNEL_SOURCE);
        observations = { received: observations.received + written.received, inserted: observations.inserted + written.inserted, skipped: observations.skipped + written.skipped };
        group.rows.forEach((row) => productDays.push({ nmId: row.nmId, calendarDay: row.calendarDay }));
      }
      const facts = await versionFunnelDaily(client, { tenantId: args.tenantId, runId: runId!, productDays, source: FUNNEL_SOURCE });
      outcome = { tasks: tasks.size, rows: staged.length, observations, facts };
    });
    if (!outcome) throw new Error('funnel_csv_promote: transaction produced no outcome');
    logRunStep({ level: 'info', run_id: runId, tenant_id: args.tenantId, kind: RUN_KIND, step: 'facts', msg: 'CSV promotion committed', ...outcome });
    return { runId, tenantId: args.tenantId, ...outcome };
  } catch (error) {
    if (runId) await ledger.fail(args.tenantId, runId).catch(() => undefined);
    throw error;
  } finally {
    await pool.end();
  }
}

async function main(): Promise<void> {
  const result = await promoteFunnelCsv(parseFunnelCsvArgs(process.argv.slice(2)));
  process.stdout.write(`${JSON.stringify({ run_id: result.runId, tenant_id: result.tenantId, kind: RUN_KIND, tasks: result.tasks, rows: result.rows, observations: result.observations, facts: result.facts })}\n`);
}

if (process.argv[1] && /[\\/]funnel-csv-promote\.(?:ts|js)$/.test(process.argv[1])) {
  main().catch((error: unknown) => {
    process.stderr.write(`funnel-csv-promote: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  });
}
