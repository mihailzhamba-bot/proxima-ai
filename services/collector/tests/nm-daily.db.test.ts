// Story 4.0 db-tests (AD-19): the collect run on the 30.08 fixtures versions
// fact_nm_daily and dim_nm_subject on the disposable PostgreSQL 16 of
// tools/pg_local_roundtrip.sh, through the production LOGIN roles (no SET
// ROLE, no superuser for the job). One row per (day, nmId) with a category,
// per-nm sums equal to fact_cabinet_daily_current, replay, transitive removal
// through the real tools/delete_run.py, and the RLS matrix of AD-11/AD-12.
// Without the harness env the file skips.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { Client } from 'pg';

import { checkPerNmSumsVsCabinet } from '../src/facts/nm-daily.js';
import { runCollect, type CollectResult } from '../src/jobs/collect.js';
import type { Clock } from '../src/wb/client.js';
import { FixtureTransport } from '../src/wb/fixture-transport.js';

const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const normDsn = process.env.PROXIMA_TEST_DSN_NORM ?? '';
const webappDsn = process.env.PROXIMA_TEST_DSN_WEBAPP ?? '';
const janitorDsn = process.env.PROXIMA_TEST_DSN_JANITOR ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const ready = collectorDsn !== '' && normDsn !== '' && webappDsn !== '' && janitorDsn !== '' && postgresDsn !== '';
const skip = ready ? false : 'PROXIMA_TEST_DSN_COLLECTOR, _NORM, _WEBAPP, _JANITOR and PROXIMA_TEST_POSTGRES_DSN must be set (run via tools/pg_local_roundtrip.sh)';
/** Own tenant: the roundtrip database is shared by every *.db.test.ts file. */
const tenantId = 'nm-daily-harness';
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
/** Fixtures cover 2026-08-17..30; a run on 08-31 versions 14 days (AD-2: `= run_day` is never versioned). */
const RUN_INSTANT = Date.parse('2026-08-31T03:00:00Z');
const FIXTURE_DAYS = 14;
const FIXTURE_NM_IDS = 97;

/** Structural read-only WB statistics JWT (category bit 5 + read-only bit 30), no real claims. */
function readOnlyStatisticsJwt(): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ s: (1 << 30) | (1 << 5), exp: 2_000_000_000 })).toString('base64url');
  return `${header}.${payload}.fixture-signature`;
}

/** Virtual clock: the run day is fixed and the client's budget sleeps advance it instead of waiting. */
function virtualClock(): Clock {
  let now = RUN_INSTANT;
  return { now: () => now, sleep: async (milliseconds) => { now += milliseconds; } };
}

async function withAdmin<T>(work: (client: Client) => Promise<T>): Promise<T> {
  const client = new Client({ connectionString: postgresDsn });
  await client.connect();
  try {
    await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    return await work(client);
  } finally { await client.end(); }
}

async function countAs(dsn: string, sql: string, withGuc: boolean, values: unknown[] = []): Promise<number> {
  const client = new Client({ connectionString: dsn });
  await client.connect();
  try {
    if (withGuc) await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    const result = await client.query<{ n: string }>(sql, values);
    return Number(result.rows[0]?.n);
  } finally { await client.end(); }
}

interface Harness {
  collect(): Promise<CollectResult>;
  count(table: string, runId: string): Promise<number>;
  cleanup(): Promise<void>;
}

