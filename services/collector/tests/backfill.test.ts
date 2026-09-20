import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { importCasArtifact, readImportedCasArtifact } from '../src/wb/cas-artifact.js';
import { WbClient, type Clock } from '../src/wb/client.js';
import { fetchBackfillPages, parseBackfillArgs } from '../src/jobs/backfill.js';
import type { WbTransport } from '../src/wb/transport.js';

test('backfill args separate artifact and live modes', () => {
  const sales = 'a'.repeat(64);
  const orders = 'b'.repeat(64);
  assert.deepEqual(parseBackfillArgs(['--tenant', 'pilot-tenant', '--source', `artifact:${sales},${orders}`]), { tenantId: 'pilot-tenant', mode: 'artifact', artifactShas: [sales, orders] });
  assert.deepEqual(parseBackfillArgs(['--tenant', 'pilot-tenant', '--from', '2026-08-30', '--resume', '--statistics-token-file', '/token']), { tenantId: 'pilot-tenant', mode: 'live', from: '2026-08-30', resume: true, statisticsTokenFile: '/token' });
  assert.throws(() => parseBackfillArgs(['--tenant', 'pilot-tenant', '--from', '2026-08-30']), /statistics-token-file/);
  assert.throws(() => parseBackfillArgs(['--tenant', 'pilot-tenant', '--from', '2026-08-30', '--source', `artifact:${sales},${orders}`]), /exactly one/);
});

test('cas_import stores immutable bytes and manifest outside Git', async () => {
  const workspace = await mkdtemp(join(tmpdir(), 'proxima-cas-test-'));
  const repository = join(workspace, 'repo');
  const rawRoot = join(workspace, 'raw');
  await import('node:fs/promises').then(({ mkdir }) => mkdir(repository));
  const file = join(workspace, 'supplier-orders.json');
  await writeFile(file, '[{"srid":"o-1"}]\n');
  try {
    const manifest = await importCasArtifact({ file, rawRoot, repositoryRoot: repository, retrievedAt: new Date('2026-08-30T05:59:00Z'), source: 'official_wb_statistics' });
    const loaded = await readImportedCasArtifact(rawRoot, manifest.content_sha256);
    assert.equal(loaded.manifest.endpoint_id, 'statistics.orders');
    assert.equal(loaded.manifest.retrieved_at, '2026-08-30T05:59:00.000Z');
    assert.equal((await readFile(file)).equals(loaded.body), true);
    await importCasArtifact({ file, rawRoot, repositoryRoot: repository, retrievedAt: new Date('2026-08-30T05:59:00Z'), source: 'official_wb_statistics' });
    await assert.rejects(() => importCasArtifact({ file, rawRoot: join(repository, 'raw'), repositoryRoot: repository, retrievedAt: new Date(), source: 'official_wb_statistics' }), /outside Git/);
  } finally { await rm(workspace, { recursive: true, force: true }); }
});

test('backfill: artifact replay + pagination waits at least 60 seconds after an 80,000-row sales page', async () => {
  let now = Date.parse('2026-08-30T05:59:00Z');
  const sleeps: number[] = [];
  const clock: Clock = { now: () => now, sleep: async (milliseconds) => { sleeps.push(milliseconds); now += milliseconds; } };
  const page = Array.from({ length: 80_000 }, (_, index) => ({ saleID: `S-${index}`, date: '2026-08-29T12:00:00', lastChangeDate: `2026-08-29T12:${String(Math.floor(index / 60) % 60).padStart(2, '0')}:${String(index % 60).padStart(2, '0')}` }));
  const queries: string[] = [];
  const transport: WbTransport = async (request) => {
    const url = new URL(request.url);
    queries.push(url.searchParams.get('dateFrom') ?? '');
    return { status: 200, headers: {}, body: Buffer.from(queries.length === 1 ? JSON.stringify(page) : '[]'), retrievedAt: new Date(now) };
  };
  const client = new WbClient({ statistics: 'fixture' }, { transport, clock });
  const result = await fetchBackfillPages(client, 'statistics.sales', '2026-08-01');
  assert.equal(result.rows.length, 80_000);
  assert.equal(queries.length, 2);
  assert.equal(queries[1], page[page.length - 1]!.lastChangeDate);
  assert.ok(sleeps.some((delay) => delay >= 60_000));
});
