import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';

import { Client } from 'pg';

import { aggregateCabinetDaily } from '../src/facts/cabinet-daily.js';

const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const normDsn = process.env.PROXIMA_TEST_DSN_NORM ?? '';
const webappDsn = process.env.PROXIMA_TEST_DSN_WEBAPP ?? '';
const skip = collectorDsn && postgresDsn ? false : 'PROXIMA_TEST_DSN_COLLECTOR and PROXIMA_TEST_POSTGRES_DSN must be set (run via tools/pg_local_roundtrip.sh)';
const tenantId = 'amirova-test';

test('cabinet-daily: versions every day, S1/S2 sums', { skip }, async () => {
  const sourceRun = randomUUID();
  const aggregateRun = randomUUID();
  const admin = new Client({ connectionString: postgresDsn });
  const collector = new Client({ connectionString: collectorDsn });
  await admin.connect();
  await collector.connect();
  try {
    await admin.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]);
    await admin.query(
      `INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES
       ($1, $3, 'collect', 'SUCCEEDED', CURRENT_TIMESTAMP), ($2, $3, 'collect', 'RUNNING', NULL)`,
      [sourceRun, aggregateRun, tenantId],
    );
    const orderPayloads = [
      { srid: 'synthetic-order-1', date: '2026-08-17T10:00:00', lastChangeDate: '2026-08-18T01:00:00', isCancel: false },
      { srid: 'synthetic-order-2', date: '2026-08-24T10:00:00', lastChangeDate: '2026-08-25T01:00:00', isCancel: true },
    ];
    const salePayloads = [
      { saleID: 'S-synthetic-1', date: '2026-08-17T12:00:00', lastChangeDate: '2026-08-18T01:00:00', finishedPrice: '12.50', forPay: '10.00' },
      { saleID: 'R-synthetic-1', date: '2026-08-24T12:00:00', lastChangeDate: '2026-08-25T01:00:00', finishedPrice: '12.50', forPay: '10.00' },
    ];
    for (const payload of orderPayloads) {
      await admin.query(
        "INSERT INTO stg_wb_orders_obs (tenant_id, srid, last_change_at, run_id, content_sha256, canonical_sha256, payload) VALUES ($1, $2, ($3::timestamp AT TIME ZONE 'Europe/Moscow'), $4, $5, $6, $7)",
        [tenantId, payload.srid, payload.lastChangeDate, sourceRun, 'a'.repeat(64), 'b'.repeat(64), payload],
      );
    }
    for (const payload of salePayloads) {
      await admin.query(
        "INSERT INTO stg_wb_sales_obs (tenant_id, sale_id, last_change_at, run_id, content_sha256, canonical_sha256, payload) VALUES ($1, $2, ($3::timestamp AT TIME ZONE 'Europe/Moscow'), $4, $5, $6, $7)",
        [tenantId, payload.saleID, payload.lastChangeDate, sourceRun, 'c'.repeat(64), 'd'.repeat(64), payload],
      );
    }
    await admin.query(
      "INSERT INTO wb_raw_artifacts (artifact_id, tenant_id, run_id, endpoint_id, endpoint_path, http_status, response_headers, content_sha256, content_size, object_locator, manifest_sha256, retrieved_at, attempt) VALUES ($1, $2, $3, 'statistics.orders', '/fixture', 200, '{}', $4, 1, $5, $6, CURRENT_TIMESTAMP, 1)",
      [randomUUID(), tenantId, aggregateRun, 'e'.repeat(64), `artifact://business-signal/sha256/${'e'.repeat(64)}`, 'f'.repeat(64)],
    );
    await collector.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    await collector.query('BEGIN');
    const result = await aggregateCabinetDaily(collector, { tenantId, runId: aggregateRun, floor: '2026-08-17', runDay: '2026-08-31' });
    await collector.query('COMMIT');
    assert.deepEqual(result, { days: 14, inputRuns: 1 });
    await admin.query("UPDATE collector_runs SET status = 'SUCCEEDED', finished_at = CURRENT_TIMESTAMP + interval '1 second' WHERE run_id = $1", [aggregateRun]);
    const sums = await admin.query(
      'SELECT count(*)::int AS days, sum(orders_count)::int AS orders, sum(cancelled_count)::int AS cancelled, sum(sales_count)::int AS sales, sum(returns_count)::int AS returns, sum(revenue_rub)::text AS revenue, sum(forpay_rub)::text AS forpay FROM fact_cabinet_daily_current WHERE tenant_id = $1 AND calendar_day BETWEEN $2 AND $3',
      [tenantId, '2026-08-17', '2026-08-30'],
    );
    assert.deepEqual(sums.rows[0], { days: 14, orders: 1, cancelled: 1, sales: 1, returns: 1, revenue: '12.50', forpay: '10.00' });
    assert.equal((await admin.query('SELECT count(*)::int AS n FROM fact_cabinet_daily WHERE run_id = $1 AND calendar_day = $2', [aggregateRun, '2026-08-31'])).rows[0]?.n, 0);
    assert.equal((await admin.query('SELECT count(*)::int AS n FROM collector_run_inputs WHERE run_id = $1 AND input_run_id = $2', [aggregateRun, sourceRun])).rows[0]?.n, 1);
    const status = await admin.query('SELECT last_full_day::text, stale FROM data_status_current WHERE tenant_id = $1', [tenantId]);
    assert.equal(status.rows[0]?.last_full_day, '2026-08-30');

    const yesterday = (await admin.query<{ day: string }>("SELECT ((now() AT TIME ZONE 'Europe/Moscow')::date - 1)::text AS day")).rows[0]?.day;
    assert.ok(yesterday);
    await admin.query(
      "INSERT INTO fact_cabinet_daily (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256) VALUES ($1, $2, $3, 0, 0, 0, 0, 0, 0, ARRAY[$4]::char(64)[])",
      [tenantId, yesterday, aggregateRun, 'e'.repeat(64)],
    );
    assert.equal((await admin.query('SELECT stale FROM data_status_current WHERE tenant_id = $1', [tenantId])).rows[0]?.stale, false, 'fresh run complete through yesterday is not stale');
    await admin.query("UPDATE collector_runs SET finished_at = CURRENT_TIMESTAMP - interval '25 hours' WHERE run_id = $1", [aggregateRun]);
    assert.equal((await admin.query('SELECT stale FROM data_status_current WHERE tenant_id = $1', [tenantId])).rows[0]?.stale, true, 'collected_at older than 24 hours is stale');
    await admin.query('UPDATE collector_runs SET finished_at = CURRENT_TIMESTAMP WHERE run_id = $1', [aggregateRun]);
    await admin.query('DELETE FROM fact_cabinet_daily WHERE run_id = $1 AND calendar_day = $2', [aggregateRun, yesterday]);
    assert.equal((await admin.query('SELECT stale FROM data_status_current WHERE tenant_id = $1', [tenantId])).rows[0]?.stale, true, 'an old last_full_day is stale even with fresh collected_at');
  } finally {
    await collector.query('ROLLBACK').catch(() => undefined);
    await collector.end();
    await admin.query('DELETE FROM collector_runs WHERE run_id = $1', [aggregateRun]).catch(() => undefined);
    await admin.query('DELETE FROM collector_runs WHERE run_id = $1', [sourceRun]).catch(() => undefined);
    await admin.end();
  }
});