/** The job reads its DSN and token only through private files, like production; each test deletes its own runs. */
async function openHarness(): Promise<Harness> {
  await withAdmin((client) => client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]));
  const secrets = await mkdtemp(join(tmpdir(), 'proxima-nm-daily-secrets-'));
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-nm-daily-raw-'));
  const uriFile = join(secrets, 'proxima_collector_uri');
  const tokenFile = join(secrets, 'nm-daily-harness_wb_statistics_token');
  await writeFile(uriFile, `${collectorDsn}\n`, { mode: 0o600 });
  await writeFile(tokenFile, `${readOnlyStatisticsJwt()}\n`, { mode: 0o600 });
  const env: NodeJS.ProcessEnv = { COLLECTOR_DATABASE_URI_FILE: uriFile, PROXIMA_RAW_DIR: rawRoot };
  const runIds: string[] = [];
  return {
    collect: () => runCollect(
      { tenantId, dateFrom: '2026-08-17', statisticsTokenFile: tokenFile },
      { transport: new FixtureTransport().transport, env, clock: virtualClock(), onRunOpened: (runId) => { runIds.push(runId); } },
    ),
    count: (table, runId) => withAdmin(async (client) => Number((await client.query<{ n: string }>(`SELECT count(*) AS n FROM ${table} WHERE run_id = $1`, [runId])).rows[0]?.n)),
    async cleanup() {
      await withAdmin(async (client) => {
        await client.query('DELETE FROM collector_run_inputs WHERE run_id = ANY($1::uuid[]) OR input_run_id = ANY($1::uuid[])', [runIds]);
        await client.query('DELETE FROM collector_runs WHERE run_id = ANY($1::uuid[])', [runIds]);
      });
      await rm(secrets, { recursive: true, force: true });
      await rm(rawRoot, { recursive: true, force: true });
    },
  };
}

/** Private-file contract of production: the tool receives its DSN only via a 0600 URI file (see delete-run.db.test.ts). */
async function runDeleteTool(runId: string, dryRun: boolean): Promise<{ status: number; stdout: string; stderr: string }> {
  const secrets = await mkdtemp(join(tmpdir(), 'proxima-nm-daily-janitor-'));
  const uriFile = join(secrets, 'proxima_janitor_uri');
  await writeFile(uriFile, `${janitorDsn}\n`, { mode: 0o600 });
  const python = process.env.PROXIMA_TEST_PYTHON ?? 'python3';
  try {
    const argv = [join(repoRoot, 'tools', 'delete_run.py'), '--tenant', tenantId, '--run', runId, ...(dryRun ? ['--dry-run'] : [])];
    try {
      return { status: 0, stdout: execFileSync(python, argv, { env: { ...process.env, JANITOR_DATABASE_URI_FILE: uriFile }, encoding: 'utf8', cwd: repoRoot }), stderr: '' };
    } catch (error) {
      const failure = error as { status?: number; stdout?: string; stderr?: string };
      return { status: failure.status ?? 1, stdout: failure.stdout ?? '', stderr: failure.stderr ?? '' };
    }
  } finally {
    await rm(secrets, { recursive: true, force: true });
  }
}

