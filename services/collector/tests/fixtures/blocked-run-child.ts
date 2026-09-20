import { once } from 'node:events';
import { mkdtemp } from 'node:fs/promises';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { Decimal } from 'decimal.js';

import type { HttpTransport } from '../../src/business-signal/http.js';
import { runBusinessSignal } from '../../src/business-signal/pipeline.js';
import type { ClientPassportConfig, ProductConfig, RawArtifactRecord, SignalCandidate, SignalRepository, SignalWindow, SupplyPlanRecord, WarehouseMap } from '../../src/business-signal/types.js';

function jwt(categoryBit: number): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ s: (1 << 30) | (1 << categoryBit), exp: 2_000_000_000 })).toString('base64url');
  return `${header}.${payload}.signature`;
}

const product: ProductConfig = {
  tenantId: 'pilot-tenant', nmId: 1001n, internalArticle: 'SKU-1', cogsRub: new Decimal('300.10'),
  leadTimeDays: 40, safetyBufferDays: 5, effectiveFrom: '2026-01-01',
};
const warehouse: WarehouseMap = {
  tenantId: 'pilot-tenant', salesWarehouseName: 'Коледино', stockWarehouseName: 'КОЛЕДИНО ',
  canonicalWarehouse: 'Коледино', effectiveFrom: '2026-01-01',
};

class ChildRepository implements SignalRepository {
  status = 'NONE';
  async createRun(_runId: string, _tenantId: string, _window: SignalWindow): Promise<void> { this.status = 'RUNNING'; }
  async loadProductConfig(): Promise<ProductConfig[]> { return [product]; }
  async loadWarehouseMap(): Promise<WarehouseMap[]> { return [warehouse]; }
  async loadClientPassport(): Promise<ClientPassportConfig | null> { return null; }
  async loadSupplyPlans(): Promise<SupplyPlanRecord[]> { return []; }
  async recordRawArtifact(_record: RawArtifactRecord): Promise<void> {}
  async completeRun(_runId: string, status: 'NO_SIGNAL' | 'BLOCKED'): Promise<void> { if (this.status === 'RUNNING') this.status = status; }
  async markReady(_runId: string, _candidate: SignalCandidate): Promise<void> { this.status = 'READY'; }
  async recordTelegramResult(): Promise<void> {}
}

const server = createServer((request, response) => {
  if ((request.url ?? '').includes('/stocks-report/')) {
    response.writeHead(500, { 'content-type': 'application/json', connection: 'close' }).end('{"error":"boom"}');
  }
});
server.on('connection', (socket) => socket.unref());
server.listen(0, '127.0.0.1');
server.unref();
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

const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-child-'));
const result = await runBusinessSignal(new ChildRepository(), {
  tenantId: 'pilot-tenant', repositoryRoot: resolve('.'), rawRoot,
  statisticsToken: jwt(5), analyticsToken: jwt(2), financeToken: jwt(13),
  now: new Date('2026-08-13T10:00:00Z'), httpTransport: transport,
});
process.stdout.write(`${JSON.stringify({ status: result.status, reason: result.reason })}\n`);
