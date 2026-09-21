import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { Client, type PoolClient } from 'pg';

import { canonicalJson, sha256 } from '../src/intake/manifest.js';
import { runCollect, type CollectResult } from '../src/jobs/collect.js';
import { WbClientError } from '../src/wb/client.js';
import { DEFAULT_FIXTURE_ROOT, FixtureTransport, type FixtureScript } from '../src/wb/fixture-transport.js';
import { insertObservations, toOrderObservations } from '../src/wb/observations.js';
import type { WbTransport } from '../src/wb/transport.js';

const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const ready = collectorDsn !== '' && postgresDsn !== '';
const skip = ready ? false : 'PROXIMA_TEST_DSN_COLLECTOR and PROXIMA_TEST_POSTGRES_DSN must be set (run via tools/pg_local_roundtrip.sh)';
const tenantId = 'amirova-test';
const ORDERS_FIXTURE = 301;
const SALES_FIXTURE = 295;

/** Structural read-only WB statistics JWT (category bit 5 + read-only bit 30), no real claims. */
function readOnlyStatisticsJwt(): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ s: (1 << 30) | (1 << 5), exp: 2_000_000_000 })).toString('base64url');
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
  /** Runs `collect` through the private-file contract and remembers the run for cleanup. */
  collect(transport: WbTransport): Promise<CollectResult>;
  /** Id of the most recently opened run, including one that failed. */
  lastRunId(): string;
  count(table: string, runId: string): Promise<number>;
  status(runId: string): Promise<string | undefined>;
  cleanup(): Promise<void>;
}

/**
 * The job reads its DSN and token only through private files, exactly like
 * production. The roundtrip database is shared by every *.db.test.ts file, so
 * each test deletes its own runs on exit (cascade removes observations and
 * artifacts) - the same "deletable by run_id" contract the janitor relies on.
 */
async function openHarness(harnessTenantId = tenantId): Promise<Harness> {
  await withAdmin((client) => client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [harnessTenantId]));
  const secrets = await mkdtemp(join(tmpdir(), 'proxima-collect-secrets-'));
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-collect-raw-'));
  const uriFile = join(secrets, 'proxima_collector_uri');
  const tokenFile = join(secrets, `${harnessTenantId}_wb_statistics_token`);
  await writeFile(uriFile, `${collectorDsn}\n`, { mode: 0o600 });
  await writeFile(tokenFile, `${readOnlyStatisticsJwt()}\n`, { mode: 0o600 });
  const env: NodeJS.ProcessEnv = { COLLECTOR_DATABASE_URI_FILE: uriFile, PROXIMA_RAW_DIR: rawRoot };
  const args = { tenantId: harnessTenantId, dateFrom: '2026-08-17', statisticsTokenFile: tokenFile };
  const runIds: string[] = [];
  const db = new Client({ connectionString: collectorDsn });
  await db.connect();
  await db.query("SELECT set_config('proxima.tenant_id', $1, false)", [harnessTenantId]);
  return {
    db,
    collect: (transport) => runCollect(args, { transport, env, onRunOpened: (runId) => { runIds.push(runId); } }),
    lastRunId() {
      const runId = runIds[runIds.length - 1];
      assert.ok(runId, 'no run was opened');
      return runId;
    },
    async count(table, runId) {
      const result = await db.query<{ n: string }>(`SELECT count(*) AS n FROM ${table} WHERE run_id = $1`, [runId]);
      return Number(result.rows[0]?.n);
    },
    async status(runId) {
      const result = await db.query<{ status: string }>('SELECT status FROM collector_runs WHERE run_id = $1', [runId]);
      return result.rows[0]?.status;
    },
    async cleanup() {
      await db.end();
      // Story 1.6: the aggregator records earlier runs as inputs with ON DELETE
      // RESTRICT (AD-3), so drop the input edges of this harness's runs first;
      // row order inside a single multi-row DELETE is not guaranteed.
      await withAdmin(async (client) => {
        await client.query('DELETE FROM collector_run_inputs WHERE run_id = ANY($1::uuid[]) OR input_run_id = ANY($1::uuid[])', [runIds]);
        await client.query('DELETE FROM collector_runs WHERE run_id = ANY($1::uuid[])', [runIds]);
      });
      await rm(secrets, { recursive: true, force: true });
      await rm(rawRoot, { recursive: true, force: true });
    },
  };
}