test('nm-daily: collect on the 30.08 fixtures - one row per (day, nmId) with a category, per-nm sums equal the cabinet day', { skip }, async () => {
  const h = await openHarness();
  try {
    const first = await h.collect();
    assert.equal(await countAs(collectorDsn, 'SELECT count(*) AS n FROM collector_runs WHERE run_id = $1 AND status = $2', true, [first.runId, 'SUCCEEDED']), 1);
    assert.deepEqual({ subjects: first.nmDaily.subjects, rows: first.nmDaily.rows, days: first.nmDaily.days }, { subjects: FIXTURE_NM_IDS, rows: FIXTURE_DAYS * FIXTURE_NM_IDS, days: FIXTURE_DAYS });
    assert.equal(first.aggregate.days, FIXTURE_DAYS);
    assert.deepEqual(first.nmDaily.check, { check: 'per_nm_sums_vs_cabinet', status: 'PASS', days_checked: FIXTURE_DAYS, mismatches: [] }, 'the run-scoped check of the job passed');
    assert.equal(await h.count('dim_nm_subject', first.runId), FIXTURE_NM_IDS);
    assert.equal(await h.count('fact_nm_daily', first.runId), FIXTURE_DAYS * FIXTURE_NM_IDS);
    await withAdmin(async (client) => {
      // AC: fact_nm_daily_current holds a row per (day, nmId) with a category.
      const current = await client.query<{ rows: number; keys: number; with_subject: number; zero_rows: number }>(
        `SELECT count(*)::int AS rows,
                count(DISTINCT (f.calendar_day, f.nm_id))::int AS keys,
                count(d.subject_name)::int AS with_subject,
                count(*) FILTER (WHERE f.orders_count = 0 AND f.cancelled_count = 0 AND f.sales_count = 0 AND f.returns_count = 0)::int AS zero_rows
         FROM fact_nm_daily_current f
         LEFT JOIN dim_nm_subject_current d ON d.tenant_id = f.tenant_id AND d.nm_id = f.nm_id AND d.subject_name <> ''
         WHERE f.tenant_id = $1`,
        [tenantId],
      );
      assert.deepEqual({ rows: current.rows[0]?.rows, keys: current.rows[0]?.keys, with_subject: current.rows[0]?.with_subject }, { rows: FIXTURE_DAYS * FIXTURE_NM_IDS, keys: FIXTURE_DAYS * FIXTURE_NM_IDS, with_subject: FIXTURE_DAYS * FIXTURE_NM_IDS });
      assert.ok((current.rows[0]?.zero_rows ?? 0) > 0, 'zero rows exist for (day, nmId) cells without observations');
      const range = await client.query<{ first_day: string; last_day: string }>('SELECT min(calendar_day)::text AS first_day, max(calendar_day)::text AS last_day FROM fact_nm_daily_current WHERE tenant_id = $1', [tenantId]);
      assert.deepEqual(range.rows[0], { first_day: '2026-08-17', last_day: '2026-08-30' }, 'the run day 2026-08-31 is not versioned');
      // A zero row carries the run's artifacts as evidence, like a zero cabinet day.
      const zeroEvidence = await client.query<{ n: string }>(
        `SELECT count(*) AS n FROM fact_nm_daily f
         WHERE f.tenant_id = $1 AND f.run_id = $2 AND f.orders_count = 0 AND f.cancelled_count = 0 AND f.sales_count = 0 AND f.returns_count = 0
           AND f.evidence_sha256 <> (SELECT array_agg(content_sha256::char(64) ORDER BY content_sha256) FROM wb_raw_artifacts a WHERE a.tenant_id = $1 AND a.run_id = $2)`,
        [tenantId, first.runId],
      );
      assert.equal(Number(zeroEvidence.rows[0]?.n), 0);
      // AC: the per-nmId sum of orders per day equals fact_cabinet_daily_current.orders_count.
      const orders = await client.query<{ days: number; equal: number }>(
        `SELECT count(*)::int AS days, count(*) FILTER (WHERE c.orders_count = n.orders)::int AS equal
         FROM fact_cabinet_daily_current c
         JOIN (SELECT calendar_day, sum(orders_count) AS orders FROM fact_nm_daily_current WHERE tenant_id = $1 GROUP BY calendar_day) n ON n.calendar_day = c.calendar_day
         WHERE c.tenant_id = $1`,
        [tenantId],
      );
      assert.deepEqual(orders.rows[0], { days: FIXTURE_DAYS, equal: FIXTURE_DAYS });
      // The same SQL as the job's check, over the _current views (AD-19): all six columns, every day.
      assert.deepEqual(await checkPerNmSumsVsCabinet(client, { tenantId }), { check: 'per_nm_sums_vs_cabinet', status: 'PASS', days_checked: FIXTURE_DAYS, mismatches: [] });
      // A foreign row makes the check report the day and the column without touching the run.
      await client.query(
        `INSERT INTO fact_nm_daily (tenant_id, calendar_day, nm_id, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256)
         VALUES ($1, '2026-08-20', 999999999, $2, 1, 0, 0, 0, 0.00, 0.00, ARRAY[]::char(64)[])`,
        [tenantId, first.runId],
      );
      const cabinet = await client.query<{ orders: string }>('SELECT orders_count::text AS orders FROM fact_cabinet_daily WHERE tenant_id = $1 AND run_id = $2 AND calendar_day = $3', [tenantId, first.runId, '2026-08-20']);
      const mismatch = await checkPerNmSumsVsCabinet(client, { tenantId, runId: first.runId });
      assert.deepEqual(mismatch, { check: 'per_nm_sums_vs_cabinet', status: 'MISMATCH', days_checked: FIXTURE_DAYS, mismatches: [{ calendar_day: '2026-08-20', column: 'orders_count', cabinet: cabinet.rows[0]?.orders, per_nm_sum: String(Number(cabinet.rows[0]?.orders) + 1) }] });
      await client.query('DELETE FROM fact_nm_daily WHERE tenant_id = $1 AND run_id = $2 AND nm_id = 999999999', [tenantId, first.runId]);
      assert.equal(await countAs(collectorDsn, 'SELECT count(*) AS n FROM collector_runs WHERE run_id = $1 AND status = $2', true, [first.runId, 'SUCCEEDED']), 1, 'a MISMATCH never changes the run status');
    });
  } finally { await h.cleanup(); }
});

