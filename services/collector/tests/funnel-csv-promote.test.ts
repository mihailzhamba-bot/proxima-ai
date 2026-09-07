import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import test from 'node:test';

import { CSV_COLUMN_MAP, parseFunnelCsvArgs, parseFunnelCsvRow } from '../src/jobs/funnel-csv-promote.js';
import { DEFAULT_FIXTURE_ROOT } from '../src/wb/fixture-transport.js';

const FIXTURE = join(DEFAULT_FIXTURE_ROOT, 'analytics/nm_report_downloads/funnel_csv_promote.json');

test('funnel_csv parser maps the explicit assumed columns for 3 nmIds x 7 days', async () => {
  const payload = JSON.parse(await readFile(FIXTURE, 'utf8')) as unknown[];
  const parsed = payload.map((row, index) => parseFunnelCsvRow(row, `fixture row ${index + 1}`));
  assert.equal(parsed.length, 21);
  assert.deepEqual([...new Set(parsed.map((row) => row.nmId))], [12345001, 12345002, 12345003]);
  assert.deepEqual([...new Set(parsed.map((row) => row.calendarDay))], [
    '2026-08-24', '2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28', '2026-08-29', '2026-08-30',
  ]);
  assert.deepEqual(parsed[0], {
    nmId: 12345001,
    calendarDay: '2026-08-24',
    canonicalSha256: '6352fbbefc1b88d333daac67b0094edfa4a1fb21d4053a681cf825d28af7474d',
    openCard: 101,
    cart: 31,
    orders: 11,
    ordersSumRub: '1100.10',
    buyouts: 8,
    buyoutsSumRub: '800.08',
    payload: payload[0],
  });
  assert.deepEqual(CSV_COLUMN_MAP, {
    nmId: 'nmID', calendarDay: 'dt', openCard: 'open_card', cart: 'cart', orders: 'orders',
    ordersSumRub: 'orders_sum_rub', buyouts: 'buyouts', buyoutsSumRub: 'buyouts_sum_rub',
  });
});

test('funnel_csv parser fails closed on malformed identity, date, counts and money', () => {
  const valid = {
    nmID: '12345001', dt: '2026-08-24', open_card: '1', cart: '2', orders: '3',
    orders_sum_rub: '4.50', buyouts: '5', buyouts_sum_rub: '6,70',
  };
  assert.equal(parseFunnelCsvRow(valid).buyoutsSumRub, '6.70', 'decimal comma is normalized');
  for (const changed of [
    { ...valid, nmID: '' },
    { ...valid, nmID: '0' },
    { ...valid, dt: '2026-02-30' },
    { ...valid, cart: '-1' },
    { ...valid, orders: '1.5' },
    { ...valid, orders_sum_rub: '-1.00' },
    { ...valid, buyouts_sum_rub: '1.234' },
    { ...valid, open_card: undefined },
  ]) assert.throws(() => parseFunnelCsvRow(changed), /FUNNEL_CSV_SCHEMA_DRIFT/);
});

test('funnel_csv CLI accepts one tenant and rejects ambiguous input', () => {
  assert.deepEqual(parseFunnelCsvArgs(['--tenant', 'amirova-test']), { tenantId: 'amirova-test' });
  assert.throws(() => parseFunnelCsvArgs([]), /usage/);
  assert.throws(() => parseFunnelCsvArgs(['--tenant', 'INVALID']), /must match/);
  assert.throws(() => parseFunnelCsvArgs(['--tenant', 'amirova-test', '--extra']), /usage/);
});