async function ordersFixture(): Promise<Record<string, unknown>[]> {
  return JSON.parse(await readFile(join(DEFAULT_FIXTURE_ROOT, 'statistics/orders/sample.json'), 'utf8')) as Record<string, unknown>[];
}

async function salesFixture(): Promise<Record<string, unknown>[]> {
  return JSON.parse(await readFile(join(DEFAULT_FIXTURE_ROOT, 'statistics/sales/sample.json'), 'utf8')) as Record<string, unknown>[];
}

function scriptedOrders(rows: unknown[]): FixtureTransport {
  const script: FixtureScript = { status: 200, body: JSON.stringify(rows), headers: { 'content-type': 'application/json' } };
  return new FixtureTransport({ scripts: { 'statistics.orders': [script] } });
}

function scriptedSales(rows: unknown[]): FixtureTransport {
  const script: FixtureScript = { status: 200, body: JSON.stringify(rows), headers: { 'content-type': 'application/json' } };
  return new FixtureTransport({ scripts: { 'statistics.sales': [script] } });
}

test('collect: idempotent replay 0 new rows', { skip }, async () => {
  const h = await openHarness();
  try {
    const first: CollectResult = await h.collect(new FixtureTransport().transport);
    assert.equal(await h.status(first.runId), 'SUCCEEDED');
    assert.deepEqual(first.orders, { received: ORDERS_FIXTURE, inserted: ORDERS_FIXTURE, skipped: 0 });
    assert.deepEqual(first.sales, { received: SALES_FIXTURE, inserted: SALES_FIXTURE, skipped: 0 });
    assert.equal(await h.count('stg_wb_orders_obs', first.runId), ORDERS_FIXTURE);
    assert.equal(await h.count('stg_wb_sales_obs', first.runId), SALES_FIXTURE);
    assert.equal(await h.count('wb_raw_artifacts', first.runId), 2, 'orders and sales responses are evidence of the run');
    const sample = await h.db.query<{ last_change_at: string; content_sha256: string; payload: { srid: string } }>(
      "SELECT to_char(last_change_at AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD\"T\"HH24:MI:SS') AS last_change_at, content_sha256, payload FROM stg_wb_orders_obs WHERE run_id = $1 AND srid = $2",
      [first.runId, '90000000000000001.0.0'],
    );
    assert.equal(sample.rows[0]?.last_change_at, '2026-08-17T06:48:49', 'zoneless WB lastChangeDate is stored as Moscow time');
    assert.equal(sample.rows[0]?.payload.srid, '90000000000000001.0.0');
    const artifact = await h.db.query<{ n: string }>('SELECT count(*) AS n FROM wb_raw_artifacts WHERE run_id = $1 AND content_sha256 = $2', [first.runId, sample.rows[0]?.content_sha256]);
    assert.equal(artifact.rows[0]?.n, '1', 'observation content_sha256 points at the recorded artifact');

    const replay = await h.collect(new FixtureTransport().transport);
    assert.notEqual(replay.runId, first.runId, 'a replay is a new run in the ledger');
    assert.equal(await h.status(replay.runId), 'SUCCEEDED');
    assert.deepEqual(replay.orders, { received: ORDERS_FIXTURE, inserted: 0, skipped: ORDERS_FIXTURE });
    assert.deepEqual(replay.sales, { received: SALES_FIXTURE, inserted: 0, skipped: SALES_FIXTURE });
    assert.equal(await h.count('stg_wb_orders_obs', replay.runId), 0);
    assert.equal(await h.count('stg_wb_sales_obs', replay.runId), 0);
    assert.equal(await h.count('stg_wb_orders_obs', first.runId), ORDERS_FIXTURE, 'first run keeps its observations');
  } finally {
    await h.cleanup();
  }
});

