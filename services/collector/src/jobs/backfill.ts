#!/usr/bin/env node
import { randomUUID } from 'node:crypto';

import { Pool, type PoolClient } from 'pg';

import { BusinessSignalRawStore } from '../business-signal/raw-store.js';
import { assertLeastPrivilegeToken, readPrivateSecret } from '../business-signal/secrets.js';
import { aggregateCabinetDaily, loadLatestObservations, type AggregateCabinetDailyResult } from '../facts/cabinet-daily.js';
import { writeNmDaily, type WriteNmDailyResult } from '../facts/nm-daily.js';
import { sha256 } from '../intake/manifest.js';
import { readImportedCasArtifact, type ImportedCasManifest } from '../wb/cas-artifact.js';
import { type Clock, parseJsonArray, WbClient, WbClientError } from '../wb/client.js';
import { logRunStep } from '../wb/log.js';
import { insertObservations, toOrderObservations, toSaleObservations, type InsertObservationsResult, type ObservationSet } from '../wb/observations.js';
import { RunLedger } from '../wb/run-ledger.js';
import { mskDay, mskToday } from '../wb/msk-day.js';
import { WbArtifactSink } from '../wb/recording-client.js';
import { networkTransport, type WbTransport } from '../wb/transport.js';

const PAGE_SIZE = 80_000;
const TENANT_ID = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const ARTIFACT_SOURCE = /^artifact:([0-9a-f]{64}),([0-9a-f]{64})$/;

export type BackfillArgs =
  | { tenantId: string; mode: 'artifact'; artifactShas: readonly [string, string]; retrievedAt?: string }
  | { tenantId: string; mode: 'live'; from: string; resume: boolean; statisticsTokenFile: string };

export interface BackfillDeps {
  readonly env?: NodeJS.ProcessEnv;
  readonly transport?: WbTransport;
  readonly clock?: Clock;
  readonly repositoryRoot?: string;
  readonly onRunOpened?: (runId: string) => void;
}

export interface BackfillResult {
  readonly runId: string;
  readonly tenantId: string;
  readonly runDay: string;
  readonly orders: InsertObservationsResult;
  readonly sales: InsertObservationsResult;
  readonly aggregate: AggregateCabinetDailyResult;
  readonly nmDaily: WriteNmDailyResult;
}

export function parseBackfillArgs(argv: readonly string[]): BackfillArgs {
  const values = new Map<string, string>();
  let resume = false;
  for (let index = 0; index < argv.length; index += 1) {
    const option = argv[index]!;
    if (option === '--resume') { if (resume) throw new Error('--resume given twice'); resume = true; continue; }
    if (!['--tenant', '--source', '--retrieved-at', '--from', '--statistics-token-file'].includes(option)) throw new Error(`unknown option ${option}`);
    const next = argv[index + 1];
    if (!next || next.startsWith('--')) throw new Error(`option ${option} requires a value`);
    if (values.has(option)) throw new Error(`option ${option} given twice`);
    values.set(option, next);
    index += 1;
  }
  const tenantId = values.get('--tenant');
  if (!tenantId || !TENANT_ID.test(tenantId)) throw new Error('--tenant is required and must be a safe tenant id');
  const source = values.get('--source');
  const from = values.get('--from');
  if ((source === undefined) === (from === undefined)) throw new Error('exactly one of --source or --from is required');
  if (source !== undefined) {
    if (resume || values.has('--statistics-token-file')) throw new Error('artifact mode does not accept --resume or --statistics-token-file');
    const match = ARTIFACT_SOURCE.exec(source);
    if (!match) throw new Error('--source must be artifact:<sha256_sales>,<sha256_orders>');
    const retrievedAt = values.get('--retrieved-at');
    if (retrievedAt !== undefined && !Number.isFinite(Date.parse(retrievedAt))) throw new Error('--retrieved-at must be a valid ISO timestamp');
    return { tenantId, mode: 'artifact', artifactShas: [match[1]!, match[2]!], ...(retrievedAt === undefined ? {} : { retrievedAt }) };
  }
  if (values.has('--retrieved-at')) throw new Error('live mode does not accept --retrieved-at');
  if (!from || !DAY.test(from)) throw new Error('--from must be YYYY-MM-DD');
  const statisticsTokenFile = values.get('--statistics-token-file');
  if (!statisticsTokenFile) throw new Error('live mode requires --statistics-token-file');
  return { tenantId, mode: 'live', from, resume, statisticsTokenFile };
}

function requiredEnv(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

function nextDay(day: string): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10);
}

function errorCode(error: unknown): string {
  if (error instanceof WbClientError) return error.code;
  const code = (error as { code?: unknown } | null)?.code;
  return typeof code === 'string' && code ? code : 'BACKFILL_FAILED';
}

interface PageClient { request(endpoint: 'statistics.orders' | 'statistics.sales', input: { query: Map<string, string>; artifactPageSequence: number }): Promise<{ body: Buffer }>; }

