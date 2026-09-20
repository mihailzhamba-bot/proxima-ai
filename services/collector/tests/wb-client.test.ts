import assert from 'node:assert/strict';
import test from 'node:test';

import { FixtureTransport } from '../src/wb/fixture-transport.js';
import { InMemoryArtifactSink } from '../src/wb/artifact-sink.js';
import { fallbackRetryDelayMilliseconds, MAX_RETRIES_AFTER_RATE_LIMIT, RateBudget, WbClient, WbClientError, wallClock } from '../src/wb/client.js';
import { endpointLimit, WB_ENDPOINTS, WB_ENDPOINT_LIST } from '../src/wb/registry.js';
import { parseWbCollectArgs, runWbCollect } from '../src/cli/wb-collect.js';

const TOKENS = { statistics: 'statistics-fixture-token', analytics: 'analytics-fixture-token' } as const;

function virtualClock(startMs = 0) {
  let current = startMs;
  const sleeps: number[] = [];
  return {
    now: () => current,
    async sleep(milliseconds: number): Promise<void> {
      assert.ok(milliseconds >= 0, `virtual clock refused negative sleep ${milliseconds}`);
      sleeps.push(milliseconds);
      current += milliseconds;
    },
    sleeps: () => [...sleeps],
    elapsed: () => current,
  };
}

test('registry holds exactly the four allowed endpoints with their budgets', () => {
  assert.deepEqual(
    [...WB_ENDPOINT_LIST].map((spec) => [spec.id, spec.limitPerMinute] as const).sort((a, b) => a[0].localeCompare(b[0])),
    [
      ['analytics.nm_report_downloads', 3],
      ['analytics.sales_funnel_v3_history', 3],
      ['statistics.orders', 10],
      ['statistics.sales', 1],
    ],
  );
  assert.equal(endpointLimit('statistics.orders'), 10);
  assert.equal(endpointLimit('statistics.sales'), 1);
  assert.equal(endpointLimit('analytics.sales_funnel_v3_history'), 3);
  assert.equal(endpointLimit('analytics.nm_report_downloads'), 3);
  for (const spec of WB_ENDPOINT_LIST) {
    assert.equal(new URL(spec.url).protocol, 'https:');
    assert.ok(spec.fixtureDir.length > 0);
  }
});

test('budget spacing: two sales calls are 60 seconds apart on a virtual clock', async () => {
  const clock = virtualClock();
  const transport = new FixtureTransport().transport;
  const client = new WbClient(TOKENS, { transport, clock });
  const first = await client.request('statistics.sales', { query: new Map([['dateFrom', '2026-08-28T00:00:00'], ['flag', '0']]) });
  assert.equal(first.httpStatus, 200);
  const elapsedAfterFirst = clock.elapsed();
  const second = await client.request('statistics.sales', { query: new Map([['dateFrom', '2026-08-28T00:00:00'], ['flag', '0']]) });
  assert.equal(second.httpStatus, 200);
  assert.ok(clock.elapsed() - elapsedAfterFirst >= 60_000, `second sales call after ${clock.elapsed() - elapsedAfterFirst} ms, expected >= 60000`);
  assert.deepEqual(clock.sleeps().filter((value) => value > 0), [60_000]);
});

test('budget pacing: eleven orders calls take at least a full minute', async () => {
  const clock = virtualClock();
  const client = new WbClient(TOKENS, { transport: new FixtureTransport().transport, clock });
  for (let index = 0; index < 10; index += 1) {
    await client.request('statistics.orders');
    const gap = clock.sleeps().at(-1) ?? 0;
    assert.ok(gap <= 6_000, `orders (10/min) must not wait more than one pacing interval, waited ${gap}`);
  }
  await client.request('statistics.orders');
  assert.ok(clock.elapsed() >= 60_000, `11 orders calls took ${clock.elapsed()} ms, expected >= 60000`);
});

