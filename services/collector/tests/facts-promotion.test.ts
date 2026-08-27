import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';

import { Pool } from 'pg';

import { makeLineageReference, persistLineageReference, promoteOrderCounts, PromotionError, type PromotionFaultPoint } from '../src/facts/promote-order-counts.js';
import { parsePromotionArgs } from '../src/cli/promotion-args.js';

const dsn = process.env.PROXIMA_TEST_POSTGRES_DSN;

interface Fixture {
  tenantId: string;
  taskId: string;
}

async function sourcePublisherPool(adminPool: Pool): Promise<Pool> {
  const loginRole = `it_source_${randomUUID().replaceAll('-', '').slice(0, 16)}`;
  await adminPool.query(`CREATE ROLE ${loginRole} LOGIN`);
  await adminPool.query(`GRANT proxima_source_publisher TO ${loginRole}`);
  const url = new URL(dsn!);
  url.username = loginRole;
  url.password = '';
  return new Pool({ connectionString: url.toString(), max: 1 });
}

async function seedFixture(pool: Pool, rows: Array<{ nmId: number | null; day: string | null; ordersCount: unknown }>): Promise<Fixture> {
  const tenantId = `it-promotion-${randomUUID().slice(0, 12)}`;
  const taskId = randomUUID();
  const responseId = randomUUID();
  const sha = 'a'.repeat(64);
  await pool.query('INSERT INTO tenants (tenant_id) VALUES ($1)', [tenantId]);
  await pool.query(
    `INSERT INTO wb_analytics_report_tasks
       (task_id, tenant_id, report_type, period_from, period_to, timezone, aggregation_level, request_body,
        lifecycle_status, downloaded_sha256, downloaded_size, downloaded_at)
     VALUES ($1::uuid, $2, 'DETAIL_HISTORY_REPORT', '2026-08-03', '2026-08-09', 'Europe/Moscow', 'day',
             jsonb_build_object('id', ($1::uuid)::text, 'reportType', 'DETAIL_HISTORY_REPORT'),
             'DOWNLOADED', $3, 1, '2026-08-10T09:00:00+03:00')`,
    [taskId, tenantId, sha],
  );
  await pool.query(
    `INSERT INTO raw_wb_analytics_responses
       (response_id, task_id, stage, http_status, response_headers, payload, content_sha256, byte_size, retrieved_at)
     VALUES ($1, $2, 'download', 200, '{}'::jsonb, '{"encoding":"base64","body_base64":""}'::jsonb, $3, 1, '2026-08-10T09:00:00+03:00')`,
    [responseId, taskId, sha],
  );
  for (const [index, row] of rows.entries()) {
    await pool.query(
      `INSERT INTO stg_wb_nm_report_rows (task_id, row_number, nm_id, row_date, payload)
       VALUES ($1, $2, $3, $4, jsonb_build_object('ordersCount', $5::text))`,
      [taskId, index + 1, row.nmId, row.day, String(row.ordersCount)],
    );
  }
  return { tenantId, taskId };
}

async function counts(pool: Pool, taskId: string): Promise<{ attempts: number; facts: number; quarantine: number; lineage: number; quality: number }> {
  const result = await pool.query<{ attempts: string; facts: string; quarantine: string; lineage: string; quality: string }>(
    `SELECT
       (SELECT count(*) FROM fact_attempt_runs WHERE source_ref = $1)::text AS attempts,
       (SELECT count(*) FROM fact_order_counts f JOIN fact_attempt_runs a ON a.attempt_id = f.attempt_id WHERE a.source_ref = $1)::text AS facts,
       (SELECT count(*) FROM stg_quarantine_rows q JOIN fact_attempt_runs a ON a.attempt_id = q.attempt_id WHERE a.source_ref = $1)::text AS quarantine,
       (SELECT count(*) FROM fact_lineage_records l JOIN fact_attempt_runs a ON a.attempt_id = l.attempt_id WHERE a.source_ref = $1)::text AS lineage,
       (SELECT count(*) FROM quality_check_results q JOIN fact_attempt_runs a ON a.attempt_id = q.attempt_id WHERE a.source_ref = $1)::text AS quality`,
    [taskId],
  );
  const row = result.rows[0]!;
  return Object.fromEntries(Object.entries(row).map(([key, value]) => [key, Number(value)])) as { attempts: number; facts: number; quarantine: number; lineage: number; quality: number };
}