export async function fetchBackfillPages(client: PageClient, endpoint: 'statistics.orders' | 'statistics.sales', dateFrom: string): Promise<{ rows: unknown[]; pageBodies: Buffer[] }> {
  const rows: unknown[] = [];
  const pageBodies: Buffer[] = [];
  let cursor = dateFrom;
  let artifactPageSequence = 1;
  for (;;) {
    const record = await client.request(endpoint, { query: new Map([['dateFrom', cursor], ['flag', '0']]), artifactPageSequence });
    const page = parseJsonArray(record.body, endpoint);
    rows.push(...page);
    pageBodies.push(record.body);
    if (page.length < PAGE_SIZE) break;
    const last = page[page.length - 1] as Record<string, unknown> | undefined;
    if (!last || typeof last.lastChangeDate !== 'string') throw new WbClientError('WB_SCHEMA_DRIFT', `${endpoint}: page cursor has no lastChangeDate`, endpoint);
    if (last.lastChangeDate <= cursor) throw new WbClientError('WB_SCHEMA_DRIFT', `${endpoint}: pagination cursor did not advance`, endpoint);
    cursor = last.lastChangeDate;
    artifactPageSequence += 1;
  }
  return { rows, pageBodies };
}

async function insertImportedArtifact(pool: Pool, tenantId: string, runId: string, manifest: ImportedCasManifest, manifestSha256: string): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    await client.query(
      'INSERT INTO wb_raw_artifacts (artifact_id, tenant_id, run_id, endpoint_id, endpoint_path, http_status, response_headers, content_sha256, content_size, object_locator, manifest_sha256, retrieved_at, attempt) VALUES ($1,$2,$3,$4,$5,200,$6,$7,$8,$9,$10,$11,1)',
      [randomUUID(), tenantId, runId, manifest.endpoint_id, manifest.endpoint_path, JSON.stringify({}), manifest.content_sha256, manifest.content_size, manifest.object_locator, manifestSha256, manifest.retrieved_at],
    );
  } finally {
    try { await client.query('RESET proxima.tenant_id'); client.release(); }
    catch (error) { client.release(error as Error); throw error; }
  }
}

async function writeRun(ledger: RunLedger, tenantId: string, runId: string, orders: readonly ObservationSet[], sales: readonly ObservationSet[], floor: string, runDay: string) {
  let result: { orders: InsertObservationsResult; sales: InsertObservationsResult; aggregate: AggregateCabinetDailyResult; nmDaily: WriteNmDailyResult } | undefined;
  await ledger.succeed(tenantId, runId, async (client: PoolClient) => {
    const orderParts: InsertObservationsResult[] = [];
    const saleParts: InsertObservationsResult[] = [];
    for (const set of orders) orderParts.push(await insertObservations(client, tenantId, runId, set));
    for (const set of sales) saleParts.push(await insertObservations(client, tenantId, runId, set));
    const sum = (parts: readonly InsertObservationsResult[]): InsertObservationsResult => parts.reduce((total, part) => ({ received: total.received + part.received, inserted: total.inserted + part.inserted, skipped: total.skipped + part.skipped }), { received: 0, inserted: 0, skipped: 0 });
    const orderResult = sum(orderParts);
    const saleResult = sum(saleParts);
    // One SELECT of the _latest views feeds both writers (AD-19).
    const observations = await loadLatestObservations(client, tenantId);
    const aggregate = await aggregateCabinetDaily(client, { tenantId, runId, floor, runDay, observations });
    const nmDaily = await writeNmDaily(client, { tenantId, runId, floor, runDay, observations });
    result = { orders: orderResult, sales: saleResult, aggregate, nmDaily };
  });
  if (!result) throw new Error('backfill transaction did not produce a result');
  return result;
}

async function resumeCursor(client: PoolClient, tenantId: string, from: string, table: 'stg_wb_orders_obs' | 'stg_wb_sales_obs'): Promise<string> {
  const result = await client.query<{ cursor: string | null }>(
    `SELECT to_char(max(last_change_at) AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD"T"HH24:MI:SS') AS cursor FROM ${table}
     WHERE tenant_id=$1 AND last_change_at >= ($2::timestamp AT TIME ZONE 'Europe/Moscow')`, [tenantId, from],
  );
  return result.rows[0]?.cursor ?? from;
}

