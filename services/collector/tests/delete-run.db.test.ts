// Story 1.7 db-tests: transitive run rollback through the real delete_run.py
// plus the RLS matrix of AD-11/AD-12. Runs only inside
// tools/pg_local_roundtrip.sh against the disposable PostgreSQL 16 with the
// production LOGIN roles provisioned; connections never use SET ROLE.
// Without the harness env the file skips.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { mkdtemp, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { Client } from 'pg';

const janitorDsn = process.env.PROXIMA_TEST_DSN_JANITOR ?? '';
const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const normDsn = process.env.PROXIMA_TEST_DSN_NORM ?? '';
const webappDsn = process.env.PROXIMA_TEST_DSN_WEBAPP ?? '';
const sandboxDsn = process.env.PROXIMA_TEST_DSN_SANDBOX ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

/** Rewrites the database name of a URI without touching credentials (AD-12). */
function withDatabase(dsn: string, database: string): string {
  const parsed = new URL(dsn);
  parsed.pathname = `/${database}`;
  return parsed.toString();
}

const ready =
  janitorDsn !== '' &&
  collectorDsn !== '' &&
  normDsn !== '' &&
  webappDsn !== '' &&
  sandboxDsn !== '' &&
  postgresDsn !== '';
const skip = ready ? false : 'PROXIMA_TEST_DSN_JANITOR and friends must be set (run via tools/pg_local_roundtrip.sh)';

const tenantId = 'pilot-tenant';

async function withAdmin<T>(work: (client: Client) => Promise<T>): Promise<T> {
  const client = new Client({ connectionString: postgresDsn });
  await client.connect();
  try {
    return await work(client);
  } finally {
    await client.end();
  }
}

/** Private-file contract of production: the tool receives its DSN only via a 0600 URI file.
 * PROXIMA_TEST_PYTHON lets the harness pin the interpreter that has psycopg. */
async function runDeleteTool(args: { tenant?: string; run: string; dryRun?: boolean }, env?: NodeJS.ProcessEnv): Promise<{ status: number; stdout: string; stderr: string }> {
  const secrets = await mkdtemp(join(tmpdir(), 'proxima-janitor-'));
  const uriFile = join(secrets, 'proxima_janitor_uri');
  await writeFile(uriFile, `${janitorDsn}\n`, { mode: 0o600 });
  const python = process.env.PROXIMA_TEST_PYTHON ?? 'python3';
  try {
    const argv = [join(repoRoot, 'tools', 'delete_run.py')];
    if (args.tenant !== undefined) argv.push('--tenant', args.tenant);
    argv.push('--run', args.run);
    if (args.dryRun) argv.push('--dry-run');
    const childEnv: NodeJS.ProcessEnv = { ...process.env, JANITOR_DATABASE_URI_FILE: uriFile, ...(env ?? {}) };
    try {
      const stdout = execFileSync(python, argv, { env: childEnv, encoding: 'utf8', cwd: repoRoot });
      return { status: 0, stdout, stderr: '' };
    } catch (error) {
      const failure = error as { status?: number; stdout?: string; stderr?: string };
      return { status: failure.status ?? 1, stdout: failure.stdout ?? '', stderr: failure.stderr ?? '' };
    }
  } finally {
    await rm(secrets, { recursive: true, force: true });
  }
}

interface SeedRun {
  runId: string;
  kind: 'collect' | 'backfill' | 'norm';
  artifactBodies: string[];
}