test('collect: order warehouseName-only replay retains the legacy observation and records incoming raw evidence', { skip }, async () => {
  const h = await openHarness();
  try {
    const rows = await ordersFixture();
    const original = rows[0] as Record<string, unknown> & { srid: string; warehouseName: string };
    const incoming = { ...original, warehouseName: `${original.warehouseName}-renamed` };
    const incomingRows = [incoming, ...rows.slice(1)];
    const incomingBody = JSON.stringify(incomingRows);
    const base = await h.collect(new FixtureTransport().transport);

    const replay = await h.collect(scriptedOrders(incomingRows).transport);
    assert.equal(await h.status(replay.runId), 'SUCCEEDED');
    assert.deepEqual(replay.orders, { received: ORDERS_FIXTURE, inserted: 0, skipped: ORDERS_FIXTURE });

    const stored = await h.db.query<{
      run_id: string;
      content_sha256: string;
      canonical_sha256: string;
      payload: Record<string, unknown>;
    }>(
      'SELECT run_id, content_sha256, canonical_sha256, payload FROM stg_wb_orders_obs WHERE tenant_id = $1 AND srid = $2',
      [tenantId, original.srid],
    );
    assert.equal(stored.rowCount, 1);
    assert.equal(stored.rows[0]?.run_id, base.runId, 'the first observation remains authoritative');
    assert.equal(stored.rows[0]?.payload.warehouseName, original.warehouseName, 'the legacy full payload is not rewritten');
    assert.equal(stored.rows[0]?.canonical_sha256, sha256(canonicalJson(original)), 'the full legacy canonical hash is retained');
    assert.notEqual(stored.rows[0]?.canonical_sha256, sha256(canonicalJson(incoming)), 'warehouseName remains part of new canonical hashes');

    const artifact = await h.db.query<{ content_sha256: string }>(
      "SELECT content_sha256 FROM wb_raw_artifacts WHERE run_id = $1 AND endpoint_id = 'statistics.orders'",
      [replay.runId],
    );
    assert.equal(artifact.rowCount, 1);
    assert.equal(artifact.rows[0]?.content_sha256, sha256(incomingBody), 'the renamed incoming response remains raw evidence');
    assert.notEqual(stored.rows[0]?.content_sha256, artifact.rows[0]?.content_sha256, 'the stored observation keeps its original artifact link');
  } finally {
    await h.cleanup();
  }
});

test('collect: warehouseName replay exception is scoped by tenant', { skip }, async () => {
  const originalTenant = await openHarness();
  let otherTenant: Harness | undefined;
  try {
    await originalTenant.collect(new FixtureTransport().transport);
    const rows = await ordersFixture();
    const target = rows[0] as Record<string, unknown> & { srid: string; warehouseName: string };
    const renamed = { ...target, warehouseName: `${target.warehouseName}-other-tenant` };

    otherTenant = await openHarness('amirova-other-test');
    const result = await otherTenant.collect(scriptedOrders([renamed, ...rows.slice(1)]).transport);
    assert.equal(await otherTenant.status(result.runId), 'SUCCEEDED');
    assert.deepEqual(result.orders, { received: ORDERS_FIXTURE, inserted: ORDERS_FIXTURE, skipped: 0 });
    const stored = await otherTenant.db.query<{ warehouse_name: string }>(
      "SELECT payload->>'warehouseName' AS warehouse_name FROM stg_wb_orders_obs WHERE tenant_id = $1 AND srid = $2",
      ['amirova-other-test', target.srid],
    );
    assert.equal(stored.rows[0]?.warehouse_name, renamed.warehouseName);
  } finally {
    if (otherTenant !== undefined) await otherTenant.cleanup();
    await originalTenant.cleanup();
  }
});

