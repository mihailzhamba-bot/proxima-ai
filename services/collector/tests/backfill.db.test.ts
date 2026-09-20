import assert from 'node:assert/strict';
import test from 'node:test';

import { openBackfillHarness, tenantId } from './support/backfill-harness.js';

const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const skip = collectorDsn && postgresDsn ? false : 'run via tools/pg_local_roundtrip.sh';

test('backfill: artifact replay + pagination', { skip }, async () => {
  const h = await openBackfillHarness(collectorDsn, postgresDsn);
  try {
    const first = await h.run();
    assert.equal(first.runDay, '2026-08-30');
    assert.deepEqual({ orders: first.orders.inserted, sales: first.sales.inserted, days: first.aggregate.days }, { orders: 2, sales: 2, days: 13 });
    const replay = await h.run();
    assert.deepEqual({ orders: replay.orders.inserted, sales: replay.sales.inserted }, { orders: 0, sales: 0 });
    const observations = await h.admin.query<{ first_day: string; last_day: string }>(
      `SELECT min((payload->>'date')::date)::text AS first_day, max((payload->>'date')::date)::text AS last_day FROM (
       SELECT payload FROM stg_wb_orders_obs WHERE tenant_id=$1 UNION ALL SELECT payload FROM stg_wb_sales_obs WHERE tenant_id=$1) x`, [tenantId],
    );
    assert.deepEqual(observations.rows[0], { first_day: '2026-08-17', last_day: '2026-08-24' });
    const sums = await h.admin.query(
      'SELECT count(*)::int AS days, sum(orders_count)::int AS orders, sum(cancelled_count)::int AS cancelled, sum(sales_count)::int AS sales, sum(returns_count)::int AS returns, sum(revenue_rub)::text AS revenue, sum(forpay_rub)::text AS forpay FROM fact_cabinet_daily WHERE run_id=$1',
      [replay.runId],
    );
    assert.deepEqual(sums.rows[0], { days: 13, orders: 1, cancelled: 1, sales: 1, returns: 1, revenue: '12.50', forpay: '10.00' });
    assert.equal((await h.admin.query('SELECT count(*)::int AS n FROM wb_raw_artifacts WHERE run_id=$1', [replay.runId])).rows[0]?.n, 2);
  } finally { await h.cleanup(); }
});
