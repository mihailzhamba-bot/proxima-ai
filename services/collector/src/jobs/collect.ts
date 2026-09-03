#!/usr/bin/env node
/**
 * `collect` job (Story 1.4): one run of the WB Statistics orders/sales
 * increment for one tenant.
 *
 * Flow (AD-3): open the run RUNNING, fetch orders and sales through the single
 * WB client with every response landing in CAS + wb_raw_artifacts before
 * parsing (Story 1.3), parse into observations, then write observations and
 * SUCCEEDED in one transaction. Any failure rolls that transaction back and
 * marks the run FAILED in a separate autocommit, so partial observations never
 * exist.
 *
 * Secrets follow the spine Conventions: the database URI comes from the file
 * named by COLLECTOR_DATABASE_URI_FILE, the WB token from --statistics-token-file.
 * Values are never logged. Live network stays fail-closed unless
 * WB_ALLOW_LIVE_NETWORK=1 (AD-4); tests inject FixtureTransport.
 */
import { Pool } from 'pg';

import { BusinessSignalRawStore } from '../business-signal/raw-store.js';
import { assertLeastPrivilegeToken, readPrivateSecret } from '../business-signal/secrets.js';
import { sha256 } from '../intake/manifest.js';
import { WbClient, WbClientError, parseJsonArray, type Clock } from '../wb/client.js';
import { logRunStep } from '../wb/log.js';
import {
  insertObservations,
  toOrderObservations,
  toSaleObservations,
  type InsertObservationsResult,
  type ObservationSet,
} from '../wb/observations.js';
import { WbArtifactSink } from '../wb/recording-client.js';
import { RunLedger } from '../wb/run-ledger.js';
import { networkTransport, type WbTransport } from '../wb/transport.js';

const RUN_KIND = 'collect';
const TENANT_ID = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const DATE_FROM = /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2})?$/;
const OPTIONS = ['--tenant', '--date-from', '--statistics-token-file'] as const;
type Option = (typeof OPTIONS)[number];

export interface CollectArgs {
  tenantId: string;
  /** Passed to WB verbatim as `dateFrom` together with `flag=0` (Moscow wall clock). */
  dateFrom: string;
  statisticsTokenFile: string;
}

export interface CollectDeps {
  transport: WbTransport;
  /** Defaults to process.env; reads COLLECTOR_DATABASE_URI_FILE, PROXIMA_RAW_DIR, PROXIMA_GIT_SHA, PROXIMA_IMAGE_ID. */
  env?: NodeJS.ProcessEnv;
  clock?: Clock;
  /** Git tree the CAS root must stay outside of; defaults to process.cwd(). */
  repositoryRoot?: string;
  /** Test hook: learn the run id as soon as the ledger row exists. */
  onRunOpened?: (runId: string) => void;
}

export interface CollectResult {
  runId: string;
  tenantId: string;
  orders: InsertObservationsResult;
  sales: InsertObservationsResult;
}

