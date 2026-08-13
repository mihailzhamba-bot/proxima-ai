import assert from 'node:assert/strict';
import { chmod, mkdtemp, readFile, rename, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';
import { Decimal } from 'decimal.js';

import { calculateCandidates, calculateMargins, selectTopRisk } from '../src/business-signal/calculate.js';
import { completedSignalWindow } from '../src/business-signal/date-window.js';
import { RecordedHttpClient, parseJson, type HttpRequest, type HttpResponse, type HttpTransport } from '../src/business-signal/http.js';
import { validateSignalInputFiles } from '../src/business-signal/input-validation.js';
import { runBusinessSignal } from '../src/business-signal/pipeline.js';
import { BusinessSignalRawStore } from '../src/business-signal/raw-store.js';
import { assertLeastPrivilegeToken } from '../src/business-signal/secrets.js';
import { writeFounderChatId } from '../src/business-signal/runtime.js';
import { formatStockoutMessage, preflightAndSend, type TelegramTransport } from '../src/business-signal/telegram.js';
import { discoverFounderChatId } from '../src/business-signal/telegram-setup.js';
import type { ProductConfig, RawArtifactRecord, SignalCandidate, SignalRepository, SignalWindow, WarehouseMap } from '../src/business-signal/types.js';
import { WbSignalClient, type WbSale } from '../src/business-signal/wb-client.js';

const product: ProductConfig = {
  tenantId: 'amirova-test',
  nmId: 1001n,
  internalArticle: 'SKU <ONE>',
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

function jwt(categoryBit: number, unrelatedBit?: number, readOnly = true): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64url');
  const scopes = (readOnly ? (1 << 30) : 0) | (1 << categoryBit) | (unrelatedBit === undefined ? 0 : (1 << unrelatedBit));
  const payload = Buffer.from(JSON.stringify({ s: scopes, exp: 2_000_000_000 })).toString('base64url');
  return `${header}.${payload}.signature`;
}

async function replacePrivateFile(path: string, value: string): Promise<void> {
  const temporary = `${path}.next`;
  await writeFile(temporary, value, { mode: 0o600 });
  await chmod(temporary, 0o600);
  await rename(temporary, path);
}

class MemoryRepository implements SignalRepository {
  raw: RawArtifactRecord[] = [];
  status = 'NONE';
  reason?: string;
  candidate?: SignalCandidate;
  telegramMessageId?: bigint | null;
  constructor(public products = [product], public warehouses = [warehouse]) {}
  async createRun(_runId: string, _tenantId: string, _window: SignalWindow): Promise<void> { this.status = 'RUNNING'; }
  async loadProductConfig(): Promise<ProductConfig[]> { return this.products; }
  async loadWarehouseMap(): Promise<WarehouseMap[]> { return this.warehouses; }
  async recordRawArtifact(record: RawArtifactRecord): Promise<void> { this.raw.push(record); }
  async completeRun(_runId: string, status: 'NO_SIGNAL' | 'BLOCKED', reason: string): Promise<void> {
    if (this.status === 'RUNNING') { this.status = status; this.reason = reason; }
  }
  async markReady(_runId: string, candidate: SignalCandidate): Promise<void> { this.status = 'READY'; this.candidate = candidate; }
  async recordTelegramResult(_runId: string, _attemptedAt: Date, messageId: bigint | null): Promise<void> {
    this.status = messageId === null ? 'SEND_FAILED' : 'SENT'; this.telegramMessageId = messageId;
  }
}

function financeRows() {
  return [
    { nmId: 1001n, docTypeName: 'Продажа', quantity: '1', retailPriceWithDisc: '1000.00', ppvzSalesCommission: '100.00', deliveryService: '50.00', rrdId: 1n },
    { nmId: 1001n, docTypeName: 'Продажа', quantity: '1', retailPriceWithDisc: '1200.00', ppvzSalesCommission: '120.00', deliveryService: '50.00', rrdId: 2n },
    { nmId: 1001n, docTypeName: 'Возврат', quantity: '1', retailPriceWithDisc: '0', ppvzSalesCommission: '0', deliveryService: '30.00', rrdId: 3n },
  ];
}

test('uses 14 completed Europe/Moscow calendar days', () => {
  assert.deepEqual(completedSignalWindow(new Date('2026-08-13T20:59:59Z')), { from: '2026-07-30', to: '2026-08-12' });
  assert.deepEqual(completedSignalWindow(new Date('2026-08-13T21:00:00Z')), { from: '2026-07-31', to: '2026-08-13' });
});

test('rejects a READ token that grants required and unrelated WB categories', () => {
  assert.doesNotThrow(() => assertLeastPrivilegeToken(jwt(5), 'statistics', new Date('2026-08-13T10:00:00Z')));
  assert.throws(() => assertLeastPrivilegeToken(jwt(5, 1), 'statistics', new Date('2026-08-13T10:00:00Z')), { code: 'TOKEN_SCOPE_INVALID' });
  assert.throws(() => assertLeastPrivilegeToken(jwt(13, 12), 'finance', new Date('2026-08-13T10:00:00Z')), { code: 'TOKEN_SCOPE_INVALID' });
});

test('allows an exact-category Analytics RW token only through explicit temporary opt-in', () => {
  const now = new Date('2026-08-13T10:00:00Z');
  const analyticsReadWrite = jwt(2, undefined, false);
  assert.throws(() => assertLeastPrivilegeToken(analyticsReadWrite, 'analytics', now), { code: 'TOKEN_SCOPE_INVALID' });
  assert.doesNotThrow(() => assertLeastPrivilegeToken(analyticsReadWrite, 'analytics', now, { allowReadWrite: true }));
  assert.throws(() => assertLeastPrivilegeToken(jwt(2, 1, false), 'analytics', now, { allowReadWrite: true }), { code: 'TOKEN_SCOPE_INVALID' });
});

test('validates a complete private signal input bundle without returning secret values', async () => {
  const root = await mkdtemp(join(tmpdir(), 'signal-inputs-'));
  const files = {
    statistics: join(root, 'wb_statistics_token'),
    analytics: join(root, 'wb_analytics_token'),
    finance: join(root, 'wb_finance_token'),
    telegram: join(root, 'telegram_bot_token'),
    founder: join(root, 'founder-chat.json'),
    products: join(root, 'products.csv'),
    warehouses: join(root, 'warehouses.csv'),
  };
  const telegram = ['123456789', 'x'.repeat(35)].join(':');
  await Promise.all([
    writeFile(files.statistics, jwt(5)),
    writeFile(files.analytics, jwt(2)),
    writeFile(files.finance, jwt(13)),
    writeFile(files.telegram, telegram),
    writeFile(files.founder, JSON.stringify({ chat_id: '-1001234567890' })),
    writeFile(files.products, 'tenant_id,nm_id,internal_article,cogs_rub,lead_time_days,safety_buffer_days,effective_from\namirova-test,1001,SKU-1,300.10,40,5,2026-08-13\n'),
    writeFile(files.warehouses, 'tenant_id,sales_warehouse_name,stock_warehouse_name,canonical_warehouse,effective_from\namirova-test,Коледино,Коледино,Коледино,2026-08-13\n'),
  ]);
  await Promise.all(Object.values(files).map((path) => chmod(path, 0o600)));
  const paths = {
    tenantId: 'amirova-test',
    statisticsTokenFile: files.statistics,
    analyticsTokenFile: files.analytics,
    financeTokenFile: files.finance,
    telegramTokenFile: files.telegram,
    founderChatSource: files.founder,
    productsCsv: files.products,
    warehousesCsv: files.warehouses,
  };

  const result = await validateSignalInputFiles(paths, new Date('2026-08-13T10:00:00Z'));
  assert.deepEqual(result, {
    tenantId: 'amirova-test',
    products: 1,
    warehouseMappings: 1,
    wbScopes: ['statistics', 'analytics', 'finance'],
    analyticsAccess: 'read-only',
    telegramTokenShape: 'valid',
    founderChatSource: 'valid',
  });
  assert.equal(JSON.stringify(result).includes(telegram), false);

  await replacePrivateFile(files.analytics, jwt(2, 1));
  assert.rejects(() => validateSignalInputFiles(paths, new Date('2026-08-13T10:00:00Z')), { code: 'TOKEN_SCOPE_INVALID' });

  await replacePrivateFile(files.analytics, jwt(2, undefined, false));
  const temporary = await validateSignalInputFiles({ ...paths, allowAnalyticsReadWrite: true }, new Date('2026-08-13T10:00:00Z'));
  assert.equal(temporary.analyticsAccess, 'read-write-temporary');
});

test('calculates Decimal margin including reverse logistics', () => {
  const margins = calculateMargins([product], financeRows());
  assert.equal(margins.get(1001n)?.toFixed(2), '624.90');
});

test('treats ppvzSalesCommission as a line amount when quantity is greater than one', () => {
  const margins = calculateMargins([product], [{
    nmId: 1001n,
    docTypeName: 'Продажа',
    quantity: '2',
    retailPriceWithDisc: '1000.00',
    ppvzSalesCommission: '200.00',
    deliveryService: '100.00',
    rrdId: 1n,
  }]);
  assert.equal(margins.get(1001n)?.toFixed(2), '549.90');
});

test('aggregates stock sizes, nets returns, and signals at threshold equality', () => {
  const margins = calculateMargins([product], financeRows());
  const sales: WbSale[] = Array.from({ length: 14 }, (_, index) => ({
    saleId: `S${index}`,
    kind: 'sale',
    date: '2026-08-01T12:00:00+03:00',
    lastChangeDate: '2026-08-01T12:00:00+03:00',
    nmId: 1001n,
    warehouseName: index === 0 ? ' КОЛЕДИНО ' : 'Коледино',
  }));
  sales.push({ ...sales[0]!, saleId: 'R1', kind: 'return' });
  const candidates = calculateCandidates({
    products: [product],
    warehouseMap: [warehouse],
    sales,
    stocks: [
      { nmId: 1001n, warehouseName: 'коледино', quantity: 20 },
      { nmId: 1001n, warehouseName: 'КОЛЕДИНО', quantity: 21 },
    ],
    margins,
    stockAsOf: new Date('2026-08-13T10:00:00Z'),
  });
  assert.equal(candidates[0]?.daysCover, 44);
  assert.equal(candidates[0]?.thresholdDays, 45);
  assert.equal(candidates[0]?.stockQuantity, 41);
});

test('skips zero net velocity and fails closed on an unknown warehouse', () => {
  const margins = calculateMargins([product], financeRows());
  assert.deepEqual(calculateCandidates({
    products: [product], warehouseMap: [warehouse], margins, stockAsOf: new Date(), stocks: [],
    sales: [
      { saleId: 'S1', kind: 'sale', date: '', lastChangeDate: '', nmId: 1001n, warehouseName: 'Коледино' },
      { saleId: 'R1', kind: 'return', date: '', lastChangeDate: '', nmId: 1001n, warehouseName: 'Коледино' },
    ],
  }), []);
  assert.throws(() => calculateCandidates({
    products: [product], warehouseMap: [warehouse], margins, stockAsOf: new Date(), stocks: [],
    sales: [{ saleId: 'S1', kind: 'sale', date: '', lastChangeDate: '', nmId: 1001n, warehouseName: 'Новый склад' }],
  }), { code: 'WAREHOUSE_MAP_MISSING' });
});

test('selects one deterministic maximum-deficit risk', () => {
  const base: SignalCandidate = {
    nmId: 2n, internalArticle: 'B', warehouse: 'Z', stockQuantity: 1,
    velocityUnitsPerDay: new Decimal(1), daysCover: 5, leadTimeDays: 10,
    safetyBufferDays: 0, thresholdDays: 10, marginPerUnitRub: new Decimal(1), stockAsOf: new Date(),
  };
  const selected = selectTopRisk([
    base,
    { ...base, nmId: 1n, internalArticle: 'A', warehouse: 'A' },
    { ...base, nmId: 3n, daysCover: 4, thresholdDays: 8 },
  ]);
  assert.equal(selected?.nmId, 1n);
});

test('records exact raw bytes before schema parse', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-raw-'));
  const repository = new MemoryRepository();
  const store = await BusinessSignalRawStore.open(rawRoot, resolve('.'));
  const client = new RecordedHttpClient('00000000-0000-4000-8000-000000000001', store, repository, async () => ({ status: 200, body: Buffer.from('{bad'), retrievedAt: new Date('2026-08-13T10:00:00Z') }));
  const response = await client.request({ method: 'GET', url: 'https://example.test/path', token: 'secret', source: 'official_wb_statistics', stage: 'sales', pageSequence: 0 });
  assert.equal(repository.raw.length, 1);
  assert.throws(() => parseJson(response.body, 'test'), { code: 'WB_SCHEMA_DRIFT' });
});