/** Seeds runs and their edges through the janitor/admin connections. */
async function seedGraph(): Promise<{ collect: SeedRun; backfill: SeedRun; norm: SeedRun; unrelated: SeedRun }> {
  await withAdmin((client) => client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]));
  const makeRun = async (kind: SeedRun['kind'], withArtifact: boolean): Promise<SeedRun> => {
    const runId = randomUUID();
    const artifactBodies: string[] = [];
    await withAdmin(async (client) => {
      await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
      await client.query(
        "INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES ($1, $2, $3, 'SUCCEEDED', CURRENT_TIMESTAMP)",
        [runId, tenantId, kind],
      );
      if (withArtifact) {
        const body = `evidence-of-${runId}`;
        artifactBodies.push(body);
        await client.query(
          `INSERT INTO wb_raw_artifacts (artifact_id, tenant_id, run_id, endpoint_id, endpoint_path, http_status, response_headers, content_sha256, content_size, object_locator, manifest_sha256, retrieved_at, attempt)
           VALUES ($1, $2, $3, 'statistics.orders', '/api/v1/supplier/orders', 200, '{}', $4, $5, $6, $7, CURRENT_TIMESTAMP, 1)`,
          [
            randomUUID(),
            tenantId,
            runId,
            Buffer.from(body).toString('hex').padStart(64, '0').slice(0, 64),
            Buffer.from(body).length,
            `artifact://business-signal/sha256/${'0'.repeat(64)}`,
            '1'.repeat(64),
          ],
        );
      }
    });
    return { runId, kind, artifactBodies };
  };
  const collect = await makeRun('collect', true);
  const backfill = await makeRun('backfill', true);
  const norm = await makeRun('norm', false);
  const unrelated = await makeRun('collect', false);
  await withAdmin(async (client) => {
    await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    // norm consumed the backfill, the backfill consumed the collect
    await client.query('INSERT INTO collector_run_inputs (tenant_id, run_id, input_run_id) VALUES ($1, $2, $3)', [tenantId, backfill.runId, collect.runId]);
    await client.query('INSERT INTO collector_run_inputs (tenant_id, run_id, input_run_id) VALUES ($1, $2, $3)', [tenantId, norm.runId, backfill.runId]);
  });
  return { collect, backfill, norm, unrelated };
}

async function cleanupRuns(runIds: string[]): Promise<void> {
  await withAdmin(async (client) => {
    await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    await client.query('DELETE FROM collector_run_inputs WHERE run_id = ANY($1::uuid[]) OR input_run_id = ANY($1::uuid[])', [runIds]);
    await client.query('DELETE FROM collector_runs WHERE run_id = ANY($1::uuid[])', [runIds]);
  });
}

async function runVisible(dsn: string, runId: string, withGuc: boolean): Promise<number> {
  const client = new Client({ connectionString: dsn });
  await client.connect();
  try {
    if (withGuc) await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    const result = await client.query<{ n: string }>('SELECT count(*) AS n FROM collector_runs WHERE run_id = $1', [runId]);
    return Number(result.rows[0]?.n);
  } finally {
    await client.end();
  }
}

test('delete_run: closure from the leaf ancestor reaches the far end of the chain', { skip }, async () => {
  // The middle node was the only case exercised, and it hid a real defect: the
  // closure query fetched a single hop, so deleting the input at the end of the
  // chain never saw the run two steps above it. That is not a smaller deletion -
  // collector_run_inputs.input_run_id is ON DELETE RESTRICT, so the DELETE fails
  // on a live referencing row. The daily collect -> norm -> brief chain has
  // exactly this shape, and collect is the run an operator actually removes.
  const graph = await seedGraph();
  try {
    const dry = await runDeleteTool({ tenant: tenantId, run: graph.collect.runId, dryRun: true });
    assert.equal(dry.status, 0, `dry-run failed: ${dry.stderr}`);
    const counts = JSON.parse(dry.stdout.replace(/^delete_run: dry-run closure /, ''));
    assert.deepEqual(counts, { runs: 3, artifacts: 2, run_inputs: 2 }, 'the whole chain, not just the first hop');

    const done = await runDeleteTool({ tenant: tenantId, run: graph.collect.runId });
    assert.equal(done.status, 0, `deletion failed: ${done.stderr}`);
    for (const run of [graph.collect, graph.backfill, graph.norm]) {
      assert.equal(await runVisible(collectorDsn, run.runId, true), 0, `${run.kind} run must be gone`);
    }
    assert.equal(await runVisible(collectorDsn, graph.unrelated.runId, true), 1, 'an unrelated run must survive');
  } finally {
    await cleanupRuns([graph.collect.runId, graph.backfill.runId, graph.norm.runId, graph.unrelated.runId]);
  }
});