test('429 waits X-Ratelimit-Retry seconds per response', async () => {
  const clock = virtualClock();
  const transport = new FixtureTransport({
    scripts: {
      'statistics.sales': [
        { status: 429, body: '[]', headers: { 'x-ratelimit-retry': '29' } },
        { status: 429, body: '[]', headers: { 'x-ratelimit-retry': '7' } },
      ],
    },
  }).transport;
  const client = new WbClient(TOKENS, { transport, clock });
  const response = await client.request('statistics.sales');
  assert.equal(response.httpStatus, 200);
  assert.ok(clock.sleeps().includes(29_000), 'first 429 must wait 29 s');
  assert.ok(clock.sleeps().includes(7_000), 'second 429 must wait 7 s');
});

test('429 gives up after 3 retries with WB_RATE_LIMIT_EXHAUSTED', async () => {
  const clock = virtualClock();
  const calls: number[] = [];
  const transport = new FixtureTransport({
    scripts: {
      'statistics.orders': Array.from({ length: 10 }, () => {
        calls.push(0);
        return { status: 429, body: '[]', headers: { 'x-ratelimit-retry': '1' } };
      }),
    },
  }).transport;
  const sink = new InMemoryArtifactSink();
  const client = new WbClient(TOKENS, { transport, clock, artifactSink: sink });
  await assert.rejects(
    () => client.request('statistics.orders'),
    (error: unknown) => error instanceof WbClientError
      && error.code === 'WB_RATE_LIMIT_EXHAUSTED'
      && error.httpStatus === 429,
  );
  const attempts = clock.sleeps().filter((value) => value === 1_000).length;
  assert.equal(attempts, MAX_RETRIES_AFTER_RATE_LIMIT);
  assert.equal(sink.artifacts.length, 1 + MAX_RETRIES_AFTER_RATE_LIMIT, 'every 429 is still recorded as an artifact');
});

test('three retries then success stays within the retry budget', async () => {
  const clock = virtualClock();
  const transport = new FixtureTransport({
    scripts: {
      'statistics.orders': [
        { status: 429, body: '[]', headers: { 'x-ratelimit-retry': '2' } },
        { status: 429, body: '[]', headers: { 'x-ratelimit-retry': '2' } },
        { status: 429, body: '[]', headers: { 'x-ratelimit-retry': '2' } },
      ],
    },
  }).transport;
  const client = new WbClient(TOKENS, { transport, clock });
  const response = await client.request('statistics.orders');
  assert.equal(response.httpStatus, 200);
  assert.equal(clock.sleeps().filter((value) => value === 2_000).length, 3);
});

test('network call fails closed when WB tokens are not configured', async () => {
  const previousAllow = process.env.WB_ALLOW_LIVE_NETWORK;
  delete process.env.WB_ALLOW_LIVE_NETWORK;
  const client = new WbClient({}, { clock: virtualClock() });
  await assert.rejects(
    () => client.request('statistics.sales'),
    (error: unknown) => error instanceof WbClientError && error.code === 'WB_TOKEN_NOT_CONFIGURED',
  );
  const enabled = new WbClient({}, { clock: virtualClock() });
  process.env.WB_ALLOW_LIVE_NETWORK = '1';
  try {
    await assert.rejects(
      () => enabled.request('statistics.sales'),
      (error: unknown) => error instanceof Error && error.message.includes('WB_NETWORK_FORBIDDEN') === false
        && error instanceof WbClientError && error.code === 'WB_TOKEN_NOT_CONFIGURED',
    );
  } finally {
    if (previousAllow === undefined) delete process.env.WB_ALLOW_LIVE_NETWORK;
    else process.env.WB_ALLOW_LIVE_NETWORK = previousAllow;
  }
});

test('network path fails closed when live network is not explicitly enabled', async () => {
  const previousAllow = process.env.WB_ALLOW_LIVE_NETWORK;
  delete process.env.WB_ALLOW_LIVE_NETWORK;
  try {
    const { networkTransport } = await import('../src/wb/transport.js');
    await assert.rejects(
      () => networkTransport()({ method: 'GET', url: WB_ENDPOINTS['statistics.sales'].url, token: 'token' }),
      /WB_NETWORK_FORBIDDEN/,
    );
    const clock = virtualClock();
    const client = new WbClient(TOKENS, { clock, transport: networkTransport() });
    await assert.rejects(
      () => client.request('statistics.sales'),
      /WB_NETWORK_FORBIDDEN/,
    );
  } finally {
    if (previousAllow === undefined) delete process.env.WB_ALLOW_LIVE_NETWORK;
    else process.env.WB_ALLOW_LIVE_NETWORK = previousAllow;
  }
});