test('persists 429 evidence and makes no automatic retry', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-raw-'));
  const repository = new MemoryRepository();
  const store = await BusinessSignalRawStore.open(rawRoot, resolve('.'));
  let calls = 0;
  const client = new RecordedHttpClient('00000000-0000-4000-8000-000000000003', store, repository, async () => {
    calls += 1;
    return { status: 429, body: Buffer.from('{"error":"limited"}'), retrievedAt: new Date() };
  });
  await assert.rejects(client.request({ method: 'GET', url: 'https://example.test/path', token: 'secret', source: 'official_wb_statistics', stage: 'sales', pageSequence: 0 }), { code: 'WB_RATE_LIMITED' });
  assert.equal(calls, 1);
  assert.equal(repository.raw[0]?.httpStatus, 429);
});

test('classifies strict S/R sales and blocks unknown prefix after raw persistence', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-raw-'));
  const repository = new MemoryRepository();
  const store = await BusinessSignalRawStore.open(rawRoot, resolve('.'));
  const transport: HttpTransport = async () => ({ status: 200, retrievedAt: new Date(), body: Buffer.from(JSON.stringify([
    { saleID: 'X1', date: '2026-08-01T10:00:00+03:00', lastChangeDate: '2026-08-01T11:00:00+03:00', nmId: 1001, warehouseName: 'Коледино' },
  ])) });
  const wb = new WbSignalClient(new RecordedHttpClient('00000000-0000-4000-8000-000000000002', store, repository, transport));
  await assert.rejects(wb.sales('token', { from: '2026-08-01', to: '2026-08-14' }), { code: 'WB_UNKNOWN_SALE_KIND' });
  assert.equal(repository.raw.length, 1);
});

