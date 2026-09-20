import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { Client, Pool } from 'pg';

import { BusinessSignalRawStore } from '../src/business-signal/raw-store.js';
import { WbArtifactSink } from '../src/wb/recording-client.js';
import { RunLedger } from '../src/wb/run-ledger.js';

const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const ready = collectorDsn !== '' && postgresDsn !== '';
const tenantId = 'pilot-tenant';

async function seedTenant(): Promise<void> {
  const client = new Client({ connectionString: postgresDsn });
  await client.connect();
  try { await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]); }
  finally { await client.end(); }
}

async function assertTenantGucReset(pool: Pool, runId: string): Promise<void> {
  const result = await pool.query<{ tenant_id: string | null }>("SELECT current_setting('proxima.tenant_id', true) AS tenant_id");
  assert.ok(result.rows[0]?.tenant_id === null || result.rows[0]?.tenant_id === '', 'a released pool session must not retain a tenant GUC');
  const invisible = await pool.query<{ count: string }>('SELECT count(*) FROM collector_runs WHERE run_id = $1', [runId]);
  assert.equal(invisible.rows[0]?.count, '0', 'RLS must hide a run when the tenant GUC is absent');
}

async function setTenantGuc(pool: Pool): Promise<void> {
  await pool.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
}

test('run-ledger: running/succeeded/failed', { skip: ready ? false : 'PROXIMA_TEST_DSN_COLLECTOR and PROXIMA_TEST_POSTGRES_DSN must be set (run via tools/pg_local_roundtrip.sh)' }, async () => {
  await seedTenant();
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-raw-'));
  const pool = new Pool({ connectionString: collectorDsn, max: 1 });
  let succeeded = '';
  let failed = '';
  try {
    const ledger = new RunLedger(pool);
    succeeded = await ledger.open({ tenantId, kind: 'collect' });
    await assertTenantGucReset(pool, succeeded);
    await setTenantGuc(pool);
    const running = await pool.query<{ status: string }>('SELECT status FROM collector_runs WHERE run_id = $1', [succeeded]);
    assert.equal(running.rows[0]?.status, 'RUNNING');

    const rawStore = await BusinessSignalRawStore.open(rawRoot, process.cwd());
    const sink = new WbArtifactSink(tenantId, succeeded, rawStore, pool);
    const first = await sink.store({ endpointId: 'statistics.orders', url: 'https://statistics-api.wildberries.ru/api/v1/supplier/orders', httpStatus: 200, responseHeaders: { 'content-type': 'application/json' }, body: Buffer.from('[]'), retrievedAt: new Date('2026-09-01T00:00:00.000Z'), attempt: 0, sequence: 1 });
    const second = await sink.store({ endpointId: 'statistics.sales', url: 'https://statistics-api.wildberries.ru/api/v1/supplier/sales', httpStatus: 500, responseHeaders: {}, body: Buffer.from('{"error":true}'), retrievedAt: new Date('2026-09-01T00:00:01.000Z'), attempt: 0, sequence: 1 });
    assert.match(first.objectLocator, /^artifact:\/\/business-signal\/sha256\/[0-9a-f]{64}$/);
    assert.match(second.objectLocator, /^artifact:\/\/business-signal\/sha256\/[0-9a-f]{64}$/);
    await assertTenantGucReset(pool, succeeded);
    await setTenantGuc(pool);
    const artifacts = await pool.query<{ count: string }>('SELECT count(*) FROM wb_raw_artifacts WHERE run_id = $1', [succeeded]);
    assert.equal(artifacts.rows[0]?.count, '2');
    await ledger.succeed(tenantId, succeeded);
    await setTenantGuc(pool);
    const done = await pool.query<{ status: string }>('SELECT status FROM collector_runs WHERE run_id = $1', [succeeded]);
    assert.equal(done.rows[0]?.status, 'SUCCEEDED');
    await assert.rejects(() => ledger.succeed(tenantId, succeeded), /expected one RUNNING row visible/);

    failed = await ledger.open({ tenantId, kind: 'collect' });
    const failedSink = new WbArtifactSink(tenantId, failed, rawStore, pool);
    await failedSink.store({ endpointId: 'statistics.orders', url: 'https://statistics-api.wildberries.ru/api/v1/supplier/orders', httpStatus: 500, responseHeaders: {}, body: Buffer.from('failure-evidence'), retrievedAt: new Date('2026-09-01T00:00:02.000Z'), attempt: 0, sequence: 1 });
    await assert.rejects(async () => { throw new Error('artificial processing failure'); });
    await ledger.fail(tenantId, failed);
    await setTenantGuc(pool);
    const failure = await pool.query<{ status: string; count: string }>('SELECT r.status, (SELECT count(*) FROM wb_raw_artifacts a WHERE a.run_id = r.run_id) AS count FROM collector_runs r WHERE r.run_id = $1', [failed]);
    assert.equal(failure.rows[0]?.status, 'FAILED');
    assert.equal(failure.rows[0]?.count, '1');
    await assert.rejects(() => ledger.fail(tenantId, failed), /expected one RUNNING row visible/);
  } finally {
    await pool.end();
    // Cleanup is not part of the ledger contract under test, but the roundtrip
    // database is shared: leftover runs would make data_status_current look
    // fresh and break the staleness matrix of later files (AD-3 deletability).
    const admin = new Client({ connectionString: postgresDsn });
    await admin.connect();
    try {
      await admin.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
      await admin.query('DELETE FROM collector_run_inputs WHERE run_id = ANY($1::uuid[]) OR input_run_id = ANY($1::uuid[])', [[succeeded, failed]]);
      await admin.query('DELETE FROM collector_runs WHERE run_id = ANY($1::uuid[])', [[succeeded, failed]]);
    } finally {
      await admin.end();
    }
    await rm(rawRoot, { recursive: true, force: true });
  }
});