export function parseCollectArgs(argv: readonly string[]): CollectArgs {
  const values: Partial<Record<Option, string>> = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!isOption(key)) {
      throw new Error(`unknown option ${String(key)}; expected ${OPTIONS.join(', ')}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`option ${key} requires a value`);
    if (values[key] !== undefined) throw new Error(`option ${key} given twice`);
    values[key] = value;
    index += 1;
  }
  for (const option of OPTIONS) {
    if (values[option] === undefined) throw new Error(`required option: ${option}`);
  }
  const tenantId = values['--tenant'] as string;
  const dateFrom = values['--date-from'] as string;
  if (!TENANT_ID.test(tenantId)) throw new Error('--tenant must match ^[a-z0-9][a-z0-9_-]{2,63}$');
  if (!DATE_FROM.test(dateFrom)) throw new Error('--date-from must be YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS (Moscow wall clock)');
  return { tenantId, dateFrom, statisticsTokenFile: values['--statistics-token-file'] as string };
}

function isOption(value: string | undefined): value is Option {
  return value !== undefined && (OPTIONS as readonly string[]).includes(value);
}

/** Stable code for logs and stderr: WbClientError / BusinessSignalError codes pass through. */
function errorCode(error: unknown): string {
  if (error instanceof WbClientError) return error.code;
  const code = (error as { code?: unknown } | null)?.code;
  return typeof code === 'string' && code !== '' ? code : 'COLLECT_FAILED';
}

function requiredEnv(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

export async function runCollect(args: CollectArgs, deps: CollectDeps): Promise<CollectResult> {
  const env = deps.env ?? process.env;
  const { tenantId, dateFrom } = args;
  const connectionString = await readPrivateSecret(requiredEnv(env, 'COLLECTOR_DATABASE_URI_FILE'), 'collector database URI file');
  const statisticsToken = await readPrivateSecret(args.statisticsTokenFile, 'WB statistics token file');
  // WB API is READ-only by policy: a read-write or multi-category token fails
  // closed here, before any connection or request is made.
  assertLeastPrivilegeToken(statisticsToken, 'statistics');
  const rawRoot = requiredEnv(env, 'PROXIMA_RAW_DIR');
  const pool = new Pool({ connectionString, max: 2, application_name: 'proxima-collect' });
  try {
    const ledger = new RunLedger(pool);
    const runId = await ledger.open({ tenantId, kind: RUN_KIND, gitSha: env.PROXIMA_GIT_SHA, imageId: env.PROXIMA_IMAGE_ID });
    deps.onRunOpened?.(runId);
    const log = (step: string, msg: string, extra: Record<string, unknown> = {}, level: 'info' | 'error' = 'info'): void =>
      logRunStep({ level, run_id: runId, tenant_id: tenantId, kind: RUN_KIND, step, msg, ...extra });
    try {
      const rawStore = await BusinessSignalRawStore.open(rawRoot, deps.repositoryRoot ?? process.cwd());
      const sink = new WbArtifactSink(tenantId, runId, rawStore, pool);
      const client = new WbClient(
        { statistics: statisticsToken },
        { transport: deps.transport, artifactSink: sink, ...(deps.clock ? { clock: deps.clock } : {}) },
      );
      const query = new Map([['dateFrom', dateFrom], ['flag', '0']]);

      const ordersRecord = await client.request('statistics.orders', { query });
      const orders = toOrderObservations(parseJsonArray(ordersRecord.body, 'statistics.orders'), sha256(ordersRecord.body));
      log('orders', 'fetched', { http_status: ordersRecord.httpStatus, received: orders.received, distinct: orders.rows.length });

      const salesRecord = await client.request('statistics.sales', { query });
      const sales = toSaleObservations(parseJsonArray(salesRecord.body, 'statistics.sales'), sha256(salesRecord.body));
      log('sales', 'fetched', { http_status: salesRecord.httpStatus, received: sales.received, distinct: sales.rows.length });

      const written = await writeObservations(ledger, tenantId, runId, orders, sales);
      log('observations', 'committed with SUCCEEDED', {
        orders_inserted: written.orders.inserted,
        orders_skipped: written.orders.skipped,
        sales_inserted: written.sales.inserted,
        sales_skipped: written.sales.skipped,
      });
      return { runId, tenantId, ...written };
    } catch (error) {
      log('failed', 'run failed; marking FAILED', { code: errorCode(error) }, 'error');
      // If the FAILED flip itself fails the run stays RUNNING; the original
      // error still surfaces and Story 1.7's run tooling reconciles the ledger.
      await ledger.fail(tenantId, runId).catch((failError: unknown) => {
        const detail = failError instanceof Error ? failError.message : String(failError);
        log('failed', 'could not mark run FAILED', { detail }, 'error');
      });
      throw error;
    }
  } finally {
    await pool.end();
  }
}

/** Observations and the SUCCEEDED flip share one transaction (AD-3). */
async function writeObservations(
  ledger: RunLedger,
  tenantId: string,
  runId: string,
  orders: ObservationSet,
  sales: ObservationSet,
): Promise<{ orders: InsertObservationsResult; sales: InsertObservationsResult }> {
  let ordersResult: InsertObservationsResult | undefined;
  let salesResult: InsertObservationsResult | undefined;
  await ledger.succeed(tenantId, runId, async (client) => {
    ordersResult = await insertObservations(client, tenantId, runId, orders);
    salesResult = await insertObservations(client, tenantId, runId, sales);
  });
  if (ordersResult === undefined || salesResult === undefined) {
    throw new Error('collect: observations were not written inside the run transaction');
  }
  return { orders: ordersResult, sales: salesResult };
}

async function main(): Promise<void> {
  const args = parseCollectArgs(process.argv.slice(2));
  const result = await runCollect(args, { transport: networkTransport() });
  process.stdout.write(`${JSON.stringify({ run_id: result.runId, tenant_id: result.tenantId, kind: RUN_KIND, orders: result.orders, sales: result.sales })}\n`);
}

if (process.argv[1] && /[\\/]collect\.(?:ts|js)$/.test(process.argv[1])) {
  main().catch((error: unknown) => {
    process.stderr.write(`collect: ${errorCode(error)}: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  });
}