test('FixtureTransport replays anonymized fixtures for every registry endpoint', async () => {
  const fixture = new FixtureTransport();
  const clock = virtualClock();
  const sink = new InMemoryArtifactSink();
  const client = new WbClient(TOKENS, { transport: fixture.transport, clock, artifactSink: sink });

  const arrayCases = [
    ['statistics.orders', new Map([['dateFrom', '2026-08-28T00:00:00'], ['flag', '0']])] as const,
    ['statistics.sales', new Map([['dateFrom', '2026-08-28T00:00:00'], ['flag', '0']])] as const,
  ] as const;
  for (const [endpointId, query] of arrayCases) {
    const response = await client.request(endpointId, { query: new Map(query) });
    const payload = JSON.parse(response.body.toString('utf8'));
    assert.ok(Array.isArray(payload), `${endpointId} fixture must be a JSON array of response rows`);
    assert.ok(payload.length > 0, `${endpointId} fixture must not be empty`);
  }

  const downloads = await client.request('analytics.nm_report_downloads');
  const downloadsPayload = JSON.parse(downloads.body.toString('utf8')) as { data?: unknown[] };
  assert.ok(Array.isArray(downloadsPayload.data) && downloadsPayload.data.length > 0, 'nm-report/downloads fixture must be { data: [...] }');

  const funnel = await client.request('analytics.sales_funnel_v3_history', {
    body: { selectedPeriod: { start: '2026-08-24', end: '2026-08-30' }, nmIds: [12345001], aggregationLevel: 'day' },
  });
  const funnelPayload = JSON.parse(funnel.body.toString('utf8'));
  assert.ok(Array.isArray(funnelPayload) && funnelPayload.length > 0, 'sales funnel v3 fixture must be an array of products');

  assert.deepEqual(
    [...fixture.fixtureEndpointsUsed()].sort(),
    ['analytics.nm_report_downloads', 'analytics.sales_funnel_v3_history', 'statistics.orders', 'statistics.sales'],
  );
  assert.equal(sink.artifacts.length, 4);
  for (const artifact of sink.artifacts) {
    assert.equal(artifact.httpStatus, 200);
    assert.match(artifact.contentSha256, /^[0-9a-f]{64}$/);
    assert.ok(artifact.contentSize > 0);
  }
});

test('FixtureTransport refuses URLs outside the registry', async () => {
  const fixture = new FixtureTransport();
  await assert.rejects(
    () => fixture.transport({ method: 'GET', url: 'https://example.invalid/api/v1/supplier/stocks', token: 'token' }),
    /not a WB registry endpoint/,
  );
});

test('artifact sink stores responses before the status is inspected', async () => {
  const clock = virtualClock();
  const sink = new InMemoryArtifactSink();
  const transport = new FixtureTransport({
    scripts: { 'statistics.sales': [{ status: 401, body: '[]' }] },
  }).transport;
  const client = new WbClient(TOKENS, { transport, clock, artifactSink: sink });
  await assert.rejects(
    () => client.request('statistics.sales'),
    (error: unknown) => error instanceof WbClientError && error.code === 'WB_AUTH_FAILED',
  );
  assert.equal(sink.artifacts.length, 1);
  assert.equal(sink.artifacts[0]?.httpStatus, 401);
});

test('RateBudget enforces the per-endpoint minute windows', () => {
  let current = 0;
  const now = () => current;
  const budget = new RateBudget(endpointLimit, now);

  assert.equal(budget.reserve('statistics.sales'), 0);
  assert.equal(budget.reserve('statistics.sales'), 60_000);
  current += 120_000;
  assert.equal(budget.reserve('statistics.sales'), 0, 'a fresh window opens after a quiet minute');
  assert.equal(budget.reserve('statistics.sales'), 60_000, 'and closes again after one call');

  for (let index = 0; index < 10; index += 1) assert.equal(budget.reserve('statistics.orders'), 0);
  assert.equal(budget.reserve('statistics.orders'), 60_000, 'the 11th orders call inside one window waits for the next one');
  current += 60_000;
  assert.equal(budget.reserve('statistics.orders'), 0);
});