test('escapes Telegram HTML and performs preflight plus exactly one send', async () => {
  const candidate: SignalCandidate = {
    nmId: 1001n, internalArticle: '<SKU>', warehouse: 'A&B', stockQuantity: 6,
    velocityUnitsPerDay: new Decimal(1), daysCover: 6, leadTimeDays: 40,
    safetyBufferDays: 5, thresholdDays: 45, marginPerUnitRub: new Decimal('123.50'),
    stockAsOf: new Date('2026-08-13T10:00:00Z'),
  };
  const message = formatStockoutMessage(candidate, { from: '2026-07-30', to: '2026-08-12' });
  assert.match(message, /&lt;SKU&gt;/);
  assert.match(message, /A&amp;B/);
  assert.doesNotMatch(message, /—|важно отметить|следует подчеркнуть/i);
  const calls: string[] = [];
  const telegram: TelegramTransport = { call: async (method) => {
    calls.push(method);
    return { ok: true, result: method === 'sendMessage' ? { message_id: 77 } : { id: 1 } };
  } };
  assert.equal(await preflightAndSend(telegram, 1n, message), 77n);
  assert.deepEqual(calls, ['getMe', 'getChat', 'sendMessage']);
});

test('does not retry a failed Telegram send', async () => {
  const calls: string[] = [];
  const telegram: TelegramTransport = { call: async (method) => {
    calls.push(method);
    if (method === 'sendMessage') throw new Error('timeout');
    return { ok: true, result: { id: 1 } };
  } };
  await assert.rejects(preflightAndSend(telegram, 1n, 'message'));
  assert.deepEqual(calls, ['getMe', 'getChat', 'sendMessage']);
});

