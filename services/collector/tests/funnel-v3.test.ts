import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { sha256 } from '../src/intake/manifest.js';
import { parseFunnelV3Args, runFunnelV3 } from '../src/jobs/funnel-v3.js';
import { WbClient, WbClientError, type Clock } from '../src/wb/client.js';
import { DEFAULT_FIXTURE_ROOT, FixtureTransport } from '../src/wb/fixture-transport.js';
import {
  assertBatchCoverage,
  batchNmIds,
  FUNNEL_BATCH_SIZE,
  funnelRequestBody,
  funnelWindow,
  parseFunnelV3,
  windowDays,
  type FunnelObservation,
} from '../src/wb/funnel-v3.js';

/** The fixture is the 30.08 answer for 3 nmIds over 2026-08-24..2026-08-30 (API-FACTS). */
const FIXTURE_NM_IDS = [12345001, 12345002, 12345003];
const FIXTURE_DAYS = ['2026-08-24', '2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28', '2026-08-29', '2026-08-30'];
/** sha256(canonicalJson(first history record)); tools/verify_funnel.py pins the same digest from Python. */
const FIRST_RECORD_CANONICAL_SHA256 = '6bc1aa356e207f20df1958aeb5d0930599f6c10025ab19869f785114870abb71';

type FixtureProduct = { product: { nmId: number }; history: Record<string, unknown>[]; currency: string };

async function fixtureBody(): Promise<Buffer> {
  return readFile(join(DEFAULT_FIXTURE_ROOT, 'analytics/sales_funnel_v3_history/sample.json'));
}

async function fixtureJson(): Promise<FixtureProduct[]> {
  return JSON.parse((await fixtureBody()).toString('utf8')) as FixtureProduct[];
}

function parse(value: unknown, runDay: string): readonly FunnelObservation[] {
  const body = Buffer.from(JSON.stringify(value));
  return parseFunnelV3(body, sha256(body), funnelWindow(runDay)).rows;
}

function driftCode(error: unknown): boolean {
  return error instanceof WbClientError && error.code === 'WB_SCHEMA_DRIFT';
}

test('funnel args: tenant and analytics token file are required; run-day and read-write opt-in are optional', () => {
  assert.deepEqual(parseFunnelV3Args(['--tenant', 'amirova-test', '--analytics-token-file', '/run/secrets/token']), {
    tenantId: 'amirova-test', analyticsTokenFile: '/run/secrets/token', allowAnalyticsReadWrite: false,
  });
  assert.deepEqual(parseFunnelV3Args(['--allow-analytics-read-write', '--tenant', 'amirova-test', '--run-day', '2026-08-31', '--analytics-token-file', 'f']), {
    tenantId: 'amirova-test', analyticsTokenFile: 'f', runDay: '2026-08-31', allowAnalyticsReadWrite: true,
  });
  assert.throws(() => parseFunnelV3Args(['--tenant', 'amirova-test']), /required option: --analytics-token-file/);
  assert.throws(() => parseFunnelV3Args(['--analytics-token-file', 'f']), /required option: --tenant/);
  assert.throws(() => parseFunnelV3Args(['--tenant', 'Amirova', '--analytics-token-file', 'f']), /--tenant must match/);
  assert.throws(() => parseFunnelV3Args(['--tenant', 'amirova-test', '--analytics-token-file', 'f', '--run-day', '31.08.2026']), /--run-day must be YYYY-MM-DD/);
  assert.throws(() => parseFunnelV3Args(['--tenant', 'amirova-test', '--analytics-token-file', 'f', '--run-day', '2026-02-30']), /calendar date/);
  assert.throws(() => parseFunnelV3Args(['--tenant', 'amirova-test', '--statistics-token-file', 'f']), /unknown option --statistics-token-file/);
  assert.throws(() => parseFunnelV3Args(['--tenant', 'amirova-test', '--tenant', 'x', '--analytics-token-file', 'f']), /given twice/);
  assert.throws(() => parseFunnelV3Args(['--tenant', '--analytics-token-file']), /requires a value/);
});

test('funnel window is WB [today-6, today], where today is run_day in Moscow', () => {
  assert.deepEqual(funnelWindow('2026-08-31'), { runDay: '2026-08-31', start: '2026-08-25', end: '2026-08-31' });
  assert.deepEqual(funnelWindow('2026-09-03'), { runDay: '2026-09-03', start: '2026-08-28', end: '2026-09-03' });
  assert.deepEqual(funnelWindow('2028-03-02'), { runDay: '2028-03-02', start: '2028-02-25', end: '2028-03-02' });
  assert.deepEqual(windowDays(funnelWindow('2026-08-31')), ['2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28', '2026-08-29', '2026-08-30', '2026-08-31']);
  assert.throws(() => funnelWindow('2026-02-30'), RangeError);
  assert.throws(() => funnelWindow('2026-8-31'), RangeError);
});

