import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';

import { Pool } from 'pg';

import { fileArtifactLineage, promoteOrderCounts } from '../src/facts/promote-order-counts.js';

const dsn = process.env.PROXIMA_TEST_POSTGRES_DSN;
const enabled = dsn !== undefined;

type Fixture = {
  pool: Pool;
  tenantId: string;
  taskId: string;
};

async function promote(pool: Pool, input: Parameters<typeof promoteOrderCounts>[1]) {
  const client = await pool.connect();
  try {
    return await promoteOrderCounts(client, input);
  } finally {
    client.release();
  }
}

async function promoteAsRole(pool: Pool, role: 'proxima_source_publisher' | 'proxima_release_publisher', input: Parameters<typeof promoteOrderCounts>[1]) {
  const client = await pool.connect();
  try {
    await client.query(`SET ROLE ${role}`);
    return await promoteOrderCounts(client, input);
  } finally {
    await client.query('RESET ROLE').catch(() => {});
    client.release();
  }
}

async function fixture(rows: Array<{ nmId: number | null; day: string | null; ordersCount: unknown }>): Promise<Fixture> {
  const pool = new Pool({ connectionString: dsn, max: 1 });
  const tenantId = `promotion-${randomUUID().slice(0, 8)}`;
  const taskId = randomUUID();
  await pool.query('INSERT INTO tenants (tenant_id) VALUES ($1)', [tenantId]);
  await pool.query(
    `INSERT INTO wb_analytics_report_tasks
       (task_id, tenant_id, report_type, period_from, period_to, timezone, aggregation_level, request_body, lifecycle_status, downloaded_sha256, downloaded_size, downloaded_at)
     VALUES ($1, $2, 'DETAIL_HISTORY_REPORT', '2026-08-03', '2026-08-09', 'Europe/Moscow', 'day', $3, 'DOWNLOADED', $4, 1, CURRENT_TIMESTAMP)`,
    [taskId, tenantId, JSON.stringify({ id: taskId, reportType: 'DETAIL_HISTORY_REPORT' }), 'a'.repeat(64)],
  );
  await pool.query(
    `INSERT INTO raw_wb_analytics_responses
       (response_id, task_id, stage, http_status, response_headers, payload, content_sha256, byte_size, retrieved_at)
     VALUES ($1, $2, 'download', 200, '{}', $3, $4, 1, CURRENT_TIMESTAMP)`,
    [randomUUID(), taskId, JSON.stringify({ encoding: 'base64', body_base64: 'eA==' }), 'a'.repeat(64)],
  );
  for (const [index, row] of rows.entries()) {
    await pool.query(
      'INSERT INTO stg_wb_nm_report_rows (task_id, row_number, nm_id, row_date, payload) VALUES ($1, $2, $3, $4, $5)',
      [taskId, index + 1, row.nmId, row.day, JSON.stringify({ ordersCount: row.ordersCount })],
    );
  }
  return { pool, tenantId, taskId };
}

test('promotes valid rows, quarantines typed failures, and records lineage', { skip: !enabled }, async () => {
  const data = await fixture([
    { nmId: 101, day: '2026-08-03', ordersCount: 2 },
    { nmId: null, day: '2026-08-04', ordersCount: 3 },
    { nmId: 102, day: '2026-08-04', ordersCount: -1 },
    { nmId: 101, day: '2026-08-03', ordersCount: 2 },
    { nmId: 103, day: '2026-08-10', ordersCount: 1 },
    { nmId: 104, day: null, ordersCount: 1 },
  ]);
  try {
    const result = await promote(data.pool, { tenantId: data.tenantId, taskId: data.taskId, parserVersion: 'test-v1' });
    assert.equal(result.status, 'SUCCEEDED');
    assert.deepEqual(result, { attemptId: result.attemptId, status: 'SUCCEEDED', accepted: 1, quarantined: 5 });
    const [facts, quarantine, lineage, checks, attempt] = await Promise.all([
      data.pool.query('SELECT nm_id::text, calendar_day::text, order_count FROM fact_order_counts WHERE attempt_id = $1', [result.attemptId]),
      data.pool.query('SELECT reason FROM stg_quarantine_rows WHERE attempt_id = $1 ORDER BY source_row_number', [result.attemptId]),
      data.pool.query('SELECT evidence_sha256, parser_version, acquired_via FROM fact_lineage_records WHERE attempt_id = $1', [result.attemptId]),
      data.pool.query('SELECT check_name, status FROM quality_check_results WHERE attempt_id = $1 ORDER BY check_name', [result.attemptId]),
      data.pool.query('SELECT status, finished_at IS NOT NULL AS finished FROM fact_attempt_runs WHERE attempt_id = $1', [result.attemptId]),
    ]);
    assert.deepEqual(facts.rows, [{ nm_id: '101', calendar_day: '2026-08-03', order_count: 2 }]);
    assert.deepEqual(quarantine.rows.map((row) => row.reason), ['INVALID_PRODUCT', 'INVALID_COUNT', 'DUPLICATE_GRAIN', 'STALE', 'INVALID_DATE']);
    assert.deepEqual(lineage.rows, [{ evidence_sha256: 'a'.repeat(64), parser_version: 'test-v1', acquired_via: 'wb_analytics_task' }]);
    assert.deepEqual(checks.rows, [
      { check_name: 'accepted_quarantined_counts', status: 'PASS' },
      { check_name: 'date_window_sanity', status: 'PASS' },
      { check_name: 'grain_uniqueness', status: 'PASS' },
    ]);
    assert.deepEqual(attempt.rows, [{ status: 'SUCCEEDED', finished: true }]);
  } finally {
    await data.pool.end();
  }
});