test('discovers exactly one private founder /start without sending and writes mode 0600', async () => {
  const calls: string[] = [];
  const telegram: TelegramTransport = { call: async (method) => {
    calls.push(method);
    if (method === 'getWebhookInfo') return { ok: true, result: { url: '' } };
    if (method === 'getUpdates') return { ok: true, result: [
      { update_id: 1, message: { text: '/start', from: { id: 123, is_bot: false }, chat: { id: 123, type: 'private' } } },
      { update_id: 2, message: { text: '/start payload', from: { id: 123, is_bot: false }, chat: { id: 123, type: 'private' } } },
      { update_id: 3, message: { text: '/start', from: { id: 456, is_bot: false }, chat: { id: -789, type: 'group' } } },
    ] };
    throw new Error('unexpected method');
  } };
  const chatId = await discoverFounderChatId(telegram);
  const root = await mkdtemp(join(tmpdir(), 'founder-chat-'));
  const target = join(root, 'founder-chat.json');
  await writeFounderChatId(target, chatId);
  assert.deepEqual(calls, ['getWebhookInfo', 'getUpdates']);
  assert.deepEqual(JSON.parse(await readFile(target, 'utf8')), { chat_id: '123' });
  assert.equal((await stat(target)).mode & 0o777, 0o600);
});