test('funnel fixture parses 3 nmIds x 7 days into 21 traceable observations with the scn001 dictionary', async () => {
  const body = await fixtureBody();
  const evidence = sha256(body);
  const batch = parseFunnelV3(body, evidence, funnelWindow('2026-08-31'));
  assert.equal(batch.received, 21);
  assert.equal(batch.rows.length, 21);
  assert.equal(batch.evidenceSha256, evidence);
  assert.deepEqual([...new Set(batch.rows.map((row) => row.nmId))], FIXTURE_NM_IDS);
  assert.deepEqual([...new Set(batch.rows.map((row) => row.calendarDay))].sort(), FIXTURE_DAYS);
  assert.equal(new Set(batch.rows.map((row) => row.canonicalSha256)).size, 21, 'every product-day has its own canonical hash');
  const first = batch.rows[0]!;
  assert.deepEqual(
    { ...first, payload: undefined },
    {
      nmId: 12345001, calendarDay: '2026-08-24', canonicalSha256: FIRST_RECORD_CANONICAL_SHA256,
      openCard: 271, cart: 21, orders: 2, ordersSumRub: '2375.52', buyouts: 1, buyoutsSumRub: '1187.76', payload: undefined,
    },
  );
  assert.equal(Object.keys(first.payload).length, 11, 'the full WB record stays as payload evidence');
  assert.throws(() => parseFunnelV3(body, 'not-a-sha', funnelWindow('2026-08-31')), RangeError);
});

test('funnel parser: run_day is observed, later days are dropped, earlier days WB returned are kept as evidence', async () => {
  const fixture = await fixtureJson();
  const closed = parse(fixture, '2026-08-30');
  assert.equal(closed.length, 21);
  assert.ok(closed.every((row) => row.calendarDay <= '2026-08-30'));
  assert.equal(parse(fixture, '2026-08-24').length, 3, 'the run day is retained as an observation');
  assert.equal(parse(fixture, '2026-09-10').length, 21, 'days before the window start are still WB evidence');
});

test('funnel canonical hash ignores key order and changes with the payload', async () => {
  const fixture = await fixtureJson();
  const record = fixture[0]!.history[0]!;
  const reordered = Object.fromEntries(Object.entries(record).reverse());
  fixture[0]!.history[0] = reordered;
  assert.equal(parse(fixture, '2026-08-31')[0]?.canonicalSha256, FIRST_RECORD_CANONICAL_SHA256);
  fixture[0]!.history[0] = { ...record, openCount: (record.openCount as number) + 1 };
  const changed = parse(fixture, '2026-08-31')[0]!;
  assert.notEqual(changed.canonicalSha256, FIRST_RECORD_CANONICAL_SHA256);
  assert.equal(changed.openCard, 272);
});

test('funnel batching is sorted, unique and never exceeds 20 nmIds per request', () => {
  const batches = batchNmIds([...Array.from({ length: 43 }, (_, index) => 43 - index), 1, 7]);
  assert.deepEqual(batches.map((batch) => batch.length), [20, 20, 3]);
  assert.deepEqual(batches.flat(), Array.from({ length: 43 }, (_, index) => index + 1));
  assert.deepEqual(batchNmIds([]), []);
  assert.equal(FUNNEL_BATCH_SIZE, 20);
  assert.throws(() => batchNmIds([1], 21), RangeError);
  assert.throws(() => batchNmIds([0]), RangeError);
  assert.throws(() => batchNmIds([1.5]), RangeError);
});

test('funnel request body carries the window, at most 20 nmIds and daily aggregation', () => {
  const window = funnelWindow('2026-08-31');
  assert.deepEqual(funnelRequestBody(window, [3, 1]), { selectedPeriod: { start: '2026-08-25', end: '2026-08-31' }, nmIds: [3, 1], aggregationLevel: 'day' });
  assert.throws(() => funnelRequestBody(window, []), RangeError);
  assert.throws(() => funnelRequestBody(window, Array.from({ length: 21 }, (_, index) => index + 1)), RangeError);
});

test('funnel coverage: every requested nmId on every window day, nothing twice, nothing unrequested', async () => {
  const fixture = await fixtureJson();
  const window = funnelWindow('2026-08-30');
  const rows = parse(fixture, '2026-08-30');
  assert.doesNotThrow(() => assertBatchCoverage(rows, FIXTURE_NM_IDS, window));
  assert.throws(() => assertBatchCoverage(rows.filter((row) => row.calendarDay !== '2026-08-27'), FIXTURE_NM_IDS, window), /incomplete coverage/);
  assert.throws(() => assertBatchCoverage(rows, [...FIXTURE_NM_IDS, 12345004], window), /incomplete coverage: nmId 12345004/);
  assert.throws(() => assertBatchCoverage([...rows, rows[0]!], FIXTURE_NM_IDS, window), /repeats nmId 12345001 on 2026-08-24/);
  assert.throws(() => assertBatchCoverage(rows, [12345001, 12345002], window), /unrequested nmId 12345003/);
  assert.doesNotThrow(() => assertBatchCoverage(parse(fixture, '2026-08-30'), FIXTURE_NM_IDS, funnelWindow('2026-08-30')));
});