test('delete_run: closure', { skip }, async () => {
  const graph = await seedGraph();
  try {
    // dry-run counts the whole closure without deleting anything
    const dry = await runDeleteTool({ tenant: tenantId, run: graph.backfill.runId, dryRun: true });
    assert.equal(dry.status, 0, `dry-run failed: ${dry.stderr}`);
    const counts = JSON.parse(dry.stdout.replace(/^delete_run: dry-run closure /, ''));
    assert.deepEqual(counts, { runs: 3, artifacts: 2, run_inputs: 2 }, 'closure = backfill + its collect input + the norm above');
    assert.equal(await runVisible(collectorDsn, graph.backfill.runId, true), 1, 'dry-run must not delete');

    // the real deletion removes the same closure in one transaction
    const done = await runDeleteTool({ tenant: tenantId, run: graph.backfill.runId });
    assert.equal(done.status, 0, `deletion failed: ${done.stderr}`);
    const deleted = JSON.parse(done.stdout.replace(/^delete_run: deleted closure /, ''));
    assert.deepEqual(deleted, { runs: 3, artifacts: 2, run_inputs: 2 });
    for (const run of [graph.collect, graph.backfill, graph.norm]) {
      assert.equal(await runVisible(collectorDsn, run.runId, true), 0, `${run.kind} run must be gone`);
    }
    assert.equal(await runVisible(collectorDsn, graph.unrelated.runId, true), 1, 'an unrelated run must survive');

    // a FAILED run leaves only its own row + artifacts to remove
    const failed = graph.unrelated;
    await withAdmin(async (client) => {
      await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
      await client.query("UPDATE collector_runs SET status = 'FAILED' WHERE run_id = $1", [failed.runId]);
      await client.query(
        `INSERT INTO wb_raw_artifacts (artifact_id, tenant_id, run_id, endpoint_id, endpoint_path, http_status, response_headers, content_sha256, content_size, object_locator, manifest_sha256, retrieved_at, attempt)
         VALUES ($1, $2, $3, 'statistics.sales', '/api/v1/supplier/sales', 500, '{}', $4, $5, $6, $7, CURRENT_TIMESTAMP, 1)`,
        [randomUUID(), tenantId, failed.runId, '2'.repeat(64), 11, `artifact://business-signal/sha256/${'0'.repeat(64)}`, '3'.repeat(64)],
      );
    });
    const failedDeletion = await runDeleteTool({ tenant: tenantId, run: failed.runId });
    assert.equal(failedDeletion.status, 0, `failed-run deletion errored: ${failedDeletion.stderr}`);
    const failedCounts = JSON.parse(failedDeletion.stdout.replace(/^delete_run: deleted closure /, ''));
    assert.deepEqual(failedCounts, { runs: 1, artifacts: 1, run_inputs: 0 }, 'a FAILED run takes only its row and artifacts');
    assert.equal(await runVisible(collectorDsn, failed.runId, true), 0);
  } finally {
    await cleanupRuns([graph.collect.runId, graph.backfill.runId, graph.norm.runId, graph.unrelated.runId]);
  }
});