test('founder discovery fails closed for webhook or multiple private /start senders', async () => {
  await assert.rejects(discoverFounderChatId({ call: async () => ({ ok: true, result: { url: 'https://example.invalid/hook' } }) }), { code: 'TELEGRAM_WEBHOOK_ACTIVE' });
  const transport: TelegramTransport = { call: async (method) => method === 'getWebhookInfo'
    ? { ok: true, result: { url: '' } }
    : { ok: true, result: [
      { message: { text: '/start', from: { id: 1, is_bot: false }, chat: { id: 1, type: 'private' } } },
      { message: { text: '/start', from: { id: 2, is_bot: false }, chat: { id: 2, type: 'private' } } },
    ] } };
  await assert.rejects(discoverFounderChatId(transport), { code: 'TELEGRAM_START_AMBIGUOUS' });
});

test('blocks finance pagination without HTTP 204 terminator', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-raw-'));
  const repository = new MemoryRepository();
  const store = await BusinessSignalRawStore.open(rawRoot, resolve('.'));
  const wb = new WbSignalClient(new RecordedHttpClient('00000000-0000-4000-8000-000000000004', store, repository, async () => ({
    status: 200,
    retrievedAt: new Date(),
    body: Buffer.from('[]'),
  })), { sleep: async () => {} });
  await assert.rejects(wb.finance('token', { from: '2026-08-01', to: '2026-08-14' }), { code: 'WB_INCOMPLETE_PAGINATION' });
  assert.equal(repository.raw.length, 1);
});

test('paces Finance pages for 60 seconds and requests only metric fields', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-raw-'));
  const repository = new MemoryRepository();
  const store = await BusinessSignalRawStore.open(rawRoot, resolve('.'));
  const sleeps: number[] = [];
  const requests: HttpRequest[] = [];
  let page = 0;
  const wb = new WbSignalClient(new RecordedHttpClient('00000000-0000-4000-8000-000000000005', store, repository, async (request) => {
    requests.push(request);
    page += 1;
    if (page === 1) return { status: 200, retrievedAt: new Date(), body: Buffer.from(JSON.stringify(financeRows().slice(0, 2).map((row, index) => ({ ...row, docTypeName: '', nmId: index === 1 ? 0 : Number(row.nmId), rrdId: Number(row.rrdId) })))) };
    return { status: 204, retrievedAt: new Date(), body: Buffer.alloc(0) };
  }), { sleep: async (milliseconds) => { sleeps.push(milliseconds); } });
  const rows = await wb.finance('token', { from: '2026-08-01', to: '2026-08-14' });
  assert.equal(rows.length, 1);
  assert.equal(rows[0]?.docTypeName, '');
  assert.deepEqual(sleeps, [60_000]);
  assert.equal((requests[1]?.body as { rrdId: number }).rrdId, 2);
  assert.deepEqual((requests[0]?.body as { fields: string[] }).fields, [
    'rrdId', 'nmId', 'docTypeName', 'quantity', 'retailPriceWithDisc', 'ppvzSalesCommission', 'deliveryService',
  ]);
});

