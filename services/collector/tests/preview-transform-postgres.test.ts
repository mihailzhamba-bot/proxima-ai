import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { after, before, test } from 'node:test';

import { Pool } from 'pg';

import { PreviewTransformError, transformStagingToPreview } from '../src/staging/preview-transform.js';

const dsn = process.env.PROXIMA_TEST_POSTGRES_DSN;
const MIGRATIONS_DIR = join(import.meta.dirname, '../../..', 'db', 'migrations');
const TENANT = 'preview-transform-test';

interface SeedRow {
  nmId: string | null;
  rowDate: string | null;
  ordersCount: string | null;
}

interface PoolFixture {
  pool: Pool;
}

const fixture: PoolFixture = { pool: undefined as unknown as Pool };

before(async () => {
  if (!dsn) return;
  const pool = new Pool({ connectionString: dsn, max: 2, application_name: 'preview-transform-test' });
  const client = await pool.connect();
  try {
    const ledger = await client.query<{ table_name: string | null }>(
      "SELECT to_regclass('public.schema_migrations') AS table_name",
    );
    const existing = new Set<number>();
    if (ledger.rows[0]?.table_name !== null) {
      for (const row of (await client.query<{ version: number }>('SELECT version FROM schema_migrations')).rows) {
        existing.add(row.version);
      }
    }
    const { readdir } = await import('node:fs/promises');
    const names = (await readdir(MIGRATIONS_DIR)).filter((name) => name.endsWith('.sql')).sort();
    for (const name of names) {
      const version = Number(name.slice(0, 3));
      if (existing.has(version)) continue;
      await client.query(await readFile(join(MIGRATIONS_DIR, name), 'utf8'));
    }
    for (const statement of [
      'DELETE FROM preview_order_counts WHERE tenant_id = $1',
      `DELETE FROM preview_quarantine_rows WHERE task_id IN (SELECT task_id FROM wb_analytics_report_tasks WHERE tenant_id = $1)`,
      'DELETE FROM artifact_parse_runs WHERE tenant_id = $1',
      `DELETE FROM stg_wb_nm_report_rows WHERE task_id IN (SELECT task_id FROM wb_analytics_report_tasks WHERE tenant_id = $1)`,
      'DELETE FROM wb_analytics_report_tasks WHERE tenant_id = $1',
      'DELETE FROM tenants WHERE tenant_id = $1',
    ]) {
      await client.query(statement, [TENANT]);
    }
  } finally {
    client.release();
  }
  fixture.pool = pool;
});

after(async () => {
  if (fixture.pool) await fixture.pool.end();
});

let seedSequence = 0;

async function seedTask(
  rows: SeedRow[],
  options: { lifecycleStatus?: string; declaredRowCount?: number } = {},
): Promise<string> {
  const taskId = randomUUID();
  const artifactSha = randomBytes(32).toString('hex');
  seedSequence += 1;
  const periodFrom = `2026-01-${String(1 + (seedSequence % 20)).padStart(2, '0')}`;
  const periodTo = `2026-02-${String(1 + (seedSequence % 20)).padStart(2, '0')}`;
  const client = await fixture.pool.connect();
  try {
    await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [TENANT]);
    await client.query(
      `INSERT INTO wb_analytics_report_tasks
       (task_id, tenant_id, report_type, period_from, period_to, timezone, aggregation_level,
        request_body, lifecycle_status, api_status, downloaded_sha256, downloaded_size, downloaded_at,
        parsed_row_count, staged_row_count)
       VALUES ($1::uuid, $2, 'DETAIL_HISTORY_REPORT', $3::date, $4::date, 'Europe/Moscow', 'day',
        jsonb_build_object('id', $1::uuid::text, 'reportType', 'DETAIL_HISTORY_REPORT'),
        $5, 'SUCCESS', $6, 1234, CURRENT_TIMESTAMP, $7, $7)`,
      [taskId, TENANT, periodFrom, periodTo, options.lifecycleStatus ?? 'DOWNLOADED', artifactSha, options.declaredRowCount ?? rows.length],
    );
    let rowNumber = 0;
    for (const row of rows) {
      rowNumber += 1;
      await client.query(
        `INSERT INTO stg_wb_nm_report_rows (task_id, row_number, nm_id, row_date, payload)
         VALUES ($1::uuid, $2, $3::bigint, $4::date, jsonb_build_object('nmID', $5::text, 'dt', $6::text, 'ordersCount', $7::text))`,
        [taskId, rowNumber, row.nmId, row.rowDate, row.nmId ?? '', row.rowDate ?? '', row.ordersCount ?? ''],
      );
    }
  } finally {
    client.release();
  }
  return taskId;
}

const DEFAULT_ROWS: SeedRow[] = [
  { nmId: '11051441', rowDate: '2026-07-15', ordersCount: '3' },
  { nmId: '11051441', rowDate: '2026-07-15', ordersCount: '2' },
  { nmId: '11051442', rowDate: '2026-07-16', ordersCount: '1' },
  { nmId: null, rowDate: '2026-07-16', ordersCount: '1' },
  { nmId: '11051443', rowDate: null, ordersCount: '1' },
  { nmId: '11051444', rowDate: '2026-07-17', ordersCount: 'not-a-number' },
];