test('funnel parser fails closed on schema drift instead of inventing fields', async () => {
  const runDay = '2026-08-31';
  const drifted = async (mutate: (fixture: FixtureProduct[]) => unknown): Promise<void> => {
    const fixture = await fixtureJson();
    const value = mutate(fixture) ?? fixture;
    assert.throws(() => parse(value, runDay), driftCode);
  };
  await drifted(() => ({ data: [] }));
  await drifted((fixture) => { delete fixture[0]!.history[0]!.openCount; });
  await drifted((fixture) => { fixture[0]!.history[0]!.cartCount = -1; });
  await drifted((fixture) => { fixture[0]!.history[0]!.orderSum = '2375.52'; });
  await drifted((fixture) => { fixture[0]!.history[0]!.buyoutCount = 1.5; });
  await drifted((fixture) => { fixture[0]!.history[0]!.date = '2026-13-01'; });
  await drifted((fixture) => { fixture[0]!.history[0]!.date = '2026-08-24T00:00:00'; });
  await drifted((fixture) => { fixture[0]!.currency = 'USD'; });
  await drifted((fixture) => { delete (fixture[0] as Partial<FixtureProduct>).currency; });
  await drifted((fixture) => { (fixture[0] as { history: unknown }).history = {}; });
  await drifted((fixture) => { (fixture[0] as { product: unknown }).product = { nmId: 0 }; });
  await drifted((fixture) => { (fixture as unknown[])[1] = 'not-an-object'; });
  const body = Buffer.from('{not json');
  assert.throws(() => parseFunnelV3(body, sha256(body), funnelWindow(runDay)), driftCode);
});

test('funnel endpoint honours X-Ratelimit-Retry on 429 and gives up after three retries', async () => {
  let now = Date.parse('2026-08-31T03:15:00Z');
  const sleeps: number[] = [];
  const clock: Clock = { now: () => now, sleep: async (milliseconds) => { sleeps.push(milliseconds); now += milliseconds; } };
  const limited = { status: 429, headers: { 'x-ratelimit-retry': '2' }, body: '{}' } as const;
  const transport = new FixtureTransport({ scripts: { 'analytics.sales_funnel_v3_history': [limited, limited, limited, limited] } });
  const client = new WbClient({ analytics: 'fixture-token' }, { transport: transport.transport, clock });
  await assert.rejects(
    () => client.request('analytics.sales_funnel_v3_history', { body: funnelRequestBody(funnelWindow('2026-08-31'), FIXTURE_NM_IDS) }),
    (error: unknown) => error instanceof WbClientError && error.code === 'WB_RATE_LIMIT_EXHAUSTED',
  );
  assert.equal(transport.recordedRequests().length, 4, 'one call plus three retries');
  assert.equal(sleeps.filter((delay) => delay === 2_000).length, 3, 'every retry waited the hinted 2 seconds');
  assert.ok(sleeps.some((delay) => delay >= 60_000), 'the 3/min budget paced the fourth call into the next window');
});

function jwt(scopes: number): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ s: scopes, exp: 2_000_000_000 })).toString('base64url');
  return `${header}.${payload}.fixture-signature`;
}

test('funnel_v3: a read-write or multi-category analytics token fails closed before any connection; read-write is an explicit opt-in', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'proxima-funnel-token-'));
  try {
    const uriFile = join(dir, 'proxima_collector_uri');
    await writeFile(uriFile, 'postgresql://unused@127.0.0.1:1/unused\n', { mode: 0o600 });
    const env = { COLLECTOR_DATABASE_URI_FILE: uriFile, PROXIMA_RAW_DIR: dir };
    const transport = () => { throw new Error('network must not be touched'); };
    const args = (tokenFile: string, allowAnalyticsReadWrite = false) => ({ tenantId: 'amirova-test', runDay: '2026-08-31', analyticsTokenFile: tokenFile, allowAnalyticsReadWrite });

    const readWrite = join(dir, 'rw');
    await writeFile(readWrite, `${jwt(1 << 2)}\n`, { mode: 0o600 });
    await assert.rejects(() => runFunnelV3(args(readWrite), { transport, env }), { code: 'TOKEN_SCOPE_INVALID' });

    const twoCategories = join(dir, 'two');
    await writeFile(twoCategories, `${jwt((1 << 30) | (1 << 2) | (1 << 5))}\n`, { mode: 0o600 });
    await assert.rejects(() => runFunnelV3(args(twoCategories), { transport, env }), { code: 'TOKEN_SCOPE_INVALID' });
    await assert.rejects(() => runFunnelV3(args(twoCategories, true), { transport, env }), { code: 'TOKEN_SCOPE_INVALID' });

    const notJwt = join(dir, 'plain');
    await writeFile(notJwt, 'analytics-fixture-token\n', { mode: 0o600 });
    await assert.rejects(() => runFunnelV3(args(notJwt), { transport, env }), { code: 'TOKEN_INVALID' });

    // PA-13: with the opt-in the read-write token passes the scope gate; the
    // run then fails on the unreachable database, not on the token.
    await assert.rejects(() => runFunnelV3(args(readWrite, true), { transport, env }), (error: unknown) => {
      const code = (error as { code?: unknown } | null)?.code;
      return code !== 'TOKEN_SCOPE_INVALID' && code !== 'TOKEN_INVALID';
    });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
