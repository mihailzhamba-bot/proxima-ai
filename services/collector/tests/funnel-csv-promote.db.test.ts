import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import test from 'node:test';

import { Client } from 'pg';

import { promoteFunnelCsv } from '../src/jobs/funnel-csv-promote.js';
import { canonicalJson, sha256 } from '../src/intake/manifest.js';

const execFileAsync = promisify(execFile);
const collectorDsn = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const janitorDsn = process.env.PROXIMA_TEST_DSN_JANITOR ?? '';
const postgresDsn = process.env.PROXIMA_TEST_POSTGRES_DSN ?? '';
const python = process.env.PROXIMA_TEST_PYTHON ?? '';
const ready = collectorDsn !== '' && janitorDsn !== '' && postgresDsn !== '' && python !== '';
const skip = ready ? false : 'run via tools/pg_local_roundtrip.sh with collector, janitor, postgres DSNs and project Python';
const tenantId = 'funnel-csv-harness';
const fixturePath = resolve('services/collector/tests/fixtures/wb-api/analytics/nm_report_downloads/funnel_csv_promote.json');

async function admin<T>(work: (client: Client) => Promise<T>): Promise<T> {
  const client = new Client({ connectionString: postgresDsn });
  await client.connect();
  try { return await work(client); }
  finally { await client.end(); }
}

async function count(client: Client, table: string, where: string, values: unknown[] = []): Promise<number> {
  const result = await client.query<{ n: string }>(`SELECT count(*) AS n FROM ${table} WHERE ${where}`, values);
  return Number(result.rows[0]?.n);
}

test('funnel_csv: promote, csv preference, delete_run and replay without a new report', { skip }, async () => {
  const downloadRun = randomUUID();
  const v3Run = randomUUID();
  const taskId = randomUUID();
  const reportSha = 'c'.repeat(64);
  const fixture = JSON.parse(await readFile(fixturePath, 'utf8')) as Record<string, string>[];
  const temp = await mkdtemp(join(tmpdir(), 'proxima-funnel-csv-'));
  const uriFile = join(temp, 'collector-uri');
  await writeFile(uriFile, `${collectorDsn}\n`, { mode: 0o600 });
  const openedRuns: string[] = [];
  const env = { COLLECTOR_DATABASE_URI_FILE: uriFile };
  try {
    await admin(async (client) => {
      await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]);
      await client.query(
        `INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES
         ($1, $3, 'funnel_csv_download', 'SUCCEEDED', CURRENT_TIMESTAMP - interval '2 minutes'),
         ($2, $3, 'funnel_v3', 'SUCCEEDED', CURRENT_TIMESTAMP - interval '1 minute')`,
        [downloadRun, v3Run, tenantId],
      );
      await client.query(
        `INSERT INTO wb_analytics_report_tasks
         (task_id, tenant_id, report_type, period_from, period_to, timezone, aggregation_level, request_body,
          lifecycle_status, downloaded_sha256, downloaded_size, downloaded_at, parsed_row_count, staged_row_count, collector_run_id)
         VALUES ($1, $2, 'DETAIL_HISTORY_REPORT', DATE '2026-08-24', DATE '2026-08-30', 'Europe/Moscow', 'day',
          jsonb_build_object('id', $1::text, 'reportType', 'DETAIL_HISTORY_REPORT'),
          'FAILED', $3, 100, CURRENT_TIMESTAMP, 21, 21, $4)`,
        [taskId, tenantId, reportSha, downloadRun],
      );
      for (const [index, payload] of fixture.entries()) {
        await client.query(
          'INSERT INTO stg_wb_nm_report_rows (task_id, row_number, nm_id, row_date, payload) VALUES ($1, $2, $3, $4, $5)',
          [taskId, index + 1, Number(payload.nmID), payload.dt, JSON.stringify(payload)],
        );
      }
      const v3Payload = { date: '2026-08-24', openCount: 999, cartCount: 999, orderCount: 999, orderSum: 999, buyoutCount: 999, buyoutSum: 999 };
      const canonical = sha256(canonicalJson(v3Payload));
      await client.query(
        `INSERT INTO stg_wb_funnel_obs
         (tenant_id, nm_id, calendar_day, source, canonical_sha256, run_id, evidence_sha256,
          open_card, cart, orders, orders_sum_rub, buyouts, buyouts_sum_rub, payload)
         VALUES ($1, 12345001, DATE '2026-08-24', 'v3', $2, $3, $4, 999, 999, 999, 999, 999, 999, $5)`,
        [tenantId, canonical, v3Run, 'd'.repeat(64), JSON.stringify(v3Payload)],
      );
      await client.query(
        `INSERT INTO fact_funnel_daily
         (tenant_id, nm_id, calendar_day, source, run_id, canonical_sha256, evidence_sha256,
          open_card, cart, orders, orders_sum_rub, buyouts, buyouts_sum_rub)
         VALUES ($1, 12345001, DATE '2026-08-24', 'v3', $2, $3, $4, 999, 999, 999, 999, 999, 999)`,
        [tenantId, v3Run, canonical, 'd'.repeat(64)],
      );
    });

    const first = await promoteFunnelCsv({ tenantId }, { env, onRunOpened: (runId) => openedRuns.push(runId) });
    assert.equal(first.tasks, 1);
    assert.equal(first.rows, 21, 'lifecycle FAILED does not suppress durable rows');
    assert.deepEqual(first.observations, { received: 21, inserted: 21, skipped: 0 });
    assert.deepEqual(first.facts, { versions: 21, inputRuns: 0 });

    const db = new Client({ connectionString: collectorDsn });
    await db.connect();
    await db.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
    try {
      assert.equal(await count(db, 'stg_wb_funnel_obs', "run_id = $1 AND source = 'csv' AND evidence_sha256 = $2", [first.runId, reportSha]), 21);
      assert.equal(await count(db, 'fact_funnel_daily', "run_id = $1 AND source = 'csv'", [first.runId]), 21);
      const preferred = await db.query<{ source: string; open_card: number }>(
        "SELECT source, open_card FROM fact_funnel_daily_current WHERE nm_id = 12345001 AND calendar_day = DATE '2026-08-24'",
      );
      assert.deepEqual(preferred.rows, [{ source: 'csv', open_card: 101 }]);
    } finally { await db.end(); }

    const deleted = await execFileAsync(python, ['tools/delete_run.py', '--tenant', tenantId, '--run', first.runId], {
      cwd: resolve('.'), env: { ...process.env, JANITOR_DATABASE_URI: janitorDsn },
    });
    assert.match(deleted.stdout, /delete_run: deleted closure/);

    const replay = await promoteFunnelCsv({ tenantId }, { env, onRunOpened: (runId) => openedRuns.push(runId) });
    assert.notEqual(replay.runId, first.runId);
    assert.deepEqual(replay.observations, { received: 21, inserted: 21, skipped: 0 });
    assert.deepEqual(replay.facts, { versions: 21, inputRuns: 0 });
    assert.equal(await admin((client) => count(client, 'wb_analytics_report_tasks', 'task_id = $1', [taskId])), 1, 'report task survives promote deletion');
    assert.equal(await admin((client) => count(client, 'stg_wb_nm_report_rows', 'task_id = $1', [taskId])), 21, 'staged report rows survive promote deletion');
  } finally {
    await admin(async (client) => {
      await client.query('DELETE FROM collector_run_inputs WHERE tenant_id = $1', [tenantId]);
      await client.query('DELETE FROM stg_wb_nm_report_rows WHERE task_id = $1', [taskId]);
      await client.query('DELETE FROM wb_analytics_report_tasks WHERE task_id = $1', [taskId]);
      await client.query('DELETE FROM collector_runs WHERE tenant_id = $1', [tenantId]);
      await client.query('DELETE FROM tenants WHERE tenant_id = $1', [tenantId]);
    });
    await rm(temp, { recursive: true, force: true });
  }
});