test('source publisher can complete promotion and release publisher is denied', { skip: !enabled }, async () => {
  const source = await fixture([{ nmId: 101, day: '2026-08-03', ordersCount: 2 }]);
  const release = await fixture([{ nmId: 102, day: '2026-08-03', ordersCount: 3 }]);
  try {
    const completed = await promoteAsRole(source.pool, 'proxima_source_publisher', {
      tenantId: source.tenantId,
      taskId: source.taskId,
      parserVersion: 'role-gated-v1',
    });
    assert.deepEqual(completed, { attemptId: completed.attemptId, status: 'SUCCEEDED', accepted: 1, quarantined: 0 });

    await assert.rejects(
      promoteAsRole(release.pool, 'proxima_release_publisher', {
        tenantId: release.tenantId,
        taskId: release.taskId,
        parserVersion: 'role-gated-v1',
      }),
      (error: unknown) => typeof error === 'object' && error !== null && 'code' in error && error.code === '42501',
    );
  } finally {
    await Promise.all([source.pool.end(), release.pool.end()]);
  }
});

for (const boundary of ['attempt', 'quarantine', 'fact', 'lineage', 'quality', 'success'] as const) {
  test(`rolls back completely after injected ${boundary} write`, { skip: !enabled }, async () => {
    const data = await fixture([{ nmId: 101, day: '2026-08-03', ordersCount: 2 }, { nmId: null, day: '2026-08-04', ordersCount: 2 }]);
    try {
      await assert.rejects(
        promote(data.pool, {
          tenantId: data.tenantId,
          taskId: data.taskId,
          parserVersion: 'test-v1',
          afterWrite: (written) => { if (written === boundary) throw new Error(`injected-${boundary}`); },
        }),
        new RegExp(`injected-${boundary}`),
      );
      const count = async (table: string): Promise<number> => Number((await data.pool.query(`SELECT count(*)::int AS count FROM ${table} WHERE tenant_id = $1`, [data.tenantId])).rows[0]?.count);
      assert.deepEqual(await Promise.all(['fact_attempt_runs', 'stg_quarantine_rows', 'fact_order_counts', 'fact_lineage_records', 'quality_check_results'].map(count)), [0, 0, 0, 0, 0]);
      const retry = await promote(data.pool, { tenantId: data.tenantId, taskId: data.taskId, parserVersion: 'test-v1' });
      assert.equal(retry.status, 'SUCCEEDED');
      assert.deepEqual(await Promise.all(['fact_attempt_runs', 'stg_quarantine_rows', 'fact_order_counts', 'fact_lineage_records', 'quality_check_results'].map(count)), [1, 1, 1, 1, 3]);
    } finally {
      await data.pool.end();
    }
  });
}

test('commits a visible failed attempt when every row is quarantined', { skip: !enabled }, async () => {
  const data = await fixture([{ nmId: null, day: null, ordersCount: 'bad' }]);
  try {
    const result = await promote(data.pool, { tenantId: data.tenantId, taskId: data.taskId, parserVersion: 'test-v1' });
    assert.deepEqual(result, { attemptId: result.attemptId, status: 'FAILED', accepted: 0, quarantined: 1 });
    const attempt = await data.pool.query('SELECT status, failure_code FROM fact_attempt_runs WHERE attempt_id = $1', [result.attemptId]);
    assert.deepEqual(attempt.rows, [{ status: 'FAILED', failure_code: 'ALL_ROWS_QUARANTINED' }]);
  } finally {
    await data.pool.end();
  }
});

test('keeps dormant file-artifact lineage in the unified record shape', () => {
  assert.deepEqual(fileArtifactLineage({ evidenceSha256: 'b'.repeat(64), evidenceLocator: 'source_artifacts/example.xlsx', parserVersion: 'xlsx-v1' }), {
    sourceFamily: 'file_artifact',
    acquiredVia: 'manual_xlsx_intake',
    evidenceSha256: 'b'.repeat(64),
    evidenceLocator: 'source_artifacts/example.xlsx',
    parserVersion: 'xlsx-v1',
  });
});
