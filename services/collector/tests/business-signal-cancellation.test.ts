import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp } from 'node:fs/promises';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';
import { Decimal } from 'decimal.js';

import { cancellationError, sleep } from '../src/business-signal/cancellation.js';
import { RecordedHttpClient, type HttpTransport } from '../src/business-signal/http.js';
import { runBusinessSignal } from '../src/business-signal/pipeline.js';
import { BusinessSignalRawStore } from '../src/business-signal/raw-store.js';
import type { ClientPassportConfig, ProductConfig, RawArtifactRecord, SignalCandidate, SignalRepository, SignalWindow, SupplyPlanRecord, WarehouseMap } from '../src/business-signal/types.js';
import { WbSignalClient } from '../src/business-signal/wb-client.js';

const product: ProductConfig = {
  tenantId: 'amirova-test',
  nmId: 1001n,
  internalArticle: 'SKU-1',
  cogsRub: new Decimal('300.10'),
  leadTimeDays: 40,
  safetyBufferDays: 5,
  effectiveFrom: '2026-01-01',
};
const warehouse: WarehouseMap = {
  tenantId: 'amirova-test',
  salesWarehouseName: 'Коледино',
  stockWarehouseName: 'КОЛЕДИНО ',
  canonicalWarehouse: 'Коледино & центр',
  effectiveFrom: '2026-01-01',
};

function jwt(categoryBit: number): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ s: (1 << 30) | (1 << categoryBit), exp: 2_000_000_000 })).toString('base64url');
  return `${header}.${payload}.signature`;
}

class TimedRepository implements SignalRepository {
  raw: { record: RawArtifactRecord; at: number }[] = [];
  status = 'NONE';
  reason?: string;
  completedAt?: number;
  async createRun(_runId: string, _tenantId: string, _window: SignalWindow): Promise<void> { this.status = 'RUNNING'; }
  async loadProductConfig(): Promise<ProductConfig[]> { return [product]; }
  async loadWarehouseMap(): Promise<WarehouseMap[]> { return [warehouse]; }
  async loadClientPassport(): Promise<ClientPassportConfig | null> { return null; }
  async loadSupplyPlans(): Promise<SupplyPlanRecord[]> { return []; }
  async recordRawArtifact(record: RawArtifactRecord): Promise<void> { this.raw.push({ record, at: Date.now() }); }
  async completeRun(_runId: string, status: 'NO_SIGNAL' | 'BLOCKED', reason: string): Promise<void> {
    if (this.status === 'RUNNING') { this.status = status; this.reason = reason; this.completedAt = Date.now(); }
  }
  async markReady(_runId: string, _candidate: SignalCandidate): Promise<void> { this.status = 'READY'; }
  async recordTelegramResult(): Promise<void> {}
}

test('abortable sleep settles immediately after abort', async () => {
  const controller = new AbortController();
  const started = Date.now();
  const pending = sleep(600_000, controller.signal);
  setTimeout(() => controller.abort(cancellationError('test abort')), 50);
  await assert.rejects(pending, { code: 'CANCELLED' });
  assert.ok(Date.now() - started < 150, `sleep held for ${Date.now() - started}ms after abort`);
});