test('funnel_csv invalid durable row fails atomically and marks the run FAILED', { skip }, async () => {
  const downloadRun = randomUUID();
  const taskId = randomUUID();
  const temp = await mkdtemp(join(tmpdir(), 'proxima-funnel-csv-invalid-'));
  const uriFile = join(temp, 'collector-uri');
  await writeFile(uriFile, `${collectorDsn}\n`, { mode: 0o600 });
  let runId = '';
  try {
    await admin(async (client) => {
      await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]);
      await client.query("INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES ($1, $2, 'funnel_csv_download', 'SUCCEEDED', CURRENT_TIMESTAMP)", [downloadRun, tenantId]);
      await client.query(
        `INSERT INTO wb_analytics_report_tasks
         (task_id, tenant_id, report_type, period_from, period_to, timezone, aggregation_level, request_body, lifecycle_status,
          downloaded_sha256, downloaded_size, downloaded_at, parsed_row_count, staged_row_count, collector_run_id)
         VALUES ($1, $2, 'DETAIL_HISTORY_REPORT', CURRENT_DATE - 1, CURRENT_DATE - 1, 'Europe/Moscow', 'day',
          jsonb_build_object('id', $1::text, 'reportType', 'DETAIL_HISTORY_REPORT'), 'DOWNLOADED', $3, 1, CURRENT_TIMESTAMP, 1, 1, $4)`,
        [taskId, tenantId, 'e'.repeat(64), downloadRun],
      );
      await client.query("INSERT INTO stg_wb_nm_report_rows (task_id, row_number, nm_id, row_date, payload) VALUES ($1, 1, 12345001, CURRENT_DATE - 1, '{\"nmID\":\"12345001\",\"dt\":\"2026-08-24\"}'::jsonb)", [taskId]);
    });
    await assert.rejects(
      () => promoteFunnelCsv({ tenantId }, { env: { COLLECTOR_DATABASE_URI_FILE: uriFile }, onRunOpened: (value) => { runId = value; } }),
      /FUNNEL_CSV_SCHEMA_DRIFT/,
    );
    const status = await admin((client) => client.query<{ status: string }>('SELECT status FROM collector_runs WHERE run_id = $1', [runId]));
    assert.equal(status.rows[0]?.status, 'FAILED');
    assert.equal(await admin((client) => count(client, 'stg_wb_funnel_obs', 'run_id = $1', [runId])), 0);
    assert.equal(await admin((client) => count(client, 'fact_funnel_daily', 'run_id = $1', [runId])), 0);
  } finally {
    await admin(async (client) => {
      await client.query('DELETE FROM stg_wb_nm_report_rows WHERE task_id = $1', [taskId]);
      await client.query('DELETE FROM wb_analytics_report_tasks WHERE task_id = $1', [taskId]);
      await client.query('DELETE FROM collector_runs WHERE tenant_id = $1', [tenantId]);
      await client.query('DELETE FROM tenants WHERE tenant_id = $1', [tenantId]);
    });
    await rm(temp, { recursive: true, force: true });
  }
});