async function visibleCounts(taskId: string): Promise<{ runs: number; preview: number; quarantine: number }> {
  const result = await fixture.pool.query<{ runs: string; preview: string; quarantine: string }>(
    `SELECT
       (SELECT count(*) FROM artifact_parse_runs WHERE task_id = $1::uuid) AS runs,
       (SELECT count(*) FROM preview_order_counts WHERE task_id = $1::uuid) AS preview,
       (SELECT count(*) FROM preview_quarantine_rows WHERE task_id = $1::uuid) AS quarantine`,
    [taskId],
  );
  const row = result.rows[0];
  assert.ok(row);
  return { runs: Number(row.runs), preview: Number(row.preview), quarantine: Number(row.quarantine) };
}

test('transform creates one complete preview set and stays idempotent on retry', { skip: !dsn }, async () => {
  const taskId = await seedTask(DEFAULT_ROWS);
  const first = await transformStagingToPreview(fixture.pool, { tenantId: TENANT, taskId });
  assert.equal(first.state, 'created');
  assert.equal(first.stagedRowCount, 6);
  assert.equal(first.validRowCount, 3);
  assert.equal(first.quarantinedRowCount, 3);
  assert.equal(first.previewRowCount, 2);

  const facts = await fixture.pool.query<{ calendar_day: string; nm_id: string; order_count: number; release_status: string }>(
    'SELECT calendar_day::text, nm_id::text, order_count, release_status FROM preview_order_counts WHERE task_id = $1::uuid ORDER BY calendar_day, nm_id',
    [taskId],
  );
  assert.deepEqual(
    facts.rows.map((row) => [row.calendar_day, row.nm_id, row.order_count, row.release_status]),
    [
      ['2026-07-15', '11051441', 5, 'unreleased'],
      ['2026-07-16', '11051442', 1, 'unreleased'],
    ],
  );

  const second = await transformStagingToPreview(fixture.pool, { tenantId: TENANT, taskId });
  assert.equal(second.state, 'existing');
  assert.equal(second.runId, first.runId);
  assert.deepEqual(await visibleCounts(taskId), { runs: 1, preview: 2, quarantine: 3 });
});

test('transform rejects a task that is not downloaded', { skip: !dsn }, async () => {
  const taskId = await seedTask(DEFAULT_ROWS, { lifecycleStatus: 'WAITING' });
  await assert.rejects(
    transformStagingToPreview(fixture.pool, { tenantId: TENANT, taskId }),
    (error: unknown) => error instanceof PreviewTransformError && error.code === 'TASK_NOT_DOWNLOADED',
  );
  assert.deepEqual(await visibleCounts(taskId), { runs: 0, preview: 0, quarantine: 0 });
});

test('transform rejects a tenant mismatch', { skip: !dsn }, async () => {
  const taskId = await seedTask(DEFAULT_ROWS);
  await assert.rejects(
    transformStagingToPreview(fixture.pool, { tenantId: 'another-tenant', taskId }),
    (error: unknown) => error instanceof PreviewTransformError && error.code === 'TENANT_MISMATCH',
  );
});

test('transform rejects a staged count drift', { skip: !dsn }, async () => {
  const taskId = await seedTask(DEFAULT_ROWS.slice(0, 3), { declaredRowCount: DEFAULT_ROWS.length });
  await assert.rejects(
    transformStagingToPreview(fixture.pool, { tenantId: TENANT, taskId }),
    (error: unknown) => error instanceof PreviewTransformError && error.code === 'STAGED_COUNT_MISMATCH',
  );
  assert.deepEqual(await visibleCounts(taskId), { runs: 0, preview: 0, quarantine: 0 });
});

for (const crashPoint of ['after_run_created', 'after_quarantine_written', 'after_preview_written', 'after_success_marker'] as const) {
  test(`crash at ${crashPoint} rolls back and a retry produces exactly one complete set`, { skip: !dsn }, async () => {
    const taskId = await seedTask(DEFAULT_ROWS);
    await assert.rejects(
      transformStagingToPreview(fixture.pool, {
        tenantId: TENANT,
        taskId,
        hooks: {
          at: (point) => {
            if (point === crashPoint) throw new Error(`injected crash at ${point}`);
          },
        },
      }),
      (error: unknown) => error instanceof PreviewTransformError && error.message.includes('injected crash'),
    );
    assert.deepEqual(await visibleCounts(taskId), { runs: 0, preview: 0, quarantine: 0 });

    const retried = await transformStagingToPreview(fixture.pool, { tenantId: TENANT, taskId });
    assert.equal(retried.state, 'created');
    assert.deepEqual(await visibleCounts(taskId), { runs: 1, preview: 2, quarantine: 3 });

    const totals = await fixture.pool.query<{ total: string }>(
      'SELECT sum(order_count) AS total FROM preview_order_counts WHERE task_id = $1::uuid',
      [taskId],
    );
    assert.equal(totals.rows[0]?.total, '6');

    const again = await transformStagingToPreview(fixture.pool, { tenantId: TENANT, taskId });
    assert.equal(again.state, 'existing');
    assert.deepEqual(await visibleCounts(taskId), { runs: 1, preview: 2, quarantine: 3 });
  });
}