test('nm-daily: replay versions again and _current moves to the latest run; delete_run removes both tables transitively', { skip }, async () => {
  const h = await openHarness();
  try {
    const first = await h.collect();
    const replay = await h.collect();
    assert.notEqual(replay.runId, first.runId);
    assert.deepEqual({ orders: replay.orders.inserted, sales: replay.sales.inserted }, { orders: 0, sales: 0 }, 'a replay adds no observations');
    assert.deepEqual({ subjects: replay.nmDaily.subjects, rows: replay.nmDaily.rows, status: replay.nmDaily.check.status }, { subjects: FIXTURE_NM_IDS, rows: FIXTURE_DAYS * FIXTURE_NM_IDS, status: 'PASS' }, 'but versions every day x nmId again');
    assert.equal(await h.count('fact_nm_daily', first.runId), FIXTURE_DAYS * FIXTURE_NM_IDS, 'the first run keeps its versions');
    assert.equal(await h.count('fact_nm_daily', replay.runId), FIXTURE_DAYS * FIXTURE_NM_IDS);
    await withAdmin(async (client) => {
      const current = await client.query<{ facts: string; subjects: string }>(
        'SELECT (SELECT count(DISTINCT run_id) FROM fact_nm_daily_current WHERE tenant_id = $1) AS facts, (SELECT count(DISTINCT run_id) FROM dim_nm_subject_current WHERE tenant_id = $1) AS subjects',
        [tenantId],
      );
      assert.deepEqual(current.rows[0], { facts: '1', subjects: '1' }, '_current is one run per key');
      const owner = await client.query<{ run_id: string }>('SELECT DISTINCT run_id::text FROM fact_nm_daily_current WHERE tenant_id = $1 UNION SELECT DISTINCT run_id::text FROM dim_nm_subject_current WHERE tenant_id = $1', [tenantId]);
      assert.deepEqual(owner.rows.map((row) => row.run_id), [replay.runId], '_current follows the latest SUCCEEDED run (AD-3)');
      const inputs = await client.query<{ input_run_id: string }>('SELECT input_run_id::text FROM collector_run_inputs WHERE tenant_id = $1 AND run_id = $2', [tenantId, replay.runId]);
      assert.deepEqual(inputs.rows.map((row) => row.input_run_id), [first.runId], 'collector_run_inputs is written once by the cabinet aggregator');
      // A run is a version: JOIN ... USING (tenant_id, nm_id, run_id) yields the subject each run saw.
      const perRun = await client.query<{ n: string }>('SELECT count(*) AS n FROM fact_nm_daily f JOIN dim_nm_subject d USING (tenant_id, nm_id, run_id) WHERE f.tenant_id = $1', [tenantId]);
      assert.equal(Number(perRun.rows[0]?.n), 2 * FIXTURE_DAYS * FIXTURE_NM_IDS);
    });
    // Story 1.7 tool, unchanged: CASCADE from collector_runs takes both tables; the closure from
    // the first run reaches the replay that consumed it (AD-3), so nothing of the tenant survives.
    const dry = await runDeleteTool(first.runId, true);
    assert.equal(dry.status, 0, `dry-run failed: ${dry.stderr}`);
    assert.deepEqual(JSON.parse(dry.stdout.replace(/^delete_run: dry-run closure /, '')), { runs: 2, artifacts: 4, run_inputs: 1 });
    const done = await runDeleteTool(first.runId, false);
    assert.equal(done.status, 0, `deletion failed: ${done.stderr}`);
    for (const runId of [first.runId, replay.runId]) {
      assert.equal(await h.count('fact_nm_daily', runId), 0, 'fact_nm_daily rows go with the run');
      assert.equal(await h.count('dim_nm_subject', runId), 0, 'dim_nm_subject rows go with the run');
      assert.equal(await h.count('fact_cabinet_daily', runId), 0);
      assert.equal(await h.count('collector_runs', runId), 0);
    }
    assert.equal(await countAs(collectorDsn, 'SELECT count(*) AS n FROM fact_nm_daily_current WHERE tenant_id = $1', true, [tenantId]), 0);
    assert.equal(await countAs(collectorDsn, 'SELECT count(*) AS n FROM dim_nm_subject_current WHERE tenant_id = $1', true, [tenantId]), 0);
  } finally { await h.cleanup(); }
});

