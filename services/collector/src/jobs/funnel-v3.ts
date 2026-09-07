#!/usr/bin/env node
/**
 * `funnel_v3` job (Story 3.1): one daily run of the WB sales funnel v3 history
 * for one tenant.
 *
 * Flow: open the run RUNNING (AD-3); active nmIds = distinct nmId of
 * `stg_wb_orders_latest` ordered on the last 30 full Moscow days; request the
 * window `[run_day-6, run_day-1]` in batches of at most 20 nmIds through the
 * single WB client (every response lands in CAS + wb_raw_artifacts before it
 * is parsed, 429 waits on X-Ratelimit-Retry with at most 3 retries); each
 * received batch is parsed, checked for full coverage and committed on its own,
 * so a failed batch never cancels the batches already received (Story 3.1 AC).
 * When every batch is covered, the versions of all observed product-days,
 * their run inputs and SUCCEEDED are one transaction; otherwise the run is
 * marked FAILED with the coverage summary in `notes` and no version exists.
 *
 * Every run re-requests the whole window, so late WB changes become new
 * observations and new versions. The live rate limit is written to the log
 * from the response headers of the first server run (measurement beats the
 * specification, PRD 4.0); the client budget stays 3/min until then.
 *
 * Secrets follow the spine Conventions: the database URI comes from the file
 * named by COLLECTOR_DATABASE_URI_FILE, the WB token from
 * --analytics-token-file. Values are never logged. Live network stays
 * fail-closed unless WB_ALLOW_LIVE_NETWORK=1 (AD-4); tests inject FixtureTransport.
 */
import { Pool, type PoolClient } from 'pg';

import { BusinessSignalRawStore } from '../business-signal/raw-store.js';
import { assertLeastPrivilegeToken, readPrivateSecret } from '../business-signal/secrets.js';
import { versionFunnelDaily, type FunnelProductDay, type VersionFunnelDailyResult } from '../facts/funnel-daily.js';
import { sha256 } from '../intake/manifest.js';
import { WbClient, WbClientError, type Clock } from '../wb/client.js';
import {
  ACTIVE_NM_ID_DAYS,
  assertBatchCoverage,
  batchNmIds,
  FUNNEL_ENDPOINT,
  funnelRequestBody,
  funnelWindow,
  insertFunnelObservations,
  parseFunnelV3,
  shiftDay,
  type FunnelWindow,
} from '../wb/funnel-v3.js';
import { logRunStep } from '../wb/log.js';
import { mskDay, mskToday } from '../wb/msk-day.js';
import { WbArtifactSink } from '../wb/recording-client.js';
import { RunLedger } from '../wb/run-ledger.js';
import { networkTransport, type WbTransport } from '../wb/transport.js';

const RUN_KIND = 'funnel_v3';
const TENANT_ID = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const OPTIONS = ['--tenant', '--analytics-token-file', '--run-day'] as const;
const FLAGS = ['--allow-analytics-read-write'] as const;
type Option = (typeof OPTIONS)[number];

export interface FunnelV3Args {
  tenantId: string;
  analyticsTokenFile: string;
  /** Moscow calendar day the run belongs to; defaults to today in Europe/Moscow. */
  runDay?: string;
  /** PA-13: the server analytics token is still read-write; opt in explicitly, never by default. */
  allowAnalyticsReadWrite: boolean;
}

export interface FunnelV3Deps {
  transport: WbTransport;
  /** Defaults to process.env; reads COLLECTOR_DATABASE_URI_FILE, PROXIMA_RAW_DIR, PROXIMA_GIT_SHA, PROXIMA_IMAGE_ID. */
  env?: NodeJS.ProcessEnv;
  clock?: Clock;
  /** Git tree the CAS root must stay outside of; defaults to process.cwd(). */
  repositoryRoot?: string;
  /** Test hook: learn the run id as soon as the ledger row exists. */
  onRunOpened?: (runId: string) => void;
}

export interface FunnelBatchOutcome {
  readonly batch: number;
  readonly nmIds: number;
  readonly received: number;
  readonly inserted: number;
  readonly skipped: number;
}

