import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { Client } from 'pg';

import { runBackfill, type BackfillResult } from '../../src/jobs/backfill.js';
import { importCasArtifact } from '../../src/wb/cas-artifact.js';

export const tenantId = 'amirova-test';

export interface BackfillHarness {
  readonly admin: Client;
  run(): Promise<BackfillResult>;
  cleanup(): Promise<void>;
}

export async function openBackfillHarness(collectorDsn: string, postgresDsn: string): Promise<BackfillHarness> {
  const admin = new Client({ connectionString: postgresDsn });
  await admin.connect();
  await admin.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
  await admin.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT DO NOTHING', [tenantId]);
  const root = await mkdtemp(join(tmpdir(), 'proxima-backfill-harness-'));
  const repository = join(root, 'repo');
  const rawRoot = join(root, 'raw');
  await import('node:fs/promises').then(({ mkdir }) => mkdir(repository));
  const uriFile = join(root, 'collector-uri');
  await writeFile(uriFile, `${collectorDsn}\n`, { mode: 0o600 });
  const ordersFile = join(root, 'synthetic-orders.json');
  const salesFile = join(root, 'synthetic-sales.json');
  await writeFile(ordersFile, JSON.stringify([
    { srid: 'backfill-o-1', date: '2026-08-17T10:00:00', lastChangeDate: '2026-08-18T01:00:00', isCancel: false },
    { srid: 'backfill-o-2', date: '2026-08-24T10:00:00', lastChangeDate: '2026-08-25T01:00:00', isCancel: true },
  ]));
  await writeFile(salesFile, JSON.stringify([
    { saleID: 'S-backfill-1', date: '2026-08-17T12:00:00', lastChangeDate: '2026-08-18T01:00:00', finishedPrice: '12.50', forPay: '10.00' },
    { saleID: 'R-backfill-1', date: '2026-08-24T12:00:00', lastChangeDate: '2026-08-25T01:00:00', finishedPrice: '12.50', forPay: '10.00' },
  ]));
  const retrievedAt = new Date('2026-08-30T05:59:00Z');
  const orders = await importCasArtifact({ file: ordersFile, rawRoot, repositoryRoot: repository, retrievedAt, source: 'official_wb_statistics' });
  const sales = await importCasArtifact({ file: salesFile, rawRoot, repositoryRoot: repository, retrievedAt, source: 'official_wb_statistics' });
  const runIds: string[] = [];
  return {
    admin,
    run: () => runBackfill(
      { tenantId, mode: 'artifact', artifactShas: [sales.content_sha256, orders.content_sha256] },
      { env: { COLLECTOR_DATABASE_URI_FILE: uriFile, PROXIMA_RAW_DIR: rawRoot }, repositoryRoot: repository, onRunOpened: (runId) => runIds.push(runId) },
    ),
    async cleanup() {
      if (runIds.length > 0) {
        await admin.query('DELETE FROM collector_run_inputs WHERE run_id = ANY($1::uuid[]) OR input_run_id = ANY($1::uuid[])', [runIds]);
        await admin.query('DELETE FROM collector_runs WHERE run_id = ANY($1::uuid[])', [runIds]);
      }
      await admin.end();
      await rm(root, { recursive: true, force: true });
    },
  };
}
