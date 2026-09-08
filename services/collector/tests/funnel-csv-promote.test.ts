import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import test from 'node:test';

import { CSV_COLUMN_MAP, parseFunnelCsvArgs, parseFunnelCsvRow } from '../src/jobs/funnel-csv-promote.js';
import { DEFAULT_FIXTURE_ROOT } from '../src/wb/fixture-transport.js';

const FIXTURE = join(DEFAULT_FIXTURE_ROOT, 'analytics/nm_report_downloads/funnel_csv_promote.json');

test('funnel_csv parser maps the Story 3.0 columns for 3 nmIds x 7 days', async () => {
  const legacyFixture = JSON.parse(await readFile(FIXTURE, 'utf8')) as Record<string, string>[];
  const payload = legacyFixture.map((row) => ({
    nmID: row.nmID, dt: row.dt, openCardCount: row.open_card, addToCartCount: row.cart,
    ordersCount: row.orders, ordersSumRub: row.orders_sum_rub,
    buyoutsCount: row.buyouts, buyoutsSumRub: row.buyouts_sum_rub, currency: 'RUB',
  }));
  const parsed = payload.map((row, index) => parseFunnelCsvRow(row, `fixture row ${index + 1}`));
  assert.equal(parsed.length, 21);
  assert.deepEqual([...new Set(parsed.map((row) => row.nmId))], [12345001, 12345002, 12345003]);
  assert.deepEqual([...new Set(parsed.map((row) => row.calendarDay))], [
    '2026-08-24', '2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28', '2026-08-29', '2026-08-30',
  ]);
  assert.deepEqual(parsed[0], {
    nmId: 12345001,
    calendarDay: '2026-08-24',
    canonicalSha256: '00fe55121759fc5768deb11d2ac68ca2ece77eb467fd060d5f70ec65b8fa487c',
    openCard: 101,
    cart: 31,
    orders: 11,
    ordersSumRub: '1100.10',
    buyouts: 8,
    buyoutsSumRub: '800.08',
    payload: payload[0],
  });
  assert.deepEqual(CSV_COLUMN_MAP, {
    nmId: 'nmID', calendarDay: 'dt', openCard: 'openCardCount', cart: 'addToCartCount', orders: 'ordersCount',
    ordersSumRub: 'ordersSumRub', buyouts: 'buyoutsCount', buyoutsSumRub: 'buyoutsSumRub',
  });
});

test('funnel_csv parser fails closed on malformed identity, date, counts and money', () => {
  const valid = {
    nmID: '12345001', dt: '2026-08-24', openCardCount: '1', addToCartCount: '2', ordersCount: '3',
    ordersSumRub: '4.50', buyoutsCount: '5', buyoutsSumRub: '6,70', currency: 'RUB',
  };
  assert.equal(parseFunnelCsvRow(valid).buyoutsSumRub, '6.70', 'decimal comma is normalized');
  for (const changed of [
    { ...valid, nmID: '' },
    { ...valid, nmID: '0' },
    { ...valid, dt: '2026-02-30' },
    { ...valid, addToCartCount: '-1' },
    { ...valid, ordersCount: '1.5' },
    { ...valid, ordersSumRub: '-1.00' },
    { ...valid, buyoutsSumRub: '1.234' },
    { ...valid, currency: 'USD' },
    ...(['openCardCount', 'addToCartCount', 'ordersCount', 'ordersSumRub', 'buyoutsCount', 'buyoutsSumRub'] as const)
      .map((column) => ({ ...valid, [column]: undefined })),
  ]) assert.throws(() => parseFunnelCsvRow(changed), /FUNNEL_CSV_SCHEMA_DRIFT/);
});

test('funnel_csv CLI accepts one tenant and rejects ambiguous input', () => {
  assert.deepEqual(parseFunnelCsvArgs(['--tenant', 'amirova-test']), { tenantId: 'amirova-test' });
  assert.throws(() => parseFunnelCsvArgs([]), /usage/);
  assert.throws(() => parseFunnelCsvArgs(['--tenant', 'INVALID']), /must match/);
  assert.throws(() => parseFunnelCsvArgs(['--tenant', 'amirova-test', '--extra']), /usage/);
});