export async function runBackfill(args: BackfillArgs, deps: BackfillDeps = {}): Promise<BackfillResult> {
  const env = deps.env ?? process.env;
  const connectionString = await readPrivateSecret(requiredEnv(env, 'COLLECTOR_DATABASE_URI_FILE'), 'collector database URI file');
  const rawRoot = requiredEnv(env, 'PROXIMA_RAW_DIR');
  let token: string | undefined;
  if (args.mode === 'live') {
    token = await readPrivateSecret(args.statisticsTokenFile, 'WB statistics token file');
    assertLeastPrivilegeToken(token, 'statistics');
  }
  const pool = new Pool({ connectionString, max: 2, application_name: 'proxima-backfill' });
  const ledger = new RunLedger(pool);
  let runId = '';
  try {
    runId = await ledger.open({ tenantId: args.tenantId, kind: 'backfill', gitSha: env.PROXIMA_GIT_SHA, imageId: env.PROXIMA_IMAGE_ID });
    deps.onRunOpened?.(runId);
    const log = (step: string, msg: string, extra: Record<string, unknown> = {}, level: 'info' | 'warn' | 'error' = 'info') => logRunStep({ level, run_id: runId, tenant_id: args.tenantId, kind: 'backfill', step, msg, ...extra });
    try {
      let orders: ObservationSet[];
      let sales: ObservationSet[];
      let floor: string;
      let runDay: string;
      if (args.mode === 'artifact') {
        const artifacts = await Promise.all(args.artifactShas.map((item) => readImportedCasArtifact(rawRoot, item)));
        const byEndpoint = new Map(artifacts.map((item) => [item.manifest.endpoint_id, item]));
        const orderArtifact = byEndpoint.get('statistics.orders');
        const saleArtifact = byEndpoint.get('statistics.sales');
        if (!orderArtifact || !saleArtifact || byEndpoint.size !== 2) throw new Error('artifact pair must contain one sales and one orders response');
        for (const artifact of artifacts) await insertImportedArtifact(pool, args.tenantId, runId, artifact.manifest, artifact.manifestSha256);
        const retrievedAt = args.retrievedAt ?? artifacts.map((item) => item.manifest.retrieved_at).sort()[0]!;
        runDay = mskDay(retrievedAt);
        orders = [toOrderObservations(parseJsonArray(orderArtifact.body, 'statistics.orders'), orderArtifact.manifest.content_sha256)];
        sales = [toSaleObservations(parseJsonArray(saleArtifact.body, 'statistics.sales'), saleArtifact.manifest.content_sha256)];
        const days = [...orders.flatMap((set) => set.rows), ...sales.flatMap((set) => set.rows)].map((row) => mskDay(String(row.payload.date))).sort();
        if (!days[0]) throw new Error('artifact pair contains no observations');
        floor = days[0];
      } else {
        const rawStore = await BusinessSignalRawStore.open(rawRoot, deps.repositoryRoot ?? process.cwd());
        const sink = new WbArtifactSink(args.tenantId, runId, rawStore, pool);
        const client = new WbClient({ statistics: token! }, { transport: deps.transport ?? networkTransport(), artifactSink: sink, ...(deps.clock ? { clock: deps.clock } : {}) });
        let orderCursor = args.from;
        let saleCursor = args.from;
        if (args.resume) {
          const db = await pool.connect();
          try {
            await db.query("SELECT set_config('proxima.tenant_id', $1, false)", [args.tenantId]);
            orderCursor = await resumeCursor(db, args.tenantId, args.from, 'stg_wb_orders_obs');
            saleCursor = await resumeCursor(db, args.tenantId, args.from, 'stg_wb_sales_obs');
          }
          finally { await db.query('RESET proxima.tenant_id').catch(() => undefined); db.release(); }
        }
        const orderPages = await fetchBackfillPages(client, 'statistics.orders', orderCursor);
        const salePages = await fetchBackfillPages(client, 'statistics.sales', saleCursor);
        orders = orderPages.pageBodies.map((body) => toOrderObservations(parseJsonArray(body, 'statistics.orders'), sha256(body)));
        sales = salePages.pageBodies.map((body) => toSaleObservations(parseJsonArray(body, 'statistics.sales'), sha256(body)));
        floor = nextDay(args.from);
        runDay = mskToday(new Date(deps.clock?.now() ?? Date.now()));
      }
      const written = await writeRun(ledger, args.tenantId, runId, orders, sales, floor, runDay);
      log('complete', 'backfill committed', { run_day: runDay, floor, orders_inserted: written.orders.inserted, sales_inserted: written.sales.inserted, days: written.aggregate.days, nm_subjects: written.nmDaily.subjects, nm_rows: written.nmDaily.rows });
      // AD-19: the check per_nm_sums_vs_cabinet is one AD-17 line and never blocks the run.
      const passed = written.nmDaily.check.status === 'PASS';
      log('quality_check', passed ? 'per-nm sums equal the cabinet day' : 'per-nm sums differ from the cabinet day (threshold UNKNOWN until OQ-7)', { ...written.nmDaily.check }, passed ? 'info' : 'warn');
      return { runId, tenantId: args.tenantId, runDay, ...written };
    } catch (error) {
      log('failed', 'backfill failed; marking FAILED', { code: errorCode(error) }, 'error');
      await ledger.fail(args.tenantId, runId).catch(() => undefined);
      throw error;
    }
  } finally { await pool.end(); }
}

async function main(): Promise<void> {
  const result = await runBackfill(parseBackfillArgs(process.argv.slice(2)));
  process.stdout.write(`${JSON.stringify({ run_id: result.runId, tenant_id: result.tenantId, kind: 'backfill', run_day: result.runDay, orders: result.orders, sales: result.sales, aggregate: result.aggregate, nm_daily: result.nmDaily })}\n`);
}

if (process.argv[1] && /[\\/]backfill\.(?:ts|js)$/.test(process.argv[1])) {
  main().catch((error: unknown) => { process.stderr.write(`backfill: ${errorCode(error)}: ${error instanceof Error ? error.message : String(error)}\n`); process.exit(1); });
}