test('lineage contract preserves both WB task and dormant file-artifact families', () => {
  const lineage = makeLineageReference({
    sourceFamily: 'file_artifact',
    sourceRef: 'artifact-structural-fixture',
    evidenceSha256: 'b'.repeat(64),
    evidenceLocator: 'artifact://manual/sha256/structural-fixture',
    parserVersion: 'manual-xlsx-v1',
    acquiredVia: 'manual_xlsx_intake',
    acquiredAt: '2026-08-10T06:00:00.000Z',
  });
  assert.equal(lineage.acquiredVia, 'manual_xlsx_intake');
  assert.throws(() => makeLineageReference({ ...lineage, acquiredVia: 'wb_analytics_task' }), PromotionError);
});

test('promotion CLI argument parser accepts only complete unique input', () => {
  assert.deepEqual(
    parsePromotionArgs(['--tenant', 'tenant-a', '--task-id', 'task-a', '--database-url-file', '/tmp/database-url']),
    {
      tenant: 'tenant-a',
      'task-id': 'task-a',
      'database-url-file': '/tmp/database-url',
    },
  );
  assert.throws(() => parsePromotionArgs([]), { code: 'PROMOTION_FAILED' });
  assert.throws(
    () => parsePromotionArgs(['--tenant', 'tenant-a', '--tenant', 'tenant-b']),
    { code: 'PROMOTION_FAILED' },
  );
});

test('promotion writes accepted facts, typed quarantine, lineage and quality in one attempt', { skip: !dsn }, async () => {
  const pool = new Pool({ connectionString: dsn, max: 1 });
  const sourcePool = await sourcePublisherPool(pool);
  try {
    const fixture = await seedFixture(pool, [
      { nmId: 101, day: '2026-08-03', ordersCount: '2' },
      { nmId: null, day: '2026-08-04', ordersCount: '1' },
      { nmId: 102, day: null, ordersCount: '1' },
      { nmId: 103, day: '2026-08-05', ordersCount: '-1' },
      { nmId: 101, day: '2026-08-03', ordersCount: '4' },
      { nmId: 104, day: '2026-08-10', ordersCount: '1' },
    ]);
    await assert.rejects(promoteOrderCounts(pool, fixture), { code: 'SOURCE_ROLE_REQUIRED' });
    const result = await promoteOrderCounts(sourcePool, fixture);
    assert.deepEqual({ status: result.status, acceptedRows: result.acceptedRows, quarantinedRows: result.quarantinedRows }, { status: 'SUCCEEDED', acceptedRows: 1, quarantinedRows: 5 });
    assert.deepEqual(await counts(pool, fixture.taskId), { attempts: 1, facts: 1, quarantine: 5, lineage: 1, quality: 3 });
    const reasons = await pool.query<{ reason: string }>(
      `SELECT q.reason FROM stg_quarantine_rows q JOIN fact_attempt_runs a ON a.attempt_id = q.attempt_id WHERE a.source_ref = $1 ORDER BY q.source_row_number`,
      [fixture.taskId],
    );
    assert.deepEqual(reasons.rows.map((row) => row.reason), ['INVALID_PRODUCT', 'INVALID_DATE', 'INVALID_COUNT', 'DUPLICATE_GRAIN', 'STALE']);
  } finally {
    await sourcePool.end();
    await pool.end();
  }
});

test('all-invalid promotion persists a typed failed attempt without facts', { skip: !dsn }, async () => {
  const pool = new Pool({ connectionString: dsn, max: 1 });
  const sourcePool = await sourcePublisherPool(pool);
  try {
    const fixture = await seedFixture(pool, [{ nmId: null, day: null, ordersCount: '-1' }]);
    const result = await promoteOrderCounts(sourcePool, fixture);
    assert.deepEqual({ status: result.status, acceptedRows: result.acceptedRows, quarantinedRows: result.quarantinedRows }, { status: 'FAILED', acceptedRows: 0, quarantinedRows: 1 });
    assert.deepEqual(await counts(pool, fixture.taskId), { attempts: 1, facts: 0, quarantine: 1, lineage: 0, quality: 3 });
    const failure = await pool.query<{ status: string; failure_code: string }>('SELECT status, failure_code FROM fact_attempt_runs WHERE source_ref = $1', [fixture.taskId]);
    assert.deepEqual(failure.rows[0], { status: 'FAILED', failure_code: 'ALL_ROWS_QUARANTINED' });
  } finally {
    await sourcePool.end();
    await pool.end();
  }
});