export interface FunnelV3Result {
  runId: string;
  tenantId: string;
  window: FunnelWindow;
  activeNmIds: number;
  batches: readonly FunnelBatchOutcome[];
  observations: { received: number; inserted: number; skipped: number };
  facts: VersionFunnelDailyResult;
}

/** The run received some batches but not all of them: no version, FAILED with the summary. */
export class FunnelCoverageError extends Error {
  readonly code = 'FUNNEL_COVERAGE_INCOMPLETE';

  constructor(message: string, readonly notes: string, readonly firstCause: unknown) {
    super(message);
    this.name = 'FunnelCoverageError';
  }
}

export function parseFunnelV3Args(argv: readonly string[]): FunnelV3Args {
  const values: Partial<Record<Option, string>> = {};
  let allowAnalyticsReadWrite = false;
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if ((FLAGS as readonly string[]).includes(key as string)) {
      if (allowAnalyticsReadWrite) throw new Error(`flag ${key} given twice`);
      allowAnalyticsReadWrite = true;
      continue;
    }
    if (!isOption(key)) throw new Error(`unknown option ${String(key)}; expected ${[...OPTIONS, ...FLAGS].join(', ')}`);
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`option ${key} requires a value`);
    if (values[key] !== undefined) throw new Error(`option ${key} given twice`);
    values[key] = value;
    index += 1;
  }
  const tenantId = values['--tenant'];
  const analyticsTokenFile = values['--analytics-token-file'];
  if (!tenantId) throw new Error('required option: --tenant');
  if (!analyticsTokenFile) throw new Error('required option: --analytics-token-file');
  if (!TENANT_ID.test(tenantId)) throw new Error('--tenant must match ^[a-z0-9][a-z0-9_-]{2,63}$');
  const runDay = values['--run-day'];
  if (runDay !== undefined) {
    if (!DAY.test(runDay)) throw new Error('--run-day must be YYYY-MM-DD');
    try {
      shiftDay(runDay, 0);
    } catch {
      throw new Error('--run-day must be a calendar date');
    }
  }
  return { tenantId, analyticsTokenFile, ...(runDay === undefined ? {} : { runDay }), allowAnalyticsReadWrite };
}

function isOption(value: string | undefined): value is Option {
  return value !== undefined && (OPTIONS as readonly string[]).includes(value);
}

/** Stable code for logs and stderr: WbClientError / BusinessSignalError codes pass through. */
function errorCode(error: unknown): string {
  if (error instanceof WbClientError || error instanceof FunnelCoverageError) return error.code;
  const code = (error as { code?: unknown } | null)?.code;
  return typeof code === 'string' && code !== '' ? code : 'FUNNEL_V3_FAILED';
}

/**
 * Batch failures that cannot improve on the next batch stop the run at once;
 * everything else (rate limit exhausted, drift, HTTP failure) lets the run
 * try the remaining batches so the day gets as much coverage as it can.
 */
function isFatal(error: unknown): boolean {
  if (!(error instanceof WbClientError)) return true;
  return error.code === 'WB_AUTH_FAILED' || error.code === 'WB_TOKEN_NOT_CONFIGURED' || error.code === 'CANCELLED';
}

function requiredEnv(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

async function withTenantSession<T>(pool: Pool, tenantId: string, work: (client: PoolClient) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    return await work(client);
  } finally {
    try {
      await client.query('RESET proxima.tenant_id');
      client.release();
    } catch (error) {
      client.release(error as Error);
    }
  }
}

/**
 * Active nmIds: every product with an order observation (`stg_wb_orders_latest`)
 * dated on one of the last 30 full Moscow days before `run_day`. The SQL text
 * comparison on the zoneless WB `date` is a cheap superset; the exact day
 * boundary is `mskDay()` (AD-7), applied here.
 */