test('RateBudget keeps concurrent reserves within the window limit', async () => {
  let current = 0;
  const now = () => current;
  const budget = new RateBudget(endpointLimit, now);

  const delays = await Promise.all(
    Array.from({ length: 20 }, () => Promise.resolve().then(() => budget.reserve('statistics.orders'))),
  );
  const immediate = delays.filter((delay) => delay === 0);
  const waiting = delays.filter((delay) => delay > 0);
  assert.equal(immediate.length, 10, `expected exactly 10 zero-delay slots, got ${immediate.length}`);
  assert.equal(waiting.length, 10, `expected 10 deferred slots, got ${waiting.length}`);
  assert.ok(
    waiting.every((delay) => delay >= 60_000 && delay < 120_000),
    `deferred slots must land in the second window (60-120s), got ${waiting.join(',')}`,
  );
  current = 60_000;
  const nextWindow = budget.reserve('statistics.orders');
  assert.ok(nextWindow >= 60_000, `a 21st call right after the first window must keep waiting, got ${nextWindow}`);
});

test('WbClient holds the endpoint budget under 20 concurrent requests', async () => {
  const clock = virtualClock();
  const sendTimes: number[] = [];
  const transport: import('../src/wb/transport.js').WbTransport = async () => {
    sendTimes.push(clock.now());
    return { status: 200, headers: {}, body: Buffer.from('[]'), retrievedAt: new Date(clock.now()) };
  };
  const client = new WbClient(TOKENS, { transport, clock });
  const responses = await Promise.all(
    Array.from({ length: 20 }, () => client.request('statistics.orders')),
  );
  assert.equal(responses.length, 20);
  assert.equal(responses.every((record) => record.httpStatus === 200), true);
  assert.equal(sendTimes.length, 20);
  const inFirstWindow = sendTimes.filter((at) => at < 60_000);
  assert.equal(inFirstWindow.length, 10, `at most 10 sends inside the first minute, saw ${inFirstWindow.length}`);
  assert.equal(
    sendTimes.filter((at) => at >= 60_000).length,
    10,
    `the remaining sends must wait for the second window, saw sends at ${sendTimes.join(',')}`,
  );
  assert.ok(
    sendTimes.every((at) => at < 120_000),
    `no send may slip past two windows, saw ${sendTimes.join(',')}`,
  );
});

test('429 without a retry header falls back to the endpoint pacing interval', async () => {
  const clock = virtualClock();
  const transport = new FixtureTransport({
    scripts: {
      'statistics.orders': [
        { status: 429, body: '[]', headers: {} },
        { status: 429, body: '[]', headers: { 'content-type': 'application/json' } },
      ],
    },
  }).transport;
  const client = new WbClient(TOKENS, { transport, clock });
  const response = await client.request('statistics.orders');
  assert.equal(response.httpStatus, 200);
  const paced = clock.sleeps().filter((value) => value === 6_000);
  assert.equal(paced.length, 2, `both headerless 429s must wait one orders pacing interval (6 s), saw ${clock.sleeps().join(',')}`);

  const salesClock = virtualClock();
  const salesTransport = new FixtureTransport({
    scripts: { 'statistics.sales': [{ status: 429, body: '[]', headers: {} }] },
  }).transport;
  const salesClient = new WbClient(TOKENS, { transport: salesTransport, clock: salesClock });
  await salesClient.request('statistics.sales');
  assert.ok(
    salesClock.sleeps().includes(60_000),
    `sales (1/min) must wait a full minute without a hint, saw ${salesClock.sleeps().join(',')}`,
  );
  assert.equal(fallbackRetryDelayMilliseconds(10), 6_000);
  assert.equal(fallbackRetryDelayMilliseconds(1), 60_000);
  assert.equal(fallbackRetryDelayMilliseconds(600), 1_000, 'the fallback is floored at one second');
});