test('collect: late change of the same srid is a second observation and _latest returns it', { skip }, async () => {
  const h = await openHarness();
  try {
    const base = await h.collect(new FixtureTransport().transport);
    const rows = await ordersFixture();
    const target = rows[0] as Record<string, unknown> & { srid: string; lastChangeDate: string };
    const bumped = { ...target, lastChangeDate: '2026-08-31T09:15:00', isCancel: true, cancelDate: '2026-08-31T09:15:00' };
    const late = await h.collect(scriptedOrders([bumped, ...rows.slice(1)]).transport);
    assert.equal(await h.status(late.runId), 'SUCCEEDED');
    assert.deepEqual(late.orders, { received: ORDERS_FIXTURE, inserted: 1, skipped: ORDERS_FIXTURE - 1 });
    assert.equal(late.sales.inserted, 0);
    const versions = await h.db.query<{ run_id: string; last_change_at: string }>(
      "SELECT run_id, to_char(last_change_at AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD\"T\"HH24:MI:SS') AS last_change_at FROM stg_wb_orders_obs WHERE tenant_id = $1 AND srid = $2 ORDER BY last_change_at",
      [tenantId, target.srid],
    );
    assert.deepEqual(versions.rows.map((row) => row.last_change_at), [target.lastChangeDate, '2026-08-31T09:15:00']);
    assert.deepEqual(versions.rows.map((row) => row.run_id), [base.runId, late.runId], 'each version keeps the run that first observed it');
    const latest = await h.db.query<{ run_id: string; last_change_at: string; is_cancel: boolean }>(
      "SELECT run_id, to_char(last_change_at AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD\"T\"HH24:MI:SS') AS last_change_at, (payload->>'isCancel')::boolean AS is_cancel FROM stg_wb_orders_latest WHERE tenant_id = $1 AND srid = $2",
      [tenantId, target.srid],
    );
    assert.equal(latest.rowCount, 1);
    assert.deepEqual(latest.rows[0], { run_id: late.runId, last_change_at: '2026-08-31T09:15:00', is_cancel: true });
  } finally {
    await h.cleanup();
  }
});

test('collect: warehouse metadata plus financial drift is WB_SCHEMA_DRIFT, run FAILED, no observations', { skip }, async () => {
  const h = await openHarness();
  try {
    await h.collect(new FixtureTransport().transport);
    const rows = await ordersFixture();
    const target = rows[0] as Record<string, unknown> & { totalPrice: number; warehouseName: string };
    const drifted = { ...target, warehouseName: `${target.warehouseName}-renamed`, totalPrice: target.totalPrice + 1 };
    await assert.rejects(
      () => h.collect(scriptedOrders([drifted, ...rows.slice(1)]).transport),
      (error: unknown) => error instanceof WbClientError && error.code === 'WB_SCHEMA_DRIFT',
    );
    const failedRunId = h.lastRunId();
    assert.equal(await h.status(failedRunId), 'FAILED');
    assert.equal(await h.count('stg_wb_orders_obs', failedRunId), 0);
    assert.equal(await h.count('stg_wb_sales_obs', failedRunId), 0);
    assert.equal(await h.count('wb_raw_artifacts', failedRunId), 2, 'evidence of the failed run survives the rollback');
  } finally {
    await h.cleanup();
  }
});