test('BLOCKED aborts sibling branches: sockets close, requests stop, no rows after run close', async () => {
  const rejections: unknown[] = [];
  const onRejection = (reason: unknown): void => { rejections.push(reason); };
  process.on('unhandledRejection', onRejection);
  let requests = 0;
  let hungClosed = 0;
  const server = createServer((request, response) => {
    requests += 1;
    if ((request.url ?? '').includes('/stocks-report/')) {
      response.writeHead(500, { 'content-type': 'application/json' }).end('{"error":"boom"}');
      return;
    }
    response.on('close', () => { hungClosed += 1; });
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const port = (server.address() as AddressInfo).port;
  const transport: HttpTransport = async (request) => {
    const url = new URL(request.url);
    const response = await fetch(`http://127.0.0.1:${port}${url.pathname}${url.search}`, {
      method: request.method,
      headers: { 'Content-Type': 'application/json' },
      ...(request.body === undefined ? {} : { body: JSON.stringify(request.body) }),
      ...(request.signal ? { signal: request.signal } : {}),
    });
    return { status: response.status, body: Buffer.from(await response.arrayBuffer()), retrievedAt: new Date() };
  };
  try {
    const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-cancel-'));
    const repository = new TimedRepository();
    const result = await runBusinessSignal(repository, {
      tenantId: 'amirova-test', repositoryRoot: resolve('.'), rawRoot,
      statisticsToken: jwt(5), analyticsToken: jwt(2), financeToken: jwt(13),
      now: new Date('2026-08-13T10:00:00Z'), httpTransport: transport,
    });
    assert.equal(result.status, 'BLOCKED');
    assert.equal(result.reason, 'WB_HTTP_FAILED');
    const requestsAtClose = requests;
    await new Promise((resolveWait) => setTimeout(resolveWait, 1_500));
    assert.equal(requests, requestsAtClose, 'WB requests kept arriving after the run was closed');
    assert.equal(hungClosed, 2, 'hung sibling requests were not aborted');
    assert.ok(repository.completedAt);
    for (const { at } of repository.raw) assert.ok(at <= repository.completedAt, 'raw artifact recorded after run close');
    assert.equal(repository.status, 'BLOCKED');
    assert.deepEqual(rejections, []);
  } finally {
    process.off('unhandledRejection', onRejection);
    server.closeAllConnections();
    server.close();
  }
});

test('a paginating branch makes zero calls during 100 minutes after abort', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-cancel-'));
  const repository = new TimedRepository();
  const store = await BusinessSignalRawStore.open(rawRoot, resolve('.'));
  const controller = new AbortController();
  let calls = 0;
  const transport: HttpTransport = async () => {
    calls += 1;
    return { status: 200, retrievedAt: new Date(), body: Buffer.from(JSON.stringify([
      { saleID: 'S1', date: '2026-08-05T10:00:00+03:00', lastChangeDate: '2026-08-05T11:00:00+03:00', nmId: 1001, warehouseName: 'Коледино' },
      { saleID: 'S2', date: '2026-08-05T10:30:00+03:00', lastChangeDate: '2026-08-05T12:00:00+03:00', nmId: 1001, warehouseName: 'Коледино' },
    ])) };
  };
  let sleepEntered: (() => void) | undefined;
  const sleepStarted = new Promise<void>((resolveStart) => { sleepEntered = resolveStart; });
  const wb = new WbSignalClient(new RecordedHttpClient('00000000-0000-4000-8000-00000000c001', store, repository, transport), {
    salesPageLimit: 2,
    signal: controller.signal,
    sleep: (milliseconds, signal) => { sleepEntered?.(); return sleep(milliseconds, signal); },
  });
  const pending = wb.sales('token', { from: '2026-08-01', to: '2026-08-14' });
  await sleepStarted;
  assert.equal(calls, 1);
  controller.abort(cancellationError('run blocked: WB_HTTP_FAILED'));
  await assert.rejects(pending, { code: 'CANCELLED' });
  t.mock.timers.tick(100 * 60 * 1000);
  for (let turn = 0; turn < 20; turn += 1) await new Promise((resolveTurn) => setImmediate(resolveTurn));
  assert.equal(calls, 1, 'the cancelled branch kept calling WB after the clock advanced 100 minutes');
});

test('a successful run is unaffected by the finally abort', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-cancel-'));
  const repository = new TimedRepository();
  const bodies: HttpTransport = async (request) => {
    if (request.url.includes('/supplier/sales')) return { status: 200, retrievedAt: new Date('2026-08-13T09:00:00Z'), body: Buffer.from(JSON.stringify([
      { saleID: 'S1', date: '2026-08-05T10:00:00+03:00', lastChangeDate: '2026-08-05T11:00:00+03:00', nmId: 1001, warehouseName: 'Коледино' },
    ])) };
    if (request.url.includes('/stocks-report/')) return { status: 200, retrievedAt: new Date('2026-08-13T10:00:00Z'), body: Buffer.from(JSON.stringify({ data: { items: [
      { nmId: 1001, warehouseName: 'КОЛЕДИНО', quantity: 0 },
    ] } })) };
    const body = request.body as { rrdId: number };
    if (body.rrdId === 0) return { status: 200, retrievedAt: new Date('2026-08-13T11:00:00Z'), body: Buffer.from(JSON.stringify([
      { nmId: 1001, docTypeName: 'Продажа', quantity: '1', retailPriceWithDisc: '1000.00', ppvzSalesCommission: '100.00', deliveryService: '50.00', rrdId: 1 },
    ])) };
    return { status: 204, retrievedAt: new Date('2026-08-13T11:00:01Z'), body: Buffer.alloc(0) };
  };
  const result = await runBusinessSignal(repository, {
    tenantId: 'amirova-test', repositoryRoot: resolve('.'), rawRoot,
    statisticsToken: jwt(5), analyticsToken: jwt(2), financeToken: jwt(13),
    now: new Date('2026-08-13T10:00:00Z'), httpTransport: bodies,
    sleep: async () => {},
  });
  assert.equal(result.status, 'READY');
  assert.equal(repository.status, 'READY');
  assert.equal(repository.raw.length, 4);
});

test('a BLOCKED run lets the CLI process exit on its own', async () => {
  const fixture = join(import.meta.dirname, 'fixtures', 'blocked-run-child.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', fixture], { cwd: resolve('.'), stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '';
  let stderr = '';
  child.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString('utf8'); });
  child.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString('utf8'); });
  const started = Date.now();
  const guard = setTimeout(() => child.kill('SIGKILL'), 10_000);
  const [code] = await once(child, 'exit') as [number | null];
  clearTimeout(guard);
  assert.equal(code, 0, `child did not exit cleanly within 10s (${Date.now() - started}ms): ${stderr}`);
  const payload = JSON.parse(stdout) as { status: string; reason?: string };
  assert.equal(payload.status, 'BLOCKED');
  assert.equal(payload.reason, 'WB_HTTP_FAILED');
});