test('retryDelayMilliseconds prefers x-ratelimit-retry and tolerates the fallbacks', async () => {
  const { retryDelayMilliseconds } = await import('../src/wb/transport.js');
  assert.equal(retryDelayMilliseconds({ 'x-ratelimit-retry': '29' }), 29_000);
  assert.equal(retryDelayMilliseconds({ 'x-ratelimit-reset': '12' }), 12_000);
  assert.equal(retryDelayMilliseconds({ 'retry-after': '5' }), 5_000);
  assert.equal(retryDelayMilliseconds({ 'x-ratelimit-retry': '1.9' }), 2_000);
  assert.equal(retryDelayMilliseconds({}), null);
  assert.equal(retryDelayMilliseconds(undefined), null);
  assert.equal(retryDelayMilliseconds({ 'x-ratelimit-retry': 'soon' }), null);
});

test('wallClock sleep resolves immediately for non-positive delays', async () => {
  await wallClock.sleep(0);
});

test('POST endpoints carry their body to the transport', async () => {
  const fixture = new FixtureTransport();
  const body = { selectedPeriod: { start: '2026-08-24', end: '2026-08-30' }, nmIds: [12345001, 12345002], aggregationLevel: 'day' };
  const clock = virtualClock();
  const client = new WbClient(TOKENS, { transport: fixture.transport, clock });
  await client.request('analytics.sales_funnel_v3_history', { body });
  const request = fixture.recordedRequests().at(-1);
  assert.equal(request?.method, 'POST');
  assert.deepEqual(request?.body, body);
});

test('wb-collect CLI parses token-file flags for a registry endpoint', () => {
  const args = parseWbCollectArgs([
    '--endpoint', 'statistics.sales',
    '--statistics-token-file', '/run/secrets/wb-statistics',
  ]);
  assert.equal(args.endpoint, 'statistics.sales');
  assert.deepEqual(args.tokenFiles, { statistics: '/run/secrets/wb-statistics' });

  const analytics = parseWbCollectArgs([
    '--endpoint', 'analytics.nm_report_downloads',
    '--analytics-token-file', '/run/secrets/wb-analytics',
  ]);
  assert.deepEqual(analytics.tokenFiles, { analytics: '/run/secrets/wb-analytics' });
});

test('wb-collect CLI rejects unknown options, endpoints and missing token files', () => {
  assert.throws(() => parseWbCollectArgs(['--url', 'https://example.invalid']), /unknown option --url/);
  assert.throws(() => parseWbCollectArgs(['--endpoint']), /option --endpoint requires a value/);
  assert.throws(() => parseWbCollectArgs(['--statistics-token-file', '/run/secrets/wb']), /required option: --endpoint/);
  assert.throws(
    () => parseWbCollectArgs(['--endpoint', 'statistics.orders_burst', '--statistics-token-file', '/run/secrets/wb']),
    /unknown endpoint statistics\.orders_burst/,
  );
  assert.throws(
    () => parseWbCollectArgs(['--endpoint', 'statistics.orders', '--analytics-token-file', '/run/secrets/wb']),
    /endpoint statistics\.orders requires --statistics-token-file/,
  );
});

test('wb-collect CLI collects through an injected transport and fails closed without tokens', async () => {
  const seen: string[] = [];
  const transport: import('../src/wb/transport.js').WbTransport = async (request) => {
    seen.push(request.url);
    return { status: 200, headers: {}, body: Buffer.from('[]'), retrievedAt: new Date(0) };
  };
  const result = await runWbCollect(
    { endpoint: 'statistics.sales', tokenFiles: { statistics: '/run/secrets/wb' } },
    { statistics: 'fixture-token' },
    { transport },
  );
  assert.equal(result.status, 200);
  assert.equal(result.endpoint, 'statistics.sales');
  assert.equal(result.url, WB_ENDPOINTS['statistics.sales'].url);
  assert.deepEqual(seen, [WB_ENDPOINTS['statistics.sales'].url]);

  await assert.rejects(
    () => runWbCollect(
      { endpoint: 'statistics.sales', tokenFiles: { statistics: '/run/secrets/wb' } },
      {},
      { transport },
    ),
    (error: unknown) => error instanceof WbClientError && error.code === 'WB_TOKEN_NOT_CONFIGURED',
  );
  assert.deepEqual(seen, [WB_ENDPOINTS['statistics.sales'].url], 'a tokenless run must never reach the transport');
});