test('each forced write-boundary failure rolls back fully and a retry is idempotent', { skip: !dsn }, async () => {
  const points: PromotionFaultPoint[] = ['after_attempt', 'after_quarantine', 'after_fact', 'after_lineage', 'after_quality', 'after_success'];
  const pool = new Pool({ connectionString: dsn, max: 1 });
  const sourcePool = await sourcePublisherPool(pool);
  try {
    for (const point of points) {
      const fixture = await seedFixture(pool, [
        { nmId: 201, day: '2026-08-03', ordersCount: '2' },
        { nmId: null, day: '2026-08-04', ordersCount: '1' },
      ]);
      await assert.rejects(
        promoteOrderCounts(sourcePool, fixture, { afterWrite: (current) => { if (current === point) throw new Error(`forced-${point}`); } }),
        { code: 'PROMOTION_FAILED' },
      );
      assert.deepEqual(await counts(pool, fixture.taskId), { attempts: 0, facts: 0, quarantine: 0, lineage: 0, quality: 0 });
      const retry = await promoteOrderCounts(sourcePool, fixture);
      assert.equal(retry.status, 'SUCCEEDED');
      assert.deepEqual(await counts(pool, fixture.taskId), { attempts: 1, facts: 1, quarantine: 1, lineage: 1, quality: 3 });
    }
  } finally {
    await sourcePool.end();
    await pool.end();
  }
});

test('file-artifact lineage persists through the shared source-publisher path', { skip: !dsn }, async () => {
  const pool = new Pool({ connectionString: dsn, max: 1 });
  const sourcePool = await sourcePublisherPool(pool);
  try {
    const tenantId = `it-artifact-${randomUUID().slice(0, 12)}`;
    const attemptId = randomUUID();
    const contentSha = 'c'.repeat(64);
    const manifestSha = 'd'.repeat(64);
    const intakeAttemptId = `attempt:sha256:${'e'.repeat(64)}`;
    const artifactId = `artifact:sha256:${contentSha}`;
    const retrievedAt = '2026-08-10T06:00:00.000Z';
    await pool.query('INSERT INTO tenants (tenant_id) VALUES ($1)', [tenantId]);
    await pool.query(
      `INSERT INTO source_artifacts (artifact_id, content_sha256, content_size, object_locator)
       VALUES ($1, $2, 1, $3)`,
      [artifactId, contentSha, `artifact://sha256/${contentSha}`],
    );
    await pool.query(
      `INSERT INTO artifact_manifests (artifact_id, manifest_sha256, manifest_locator, schema_version)
       VALUES ($1, $2, $3, 1)`,
      [artifactId, manifestSha, `artifact://manifest/sha256/${manifestSha}`],
    );
    await pool.query(
      `INSERT INTO intake_attempts
         (attempt_id, tenant_id, artifact_id, source, dataset, period_from, period_to, data_as_of, retrieved_at, source_schema_version)
       VALUES ($1, $2, $3, 'official_wb_manual', 'orders', '2026-08-03', '2026-08-03', $4, $4, 'manual-xlsx-v1')`,
      [intakeAttemptId, tenantId, artifactId, retrievedAt],
    );
    await pool.query(
      `INSERT INTO fact_attempt_runs (attempt_id, tenant_id, source_family, source_ref, status)
       VALUES ($1, $2, 'file_artifact', $3, 'RUNNING')`,
      [attemptId, tenantId, intakeAttemptId],
    );
    await persistLineageReference(sourcePool, {
      tenantId,
      attemptId,
      lineage: makeLineageReference({
        sourceFamily: 'file_artifact',
        sourceRef: intakeAttemptId,
        evidenceSha256: contentSha,
        evidenceLocator: `artifact://sha256/${contentSha}`,
        parserVersion: 'manual-xlsx-v1',
        acquiredVia: 'manual_xlsx_intake',
        acquiredAt: retrievedAt,
      }),
    });
    await assert.rejects(
      persistLineageReference(sourcePool, {
        tenantId,
        attemptId,
        lineage: makeLineageReference({
          sourceFamily: 'file_artifact',
          sourceRef: intakeAttemptId,
          evidenceSha256: 'f'.repeat(64),
          evidenceLocator: `artifact://sha256/${contentSha}`,
          parserVersion: 'manual-xlsx-v1',
          acquiredVia: 'manual_xlsx_intake',
          acquiredAt: retrievedAt,
        }),
      }),
      { code: 'SOURCE_NOT_FOUND' },
    );
    const lineage = await pool.query<{ acquired_via: string; evidence_sha256: string }>('SELECT acquired_via, evidence_sha256 FROM fact_lineage_records WHERE attempt_id = $1', [attemptId]);
    assert.deepEqual(lineage.rows[0], { acquired_via: 'manual_xlsx_intake', evidence_sha256: contentSha });
  } finally {
    await sourcePool.end();
    await pool.end();
  }
});