test('paces Statistics and Analytics pagination without treating it as a retry', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-raw-'));
  const repository = new MemoryRepository();
  const store = await BusinessSignalRawStore.open(rawRoot, resolve('.'));
  const sleeps: number[] = [];
  let salesPage = 0;
  let stockPage = 0;
  const wb = new WbSignalClient(new RecordedHttpClient('00000000-0000-4000-8000-000000000006', store, repository, async (request) => {
    if (request.url.includes('/supplier/sales')) {
      salesPage += 1;
      return {
        status: 200,
        retrievedAt: new Date(),
        body: Buffer.from(JSON.stringify(salesPage === 1 ? [{ saleID: 'S1', date: '2026-08-01T10:00:00+03:00', lastChangeDate: '2026-08-01T11:00:00+03:00', nmId: 1001, warehouseName: 'Коледино' }] : [])),
      };
    }
    stockPage += 1;
    return {
      status: 200,
      retrievedAt: new Date(),
      body: Buffer.from(JSON.stringify({ data: { items: stockPage === 1 ? [{ nmId: 1001, warehouseName: 'Коледино', quantity: 1 }] : [] } })),
    };
  }), {
    sleep: async (milliseconds) => { sleeps.push(milliseconds); },
    salesPageLimit: 1,
    stockPageLimit: 1,
  });
  await wb.sales('token', { from: '2026-08-01', to: '2026-08-14' });
  await wb.stocks('token', [1001n]);
  assert.deepEqual(sleeps, [60_000, 20_000]);
  assert.equal(salesPage, 2);
  assert.equal(stockPage, 2);
});

test('runs one complete mocked vertical slice and sends one top-risk message', async () => {
  const rawRoot = await mkdtemp(join(tmpdir(), 'proxima-signal-raw-'));
  const repository = new MemoryRepository();
  const bodies = (request: HttpRequest): HttpResponse => {
    if (request.url.includes('/supplier/sales')) return { status: 200, retrievedAt: new Date('2026-08-13T09:00:00Z'), body: Buffer.from(JSON.stringify([
      { saleID: 'S1', date: '2026-08-05T10:00:00+03:00', lastChangeDate: '2026-08-05T11:00:00+03:00', nmId: 1001, warehouseName: 'Коледино' },
    ])) };
    if (request.url.includes('/stocks-report/')) return { status: 200, retrievedAt: new Date('2026-08-13T10:00:00Z'), body: Buffer.from(JSON.stringify({ data: { items: [
      { nmId: 1001, warehouseName: 'КОЛЕДИНО', quantity: 0 },
    ] } })) };
    const body = request.body as { rrdId: number };
    if (body.rrdId === 0) return { status: 200, retrievedAt: new Date('2026-08-13T11:00:00Z'), body: Buffer.from(JSON.stringify(financeRows().map((row) => ({ ...row, nmId: Number(row.nmId), rrdId: Number(row.rrdId) })))) };
    return { status: 204, retrievedAt: new Date('2026-08-13T11:00:01Z'), body: Buffer.alloc(0) };
  };
  const telegramCalls: string[] = [];
  const result = await runBusinessSignal(repository, {
    tenantId: 'amirova-test', repositoryRoot: resolve('.'), rawRoot,
    statisticsToken: jwt(5), analyticsToken: jwt(2), financeToken: jwt(13),
    now: new Date('2026-08-13T10:00:00Z'), httpTransport: async (request) => bodies(request),
    sleep: async () => {},
    send: { founderChatId: 1n, telegram: { call: async (method) => {
      telegramCalls.push(method); return { ok: true, result: method === 'sendMessage' ? { message_id: 88 } : { id: 1 } };
    } } },
  });
  assert.equal(result.status, 'SENT');
  assert.equal(repository.raw.length, 4);
  assert.equal(repository.status, 'SENT');
  assert.deepEqual(telegramCalls, ['getMe', 'getChat', 'sendMessage']);
});
