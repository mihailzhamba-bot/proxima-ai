import assert from 'node:assert/strict';
import test from 'node:test';

import { Client } from 'pg';

import { openBackfillHarness, tenantId } from './support/backfill-harness.js';

const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const normDsn = process.env.PROXIMA_TEST_DSN_NORM ?? '';
const webappDsn = process.env.PROXIMA_TEST_DSN_WEBAPP ?? '';
const skip = collectorDsn && postgresDsn ? false : 'run via tools/pg_local_roundtrip.sh';

test('cabinet-daily: versions every artifact day, S1/S2 sums through backfill', { skip }, async () => {
  const h = await openBackfillHarness(collectorDsn, postgresDsn);
  try {
    const result = await h.run();
    const sums = await h.admin.query(
      'SELECT count(*)::int AS days, sum(orders_count)::int AS orders, sum(cancelled_count)::int AS cancelled, sum(sales_count)::int AS sales, sum(returns_count)::int AS returns, sum(revenue_rub)::text AS revenue, sum(forpay_rub)::text AS forpay FROM fact_cabinet_daily_current WHERE tenant_id=$1 AND calendar_day BETWEEN $2 AND $3',
      [tenantId, '2026-08-17', '2026-08-29'],
    );
    assert.deepEqual(sums.rows[0], { days: 13, orders: 1, cancelled: 1, sales: 1, returns: 1, revenue: '12.50', forpay: '10.00' });
    assert.equal((await h.admin.query('SELECT count(*)::int AS n FROM fact_cabinet_daily WHERE run_id=$1 AND calendar_day=$2', [result.runId, '2026-08-30'])).rows[0]?.n, 0);
    assert.equal((await h.admin.query('SELECT count(*)::int AS n FROM collector_run_inputs WHERE run_id=$1', [result.runId])).rows[0]?.n, 0, 'artifact observations belong to the backfill run itself');
    const yesterday = (await h.admin.query<{ day: string }>("SELECT ((now() AT TIME ZONE 'Europe/Moscow')::date - 1)::text AS day")).rows[0]?.day;
    assert.ok(yesterday);
    await h.admin.query('UPDATE fact_cabinet_daily SET calendar_day=$2 WHERE run_id=$1 AND calendar_day=$3', [result.runId, yesterday, '2026-08-29']);
    assert.equal((await h.admin.query('SELECT stale FROM data_status_current WHERE tenant_id=$1', [tenantId])).rows[0]?.stale, false, 'fresh backfill complete through yesterday is not stale');
    await h.admin.query("UPDATE collector_runs SET finished_at=CURRENT_TIMESTAMP - interval '25 hours' WHERE run_id=$1", [result.runId]);
    assert.equal((await h.admin.query('SELECT stale FROM data_status_current WHERE tenant_id=$1', [tenantId])).rows[0]?.stale, true, 'a backfill older than 24 hours is stale');
    // AD-7: stale has two independent causes. The second one - a fresh collection
    // that nonetheless stops short of yesterday - is the reason the OR exists, so
    // it needs its own case: a fresh finished_at must not hide an old last_full_day.
    await h.admin.query('UPDATE collector_runs SET finished_at=CURRENT_TIMESTAMP WHERE run_id=$1', [result.runId]);
    await h.admin.query('UPDATE fact_cabinet_daily SET calendar_day=$2::date - 3 WHERE run_id=$1 AND calendar_day=$2', [result.runId, yesterday]);
    const behind = (await h.admin.query('SELECT last_full_day::text AS day, stale FROM data_status_current WHERE tenant_id=$1', [tenantId])).rows[0];
    assert.equal(behind?.stale, true, 'a fresh run that stops short of yesterday is still stale');
    assert.equal(behind?.day, (await h.admin.query<{ d: string }>('SELECT ($1::date - 3)::text AS d', [yesterday])).rows[0]?.d, 'last_full_day is the newest versioned day, not the run time');
  } finally { await h.cleanup(); }
});

test('cabinet-daily: a second run records the first run as its input (AD-3 closure)', { skip }, async () => {
  // The transitive closure tools/delete_run.py walks is built from collector_run_inputs.
  // A single backfill owns its own observations, so the link only appears once a second
  // run aggregates versions someone else collected - that is the case worth pinning.
  const h = await openBackfillHarness(collectorDsn, postgresDsn);
  try {
    const first = await h.run();
    const second = await h.run();
    assert.notEqual(second.runId, first.runId);
    const inputs = await h.admin.query<{ input_run_id: string }>(
      'SELECT input_run_id::text FROM collector_run_inputs WHERE tenant_id=$1 AND run_id=$2',
      [tenantId, second.runId],
    );
    assert.deepEqual(inputs.rows.map((row) => row.input_run_id), [first.runId], 'the replay names the run whose observations it rolled up');
    assert.equal((await h.admin.query('SELECT count(*)::int AS n FROM collector_run_inputs WHERE run_id=$1', [first.runId])).rows[0]?.n, 0);
  } finally { await h.cleanup(); }
});

test('cabinet-daily views enforce tenant GUC for norm and webapp using backfill data', { skip: normDsn && webappDsn && collectorDsn && postgresDsn ? false : 'DB role DSNs are required' }, async () => {
  const h = await openBackfillHarness(collectorDsn, postgresDsn);
  try {
    const result = await h.run();
    for (const dsn of [normDsn, webappDsn]) {
      const reader = new Client({ connectionString: dsn });
      await reader.connect();
      try {
        assert.equal((await reader.query('SELECT count(*)::int AS n FROM data_status_current')).rows[0]?.n, 0);
        await reader.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
        assert.equal((await reader.query('SELECT count(*)::int AS n FROM fact_cabinet_daily_current WHERE run_id=$1', [result.runId])).rows[0]?.n, 13);
        assert.equal((await reader.query('SELECT count(*)::int AS n FROM data_status_current WHERE tenant_id=$1', [tenantId])).rows[0]?.n, 1);
      } finally { await reader.end(); }
    }
  } finally { await h.cleanup(); }
});