test('cabinet-daily views enforce tenant GUC for norm and webapp', { skip: normDsn && webappDsn && postgresDsn ? false : 'PROXIMA_TEST_DSN_NORM, PROXIMA_TEST_DSN_WEBAPP and PROXIMA_TEST_POSTGRES_DSN must be set' }, async () => {
  const runId = randomUUID();
  const admin = new Client({ connectionString: postgresDsn });
  await admin.connect();
  try {
    await admin.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]);
    await admin.query("INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES ($1, $2, 'collect', 'SUCCEEDED', CURRENT_TIMESTAMP)", [runId, tenantId]);
    await admin.query("INSERT INTO fact_cabinet_daily (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256) VALUES ($1, (now() AT TIME ZONE 'Europe/Moscow')::date - 1, $2, 1, 0, 1, 0, 1, 1, ARRAY[$3]::char(64)[])", [tenantId, runId, 'a'.repeat(64)]);
    for (const dsn of [normDsn, webappDsn]) {
      const reader = new Client({ connectionString: dsn });
      await reader.connect();
      try {
        assert.equal((await reader.query('SELECT count(*)::int AS n FROM data_status_current')).rows[0]?.n, 0);
        await reader.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
        assert.equal((await reader.query('SELECT count(*)::int AS n FROM fact_cabinet_daily_current WHERE run_id = $1', [runId])).rows[0]?.n, 1);
        assert.equal((await reader.query('SELECT count(*)::int AS n FROM data_status_current WHERE tenant_id = $1', [tenantId])).rows[0]?.n, 1);
      } finally { await reader.end(); }
    }
  } finally {
    await admin.query('DELETE FROM collector_runs WHERE run_id = $1', [runId]).catch(() => undefined);
    await admin.end();
  }
});