test('orders: replay exception fails closed for missing, null or non-string warehouseName', { skip }, async () => {
  const h = await openHarness();
  try {
    const base = await h.collect(new FixtureTransport().transport);
    const rows = await ordersFixture();
    const target = rows[0] as Record<string, unknown> & { srid: string; warehouseName: string };
    const { warehouseName: _warehouseName, ...withoutWarehouse } = target;
    const invalidIncoming = [withoutWarehouse, { ...target, warehouseName: null }, { ...target, warehouseName: 42 }];
    for (const incoming of invalidIncoming) {
      const body = JSON.stringify([incoming]);
      const set = toOrderObservations([incoming], sha256(body));
      await assert.rejects(
        () => insertObservations(h.db as unknown as PoolClient, tenantId, base.runId, set, 1),
        (error: unknown) => error instanceof WbClientError && error.code === 'WB_SCHEMA_DRIFT',
      );
    }

    const invalidPersisted = [
      { ...withoutWarehouse, srid: `${target.srid}.persisted-missing` },
      { ...target, srid: `${target.srid}.persisted-null`, warehouseName: null },
      { ...target, srid: `${target.srid}.persisted-number`, warehouseName: 42 },
    ];
    for (const persistedRow of invalidPersisted) {
      const persistedBody = JSON.stringify([persistedRow]);
      const persisted = toOrderObservations([persistedRow], sha256(persistedBody));
      assert.equal((await insertObservations(h.db as unknown as PoolClient, tenantId, base.runId, persisted, 1)).inserted, 1);
      const incomingString = { ...persistedRow, warehouseName: 'warehouse-now-present' };
      const incomingBody = JSON.stringify([incomingString]);
      await assert.rejects(
        () => insertObservations(
          h.db as unknown as PoolClient,
          tenantId,
          base.runId,
          toOrderObservations([incomingString], sha256(incomingBody)),
          1,
        ),
        (error: unknown) => error instanceof WbClientError && error.code === 'WB_SCHEMA_DRIFT',
      );
    }
  } finally {
    await h.cleanup();
  }
});

test('orders: drift in a later batch rolls back earlier inserts across a warehouseName replay', { skip }, async () => {
  const h = await openHarness();
  try {
    const base = await h.collect(new FixtureTransport().transport);
    const rows = await ordersFixture();
    const first = rows[0] as Record<string, unknown> & { srid: string; warehouseName: string };
    const second = rows[1] as Record<string, unknown> & { totalPrice: number; warehouseName: string };
    const newSrid = `${first.srid}.batch-before-drift`;
    const newRow = { ...first, srid: newSrid };
    const warehouseReplay = { ...first, warehouseName: `${first.warehouseName}-renamed` };
    const mixedDrift = {
      ...second,
      warehouseName: `${second.warehouseName}-renamed`,
      totalPrice: second.totalPrice + 1,
    };
    const incoming = [newRow, warehouseReplay, mixedDrift];
    const set = toOrderObservations(incoming, sha256(JSON.stringify(incoming)));

    await h.db.query('BEGIN');
    try {
      await assert.rejects(
        () => insertObservations(h.db as unknown as PoolClient, tenantId, base.runId, set, 1),
        (error: unknown) => error instanceof WbClientError && error.code === 'WB_SCHEMA_DRIFT',
      );
    } finally {
      await h.db.query('ROLLBACK');
    }
    const earlierInsert = await h.db.query<{ n: string }>(
      'SELECT count(*) AS n FROM stg_wb_orders_obs WHERE tenant_id = $1 AND srid = $2',
      [tenantId, newSrid],
    );
    assert.equal(earlierInsert.rows[0]?.n, '0');
  } finally {
    await h.cleanup();
  }
});

test('collect: sales remain strict for warehouseName-only changes', { skip }, async () => {
  const h = await openHarness();
  try {
    await h.collect(new FixtureTransport().transport);
    const rows = await salesFixture();
    const target = rows[0] as Record<string, unknown> & { warehouseName: string };
    const renamed = { ...target, warehouseName: `${target.warehouseName}-renamed` };
    await assert.rejects(
      () => h.collect(scriptedSales([renamed, ...rows.slice(1)]).transport),
      (error: unknown) => error instanceof WbClientError && error.code === 'WB_SCHEMA_DRIFT',
    );
    const failedRunId = h.lastRunId();
    assert.equal(await h.status(failedRunId), 'FAILED');
    assert.equal(await h.count('stg_wb_orders_obs', failedRunId), 0);
    assert.equal(await h.count('stg_wb_sales_obs', failedRunId), 0);
    assert.equal(await h.count('wb_raw_artifacts', failedRunId), 2);
  } finally {
    await h.cleanup();
  }
});
