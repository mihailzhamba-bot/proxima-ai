// Story 3.1 db-tests: the funnel_v3 job end to end on the disposable
// PostgreSQL 16 of tools/pg_local_roundtrip.sh, through the production LOGIN
// roles (no SET ROLE, no superuser for the job). Without the harness env the
// file skips. The fixture is the 30.08 answer for 3 nmIds x 2026-08-24..30.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { Client } from 'pg';

import { FunnelCoverageError, runFunnelV3, type FunnelV3Result } from '../src/jobs/funnel-v3.js';
import type { Clock } from '../src/wb/client.js';
import { DEFAULT_FIXTURE_ROOT, FixtureTransport, type FixtureScript } from '../src/wb/fixture-transport.js';
import { windowDays, funnelWindow } from '../src/wb/funnel-v3.js';
import type { WbTransport } from '../src/wb/transport.js';

const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const normDsn = process.env.PROXIMA_TEST_DSN_NORM ?? '';
const webappDsn = process.env.PROXIMA_TEST_DSN_WEBAPP ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const ready = collectorDsn !== '' && normDsn !== '' && webappDsn !== '' && postgresDsn !== '';
const skip = ready ? false : 'PROXIMA_TEST_DSN_COLLECTOR, PROXIMA_TEST_DSN_NORM, PROXIMA_TEST_DSN_WEBAPP and PROXIMA_TEST_POSTGRES_DSN must be set (run via tools/pg_local_roundtrip.sh)';
/** Own tenant: the roundtrip database is shared by every *.db.test.ts file. */
const tenantId = 'funnel-harness';
const RUN_DAY = '2026-08-31';
const FIXTURE_NM_IDS = [12345001, 12345002, 12345003];
const FIXTURE_OBSERVATIONS = 21;

/** Structural read-only WB analytics JWT (category bit 2 + read-only bit 30), no real claims. */
function readOnlyAnalyticsJwt(): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ s: (1 << 30) | (1 << 2), exp: 2_000_000_000 })).toString('base64url');
  return `${header}.${payload}.fixture-signature`;
}

async function withAdmin<T>(work: (client: Client) => Promise<T>): Promise<T> {
  const client = new Client({ connectionString: postgresDsn });
  await client.connect();
  try { return await work(client); }
  finally { await client.end(); }
}

interface Harness {
  db: Client;
  /** Runs `funnel_v3` through the private-file contract and remembers the run for cleanup. */
  run(transport: WbTransport, runDay?: string, clock?: Clock): Promise<FunnelV3Result>;
  /** Id of the most recently opened run, including one that failed. */
  lastRunId(): string;
  count(table: string, where: string, values?: unknown[]): Promise<number>;
  run_(runId: string): Promise<{ status: string; notes: string | null }>;
  cleanup(): Promise<void>;
}

/**
 * Seeds the active-nmId source: one SUCCEEDED `collect` run with an order
 * observation per nmId inside the 30-day window, plus one nmId ordered too
 * long ago and one ordered on the run day itself - both must stay inactive.
 */
