import assert from 'node:assert/strict';
import test from 'node:test';

import { summarizeCabinetDaily } from '../src/facts/cabinet-daily.js';
import { selectCollectDateFrom } from '../src/jobs/collect.js';

const A = 'a'.repeat(64);
const B = 'b'.repeat(64);
const RUN = '00000000-0000-4000-8000-000000000001';

test('cabinet daily formulas: orders, cancellations, S sales, R returns and money', () => {
  const rows = [
    { kind: 'order' as const, runId: RUN, contentSha256: A, payload: { date: '2026-08-18T10:00:00', isCancel: false } },
    { kind: 'order' as const, runId: RUN, contentSha256: A, payload: { date: '2026-08-18T11:00:00', isCancel: true } },
    { kind: 'sale' as const, runId: RUN, contentSha256: B, payload: { date: '2026-08-18T12:00:00', saleID: 'S-1', finishedPrice: '10.25', forPay: '8.10' } },
    { kind: 'sale' as const, runId: RUN, contentSha256: B, payload: { date: '2026-08-18T13:00:00', saleID: 'R-1', finishedPrice: '99.00', forPay: '99.00' } },
  ];
  assert.deepEqual(summarizeCabinetDaily(rows, '2026-08-18', '2026-08-20', ['c'.repeat(64)]), [
    { calendarDay: '2026-08-18', ordersCount: 1, cancelledCount: 1, salesCount: 1, returnsCount: 1, revenueRub: '10.25', forpayRub: '8.10', evidenceSha256: [A, B] },
    { calendarDay: '2026-08-19', ordersCount: 0, cancelledCount: 0, salesCount: 0, returnsCount: 0, revenueRub: '0.00', forpayRub: '0.00', evidenceSha256: ['c'.repeat(64)] },
  ]);
});

test('collect date-from default heals gaps and explicit flag wins', () => {
  const now = new Date('2026-09-02T03:00:00Z'); // 06:00 MSK
  assert.deepEqual(selectCollectDateFrom(undefined, null, now), { dateFrom: '2026-08-30', source: 'default', runDay: '2026-09-02' });
  assert.equal(selectCollectDateFrom(undefined, '2026-09-01', now).dateFrom, '2026-08-30');
  assert.equal(selectCollectDateFrom(undefined, '2026-08-23', now).dateFrom, '2026-08-24');
  assert.deepEqual(selectCollectDateFrom('2026-08-01T00:00:00', null, now), { dateFrom: '2026-08-01T00:00:00', source: 'flag', runDay: '2026-09-02' });
});