export async function activeNmIds(pool: Pool, tenantId: string, runDay: string): Promise<number[]> {
  const floor = shiftDay(runDay, -ACTIVE_NM_ID_DAYS);
  return withTenantSession(pool, tenantId, async (client) => {
    const result = await client.query<{ srid: string; nm_id: unknown; date: unknown }>(
      `SELECT srid, payload->'nmId' AS nm_id, payload->>'date' AS date
       FROM stg_wb_orders_latest
       WHERE tenant_id = $1 AND payload->>'date' >= $2`,
      [tenantId, floor],
    );
    const ids = new Set<number>();
    for (const row of result.rows) {
      if (typeof row.date !== 'string') throw new WbClientError('WB_SCHEMA_DRIFT', `statistics.orders: srid ${row.srid} has no date`, 'statistics.orders');
      const day = mskDay(row.date);
      if (day < floor || day >= runDay) continue;
      if (!Number.isSafeInteger(row.nm_id) || (row.nm_id as number) <= 0) {
        throw new WbClientError('WB_SCHEMA_DRIFT', `statistics.orders: srid ${row.srid} has no positive nmId`, 'statistics.orders');
      }
      ids.add(row.nm_id as number);
    }
    return [...ids].sort((a, b) => a - b);
  });
}

export async function runFunnelV3(args: FunnelV3Args, deps: FunnelV3Deps): Promise<FunnelV3Result> {
  const env = deps.env ?? process.env;
  const { tenantId } = args;
  const now = new Date(deps.clock?.now() ?? Date.now());
  const connectionString = await readPrivateSecret(requiredEnv(env, 'COLLECTOR_DATABASE_URI_FILE'), 'collector database URI file');
  const analyticsToken = await readPrivateSecret(args.analyticsTokenFile, 'WB analytics token file');
  // WB API is READ-only by policy: a multi-category token fails closed here,
  // before any connection or request; read-write is an explicit opt-in (PA-13).
  assertLeastPrivilegeToken(analyticsToken, 'analytics', now, { allowReadWrite: args.allowAnalyticsReadWrite });
  const rawRoot = requiredEnv(env, 'PROXIMA_RAW_DIR');
  const runDay = args.runDay ?? mskToday(now);
  const window = funnelWindow(runDay);
  const pool = new Pool({ connectionString, max: 2, application_name: 'proxima-funnel-v3' });
  try {
    const ledger = new RunLedger(pool);
    const runId = await ledger.open({ tenantId, kind: RUN_KIND, gitSha: env.PROXIMA_GIT_SHA, imageId: env.PROXIMA_IMAGE_ID });
    deps.onRunOpened?.(runId);
    const log = (step: string, msg: string, extra: Record<string, unknown> = {}, level: 'info' | 'warn' | 'error' = 'info'): void =>
      logRunStep({ level, run_id: runId, tenant_id: tenantId, kind: RUN_KIND, step, msg, ...extra });
    try {
      const ids = await activeNmIds(pool, tenantId, runDay);
      const batches = batchNmIds(ids);
      log('window', 'funnel window selected', { run_day: runDay, start: window.start, end: window.end, active_nm_ids: ids.length, batches: batches.length });
      if (ids.length === 0) log('window', 'no active nmId in the last 30 days; nothing to request', { days: ACTIVE_NM_ID_DAYS }, 'warn');

      const rawStore = await BusinessSignalRawStore.open(rawRoot, deps.repositoryRoot ?? process.cwd());
      const sink = new WbArtifactSink(tenantId, runId, rawStore, pool);
      const client = new WbClient(
        { analytics: analyticsToken },
        { transport: deps.transport, artifactSink: sink, ...(deps.clock ? { clock: deps.clock } : {}) },
      );

      const outcomes: FunnelBatchOutcome[] = [];
      const productDays: FunnelProductDay[] = [];
      const failures: { batch: number; nm_ids: number; code: string }[] = [];
      let firstCause: unknown;
      for (const [index, nmIds] of batches.entries()) {
        const batch = index + 1;
        try {
          const record = await client.request(FUNNEL_ENDPOINT, { body: funnelRequestBody(window, nmIds), artifactPageSequence: batch });
          log('ratelimit', 'WB rate limit headers as measured', {
            batch,
            http_status: record.httpStatus,
            limit: record.responseHeaders['x-ratelimit-limit'] ?? null,
            remaining: record.responseHeaders['x-ratelimit-remaining'] ?? null,
          });
          const parsed = parseFunnelV3(record.body, sha256(record.body), window);
          assertBatchCoverage(parsed.rows, nmIds, window);
          const written = await withTenantSession(pool, tenantId, async (session) => {
            await session.query('BEGIN');
            try {
              const result = await insertFunnelObservations(session, tenantId, runId, parsed);
              await session.query('COMMIT');
              return result;
            } catch (error) {
              await session.query('ROLLBACK').catch(() => undefined);
              throw error;
            }
          });
          for (const row of parsed.rows) productDays.push({ nmId: row.nmId, calendarDay: row.calendarDay });
          outcomes.push({ batch, nmIds: nmIds.length, received: written.received, inserted: written.inserted, skipped: written.skipped });
          log('batch', 'observations committed', { batch, batches_total: batches.length, nm_ids: nmIds.length, received: written.received, inserted: written.inserted, skipped: written.skipped });
        } catch (error) {
          firstCause ??= error;
          failures.push({ batch, nm_ids: nmIds.length, code: errorCode(error) });
          log('batch', 'batch failed; received batches stay committed', { batch, batches_total: batches.length, nm_ids: nmIds.length, code: errorCode(error) }, 'error');
          if (isFatal(error)) break;
        }
      }

      if (failures.length > 0) {
        const uncovered = batches.length - outcomes.length;
        const summary = { coverage: 'incomplete', batches_total: batches.length, batches_succeeded: outcomes.length, batches_uncovered: uncovered, failures };
        throw new FunnelCoverageError(
          `funnel_v3: ${uncovered} of ${batches.length} batches not covered (first failure: ${errorCode(firstCause)})`,
          JSON.stringify(summary),
          firstCause,
        );
      }

      let facts: VersionFunnelDailyResult | undefined;
      await ledger.succeed(tenantId, runId, async (session) => {
        facts = await versionFunnelDaily(session, { tenantId, runId, productDays });
      });
      if (facts === undefined) throw new Error('funnel_v3: versions were not written inside the run transaction');
      const observations = outcomes.reduce(
        (sum, outcome) => ({ received: sum.received + outcome.received, inserted: sum.inserted + outcome.inserted, skipped: sum.skipped + outcome.skipped }),
        { received: 0, inserted: 0, skipped: 0 },
      );
      log('facts', 'versions committed with SUCCEEDED', { versions: facts.versions, input_runs: facts.inputRuns, ...observations });
      return { runId, tenantId, window, activeNmIds: ids.length, batches: outcomes, observations, facts };
    } catch (error) {
      log('failed', 'run failed; marking FAILED', { code: errorCode(error) }, 'error');
      // If the FAILED flip itself fails the run stays RUNNING; the original
      // error still surfaces and Story 1.7's run tooling reconciles the ledger.
      await ledger.fail(tenantId, runId, error instanceof FunnelCoverageError ? error.notes : undefined).catch((failError: unknown) => {
        const detail = failError instanceof Error ? failError.message : String(failError);
        log('failed', 'could not mark run FAILED', { detail }, 'error');
      });
      throw error;
    }
  } finally {
    await pool.end();
  }
}

async function main(): Promise<void> {
  const args = parseFunnelV3Args(process.argv.slice(2));
  const result = await runFunnelV3(args, { transport: networkTransport() });
  process.stdout.write(`${JSON.stringify({ run_id: result.runId, tenant_id: result.tenantId, kind: RUN_KIND, window: result.window, active_nm_ids: result.activeNmIds, batches: result.batches.length, observations: result.observations, facts: result.facts })}\n`);
}

if (process.argv[1] && /[\\/]funnel-v3\.(?:ts|js)$/.test(process.argv[1])) {
  main().catch((error: unknown) => {
    process.stderr.write(`funnel-v3: ${errorCode(error)}: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  });
}