test('delete_run: closure without a tenant or without the GUC errors, never deletes zeros', { skip }, async () => {
  const graph = await seedGraph();
  try {
    const withoutFlag = await runDeleteTool({ run: graph.collect.runId });
    assert.equal(withoutFlag.status, 1);
    assert.match(withoutFlag.stderr, /0 строк для run_id/);

    const foreignTenant = await runDeleteTool({ tenant: 'some-other-tenant', run: graph.collect.runId });
    assert.equal(foreignTenant.status, 1);
    assert.match(foreignTenant.stderr, /0 строк для run_id/);
    assert.equal(await runVisible(collectorDsn, graph.collect.runId, true), 1, 'a refused deletion must leave the run in place');
  } finally {
    await cleanupRuns([graph.collect.runId, graph.backfill.runId, graph.norm.runId, graph.unrelated.runId]);
  }
});

test('delete_run: closure keeps the CAS files on disk', { skip }, async () => {
  const graph = await seedGraph();
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-cas-'));
  try {
    // simulate CAS files the seeded artifacts point at
    const files: string[] = [];
    for (const body of graph.collect.artifactBodies) {
      const path = join(rawRoot, `${body}.bin`);
      await writeFile(path, body);
      files.push(path);
    }
    const done = await runDeleteTool({ tenant: tenantId, run: graph.backfill.runId });
    assert.equal(done.status, 0, done.stderr);
    for (const path of files) {
      await stat(path);
    }
  } finally {
    await rm(rawRoot, { recursive: true, force: true });
    await cleanupRuns([graph.collect.runId, graph.backfill.runId, graph.norm.runId, graph.unrelated.runId]);
  }
});

test('rls: matrix', { skip }, async () => {
  const graph = await seedGraph();
  try {
    // Roles holding grants on the base tables behind the security_invoker
    // views see the run with the GUC and zero rows without it.
    for (const [label, dsn] of [['collector', collectorDsn], ['norm', normDsn], ['webapp', webappDsn], ['janitor', janitorDsn]] as const) {
      assert.equal(await runVisible(dsn, graph.collect.runId, true), 1, `${label} must see the run with the GUC`);
      assert.equal(await runVisible(dsn, graph.collect.runId, false), 0, `${label} must see zero rows without the GUC`);
    }
    // The sandbox role holds grants and BYPASSRLS in proxima_test only; against
    // the main database it must not get past its missing privileges (AD-12).
    await assert.rejects(
      async () => {
        const client = new Client({ connectionString: withDatabase(sandboxDsn, 'proxima') });
        await client.connect();
        try {
          await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
          await client.query('SELECT count(*) FROM collector_runs');
        } finally {
          await client.end();
        }
      },
      (error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        if (!/permission denied/i.test(message)) throw new Error(`expected permission denied, got: ${message}`);
        return true;
      },
    );

    // Every table carrying a run_id must have a janitor policy (AD-11).
    // business_signal_raw_artifacts predates the ledger (004) and carries no
    // tenant_id, so the canonical tenant-guard policy cannot exist there.
    const admin = new Client({ connectionString: postgresDsn });
    await admin.connect();
    try {
      const missing = await admin.query<{ relname: string }>(
        `SELECT c.relname
         FROM pg_class c
         JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind = 'r'
           AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'run_id' AND NOT a.attisdropped)
           AND c.relname NOT IN ('business_signal_runs', 'business_signal_raw_artifacts')
           AND NOT EXISTS (
             SELECT 1 FROM pg_policies p
             WHERE p.schemaname = 'public' AND p.tablename = c.relname
               AND p.policyname LIKE '%janitor%'
           )`,
      );
      assert.deepEqual(missing.rows.map((row) => row.relname), [], 'every ledger run_id table needs a janitor policy (AD-11)');
      const collectorRunJanitor = await admin.query<{ n: string }>(
        "SELECT count(*) AS n FROM pg_policies WHERE schemaname = 'public' AND tablename = 'collector_runs' AND policyname LIKE '%janitor%'",
      );
      assert.equal(Number(collectorRunJanitor.rows[0]?.n), 1);
    } finally {
      await admin.end();
    }
  } finally {
    await cleanupRuns([graph.collect.runId, graph.backfill.runId, graph.norm.runId, graph.unrelated.runId]);
  }
});
