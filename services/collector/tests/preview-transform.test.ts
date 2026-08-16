import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  aggregatePreviewFacts,
  classifyStagingRow,
  PreviewTransformError,
  type ValidStagingRow,
} from '../src/staging/preview-transform.js';

test('classifies a canonical valid staging row', () => {
  const result = classifyStagingRow({
    rowNumber: 1,
    nmIdText: '11051441',
    rowDateText: '2026-08-03',
    payload: { nmID: '11051441', dt: '2026-08-03', ordersCount: '2' },
  });
  assert.deepEqual(result, { rowNumber: 1, calendarDay: '2026-08-03', nmId: '11051441', orderCount: 2n });
});

test('accepts numeric ordersCount from JSON payloads', () => {
  const result = classifyStagingRow({
    rowNumber: 2,
    nmIdText: '11051441',
    rowDateText: '2026-08-03',
    payload: { ordersCount: 7 },
  });
  assert.equal('reason' in result ? null : result.orderCount, 7n);
});

test('quarantines a non-numeric nmId', () => {
  const result = classifyStagingRow({
    rowNumber: 3,
    nmIdText: '11051a41',
    rowDateText: '2026-08-03',
    payload: { ordersCount: '1' },
  });
  assert.equal('reason' in result ? result.reason : null, 'NM_ID_INVALID');
});

test('quarantines a zero nmId', () => {
  const result = classifyStagingRow({
    rowNumber: 4,
    nmIdText: '0',
    rowDateText: '2026-08-03',
    payload: { ordersCount: '1' },
  });
  assert.equal('reason' in result ? result.reason : null, 'NM_ID_INVALID');
});

test('quarantines a missing nmId', () => {
  const result = classifyStagingRow({ rowNumber: 5, nmIdText: null, rowDateText: '2026-08-03', payload: {} });
  assert.equal('reason' in result ? result.reason : null, 'NM_ID_INVALID');
});

test('quarantines an impossible calendar date', () => {
  const result = classifyStagingRow({
    rowNumber: 6,
    nmIdText: '11051441',
    rowDateText: '2026-02-30',
    payload: { ordersCount: '1' },
  });
  assert.equal('reason' in result ? result.reason : null, 'ROW_DATE_INVALID');
});

test('quarantines a missing calendar date', () => {
  const result = classifyStagingRow({ rowNumber: 7, nmIdText: '11051441', rowDateText: null, payload: {} });
  assert.equal('reason' in result ? result.reason : null, 'ROW_DATE_INVALID');
});

test('quarantines a negative order count', () => {
  const result = classifyStagingRow({
    rowNumber: 8,
    nmIdText: '11051441',
    rowDateText: '2026-08-03',
    payload: { ordersCount: '-4' },
  });
  assert.equal('reason' in result ? result.reason : null, 'ORDER_COUNT_INVALID');
});

test('quarantines a fractional order count', () => {
  const result = classifyStagingRow({
    rowNumber: 9,
    nmIdText: '11051441',
    rowDateText: '2026-08-03',
    payload: { ordersCount: '1.5' },
  });
  assert.equal('reason' in result ? result.reason : null, 'ORDER_COUNT_INVALID');
});

test('quarantines a missing order count', () => {
  const result = classifyStagingRow({ rowNumber: 10, nmIdText: '11051441', rowDateText: '2026-08-03', payload: {} });
  assert.equal('reason' in result ? result.reason : null, 'ORDER_COUNT_INVALID');
});

test('aggregates duplicate day and product rows and sorts deterministically', () => {
  const rows: ValidStagingRow[] = [
    { rowNumber: 1, calendarDay: '2026-08-04', nmId: '11051442', orderCount: 2n },
    { rowNumber: 2, calendarDay: '2026-08-03', nmId: '11051441', orderCount: 5n },
    { rowNumber: 3, calendarDay: '2026-08-04', nmId: '11051442', orderCount: 3n },
    { rowNumber: 4, calendarDay: '2026-08-03', nmId: '11051399', orderCount: 1n },
  ];
  const facts = aggregatePreviewFacts(rows);
  assert.deepEqual(
    facts.map((fact) => [fact.calendarDay, fact.nmId, fact.orderCount.toString()]),
    [
      ['2026-08-03', '11051399', '1'],
      ['2026-08-03', '11051441', '5'],
      ['2026-08-04', '11051442', '5'],
    ],
  );
});

test('rejects an aggregated order count beyond the integer column range', () => {
  assert.throws(
    () =>
      aggregatePreviewFacts([
        { rowNumber: 1, calendarDay: '2026-08-03', nmId: '11051441', orderCount: 2147483647n },
        { rowNumber: 2, calendarDay: '2026-08-03', nmId: '11051441', orderCount: 1n },
      ]),
    (error: unknown) => error instanceof PreviewTransformError && error.code === 'PREVIEW_OVERFLOW',
  );
});