async function openHarness(activeNmIds: readonly number[]): Promise<Harness> {
  const seedRun = randomUUID();
  await withAdmin(async (client) => {
    await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]);
    await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    await client.query("INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES ($1, $2, 'collect', 'SUCCEEDED', CURRENT_TIMESTAMP)", [seedRun, tenantId]);
    const orders = [
      ...activeNmIds.map((nmId) => ({ nmId, date: '2026-08-20T10:00:00' })),
      { nmId: 12345098, date: '2026-07-15T10:00:00' },
      { nmId: 12345099, date: '2026-08-31T05:00:00' },
    ];
    for (const order of orders) {
      const srid = `funnel-harness-${order.nmId}`;
      await client.query(
        `INSERT INTO stg_wb_orders_obs (tenant_id, srid, last_change_at, run_id, content_sha256, canonical_sha256, payload)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [tenantId, srid, `${order.date}+03:00`, seedRun, 'a'.repeat(64), 'b'.repeat(64), JSON.stringify({ srid, nmId: order.nmId, date: order.date, isCancel: false })],
      );
    }
  });
  const secrets = await mkdtemp(join(tmpdir(), 'proxima-funnel-secrets-'));
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-funnel-raw-'));
  const uriFile = join(secrets, 'proxima_collector_uri');
  const tokenFile = join(secrets, 'funnel-harness_wb_analytics_token');
  await writeFile(uriFile, `${collectorDsn}\n`, { mode: 0o600 });
  await writeFile(tokenFile, `${readOnlyAnalyticsJwt()}\n`, { mode: 0o600 });
  const env: NodeJS.ProcessEnv = { COLLECTOR_DATABASE_URI_FILE: uriFile, PROXIMA_RAW_DIR: rawRoot };
  const runIds: string[] = [seedRun];
  const db = new Client({ connectionString: collectorDsn });
  await db.connect();
  await db.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
  return {
    db,
    run: (transport, runDay = RUN_DAY, clock) => runFunnelV3(
      { tenantId, analyticsTokenFile: tokenFile, runDay, allowAnalyticsReadWrite: false },
      { transport, env, ...(clock ? { clock } : {}), onRunOpened: (runId) => { runIds.push(runId); } },
    ),
    lastRunId() {
      const runId = runIds[runIds.length - 1];
      assert.ok(runId, 'no run was opened');
      return runId;
    },
    async count(table, where, values = []) {
      const result = await db.query<{ n: string }>(`SELECT count(*) AS n FROM ${table} WHERE ${where}`, values);
      return Number(result.rows[0]?.n);
    },
    async run_(runId) {
      const result = await db.query<{ status: string; notes: string | null }>('SELECT status, notes FROM collector_runs WHERE run_id = $1', [runId]);
      assert.ok(result.rows[0], `run ${runId} is visible to its tenant`);
      return result.rows[0];
    },
    async cleanup() {
      await db.end();
      // Deleting a run cascades its observations, versions and artifacts; the
      // input edges (ON DELETE RESTRICT) go first, like the other harnesses.
      await withAdmin(async (client) => {
        await client.query('DELETE FROM collector_run_inputs WHERE run_id = ANY($1::uuid[]) OR input_run_id = ANY($1::uuid[])', [runIds]);
        await client.query('DELETE FROM collector_runs WHERE run_id = ANY($1::uuid[])', [runIds]);
      });
      await rm(secrets, { recursive: true, force: true });
      await rm(rawRoot, { recursive: true, force: true });
    },
  };
}

type FixtureProduct = { product: { nmId: number }; history: Record<string, unknown>[]; currency: string };

async function fixture(): Promise<FixtureProduct[]> {
  return JSON.parse(await readFile(join(DEFAULT_FIXTURE_ROOT, 'analytics/sales_funnel_v3_history/sample.json'), 'utf8')) as FixtureProduct[];
}

function scripted(...scripts: FixtureScript[]): FixtureTransport {
  return new FixtureTransport({ scripts: { 'analytics.sales_funnel_v3_history': scripts } });
}

function okScript(body: unknown): FixtureScript {
  return { status: 200, body: JSON.stringify(body), headers: { 'content-type': 'application/json', 'x-ratelimit-limit': '3', 'x-ratelimit-remaining': '2' } };
}

/** Structural zero-valued history for nmIds the fixture does not know (partial-coverage drill). */
function zeroHistory(nmIds: readonly number[], days: readonly string[]): FixtureProduct[] {
  return nmIds.map((nmId) => ({
    product: { nmId, title: `title-${nmId}`, vendorCode: `sku-${nmId}`, brandName: 'brand-1', subjectId: 9001, subjectName: 'subject-1' },
    history: days.map((date) => ({ date, openCount: 0, cartCount: 0, orderCount: 0, orderSum: 0, buyoutCount: 0, buyoutSum: 0, buyoutPercent: 0, addToCartConversion: 0, cartToOrderConversion: 0, addToWishlistCount: 0 })),
    currency: 'RUB',
  }));
}

async function countAs(dsn: string, sql: string, withGuc: boolean): Promise<number> {
  const client = new Client({ connectionString: dsn });
  await client.connect();
  try {
    if (withGuc) await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    const result = await client.query<{ n: string }>(sql);
    return Number(result.rows[0]?.n);
  } finally {
    await client.end();
  }
}

test('funnel_v3: 21 observations and 21 current rows, replay 0, changed payload versions, run_day not versioned', { skip }, async () => {
  const h = await openHarness(FIXTURE_NM_IDS);
  try {
    const transport = new FixtureTransport();
    const first = await h.run(transport.transport);
    assert.equal((await h.run_(first.runId)).status, 'SUCCEEDED');
    assert.deepEqual(first.window, { runDay: RUN_DAY, start: '2026-08-25', end: '2026-08-30' });
    assert.equal(first.activeNmIds, 3, 'stale and run-day orders do not make an nmId active');
    assert.deepEqual(first.batches, [{ batch: 1, nmIds: 3, received: FIXTURE_OBSERVATIONS, inserted: FIXTURE_OBSERVATIONS, skipped: 0 }]);
    assert.deepEqual(first.facts, { versions: FIXTURE_OBSERVATIONS, inputRuns: 0 });
    const request = transport.recordedRequests()[0];
    assert.deepEqual(request?.body, { selectedPeriod: { start: '2026-08-25', end: '2026-08-31' }, nmIds: FIXTURE_NM_IDS, aggregationLevel: 'day' });
    assert.equal(await h.count('stg_wb_funnel_obs', "run_id = $1 AND source = 'v3'", [first.runId]), FIXTURE_OBSERVATIONS);
    assert.equal(await h.count('fact_funnel_daily', 'run_id = $1', [first.runId]), FIXTURE_OBSERVATIONS);
    assert.equal(await h.count('fact_funnel_daily_current', 'run_id = $1', [first.runId]), FIXTURE_OBSERVATIONS);
    assert.equal(await h.count('wb_raw_artifacts', 'run_id = $1', [first.runId]), 1, 'the response is evidence of the run');
    const evidence = await h.db.query<{ n: string }>(
      'SELECT count(*) AS n FROM stg_wb_funnel_obs o JOIN wb_raw_artifacts a ON a.content_sha256 = o.evidence_sha256 AND a.run_id = o.run_id WHERE o.run_id = $1',
      [first.runId],
    );
    assert.equal(evidence.rows[0]?.n, String(FIXTURE_OBSERVATIONS), 'every observation points at the recorded artifact');
    const artifact = await h.db.query<{ content_sha256: string }>('SELECT content_sha256 FROM wb_raw_artifacts WHERE run_id = $1', [first.runId]);
    const sample = await h.db.query<{ open_card: number; orders_sum_rub: string; canonical_sha256: string; evidence_sha256: string }>(
      "SELECT open_card, orders_sum_rub, canonical_sha256, evidence_sha256 FROM fact_funnel_daily_current WHERE nm_id = 12345001 AND calendar_day = DATE '2026-08-24'",
    );
    assert.deepEqual(sample.rows[0], {
      open_card: 271,
      orders_sum_rub: '2375.52',
      canonical_sha256: '6bc1aa356e207f20df1958aeb5d0930599f6c10025ab19869f785114870abb71',
      evidence_sha256: artifact.rows[0]?.content_sha256,
    });

    // replay: the same window again is a new run with 0 new observations and a fresh set of versions
    const replay = await h.run(new FixtureTransport().transport);
    assert.notEqual(replay.runId, first.runId);
    assert.equal((await h.run_(replay.runId)).status, 'SUCCEEDED');
    assert.deepEqual(replay.observations, { received: FIXTURE_OBSERVATIONS, inserted: 0, skipped: FIXTURE_OBSERVATIONS });
    assert.deepEqual(replay.facts, { versions: FIXTURE_OBSERVATIONS, inputRuns: 1 });
    assert.equal(await h.count('stg_wb_funnel_obs', 'run_id = $1', [replay.runId]), 0);
    assert.equal(await h.count('stg_wb_funnel_obs', 'run_id = $1', [first.runId]), FIXTURE_OBSERVATIONS, 'the first run keeps its observations');
    assert.equal(await h.count('stg_wb_funnel_obs', 'tenant_id = $1', [tenantId]), FIXTURE_OBSERVATIONS);
    assert.equal(await h.count('fact_funnel_daily_current', 'run_id = $1', [replay.runId]), FIXTURE_OBSERVATIONS, '_current follows the latest SUCCEEDED run');
    assert.equal(await h.count('collector_run_inputs', 'run_id = $1 AND input_run_id = $2', [replay.runId, first.runId]), 1, 'the replay versions rest on the first run\'s evidence');

    // late change: the same product-day with another payload is a new observation and a new version
    const changed = await fixture();
    const target = changed[0]!.history[6]!;
    assert.equal(target.date, '2026-08-30');
    changed[0]!.history[6] = { ...target, openCount: (target.openCount as number) + 1 };
    const late = await h.run(scripted(okScript(changed)).transport);
    assert.equal((await h.run_(late.runId)).status, 'SUCCEEDED');
    assert.deepEqual(late.observations, { received: FIXTURE_OBSERVATIONS, inserted: 1, skipped: FIXTURE_OBSERVATIONS - 1 });
    assert.equal(await h.count('stg_wb_funnel_obs', "nm_id = 12345001 AND calendar_day = DATE '2026-08-30'"), 2, 'both observations of the product-day are kept');
    const latest = await h.db.query<{ run_id: string; open_card: number }>("SELECT run_id, open_card FROM stg_wb_funnel_latest WHERE nm_id = 12345001 AND calendar_day = DATE '2026-08-30'");
    assert.deepEqual(latest.rows, [{ run_id: late.runId, open_card: (target.openCount as number) + 1 }]);
    const current = await h.db.query<{ run_id: string; open_card: number }>("SELECT run_id, open_card FROM fact_funnel_daily_current WHERE nm_id = 12345001 AND calendar_day = DATE '2026-08-30'");
    assert.deepEqual(current.rows, [{ run_id: late.runId, open_card: (target.openCount as number) + 1 }]);
    assert.equal(await h.count('fact_funnel_daily_current', 'run_id = $1', [late.runId]), FIXTURE_OBSERVATIONS);
    assert.equal(await h.count('collector_run_inputs', 'run_id = $1', [late.runId]), 1, 'unchanged product-days still rest on the first run');

    // run_day is observed but never versioned.
    const closing = await h.run(new FixtureTransport().transport, '2026-08-30');
    assert.equal((await h.run_(closing.runId)).status, 'SUCCEEDED');
    assert.deepEqual(closing.window, { runDay: '2026-08-30', start: '2026-08-24', end: '2026-08-30' });
    assert.deepEqual(closing.observations, { received: FIXTURE_OBSERVATIONS, inserted: 0, skipped: FIXTURE_OBSERVATIONS });
    assert.equal(closing.facts.versions, 18);
    assert.equal(await h.count('fact_funnel_daily', "run_id = $1 AND calendar_day = DATE '2026-08-30'", [closing.runId]), 0);
    assert.equal(await h.count('fact_funnel_daily_current', "calendar_day = DATE '2026-08-30' AND run_id = $1", [late.runId]), 3, 'the 08-30 versions stay with the run that observed them');

    // RLS matrix (AD-11): norm reads the facts of its tenant only; the webapp has no grant.
    assert.equal(await countAs(normDsn, 'SELECT count(*) AS n FROM fact_funnel_daily_current', true), FIXTURE_OBSERVATIONS);
    assert.equal(await countAs(normDsn, 'SELECT count(*) AS n FROM fact_funnel_daily_current', false), 0, 'without the tenant GUC the view is empty');
    await assert.rejects(() => countAs(normDsn, 'SELECT count(*) AS n FROM stg_wb_funnel_obs', true), /permission denied/);
    await assert.rejects(() => countAs(webappDsn, 'SELECT count(*) AS n FROM fact_funnel_daily_current', true), /permission denied/);
    await withAdmin(async (client) => {
      await client.query("SELECT set_config('proxima.tenant_id', $1, false)", ['funnel-other']);
      await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', ['funnel-other']);
    });
    await h.db.query("SELECT set_config('proxima.tenant_id', $1, false)", ['funnel-other']);
    assert.equal(await h.count('fact_funnel_daily_current', 'true'), 0, 'another tenant sees nothing');
    await h.db.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
  } finally {
    await h.cleanup();
  }
});

test('funnel_v3: a failed batch keeps the received batches committed, no version, FAILED with the coverage summary', { skip }, async () => {
  const nmIds = Array.from({ length: 21 }, (_, index) => 12345001 + index);
  const h = await openHarness(nmIds);
  try {
    let now = Date.parse('2026-08-31T03:15:00Z');
    const clock: Clock = { now: () => now, sleep: async (milliseconds) => { now += milliseconds; } };
    const days = windowDays(funnelWindow(RUN_DAY));
    const limited: FixtureScript = { status: 429, headers: { 'x-ratelimit-retry': '20' }, body: '{}' };
    const transport = scripted(okScript(zeroHistory(nmIds.slice(0, 20), days)), limited, limited, limited, limited);
    await assert.rejects(
      () => h.run(transport.transport, RUN_DAY, clock),
      (error: unknown) => error instanceof FunnelCoverageError && error.code === 'FUNNEL_COVERAGE_INCOMPLETE',
    );
    const runId = h.lastRunId();
    const run = await h.run_(runId);
    assert.equal(run.status, 'FAILED');
    const notes = JSON.parse(run.notes ?? '{}') as { coverage: string; batches_total: number; batches_succeeded: number; failures: { batch: number; code: string }[] };
    assert.equal(notes.coverage, 'incomplete');
    assert.equal(notes.batches_total, 2);
    assert.equal(notes.batches_succeeded, 1);
    assert.deepEqual(notes.failures, [{ batch: 2, nm_ids: 1, code: 'WB_RATE_LIMIT_EXHAUSTED' }]);
    assert.equal(transport.recordedRequests().length, 5, 'first batch, then one call plus three retries');
    assert.equal(await h.count('stg_wb_funnel_obs', 'run_id = $1', [runId]), 20 * days.length, 'the received batch stays committed');
    assert.equal(await h.count('fact_funnel_daily', 'run_id = $1', [runId]), 0, 'an uncovered day has no version');
    assert.equal(await h.count('wb_raw_artifacts', 'run_id = $1', [runId]), 5, 'every response, 429s included, is evidence');
    assert.equal(await h.count('fact_funnel_daily_current', 'true'), 0);

    // the next run covers the whole window: yesterday's observations are replayed, the day gets its versions
    const recovered = await h.run(scripted(okScript(zeroHistory(nmIds.slice(0, 20), days)), okScript(zeroHistory(nmIds.slice(20), days))).transport, RUN_DAY, clock);
    assert.equal((await h.run_(recovered.runId)).status, 'SUCCEEDED');
    assert.deepEqual(recovered.observations, { received: 21 * days.length, inserted: days.length, skipped: 20 * days.length });
    assert.deepEqual(recovered.facts, { versions: 21 * days.length, inputRuns: 1 });
    assert.equal(await h.count('collector_run_inputs', 'run_id = $1 AND input_run_id = $2', [recovered.runId, runId]), 1, 'the failed run is evidence the recovered versions depend on');
    assert.equal(await h.count('fact_funnel_daily_current', 'run_id = $1', [recovered.runId]), 21 * days.length);
  } finally {
    await h.cleanup();
  }
});