test('nm-daily: rls matrix - collector and norm see the tenant with the GUC, nothing without it; the webapp has no grant', { skip }, async () => {
  const h = await openHarness();
  try {
    const result = await h.collect();
    for (const [label, dsn] of [['collector', collectorDsn], ['norm', normDsn]] as const) {
      assert.equal(await countAs(dsn, 'SELECT count(*) AS n FROM fact_nm_daily_current', true), FIXTURE_DAYS * FIXTURE_NM_IDS, `${label} sees the rows with the GUC`);
      assert.equal(await countAs(dsn, 'SELECT count(*) AS n FROM dim_nm_subject_current', true), FIXTURE_NM_IDS, `${label} sees the dictionary with the GUC`);
      assert.equal(await countAs(dsn, 'SELECT count(*) AS n FROM fact_nm_daily WHERE run_id = $1', false, [result.runId]), 0, `${label} sees zero rows without the GUC`);
      assert.equal(await countAs(dsn, 'SELECT count(*) AS n FROM dim_nm_subject WHERE run_id = $1', false, [result.runId]), 0, `${label} sees zero dictionary rows without the GUC`);
    }
    // norm reads only: the detector adapter of Story 4.1 never writes facts.
    await assert.rejects(
      () => countAs(normDsn, `INSERT INTO fact_nm_daily (tenant_id, calendar_day, nm_id, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256) VALUES ('${tenantId}', '2026-08-20', 1, '${result.runId}', 0, 0, 0, 0, 0.00, 0.00, ARRAY[]::char(64)[]) RETURNING 1 AS n`, true),
      /permission denied/,
    );
    // AD-9: the webapp reads brief_current and data_status_current only.
    await assert.rejects(() => countAs(webappDsn, 'SELECT count(*) AS n FROM fact_nm_daily_current', true), /permission denied/);
    await assert.rejects(() => countAs(webappDsn, 'SELECT count(*) AS n FROM dim_nm_subject_current', true), /permission denied/);
    await assert.rejects(() => countAs(webappDsn, 'SELECT count(*) AS n FROM fact_nm_daily', true), /permission denied/);
    // The janitor policy exists on both tables (AD-11; the generic check lives in delete-run.db.test.ts).
    assert.equal(await countAs(postgresDsn, "SELECT count(*) AS n FROM pg_policies WHERE schemaname = 'public' AND tablename IN ('fact_nm_daily', 'dim_nm_subject') AND policyname = 'tenant_isolation_janitor'", false), 2);
  } finally { await h.cleanup(); }
});
