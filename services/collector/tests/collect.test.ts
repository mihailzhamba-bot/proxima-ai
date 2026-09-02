import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

import { parseCollectArgs } from '../src/jobs/collect.js';
import { WbClientError } from '../src/wb/client.js';
import { DEFAULT_FIXTURE_ROOT } from '../src/wb/fixture-transport.js';
import { toOrderObservations, toSaleObservations } from '../src/wb/observations.js';

const CONTENT_SHA = 'a'.repeat(64);

function fixtureRows(endpoint: 'orders' | 'sales'): Record<string, unknown>[] {
  return JSON.parse(readFileSync(join(DEFAULT_FIXTURE_ROOT, 'statistics', endpoint, 'sample.json'), 'utf8')) as Record<string, unknown>[];
}

function firstOrder(): Record<string, unknown> & { srid: string; lastChangeDate: string; totalPrice: number } {
  const [first] = fixtureRows('orders');
  assert.ok(first, 'orders fixture is not empty');
  return first as Record<string, unknown> & { srid: string; lastChangeDate: string; totalPrice: number };
}

function driftCode(error: unknown): boolean {
  return error instanceof WbClientError && error.code === 'WB_SCHEMA_DRIFT';
}

test('collect args: tenant, date-from and statistics token file are required', () => {
  const args = parseCollectArgs(['--tenant', 'amirova-test', '--date-from', '2026-08-28', '--statistics-token-file', '/run/secrets/token']);
  assert.deepEqual(args, { tenantId: 'amirova-test', dateFrom: '2026-08-28', statisticsTokenFile: '/run/secrets/token' });
  assert.equal(parseCollectArgs(['--tenant', 'amirova-test', '--date-from', '2026-08-28T00:00:00', '--statistics-token-file', 'f']).dateFrom, '2026-08-28T00:00:00');
  assert.throws(() => parseCollectArgs(['--tenant', 'amirova-test', '--date-from', '2026-08-28']), /required option: --statistics-token-file/);
  assert.throws(() => parseCollectArgs(['--tenant', 'amirova-test', '--statistics-token-file', 'f']), /required option: --date-from/);
  assert.throws(() => parseCollectArgs(['--endpoint', 'statistics.orders']), /unknown option --endpoint/);
  assert.throws(() => parseCollectArgs(['--tenant', 'Amirova', '--date-from', '2026-08-28', '--statistics-token-file', 'f']), /--tenant must match/);
  assert.throws(() => parseCollectArgs(['--tenant', 'amirova-test', '--date-from', '28.08.2026', '--statistics-token-file', 'f']), /--date-from must be/);
  assert.throws(() => parseCollectArgs(['--tenant', 'amirova-test', '--tenant', 'x', '--date-from', '2026-08-28', '--statistics-token-file', 'f']), /given twice/);
  assert.throws(() => parseCollectArgs(['--tenant', '--date-from']), /requires a value/);
});

test('observations: fixtures map one row to one (key, lastChangeDate) observation', () => {
  const orders = toOrderObservations(fixtureRows('orders'), CONTENT_SHA);
  assert.equal(orders.table, 'stg_wb_orders_obs');
  assert.equal(orders.keyColumn, 'srid');
  assert.equal(orders.received, 301);
  assert.equal(orders.rows.length, 301);
  assert.equal(new Set(orders.rows.map((row) => `${row.key} ${row.lastChangeAt}`)).size, 301);
  for (const row of orders.rows) {
    assert.match(row.lastChangeAt, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+03:00$/);
    assert.match(row.canonicalSha256, /^[0-9a-f]{64}$/);
  }

  const sales = toSaleObservations(fixtureRows('sales'), CONTENT_SHA);
  assert.equal(sales.table, 'stg_wb_sales_obs');
  assert.equal(sales.keyColumn, 'sale_id');
  assert.equal(sales.received, 295);
  assert.equal(sales.rows.length, 295);
  assert.ok(sales.rows.every((row) => /^[SR]/.test(row.key)), 'sales keys come from saleID, not srid');
});

test('observations: canonical hash ignores key order, replay within a batch collapses, drift within a batch fails', () => {
  const first = firstOrder();
  const reordered = Object.fromEntries(Object.entries(first).reverse());
  const same = toOrderObservations([first, reordered], CONTENT_SHA);
  assert.equal(same.received, 2);
  assert.equal(same.rows.length, 1);
  assert.equal(toOrderObservations([reordered], CONTENT_SHA).rows[0]?.canonicalSha256, same.rows[0]?.canonicalSha256);

  const changed = { ...first, totalPrice: first.totalPrice + 1 };
  assert.throws(() => toOrderObservations([first, changed], CONTENT_SHA), driftCode);

  const later = { ...first, lastChangeDate: '2026-08-31T00:00:00' };
  const versions = toOrderObservations([first, later], CONTENT_SHA);
  assert.equal(versions.rows.length, 2);
});

test('observations: missing key, missing or zoned lastChangeDate and non-object rows are schema drift', () => {
  const first = firstOrder();
  const { srid: _srid, ...noKey } = first;
  assert.throws(() => toOrderObservations([noKey], CONTENT_SHA), driftCode);
  assert.throws(() => toOrderObservations([{ ...first, srid: '' }], CONTENT_SHA), driftCode);
  assert.throws(() => toOrderObservations([{ ...first, lastChangeDate: undefined }], CONTENT_SHA), driftCode);
  assert.throws(() => toOrderObservations([{ ...first, lastChangeDate: '2026-08-17T06:48:49Z' }], CONTENT_SHA), driftCode);
  assert.throws(() => toOrderObservations(['not-an-object'], CONTENT_SHA), driftCode);
  assert.throws(() => toOrderObservations([[first]], CONTENT_SHA), driftCode);
  assert.throws(() => toSaleObservations([{ ...first }], CONTENT_SHA), driftCode);
  assert.throws(() => toOrderObservations([first], 'not-a-sha'), RangeError);
});
